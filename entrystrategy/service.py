"""Unified Entry Strategy Service coordinating Bridge, Patterns, and Telemetry."""
import logging
import threading
import time
from collections import deque
from typing import Dict, Any, List, Optional, Callable
from entrystrategy.config import AppConfig
from entrystrategy.core.models import TickData, Candle, EntrySignal, SignalDirection, SignalStatus
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.engine.registry import PatternRegistry
from entrystrategy.data.mt5_bridge import MT5BridgeServer, MT5NativePoller, MT5_PACKAGE_AVAILABLE
from entrystrategy.data.simulator import MarketSimulator

logger = logging.getLogger("EntryStrategy.Service")


class EntryStrategyService:
    def __init__(self, config: Optional[AppConfig] = None, start_servers: bool = True):
        self.config = config or AppConfig()
        self.active_timeframe = getattr(self.config, "timeframe", "M5").upper()
        self.enable_ticks = getattr(self.config, "enable_ticks", True)

        self.buffer = MarketBuffer(
            tick_capacity=self.config.tick_buffer_size,
            candle_capacity=self.config.candle_buffer_size,
            default_timeframe=self.active_timeframe,
        )
        self.buffer.enable_ticks = self.enable_ticks
        self.registry = PatternRegistry()
        
        self.recent_signals: deque = deque(maxlen=100)
        self.latest_signals_by_pattern: Dict[int, EntrySignal] = {}
        self.total_buy_signals: int = 0
        self.total_sell_signals: int = 0
        self._lock = threading.RLock()
        
        # Bridge Server (TCP Port 5558 for incoming EA streams)
        self.bridge_server = MT5BridgeServer(
            host=self.config.bridge_host,
            port=self.config.bridge_port,
            on_tick=self._on_tick_received,
            on_bar_completed=self._on_bar_completed,
            on_status_change=self._on_bridge_status_changed,
        )

        # MT5 Native Direct Poller (Direct terminal API polling with auto-symbol discovery)
        self.native_poller = MT5NativePoller(
            preferred_symbol=self.config.symbol,
            on_tick=self._on_tick_received,
            on_bar_completed=self._on_bar_completed,
            on_status_change=self._on_native_status_changed,
        )
        
        # Simulator (Fallback when no live MT5 is available)
        self.simulator = MarketSimulator(
            base_price=self.config.sim_base_price,
            interval_ms=self.config.sim_tick_interval_ms,
            on_tick=self._on_sim_tick,
            on_bar=self._on_sim_bar,
        )
        
        self.bridge_connected = False
        self.bridge_status_text = f"Listening on port {self.config.bridge_port}"
        self.symbol = self.config.symbol
        self.latest_price = self.config.sim_base_price
        self.latest_spread = 1.4

        # Start servers
        if start_servers:
            self.start()

    def start(self):
        self.bridge_server.start()
        if MT5_PACKAGE_AVAILABLE:
            self.native_poller.start()
        if self.config.enable_simulation and not self.bridge_connected:
            logger.info("Starting background simulator (fallback)...")
            self.simulator.start()

    def stop(self):
        self.simulator.stop()
        self.bridge_server.stop()
        if hasattr(self, "native_poller"):
            self.native_poller.stop()

    def _on_tick_received(self, tick: TickData, is_history: bool = False):
        # Real tick from MT5 (EA Bridge or Native Direct)
        if not self.bridge_connected:
            self.bridge_connected = True
            # Stop simulator when real MT5 arrives
            self.simulator.stop()

        self.latest_price = tick.mid
        self.latest_spread = tick.spread
        self.symbol = tick.symbol
        self.buffer.add_tick(tick)

        # Update signal lifecycles against live price
        now_ms = int(time.time() * 1000)
        with self._lock:
            self._update_all_lifecycles(self.latest_price, now_ms, self.latest_spread)

        # Only evaluate on tick stream if tick mode is explicitly enabled
        if self.enable_ticks and not is_history:
            self._evaluate_patterns()

    def _on_bar_completed(self, candle: Candle, is_history: bool = False):
        self.buffer.add_completed_candle(candle)
        if not is_history:
            self._evaluate_patterns()

    def _on_sim_tick(self, tick: TickData):
        if not self.bridge_connected:
            self.latest_price = tick.mid
            self.latest_spread = tick.spread
            self.buffer.add_tick(tick)
            self._evaluate_patterns()

    def _on_sim_bar(self, candle: Candle):
        if not self.bridge_connected:
            self.buffer.add_completed_candle(candle)
            self._evaluate_patterns()

    def _on_bridge_status_changed(self, connected: bool, message: str):
        if connected:
            self.bridge_connected = True
            self.bridge_status_text = message
            self.simulator.stop()
        elif not (hasattr(self, "native_poller") and self.native_poller.connected):
            self.bridge_connected = False
            self.bridge_status_text = f"Listening on port {self.config.bridge_port}"
            if self.config.enable_simulation:
                self.simulator.start()

    def _on_native_status_changed(self, connected: bool, message: str, symbol: str):
        if connected:
            self.bridge_connected = True
            self.bridge_status_text = message
            self.symbol = symbol
            self.simulator.stop()
        elif not self.bridge_server.client_connected:
            self.bridge_connected = False
            self.bridge_status_text = f"Listening on port {self.config.bridge_port}"
            if self.config.enable_simulation:
                self.simulator.start()

    def _update_all_lifecycles(self, current_price: float, current_ts_ms: int, spread: float = 0.0):
        """Updates lifecycle state (ACTIVE -> PENDING_CONFIRMATION -> CONFIRMED / INVALIDATED / EXPIRED)
        for all tracked signals based on live market price and elapsed time.
        """
        for sig in self.latest_signals_by_pattern.values():
            sig.update_lifecycle(current_price, current_ts_ms, spread)

    def _evaluate_patterns(self):
        now_ms = int(time.time() * 1000)
        with self._lock:
            self._update_all_lifecycles(self.latest_price, now_ms, self.latest_spread)

        fired = self.registry.evaluate_all(self.buffer, enable_ticks=self.enable_ticks)
        if fired:
            with self._lock:
                for sig in fired:
                    self.recent_signals.appendleft(sig)
                    self.latest_signals_by_pattern[sig.pattern_id] = sig
                    if sig.direction == SignalDirection.BUY:
                        self.total_buy_signals += 1
                    elif sig.direction == SignalDirection.SELL:
                        self.total_sell_signals += 1

    def set_timeframe(self, tf: str) -> Dict[str, Any]:
        """Switches active candle analysis timeframe between M1 and M5."""
        tf_clean = tf.upper()
        if tf_clean not in ("M1", "M5"):
            return {"success": False, "error": f"Unsupported timeframe: {tf}"}
        with self._lock:
            self.active_timeframe = tf_clean
            self.buffer.set_active_timeframe(tf_clean)
            for p in self.registry.get_all_patterns():
                p.last_candle_ts = None
            for pid, sig in list(self.latest_signals_by_pattern.items()):
                if sig.is_alive:
                    sig.status = SignalStatus.EXPIRED
                    sig.status_reason = f"Perpindahan timeframe ke {tf_clean}"
        self._evaluate_patterns()
        logger.info(f"Switched active timeframe to {self.active_timeframe} (Buffer candles: {self.buffer.total_candles})")
        return {"success": True, "timeframe": self.active_timeframe, "candle_count": self.buffer.total_candles}

    def toggle_ticks_mode(self, enabled: Optional[bool] = None) -> Dict[str, Any]:
        """Enables or disables tick-based pattern evaluations."""
        with self._lock:
            if enabled is None:
                self.enable_ticks = not self.enable_ticks
            else:
                self.enable_ticks = bool(enabled)
            self.buffer.enable_ticks = self.enable_ticks

            # If ticks disabled, deactivate any lingering tick pattern signals
            if not self.enable_ticks:
                for pid, p in self.registry._patterns.items():
                    if p.category == "Tick":
                        sig = self.latest_signals_by_pattern.get(pid)
                        if sig and sig.is_alive:
                            sig.status = SignalStatus.EXPIRED
                            sig.status_reason = "Mode ticks dinonaktifkan"
        self._evaluate_patterns()
        logger.info(f"Tick analysis mode set to: {'ENABLED' if self.enable_ticks else 'DISABLED'}")
        return {"success": True, "enable_ticks": self.enable_ticks}

    def get_matrix_state(self) -> Dict[str, Any]:
        """Provides complete state for UI rendering in a single fast JSON packet."""
        with self._lock:
            now_ms = int(time.time() * 1000)
            self._update_all_lifecycles(self.latest_price, now_ms, self.latest_spread)

            patterns = self.registry.get_matrix_status()
            recent_sigs = [s.to_dict() for s in list(self.recent_signals)[:20]]
            
            # Format patterns with formal lifecycle state machine
            pattern_cards = []
            for p in patterns:
                pid = p["pattern_id"]
                last_sig = self.latest_signals_by_pattern.get(pid)
                
                is_active = False
                status_str = "IDLE"
                status_reason = ""
                dir_val = "NONE"
                time_ago_str = "IDLE"
                px_str = ""

                if last_sig:
                    elapsed_sec = max(0.0, (now_ms - last_sig.timestamp_ms) / 1000.0)
                    status_str = last_sig.status.value
                    status_reason = last_sig.status_reason

                    if last_sig.is_alive:
                        is_active = True
                        dir_val = last_sig.direction.value
                        if elapsed_sec < 2.0:
                            time_ago_str = "JUST NOW"
                        else:
                            time_ago_str = f"{int(elapsed_sec)}s ago"
                        px_str = f"@{last_sig.trigger_price:.2f}"

                    elif last_sig.is_terminal:
                        # Grace display period: remain visible for 8s so user sees why it ended
                        term_ts = last_sig.invalidated_time_ms or last_sig.expired_time_ms or last_sig.timestamp_ms
                        term_elapsed = max(0.0, (now_ms - term_ts) / 1000.0)
                        if term_elapsed <= 8.0:
                            is_active = True
                            dir_val = last_sig.direction.value
                            time_ago_str = f"{last_sig.status.value} ({int(term_elapsed)}s ago)"
                            px_str = f"@{last_sig.trigger_price:.2f}"
                        else:
                            is_active = False
                            dir_val = "NONE"
                            time_ago_str = "IDLE"

                pattern_cards.append({
                    "id": pid,
                    "name": p["name"],
                    "category": p["category"],
                    "description": p["description"],
                    "role": p.get("role", "ENTRY"),
                    "phenomenon": p.get("phenomenon", ""),
                    "active": is_active,
                    "status": status_str,
                    "status_reason": status_reason,
                    "direction": dir_val,
                    "time_ago": time_ago_str,
                    "price_str": px_str,
                    "last_signal": last_sig.to_dict() if last_sig else None,
                })

            active_buy = sum(1 for c in pattern_cards if c["active"] and c["direction"] == "BUY" and c["status"] in ("ACTIVE", "PENDING_CONFIRMATION", "CONFIRMED"))
            active_sell = sum(1 for c in pattern_cards if c["active"] and c["direction"] == "SELL" and c["status"] in ("ACTIVE", "PENDING_CONFIRMATION", "CONFIRMED"))

            tps_val = self.bridge_server.ticks_last_sec
            if tps_val == 0 and hasattr(self, "native_poller"):
                tps_val = self.native_poller.ticks_last_sec

            tot_ticks = self.bridge_server.total_ticks
            if hasattr(self, "native_poller") and self.native_poller.total_ticks > tot_ticks:
                tot_ticks = self.native_poller.total_ticks
            if not self.bridge_connected:
                tot_ticks = self.buffer.total_ticks

            return {
                "bridge": {
                    "connected": self.bridge_connected,
                    "port": self.config.bridge_port,
                    "status": self.bridge_status_text,
                    "symbol": self.symbol,
                    "price": round(self.latest_price, 2),
                    "spread": round(self.latest_spread, 2),
                    "tps": tps_val if self.enable_ticks else 0,
                    "total_ticks": tot_ticks,
                },
                "config": {
                    "timeframe": self.active_timeframe,
                    "enable_ticks": self.enable_ticks,
                    "total_candles": self.buffer.total_candles,
                },
                "stats": {
                    "active_buy": active_buy,
                    "active_sell": active_sell,
                    "total_buy": self.total_buy_signals,
                    "total_sell": self.total_sell_signals,
                },
                "patterns": pattern_cards,
                "recent_signals": recent_sigs,
            }

    def clear_signals(self) -> Dict[str, Any]:
        """Clears all triggered signals and resets active matrix state."""
        with self._lock:
            self.recent_signals.clear()
            self.latest_signals_by_pattern.clear()
            self.total_buy_signals = 0
            self.total_sell_signals = 0
            for pat in self.registry.get_all_patterns():
                pat.last_signal = None
                pat.last_direction = SignalDirection.NONE
        return {"success": True}

    def trigger_pattern_manual_test(self, pattern_id: int, direction_str: str) -> Dict[str, Any]:
        """Utility for instantly testing UI reaction to any pattern."""
        pat = self.registry.get_pattern(pattern_id)
        if not pat:
            return {"success": False, "error": "Pattern not found"}
        
        dir_enum = SignalDirection.BUY if direction_str.upper() == "BUY" else SignalDirection.SELL
        now_ms = int(time.time() * 1000)
        px = self.latest_price
        
        inval_px = round(px - 1.50 if dir_enum == SignalDirection.BUY else px + 1.50, 2)
        sig = EntrySignal(
            pattern_id=pattern_id,
            family_name=pat.name,
            direction=dir_enum,
            reference_price=px,
            trigger_price=px,
            timestamp_ms=now_ms,
            invalidation_price=inval_px,
            pattern_role=pat.role,
            phenomenon=pat.phenomenon or "Uji coba simulasi pemicu pola manual",
            event_id=f"manual_test_{pattern_id}_{now_ms}",
            reasons=[
                f"Sinyal uji coba manual terpicu ({direction_str.upper()})",
                f"Kondisi algoritma {pat.name} terpenuhi penuh",
                f"Harga trigger: {px:.2f} | Invalidation: {inval_px:.2f} | Spread: {self.latest_spread:.2f} pts",
            ],
            metrics={"test_mode": True},
        )
        with self._lock:
            self.recent_signals.appendleft(sig)
            self.latest_signals_by_pattern[pattern_id] = sig
            if dir_enum == SignalDirection.BUY:
                self.total_buy_signals += 1
            elif dir_enum == SignalDirection.SELL:
                self.total_sell_signals += 1
            pat.last_signal = sig
            pat.last_trigger_ms = now_ms
            pat.last_direction = dir_enum
            
        return {"success": True, "signal": sig.to_dict()}
