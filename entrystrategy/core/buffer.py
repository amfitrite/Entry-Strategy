"""Sliding Window Buffers for Ticks and Candles."""
from collections import deque
from typing import List, Optional
import threading
from entrystrategy.core.models import TickData, Candle


class MarketBuffer:
    """Thread-safe circular storage for live tick stream and recent completed candles."""
    def __init__(self, tick_capacity: int = 2000, candle_capacity: int = 300):
        self._tick_capacity = tick_capacity
        self._candle_capacity = candle_capacity
        
        self._ticks: deque = deque(maxlen=tick_capacity)
        self._candles: deque = deque(maxlen=candle_capacity)
        self._current_bar: Optional[Candle] = None
        
        self._lock = threading.Lock()

    def add_tick(self, tick: TickData):
        with self._lock:
            self._ticks.append(tick)

    def add_completed_candle(self, candle: Candle):
        with self._lock:
            self._candles.append(candle)

    def update_current_bar(self, bar: Candle):
        with self._lock:
            self._current_bar = bar

    def get_current_bar(self) -> Optional[Candle]:
        with self._lock:
            return self._current_bar

    def get_recent_ticks(self, count: int = 50) -> List[TickData]:
        with self._lock:
            n = min(len(self._ticks), count)
            return [self._ticks[-i] for i in range(n, 0, -1)]

    def get_recent_candles(self, count: int = 20) -> List[Candle]:
        """Returns candles with index 0 being the latest completed candle, index 1 being 1 bar ago, etc."""
        with self._lock:
            n = min(len(self._candles), count)
            return [self._candles[-i] for i in range(1, n + 1)]

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
            return len(self._candles)
