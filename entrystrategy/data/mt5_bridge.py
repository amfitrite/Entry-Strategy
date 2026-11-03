"""MT5 TCP Bridge Server on Port 5558 and Native MetaTrader5 Poller."""
import socket
import threading
import logging
import time
from datetime import datetime, timezone
from typing import Callable, Optional, Dict, Any, List
from entrystrategy.core.models import TickData, Candle

logger = logging.getLogger("EntryStrategy.MT5Bridge")

try:
    import MetaTrader5 as mt5
    MT5_PACKAGE_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_PACKAGE_AVAILABLE = False


class TickToBarAggregator:
    """Aggregates sub-second ticks into validated M1 and M5 candles."""
    def __init__(self, symbol: str = "XAUUSD", on_bar_completed: Optional[Callable[[Candle], None]] = None):
        self.symbol = symbol
        self.on_bar_completed = on_bar_completed
        
        # M1 State
        self.current_m1_epoch_ms: Optional[int] = None
        self.m1_open: float = 0.0
        self.m1_high: float = 0.0
        self.m1_low: float = 0.0
        self.m1_close: float = 0.0
        self.m1_tick_volume: float = 0.0
        self.m1_real_volume: float = 0.0
        self.m1_spread_accum: float = 0.0
        self.m1_tick_count: int = 0

        # M5 State
        self.current_m5_epoch_ms: Optional[int] = None
        self.m5_open: float = 0.0
        self.m5_high: float = 0.0
        self.m5_low: float = 0.0
        self.m5_close: float = 0.0
        self.m5_tick_volume: float = 0.0
        self.m5_real_volume: float = 0.0
        self.m5_spread_accum: float = 0.0
        self.m5_tick_count: int = 0

        self._lock = threading.Lock()

    def process_tick(self, tick: TickData):
        m1_epoch_ms = (tick.ts_ms // 60000) * 60000
        m5_epoch_ms = (tick.ts_ms // 300000) * 300000
        px = tick.last if tick.last > 0 else (tick.bid + tick.ask) / 2.0

        with self._lock:
            # 1. Process M1 Bar
            if self.current_m1_epoch_ms is None:
                self.current_m1_epoch_ms = m1_epoch_ms
                self.m1_open = px
                self.m1_high = px
                self.m1_low = px
                self.m1_close = px
                self.m1_tick_volume = 1.0
                self.m1_real_volume = tick.volume
                self.m1_spread_accum = tick.spread
                self.m1_tick_count = 1
            elif m1_epoch_ms > self.current_m1_epoch_ms:
                # M1 Bar closed
                dt_m1 = datetime.fromtimestamp(self.current_m1_epoch_ms / 1000.0, tz=timezone.utc)
                avg_spread_m1 = self.m1_spread_accum / max(1, self.m1_tick_count)
                candle_m1 = Candle(
                    timestamp=dt_m1,
                    open=float(self.m1_open),
                    high=float(max(self.m1_high, self.m1_open, self.m1_close)),
                    low=float(min(self.m1_low, self.m1_open, self.m1_close)),
                    close=float(self.m1_close),
                    tick_volume=float(self.m1_tick_volume),
                    real_volume=float(self.m1_real_volume),
                    spread=float(avg_spread_m1),
                    symbol=self.symbol,
                    timeframe="M1",
                    is_closed=True,
                )
                if self.on_bar_completed:
                    self.on_bar_completed(candle_m1)

                self.current_m1_epoch_ms = m1_epoch_ms
                self.m1_open = px
                self.m1_high = px
                self.m1_low = px
                self.m1_close = px
                self.m1_tick_volume = 1.0
                self.m1_real_volume = tick.volume
                self.m1_spread_accum = tick.spread
                self.m1_tick_count = 1
            else:
                if px > self.m1_high: self.m1_high = px
                if px < self.m1_low: self.m1_low = px
                self.m1_close = px
                self.m1_tick_volume += 1.0
                self.m1_real_volume += tick.volume
                self.m1_spread_accum += tick.spread
                self.m1_tick_count += 1

            # 2. Process M5 Bar
            if self.current_m5_epoch_ms is None:
                self.current_m5_epoch_ms = m5_epoch_ms
                self.m5_open = px
                self.m5_high = px
                self.m5_low = px
                self.m5_close = px
                self.m5_tick_volume = 1.0
                self.m5_real_volume = tick.volume
                self.m5_spread_accum = tick.spread
                self.m5_tick_count = 1
            elif m5_epoch_ms > self.current_m5_epoch_ms:
                # M5 Bar closed
                dt_m5 = datetime.fromtimestamp(self.current_m5_epoch_ms / 1000.0, tz=timezone.utc)
                avg_spread_m5 = self.m5_spread_accum / max(1, self.m5_tick_count)
                candle_m5 = Candle(
                    timestamp=dt_m5,
                    open=float(self.m5_open),
                    high=float(max(self.m5_high, self.m5_open, self.m5_close)),
                    low=float(min(self.m5_low, self.m5_open, self.m5_close)),
                    close=float(self.m5_close),
                    tick_volume=float(self.m5_tick_volume),
                    real_volume=float(self.m5_real_volume),
                    spread=float(avg_spread_m5),
                    symbol=self.symbol,
                    timeframe="M5",
                    is_closed=True,
                )
                if self.on_bar_completed:
                    self.on_bar_completed(candle_m5)

                self.current_m5_epoch_ms = m5_epoch_ms
                self.m5_open = px
                self.m5_high = px
                self.m5_low = px
                self.m5_close = px
                self.m5_tick_volume = 1.0
                self.m5_real_volume = tick.volume
                self.m5_spread_accum = tick.spread
                self.m5_tick_count = 1
            else:
                if px > self.m5_high: self.m5_high = px
                if px < self.m5_low: self.m5_low = px
                self.m5_close = px
                self.m5_tick_volume += 1.0
                self.m5_real_volume += tick.volume
                self.m5_spread_accum += tick.spread
                self.m5_tick_count += 1

    def get_current_building_bar(self) -> Optional[Candle]:
        with self._lock:
            if self.current_minute_epoch_ms is None:
                return None
            bar_dt = datetime.fromtimestamp(self.current_minute_epoch_ms / 1000.0, tz=timezone.utc)
            return Candle(
                timestamp=bar_dt,
                open=self.open,
                high=max(self.high, self.open, self.close),
                low=min(self.low, self.open, self.close),
                close=self.close,
                tick_volume=self.tick_volume,
                real_volume=self.real_volume,
                spread=self.spread_accum / max(1, self.tick_count),
                symbol=self.symbol,
                timeframe="M1",
                is_closed=False,
            )


class MT5BridgeServer:
    """Threaded TCP Server listening on Port 5558 for incoming streaming data from MT5 EA."""
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5558,
        on_tick: Optional[Callable[[TickData, bool], None]] = None,
        on_bar_completed: Optional[Callable[[Candle], None]] = None,
        on_status_change: Optional[Callable[[bool, str], None]] = None,
    ):
        self.host = host
        self.port = port
        self.on_tick = on_tick
        self.on_bar_completed = on_bar_completed
        self.on_status_change = on_status_change
        
        self.symbol = "XAUUSD"
        self.aggregator = TickToBarAggregator(symbol=self.symbol, on_bar_completed=self.on_bar_completed)
        
        self.running = False
        self.active_clients = 0
        self.server_sock: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        
        # Telemetry
        self.total_ticks = 0
        self.ticks_last_sec = 0
        self._tick_counter_window = 0
        self._last_sec_time = time.time()
        self.latest_tick: Optional[TickData] = None

    @property
    def client_connected(self) -> bool:
        return self.active_clients > 0

    def start(self):
        if self.running:
            return
        self.running = True
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(5)
        self.server_sock.settimeout(1.0)
        logger.info(f"EntryStrategy MT5 Bridge listening on {self.host}:{self.port}")

        self.thread = threading.Thread(target=self._server_loop, daemon=True, name="BridgeServer-5558")
        self.thread.start()

    def stop(self):
        self.running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        logger.info("Bridge Server 5558 stopped.")

    def _server_loop(self):
        while self.running:
            try:
                client_sock, addr = self.server_sock.accept()
                client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                logger.info(f"MT5 EA connected from {addr}")
                self.active_clients += 1
                if self.on_status_change:
                    self.on_status_change(True, f"EA Connected ({addr[0]}:{addr[1]})")

                # Handle client in dedicated thread so accept loop never hangs
                ct = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, addr),
                    daemon=True,
                    name=f"MT5Client-{addr[1]}",
                )
                ct.start()
            except socket.timeout:
                self._update_tick_rate()
                continue
            except Exception as e:
                if self.running:
                    logger.debug(f"Socket accept exception: {e}")
                time.sleep(0.1)

    def _handle_client(self, sock: socket.socket, addr: Any):
        sock.settimeout(5.0)
        buffer = ""
        while self.running:
            try:
                data = sock.recv(65536)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="ignore")
                lines = buffer.split("\n")
                buffer = lines[-1]

                for line in lines[:-1]:
                    # Clean line from null bytes, CR, and whitespace
                    line = line.strip().replace("\r", "").replace("\x00", "")
                    if not line:
                        continue
                    self._parse_line(line)
            except socket.timeout:
                self._update_tick_rate()
                continue
            except Exception as e:
                logger.debug(f"Client {addr} stream error: {e}")
                break

        self.active_clients = max(0, self.active_clients - 1)
        if self.active_clients == 0 and self.on_status_change:
            self.on_status_change(False, "Disconnected")
        try:
            sock.close()
        except Exception:
            pass

    def _parse_line(self, line: str):
        # Support TICK| prefix from some bridge EAs
        if line.startswith("TICK|"):
            line = line[5:]

        if line.startswith("#"):
            if line.startswith("#SYMBOL:"):
                sym = line.split(":", 1)[1].strip().replace("\x00", "")
                if sym:
                    self.symbol = sym
                    self.aggregator.symbol = sym
                    logger.info(f"Symbol switched to {sym} from EA header")
                return

            if line.startswith("#BAR:") or line.startswith("#CANDLE:"):
                content = line.split(":", 1)[1]
                parts = [p.strip().replace("\x00", "") for p in content.split(",")]
                if len(parts) >= 6:
                    try:
                        tf = parts[0].upper()
                        ts_val = int(parts[1])
                        dt = datetime.fromtimestamp(ts_val if ts_val < 10000000000 else ts_val / 1000.0, tz=timezone.utc)
                        candle = Candle(
                            timestamp=dt,
                            open=float(parts[2]),
                            high=float(parts[3]),
                            low=float(parts[4]),
                            close=float(parts[5]),
                            tick_volume=float(parts[6]) if len(parts) > 6 and parts[6] else 1.0,
                            real_volume=float(parts[7]) if len(parts) > 7 and parts[7] else 0.0,
                            spread=float(parts[8]) if len(parts) > 8 and parts[8] else 0.0,
                            symbol=self.symbol,
                            timeframe=tf or "M5",
                            is_closed=True,
                        )
                        if self.on_bar_completed:
                            self.on_bar_completed(candle)
                        return
                    except Exception as err:
                        logger.debug(f"Bar parse error: {err}")
                return
            return

        if "," in line:
            parts = [p.strip().replace("\x00", "") for p in line.split(",")]
            if len(parts) >= 3:
                try:
                    ts_ms = int(parts[0])
                    bid = float(parts[1])
                    ask = float(parts[2])
                    last = float(parts[3]) if len(parts) > 3 and parts[3] else 0.0
                    vol = float(parts[4]) if len(parts) > 4 and parts[4] else 1.0
                    flags = int(parts[5]) if len(parts) > 5 and parts[5] else 0

                    tick = TickData(
                        ts_ms=ts_ms,
                        bid=bid,
                        ask=ask,
                        last=last,
                        volume=vol,
                        flags=flags,
                        symbol=self.symbol,
                    )
                    self.latest_tick = tick
                    self.total_ticks += 1
                    self._tick_counter_window += 1
                    self._update_tick_rate()

                    # Aggregate to M1 bar
                    self.aggregator.process_tick(tick)

                    # Detect if this is a historical catch-up tick (> 15 seconds old)
                    now_ms = int(time.time() * 1000)
                    is_history = (now_ms - ts_ms) > 15000

                    if self.on_tick:
                        try:
                            self.on_tick(tick, is_history)
                        except TypeError:
                            self.on_tick(tick)
                except (ValueError, IndexError) as err:
                    logger.debug(f"Tick parse error on line '{line[:40]}': {err}")

    def _update_tick_rate(self):
        now = time.time()
        elapsed = now - self._last_sec_time
        if elapsed >= 1.0:
            self.ticks_last_sec = int(self._tick_counter_window / elapsed)
            self._tick_counter_window = 0
            self._last_sec_time = now


class MT5NativePoller:
    """Direct reader from locally running MT5 terminal via MetaTrader5 API.
    Auto-discovers broker symbol variations (e.g. XAUUSDc on Exness Cent accounts),
    preloads historical M1 bars on startup, and polls sub-millisecond ticks without requiring an EA.
    """
    def __init__(
        self,
        preferred_symbol: str = "XAUUSD",
        on_tick: Optional[Callable[[TickData, bool], None]] = None,
        on_bar_completed: Optional[Callable[[Candle], None]] = None,
        on_status_change: Optional[Callable[[bool, str, str], None]] = None,
        poll_interval_sec: float = 0.04,
    ):
        self.preferred_symbol = preferred_symbol
        self.active_symbol = preferred_symbol
        self.on_tick = on_tick
        self.on_bar_completed = on_bar_completed
        self.on_status_change = on_status_change
        self.poll_interval_sec = poll_interval_sec
        
        self.running = False
        self.connected = False
        self.thread: Optional[threading.Thread] = None
        self.total_ticks = 0
        self.ticks_last_sec = 0
        self._tick_counter_window = 0
        self._last_sec_time = time.time()
        self.last_ts_msc = 0
        self.last_completed_m1_time = 0
        self.last_completed_m5_time = 0

    def start(self) -> bool:
        if not MT5_PACKAGE_AVAILABLE:
            logger.debug("MetaTrader5 python package not installed.")
            return False

        if self.running:
            return True

        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True, name="MT5NativePoller")
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        try:
            if MT5_PACKAGE_AVAILABLE and self.connected:
                mt5.shutdown()
        except Exception:
            pass
        self.connected = False

    def _discover_symbol(self) -> Optional[str]:
        """Finds active gold symbol on current MT5 broker account."""
        candidates = [
            self.preferred_symbol,
            "XAUUSD",
            "XAUUSDc",
            "XAUUSDm",
            "GOLD",
            "XAUUSD.a",
            "XAUUSD.ecn",
            "XAUUSD.raw",
            "XAUUSD.",
        ]
        for s in candidates:
            info = mt5.symbol_info(s)
            if info:
                if not info.visible:
                    mt5.symbol_select(s, True)
                return s

        # Broader search
        all_syms = mt5.symbols_get() or []
        for s_obj in all_syms:
            name = s_obj.name
            if "XAU" in name.upper() or "GOLD" in name.upper():
                mt5.symbol_select(name, True)
                return name
        return None

    def _preload_historical_candles(self, symbol: str):
        """Loads last 100 closed M1 and M5 bars to populate pattern engine context."""
        try:
            # 1. Preload M1 bars
            rates_m1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 100)
            if rates_m1 is not None and len(rates_m1) > 1 and self.on_bar_completed:
                logger.info(f"Preloading {len(rates_m1)-1} historical M1 candles for {symbol} directly from MT5...")
                for r in rates_m1[:-1]:
                    candle = Candle(
                        timestamp=datetime.fromtimestamp(r["time"], tz=timezone.utc),
                        open=float(r["open"]),
                        high=float(r["high"]),
                        low=float(r["low"]),
                        close=float(r["close"]),
                        tick_volume=float(r["tick_volume"]),
                        real_volume=float(r["real_volume"]),
                        spread=float(r["spread"]),
                        symbol=symbol,
                        timeframe="M1",
                        is_closed=True,
                    )
                    try:
                        self.on_bar_completed(candle, is_history=True)
                    except TypeError:
                        self.on_bar_completed(candle)
                self.last_completed_m1_time = int(rates_m1[-2]["time"])

            # 2. Preload M5 bars (Default Timeframe directly from MT5)
            rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
            if rates_m5 is not None and len(rates_m5) > 1 and self.on_bar_completed:
                logger.info(f"Preloading {len(rates_m5)-1} historical M5 candles for {symbol} directly from MT5...")
                for r in rates_m5[:-1]:
                    candle = Candle(
                        timestamp=datetime.fromtimestamp(r["time"], tz=timezone.utc),
                        open=float(r["open"]),
                        high=float(r["high"]),
                        low=float(r["low"]),
                        close=float(r["close"]),
                        tick_volume=float(r["tick_volume"]),
                        real_volume=float(r["real_volume"]),
                        spread=float(r["spread"]),
                        symbol=symbol,
                        timeframe="M5",
                        is_closed=True,
                    )
                    try:
                        self.on_bar_completed(candle, is_history=True)
                    except TypeError:
                        self.on_bar_completed(candle)
                self.last_completed_m5_time = int(rates_m5[-2]["time"])
        except Exception as e:
            logger.debug(f"Error preloading MT5 candles: {e}")

    def _poll_loop(self):
        while self.running:
            # Initialize MT5 connection
            if not self.connected:
                try:
                    init_res = mt5.initialize()
                    if init_res:
                        self.connected = True
                        sym = self._discover_symbol() or self.preferred_symbol
                        self.active_symbol = sym
                        logger.info(f"MT5 Native Direct connected. Active symbol: {sym}")
                        if self.on_status_change:
                            self.on_status_change(True, f"MT5 LIVE ({sym})", sym)
                        self._preload_historical_candles(sym)
                    else:
                        time.sleep(2.0)
                        continue
                except Exception as e:
                    logger.debug(f"MT5 init exception: {e}")
                    time.sleep(2.0)
                    continue

            # Poll closed M1 candle directly from MT5
            try:
                rates_m1 = mt5.copy_rates_from_pos(self.active_symbol, mt5.TIMEFRAME_M1, 0, 3)
                if rates_m1 is not None and len(rates_m1) >= 2:
                    closed_r = rates_m1[-2]
                    closed_t = int(closed_r["time"])
                    if self.last_completed_m1_time == 0:
                        self.last_completed_m1_time = closed_t
                    elif closed_t > self.last_completed_m1_time:
                        self.last_completed_m1_time = closed_t
                        candle_m1 = Candle(
                            timestamp=datetime.fromtimestamp(closed_t, tz=timezone.utc),
                            open=float(closed_r["open"]),
                            high=float(closed_r["high"]),
                            low=float(closed_r["low"]),
                            close=float(closed_r["close"]),
                            tick_volume=float(closed_r["tick_volume"]),
                            real_volume=float(closed_r["real_volume"]),
                            spread=float(closed_r["spread"]),
                            symbol=self.active_symbol,
                            timeframe="M1",
                            is_closed=True,
                        )
                        if self.on_bar_completed:
                            self.on_bar_completed(candle_m1)
            except Exception as e:
                logger.debug(f"Error checking MT5 M1 rates: {e}")

            # Poll closed M5 candle directly from MT5
            try:
                rates_m5 = mt5.copy_rates_from_pos(self.active_symbol, mt5.TIMEFRAME_M5, 0, 3)
                if rates_m5 is not None and len(rates_m5) >= 2:
                    closed_r = rates_m5[-2]
                    closed_t = int(closed_r["time"])
                    if self.last_completed_m5_time == 0:
                        self.last_completed_m5_time = closed_t
                    elif closed_t > self.last_completed_m5_time:
                        self.last_completed_m5_time = closed_t
                        candle_m5 = Candle(
                            timestamp=datetime.fromtimestamp(closed_t, tz=timezone.utc),
                            open=float(closed_r["open"]),
                            high=float(closed_r["high"]),
                            low=float(closed_r["low"]),
                            close=float(closed_r["close"]),
                            tick_volume=float(closed_r["tick_volume"]),
                            real_volume=float(closed_r["real_volume"]),
                            spread=float(closed_r["spread"]),
                            symbol=self.active_symbol,
                            timeframe="M5",
                            is_closed=True,
                        )
                        if self.on_bar_completed:
                            self.on_bar_completed(candle_m5)
            except Exception as e:
                logger.debug(f"Error checking MT5 M5 rates: {e}")

            # Poll live tick for real-time header price & spread
            try:
                tick = mt5.symbol_info_tick(self.active_symbol)
                if tick and tick.time_msc > self.last_ts_msc:
                    self.last_ts_msc = tick.time_msc
                    vol = tick.volume_real if tick.volume_real > 0 else float(tick.volume if tick.volume > 0 else 1.0)
                    
                    td = TickData(
                        ts_ms=tick.time_msc,
                        bid=tick.bid,
                        ask=tick.ask,
                        last=tick.last,
                        volume=vol,
                        flags=tick.flags,
                        symbol=self.active_symbol,
                    )
                    self.total_ticks += 1
                    self._tick_counter_window += 1
                    self._update_tick_rate()

                    if self.on_tick:
                        try:
                            self.on_tick(td, False)
                        except TypeError:
                            self.on_tick(td)

                self._update_tick_rate()
                time.sleep(self.poll_interval_sec)
            except Exception as e:
                logger.debug(f"MT5 polling error: {e}")
                self.connected = False
                if self.on_status_change:
                    self.on_status_change(False, "MT5 Disconnected", self.active_symbol)
                time.sleep(1.0)

    def _update_tick_rate(self):
        now = time.time()
        elapsed = now - self._last_sec_time
        if elapsed >= 1.0:
            self.ticks_last_sec = int(self._tick_counter_window / elapsed)
            self._tick_counter_window = 0
            self._last_sec_time = now
