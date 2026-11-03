"""Unified Entry Strategy Service coordinating Dukascopy Live Feed, Patterns, and Telemetry."""
import logging
import threading
import time
from collections import deque
from typing import Dict, Any, List, Optional, Callable
from entrystrategy.config import AppConfig
from entrystrategy.core.models import TickData, Candle, EntrySignal, SignalDirection, SignalStatus
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.engine.registry import PatternRegistry
from entrystrategy.data.dukascopy_feed import DukascopyFeed
from entrystrategy.data.simulator import MarketSimulator

logger = logging.getLogger("EntryStrategy.Service")


class EntryStrategyService:
    def __init__(self, config: Optional[AppConfig] = None, start_servers: bool = True):
        self.config = config or AppConfig()
        self.active_timeframe = getattr(self.config, "timeframe", "M5").upper()
        self.enable_ticks = getattr(self.config, "enable_ticks", False)

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
        
        self.feed_connected = False
        self.feed_status_text = "Initializing Dukascopy Live Feed..."
        self.symbol = self.config.symbol
        self.latest_price = getattr(self.config, "sim_base_price", 3950.0)
        self.latest_spread = 1.4

        # Dukascopy ECN Live & Historical Ingestor
        self.dukascopy_feed = DukascopyFeed(
            symbol=self.symbol,
            timeframe=self.active_timeframe,
            warmup_candles=getattr(self.config, "dukascopy_warmup_candles", 100),
            poll_interval_s=getattr(self.config, "dukascopy_poll_interval_s", 1.0),
            on_tick=self._on_tick_received,
            on_bar_completed=self._on_bar_completed,
            on_status_change=self._on_feed_status_changed,
        )
        
        # Simulator (Fallback only when offline or testing)
        self.simulator = MarketSimulator(
            base_price=self.latest_price,
            interval_ms=getattr(self.config, "sim_tick_interval_ms", 250),
            on_tick=self._on_sim_tick,
            on_bar=self._on_sim_bar,
        )

        # Start servers
        if start_servers:
            self.start()

    def start(self):
        """Starts the Dukascopy feed and initial warmup."""
        self.dukascopy_feed.start()
        if self.config.enable_simulation and not self.feed_connected:
            logger.info("Starting background simulator (fallback)...")
            self.simulator.start()

    def stop(self):
        """Stops the Dukascopy feed and simulator."""
        self.simulator.stop()
        self.dukascopy_feed.stop()

    def _on_tick_received(self, tick: TickData, is_history: bool = False):
        if not self.feed_connected:
            self.feed_connected = True
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
        self.latest_price = candle.close
        self.buffer.add_completed_candle(candle)
        if not is_history:
            self._evaluate_patterns()

    def _on_sim_tick(self, tick: TickData):
        if not self.feed_connected:
            self.latest_price = tick.mid
            self.latest_spread = tick.spread
            self.buffer.add_tick(tick)
            if self.enable_ticks:
                self._evaluate_patterns()

    def _on_sim_bar(self, candle: Candle):
        if not self.feed_connected:
            self.buffer.add_completed_candle(candle)
            self._evaluate_patterns()

    def _on_feed_status_changed(self, connected: bool, message: str, details: Optional[Dict[str, Any]] = None):
        self.feed_connected = connected
        self.feed_status_text = message
        if connected:
            self.simulator.stop()
            if details and "last_price" in details and details["last_price"] > 0:
                self.latest_price = details["last_price"]
            if details and "last_spread" in details and details["last_spread"] > 0:
                self.latest_spread = details["last_spread"]
        elif self.config.enable_simulation:
            self.simulator.start()

    def _update_all_lifecycles(self, current_price: float, current_ts_ms: int, spread: float = 0.0):
        """Updates lifecycle state for all tracked signals based on live price and elapsed time."""
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
        """Switches active candle analysis timeframe between M1 and M5 with instant zero-lag response."""
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

        self.dukascopy_feed.set_timeframe(tf_clean)

        # If buffer for this timeframe has not been populated yet, trigger background sync
        if self.buffer.total_candles == 0:
            def _topup_sync():
                bars = self.dukascopy_feed.fetch_warmup_candles(tf_clean, self.dukascopy_feed.warmup_candles)
                for b in bars:
                    self.buffer.add_completed_candle(b)
                self._evaluate_patterns()
            threading.Thread(target=_topup_sync, daemon=True, name=f"TopupSync-{tf_clean}").start()

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

            tot_ticks = self.dukascopy_feed.total_ticks_received if self.feed_connected else self.buffer.total_ticks

            # Backward-compatible bridge object + feed object
            feed_info = {
                "connected": self.feed_connected,
                "source": "DUKASCOPY_ECN",
                "status": self.feed_status_text,
                "symbol": self.symbol,
                "price": round(self.latest_price, 2),
                "spread": round(self.latest_spread, 2),
                "tps": 1 if (self.enable_ticks and self.feed_connected) else 0,
                "total_ticks": tot_ticks,
                "total_candles": self.buffer.total_candles,
            }

            return {
                "bridge": feed_info,
                "feed": feed_info,
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
