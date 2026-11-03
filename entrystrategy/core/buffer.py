"""Sliding Window Buffers for Ticks and Candles supporting M1 and M5 timeframes."""
from collections import deque
from typing import List, Optional, Dict, Any
import threading
import time
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
        self._current_time_ms: Optional[int] = None
        
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
        """Returns the latest tick for pattern evaluations ONLY when tick mode is enabled."""
        if not self.enable_ticks:
            return None
        with self._lock:
            return self._ticks[-1] if self._ticks else None

    @property
    def latest_quote_tick(self) -> Optional[TickData]:
        """Always returns the most recent tick for price/spread quoting regardless of pattern mode."""
        with self._lock:
            return self._ticks[-1] if self._ticks else None

    @property
    def current_spread(self) -> float:
        """Returns current market spread in points."""
        with self._lock:
            if self._ticks:
                return self._ticks[-1].spread
            if self._candles:
                return self._candles[-1].spread or 0.25
            return 0.25

    def set_current_time_ms(self, ts_ms: Optional[int]):
        """Sets an explicit simulation/backtest timestamp (or None for wall clock / tick time)."""
        with self._lock:
            self._current_time_ms = ts_ms

    @property
    def current_time_ms(self) -> int:
        """Returns current detection time: explicit sim time, latest tick, or wall-clock ms."""
        with self._lock:
            if self._current_time_ms is not None:
                return self._current_time_ms
            if self.enable_ticks and self._ticks:
                return self._ticks[-1].ts_ms
            return int(time.time() * 1000)

    def get_execution_price(self, direction: Any, ref_close: float) -> float:
        """Calculates estimated execution price: Ask for BUY, Bid for SELL.
        Since Dukascopy candle bars are Bid-side:
        - In candle-only mode (or whenever ref_close is a candle price):
          BUY = ref_close + spread (Ask), SELL = ref_close (Bid).
        - In tick mode with live streaming ticks, uses live ask/bid quotes.
        """
        dir_upper = str(direction).upper()
        is_buy = "BUY" in dir_upper
        if self.enable_ticks and self._ticks:
            t = self._ticks[-1]
            return round(t.ask if is_buy else t.bid, 2)
        spread = self.current_spread
        if is_buy:
            return round(ref_close + spread, 2)
        return round(ref_close, 2)

    @property
    def total_ticks(self) -> int:
        with self._lock:
            return len(self._ticks)

    @property
    def total_candles(self) -> int:
        with self._lock:
            source = self._candles_m5 if self.active_timeframe == "M5" else self._candles_m1
            return len(source)

    @property
    def total_candles_m1(self) -> int:
        with self._lock:
            return len(self._candles_m1)

    @property
    def total_candles_m5(self) -> int:
        with self._lock:
            return len(self._candles_m5)
