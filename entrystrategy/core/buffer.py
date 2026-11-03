"""Sliding Window Buffers for Ticks and Candles supporting M1 and M5 timeframes."""
from collections import deque
from typing import List, Optional, Dict
import threading
from entrystrategy.core.models import TickData, Candle


class MarketBuffer:
    """Thread-safe circular storage for live tick stream and recent completed candles."""
    def __init__(
        self,
        tick_capacity: int = 2000,
        candle_capacity: int = 300,
        default_timeframe: str = "M5",
        enable_ticks: bool = True,
        active_timeframe: Optional[str] = None,
    ):
        self._tick_capacity = tick_capacity
        self._candle_capacity = candle_capacity
        self.active_timeframe: str = (active_timeframe or default_timeframe).upper()
        self.enable_ticks: bool = enable_ticks
        
        self._ticks: deque = deque(maxlen=tick_capacity)
        self._candles_m1: deque = deque(maxlen=candle_capacity)
        self._candles_m5: deque = deque(maxlen=candle_capacity)
        self._candles: deque = deque(maxlen=candle_capacity)
        self._current_bar: Optional[Candle] = None
        
        self._lock = threading.Lock()

    def set_active_timeframe(self, tf: str):
        tf_clean = tf.upper()
        with self._lock:
            self.active_timeframe = tf_clean
            source = self._candles_m5 if tf_clean == "M5" else self._candles_m1
            self._candles = deque(source, maxlen=self._candle_capacity)

    def set_enable_ticks(self, enable: bool):
        with self._lock:
            self.enable_ticks = bool(enable)

    def add_tick(self, tick: TickData):
        with self._lock:
            self._ticks.append(tick)

    def add_completed_candle(self, candle: Candle):
        tf = (candle.timeframe or "M1").upper()
        with self._lock:
            if tf == "M5":
                self._candles_m5.append(candle)
                if self.active_timeframe == "M5":
                    self._candles.append(candle)
            else:
                self._candles_m1.append(candle)
                if self.active_timeframe == "M1":
                    self._candles.append(candle)

    def update_current_bar(self, bar: Candle):
        with self._lock:
            self._current_bar = bar

    def get_current_bar(self) -> Optional[Candle]:
        with self._lock:
            return self._current_bar

    def get_recent_ticks(self, count: int = 50) -> List[TickData]:
        if not self.enable_ticks:
            return []
        with self._lock:
            n = min(len(self._ticks), count)
            return [self._ticks[-i] for i in range(n, 0, -1)]

    def get_recent_candles(self, count: int = 20, timeframe: Optional[str] = None) -> List[Candle]:
        """Returns candles with index 0 being the latest completed candle, index 1 being 1 bar ago, etc.
        Strictly isolates M1 and M5 without cross-contamination.
        """
        tf = (timeframe or self.active_timeframe).upper()
        with self._lock:
            source = self._candles_m5 if tf == "M5" else self._candles_m1
            n = min(len(source), count)
            return [source[-i] for i in range(1, n + 1)]

    @property
    def latest_tick(self) -> Optional[TickData]:
        with self._lock:
            return self._ticks[-1] if self._ticks else None

    @property
    def total_ticks(self) -> int:
        with self._lock:
            return len(self._ticks)

    @property
    def total_candles(self) -> int:
        with self._lock:
            source = self._candles_m5 if self.active_timeframe == "M5" else self._candles_m1
            if not source:
                alt = self._candles_m1 if self.active_timeframe == "M5" else self._candles_m5
                if alt:
                    return len(alt)
            return len(source)

    @property
    def total_candles_m1(self) -> int:
        with self._lock:
            return len(self._candles_m1)

    @property
    def total_candles_m5(self) -> int:
        with self._lock:
            return len(self._candles_m5)
