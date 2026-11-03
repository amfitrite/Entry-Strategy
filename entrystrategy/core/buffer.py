"""Quote telemetry and completed-candle buffers for M1/M5 strategy evaluation."""
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
        enable_ticks: bool = False,
        active_timeframe: Optional[str] = None,
    ):
        self._tick_capacity = tick_capacity
        self._candle_capacity = candle_capacity
        self.active_timeframe: str = (active_timeframe or default_timeframe).upper()
        self.enable_ticks: bool = False
        
        self._ticks: deque = deque(maxlen=tick_capacity)
        self._candles_m1: deque = deque(maxlen=candle_capacity)
        self._candles_m5: deque = deque(maxlen=candle_capacity)
        self._candles_m15: deque = deque(maxlen=candle_capacity)
        self._candles: deque = deque(maxlen=candle_capacity)
        self._current_bar: Optional[Candle] = None
        self._current_time_ms: Optional[int] = None
        
        self._lock = threading.Lock()

    def set_active_timeframe(self, tf: str):
        tf_clean = tf.upper()
        with self._lock:
            self.active_timeframe = tf_clean
            if tf_clean == "M15":
                source = self._candles_m15
            elif tf_clean == "M5":
                source = self._candles_m5
            else:
                source = self._candles_m1
            self._candles = deque(source, maxlen=self._candle_capacity)

    def set_enable_ticks(self, enable: bool):
        """Deprecated compatibility shim: strategy analysis is always candle-only."""
        with self._lock:
            self.enable_ticks = False

    def add_tick(self, tick: TickData):
        with self._lock:
            self._ticks.append(tick)

    def add_completed_candle(self, candle: Candle):
        """Store only fully closed candles; unfinished bars never enter strategy history."""
        if not candle.is_closed:
            return
        tf = (candle.timeframe or "M1").upper()
        with self._lock:
            if tf == "M15":
                self._candles_m15.append(candle)
                if self.active_timeframe == "M15":
                    self._candles.append(candle)
            elif tf == "M5":
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
        """Strategy-facing tick access is disabled; ticks are quote telemetry only."""
        return []

    def get_recent_candles(self, count: int = 20, timeframe: Optional[str] = None) -> List[Candle]:
        """Returns candles with index 0 being the latest completed candle, index 1 being 1 bar ago, etc.
        Strictly isolates M1 and M5 without cross-contamination.
        """
        tf = (timeframe or self.active_timeframe).upper()
        with self._lock:
            if tf == "M15":
                source = self._candles_m15
            elif tf == "M5":
                source = self._candles_m5
            else:
                source = self._candles_m1
            n = min(len(source), count)
            return [source[-i] for i in range(1, n + 1)]

    @property
    def latest_tick(self) -> Optional[TickData]:
        """Always None: strategy predicates are exclusively completed-candle based."""
        return None

    @property
    def latest_quote_tick(self) -> Optional[TickData]:
        """Always returns the most recent tick for price/spread quoting regardless of pattern mode."""
        with self._lock:
            return self._ticks[-1] if self._ticks else None

    @property
    def current_spread(self) -> float:
        """Returns fresh quote spread, or the latest candle spread when quotes are stale."""
        now_ms = self.current_time_ms
        with self._lock:
            if self._ticks and abs(now_ms - self._ticks[-1].ts_ms) <= 5000:
                return self._ticks[-1].spread
            if self._candles:
                return self._candles[-1].spread or 0.25
            return 0.25

    def set_current_time_ms(self, ts_ms: Optional[int]):
        """Sets an explicit simulation/backtest timestamp, or None to use wall-clock detection time."""
        with self._lock:
            self._current_time_ms = ts_ms

    @property
    def current_time_ms(self) -> int:
        """Returns explicit simulation time or wall-clock detection time; never strategy tick time."""
        with self._lock:
            if self._current_time_ms is not None:
                return self._current_time_ms
        return int(time.time() * 1000)

    def get_execution_price(self, direction: Any, ref_close: float) -> float:
        """Calculates estimated execution price: Ask for BUY, Bid for SELL.
        Since Dukascopy candle bars are Bid-side:
        - In candle-only mode (or whenever ref_close is a candle price):
          BUY = ref_close + spread (Ask), SELL = ref_close (Bid).
        - When a fresh live bid/ask quote is available, uses that quote for estimated fill.
        """
        dir_upper = str(direction).upper()
        is_buy = "BUY" in dir_upper
        t = self.latest_quote_tick
        if t is not None and abs(self.current_time_ms - t.ts_ms) <= 5000:
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
            if self.active_timeframe == "M15":
                source = self._candles_m15
            elif self.active_timeframe == "M5":
                source = self._candles_m5
            else:
                source = self._candles_m1
            return len(source)

    @property
    def total_candles_m1(self) -> int:
        with self._lock:
            return len(self._candles_m1)

    @property
    def total_candles_m5(self) -> int:
        with self._lock:
            return len(self._candles_m5)

    @property
    def total_candles_m15(self) -> int:
        with self._lock:
            return len(self._candles_m15)
