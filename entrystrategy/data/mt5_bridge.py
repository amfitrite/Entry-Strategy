"""MT5 TCP Bridge Server on Port 5558 and Real-time Tick-to-Bar Aggregator."""
import socket
import threading
import logging
import time
from datetime import datetime, timezone
from typing import Callable, Optional, Dict, Any, List
from entrystrategy.core.models import TickData, Candle

logger = logging.getLogger("EntryStrategy.MT5Bridge")


class TickToBarAggregator:
    """Aggregates sub-second ticks into validated M1 candles."""
    def __init__(self, symbol: str = "XAUUSD", on_bar_completed: Optional[Callable[[Candle], None]] = None):
        self.symbol = symbol
        self.on_bar_completed = on_bar_completed
        self.current_minute_epoch_ms: Optional[int] = None
        
        self.open: float = 0.0
        self.high: float = 0.0
        self.low: float = 0.0
        self.close: float = 0.0
        self.tick_volume: float = 0.0
        self.real_volume: float = 0.0
        self.spread_accum: float = 0.0
        self.tick_count: int = 0
        self._lock = threading.Lock()

    def process_tick(self, tick: TickData) -> Optional[Candle]:
        minute_epoch_ms = (tick.ts_ms // 60000) * 60000
        completed_candle = None

        with self._lock:
            px = tick.last if tick.last > 0 else (tick.bid + tick.ask) / 2.0
            
            if self.current_minute_epoch_ms is None:
                self.current_minute_epoch_ms = minute_epoch_ms
                self.open = px
                self.high = px
                self.low = px
                self.close = px
                self.tick_volume = 1.0
                self.real_volume = tick.volume
                self.spread_accum = tick.spread
                self.tick_count = 1
                return None

            if minute_epoch_ms > self.current_minute_epoch_ms:
                # Minute closed
                bar_dt = datetime.fromtimestamp(self.current_minute_epoch_ms / 1000.0, tz=timezone.utc)
                avg_spread = self.spread_accum / max(1, self.tick_count)
                high_adj = max(self.high, self.open, self.close)
                low_adj = min(self.low, self.open, self.close)

                completed_candle = Candle(
                    timestamp=bar_dt,
                    open=float(self.open),
                    high=float(high_adj),
                    low=float(low_adj),
                    close=float(self.close),
                    tick_volume=float(self.tick_volume),
                    real_volume=float(self.real_volume),
                    spread=float(avg_spread),
                    symbol=self.symbol,
                    timeframe="M1",
                    is_closed=True,
                )
                if self.on_bar_completed:
                    self.on_bar_completed(completed_candle)

                # Start next bar
                self.current_minute_epoch_ms = minute_epoch_ms
                self.open = px
                self.high = px
                self.low = px
                self.close = px
                self.tick_volume = 1.0
                self.real_volume = tick.volume
                self.spread_accum = tick.spread
                self.tick_count = 1

            elif minute_epoch_ms == self.current_minute_epoch_ms:
                if px > self.high:
                    self.high = px
                if px < self.low:
                    self.low = px
                self.close = px
                self.tick_volume += 1.0
                self.real_volume += tick.volume
                self.spread_accum += tick.spread
                self.tick_count += 1

        return completed_candle

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
    """TCP Server listening on Port 5558 for incoming streaming data from MT5 EA."""
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5558,
        on_tick: Optional[Callable[[TickData], None]] = None,
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
        self.client_connected = False
        self.server_sock: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        
        # Telemetry
        self.total_ticks = 0
        self.ticks_last_sec = 0
        self._tick_counter_window = 0
        self._last_sec_time = time.time()
        self.latest_tick: Optional[TickData] = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(2)
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
                logger.info(f"MT5 EA connected from {addr}")
                self.client_connected = True
                if self.on_status_change:
                    self.on_status_change(True, f"Connected ({addr[0]}:{addr[1]})")
                self._handle_client(client_sock)
            except socket.timeout:
                self._update_tick_rate()
                continue
            except Exception as e:
                if self.running:
                    logger.debug(f"Socket accept exception: {e}")
                time.sleep(0.1)

    def _handle_client(self, sock: socket.socket):
        sock.settimeout(2.0)
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
                    line = line.strip().replace("\r", "")
                    if not line:
                        continue
                    self._parse_line(line)
            except socket.timeout:
                self._update_tick_rate()
                continue
            except Exception as e:
                logger.debug(f"Client stream error: {e}")
                break

        self.client_connected = False
        if self.on_status_change:
            self.on_status_change(False, "Disconnected")
        try:
            sock.close()
        except Exception:
            pass

    def _parse_line(self, line: str):
        if line.startswith("#"):
            if line.startswith("#SYMBOL:"):
                sym = line.split(":", 1)[1].strip()
                if sym:
                    self.symbol = sym
                    self.aggregator.symbol = sym
            return

        if "," in line:
            parts = line.split(",")
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

                    if self.on_tick:
                        self.on_tick(tick)
                except (ValueError, IndexError):
                    pass

    def _update_tick_rate(self):
        now = time.time()
        elapsed = now - self._last_sec_time
        if elapsed >= 1.0:
            self.ticks_last_sec = int(self._tick_counter_window / elapsed)
            self._tick_counter_window = 0
            self._last_sec_time = now
