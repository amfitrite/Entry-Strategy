"""Dukascopy Bank Data Ingestor (Historical Warm-up & Real-time Live Stream).

Provides institutional-grade XAUUSD tick and candlestick feeds directly from
Dukascopy Bank (Swiss FX/Metal ECN marketplace) without requiring MetaTrader 5.
"""
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Callable, List, Dict, Any

from entrystrategy.core.models import Candle, TickData

logger = logging.getLogger("EntryStrategy.DukascopyFeed")

# dukascopy-python 5.0.0 references requests.Session in module-level
# annotations without importing requests into its own namespace. Supply the
# name during import, then bind it on the package for later function lookups.
try:
    import builtins
    import requests as _requests
    from typing import Any as _TypingAny

    _had_builtin_requests = hasattr(builtins, "requests")
    _had_builtin_datafeed = hasattr(builtins, "DataFeed")
    if not _had_builtin_requests:
        builtins.requests = _requests
    # dukascopy-python 5.0.0 imports DataFeed only under TYPE_CHECKING but
    # still evaluates it in a runtime function annotation.
    if not _had_builtin_datafeed:
        builtins.DataFeed = _TypingAny
    try:
        import dukascopy_python as duka
        from dukascopy_python.instruments import I_XAU_USD
        DUKASCOPY_AVAILABLE = True
    finally:
        if not _had_builtin_requests:
            del builtins.requests
        if not _had_builtin_datafeed:
            del builtins.DataFeed
except Exception as exc:
    duka = None
    I_XAU_USD = None
    DUKASCOPY_AVAILABLE = False
    logger.warning("dukascopy-python import unavailable: %s", exc)


class DukascopyFeed:
    """Manages real-time streaming and warmup candle synchronization from Dukascopy."""

    def __init__(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "M5",
        warmup_candles: int = 100,
        poll_interval_s: float = 1.0,
        on_tick: Optional[Callable[[TickData, bool], None]] = None,
        on_bar_completed: Optional[Callable[[Candle, bool], None]] = None,
        on_status_change: Optional[Callable[[bool, str, Dict[str, Any]], None]] = None,
    ):
        self.symbol = symbol.upper()
        self.timeframe = timeframe.upper()
        self.warmup_candles = warmup_candles
        self.poll_interval_s = max(0.5, float(poll_interval_s))

        self.on_tick = on_tick
        self.on_bar_completed = on_bar_completed
        self.on_status_change = on_status_change

        self.is_connected = False
        self.status_message = "Initializing Dukascopy ECN Feed..."
        self.last_tick_time: Optional[datetime] = None
        self.last_candle_timestamp: Dict[str, Optional[datetime]] = {
            "M1": None,
            "M5": None,
        }
        self.last_price: float = 0.0
        self.last_spread: float = 0.0
        self.total_ticks_received: int = 0
        self.total_candles_received: int = 0

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()

    def start(self):
        """Starts background feed thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_feed_loop, daemon=True, name="DukascopyFeedWorker")
        self._thread.start()
        logger.info(f"Dukascopy Feed started for {self.symbol} [{self.timeframe}]")

    def stop(self):
        """Stops background feed thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self.is_connected = False
        self._notify_status(False, "Dukascopy Feed stopped")
        logger.info("Dukascopy Feed stopped")

    def _notify_status(self, connected: bool, message: str):
        self.is_connected = connected
        self.status_message = message
        if self.on_status_change:
            details = {
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "last_price": self.last_price,
                "last_spread": self.last_spread,
                "total_ticks": self.total_ticks_received,
                "total_candles": self.total_candles_received,
            }
            try:
                self.on_status_change(connected, message, details)
            except Exception as e:
                logger.error(f"Error in on_status_change callback: {e}")

    def fetch_warmup_candles(self, timeframe: Optional[str] = None, count: Optional[int] = None) -> List[Candle]:
        """Fetches the last N historical candles from Dukascopy to immediately populate buffer."""
        if not DUKASCOPY_AVAILABLE:
            logger.warning("dukascopy-python not available, skipping warmup.")
            return []

        tf = (timeframe or self.timeframe).upper()
        req_count = count or self.warmup_candles
        interval_min = 5 if tf == "M5" else 1

        # Look back enough hours to comfortably cover requested candle count + weekends/gaps
        hours_needed = max(3.0, (req_count * interval_min / 60.0) * 1.5)
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours_needed)

        logger.info(f"Fetching {req_count} {tf} warmup candles for {self.symbol} from Dukascopy...")
        self._notify_status(False, f"Downloading {req_count} {tf} warmup candles from Geneva...")

        try:
            raw_candles = list(duka.fetch_candles(
                instrument=I_XAU_USD,
                interval=interval_min,
                time_unit=duka.TimeUnit.MINUTE,
                offer_side=duka.OfferSide.BID,
                start=start,
                end=now
            ))
            
            parsed: List[Candle] = []
            for c in raw_candles:
                # STRICT CHECK: Only truly closed candles whose duration has completely elapsed
                candle_end = c.timestamp + timedelta(minutes=interval_min)
                if candle_end > now:
                    continue

                c_obj = Candle(
                    timestamp=c.timestamp,
                    open=float(c.open),
                    high=float(c.high),
                    low=float(c.low),
                    close=float(c.close),
                    tick_volume=float(c.volume),
                    symbol=self.symbol,
                    timeframe=tf,
                    is_closed=True
                )
                parsed.append(c_obj)

            parsed.sort(key=lambda x: x.timestamp)
            if len(parsed) > req_count:
                parsed = parsed[-req_count:]

            with self._lock:
                if parsed:
                    self.last_candle_timestamp[tf] = parsed[-1].timestamp
                    self.last_price = parsed[-1].close

            logger.info(f"Successfully loaded {len(parsed)} {tf} closed warmup candles from Dukascopy.")
            return parsed

        except Exception as e:
            logger.error(f"Failed to fetch warmup candles from Dukascopy: {e}")
            self._notify_status(False, f"Warmup fetch error: {e}")
            return []

    def set_timeframe(self, new_tf: str):
        """Switches active timeframe for live stream aggregation."""
        clean_tf = new_tf.upper()
        if clean_tf not in ("M1", "M5"):
            return
        with self._lock:
            self.timeframe = clean_tf

    def _run_feed_loop(self):
        """Continuous live ingestor loop fetching ticks and completed bars."""
        if not DUKASCOPY_AVAILABLE:
            self._notify_status(False, "dukascopy-python not installed")
            return

        # 1. Dual historical warmup (pre-warm both M5 and M1 so timeframe switching is 100% instant)
        warmup_m5 = self.fetch_warmup_candles("M5", self.warmup_candles)
        if warmup_m5 and self.on_bar_completed:
            for bar in warmup_m5:
                try:
                    self.on_bar_completed(bar, True)  # is_history=True
                except Exception as e:
                    logger.error(f"Error in on_bar_completed during M5 warmup: {e}")

        warmup_m1 = self.fetch_warmup_candles("M1", self.warmup_candles)
        if warmup_m1 and self.on_bar_completed:
            for bar in warmup_m1:
                try:
                    self.on_bar_completed(bar, True)  # is_history=True
                except Exception as e:
                    logger.error(f"Error in on_bar_completed during M1 warmup: {e}")

        # Set initial tick search window (last 60 seconds)
        self.last_tick_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        self._notify_status(True, "DUKASCOPY LIVE (XAUUSD)")

        candle_sync_counter = 0

        while not self._stop_event.is_set():
            loop_start = time.time()
            try:
                now = datetime.now(timezone.utc)
                # Ensure start is strictly before end
                start_window = self.last_tick_time if self.last_tick_time else (now - timedelta(seconds=60))
                if (now - start_window).total_seconds() < 0.5:
                    start_window = now - timedelta(seconds=1)

                # Fetch newest ticks from Dukascopy
                ticks = list(duka.fetch_ticks(
                    instrument=I_XAU_USD,
                    start=start_window,
                    end=now
                ))

                if ticks:
                    ticks.sort(key=lambda t: t.timestamp)
                    newest_ticks = [t for t in ticks if self.last_tick_time is None or t.timestamp > self.last_tick_time]

                    for t in newest_ticks:
                        ts_ms = int(t.timestamp.timestamp() * 1000)
                        mid = (t.bid + t.ask) / 2.0
                        spread = max(0.0, t.ask - t.bid)

                        tick_obj = TickData(
                            ts_ms=ts_ms,
                            bid=float(t.bid),
                            ask=float(t.ask),
                            last=mid,
                            volume=float(t.volume if hasattr(t, "volume") else 1.0),
                            flags=6,
                            symbol=self.symbol
                        )

                        self.last_price = mid
                        self.last_spread = spread
                        self.last_tick_time = t.timestamp
                        self.total_ticks_received += 1

                        if self.on_tick:
                            try:
                                self.on_tick(tick_obj, False)
                            except Exception as e:
                                logger.error(f"Error in on_tick callback: {e}")

                    if not self.is_connected:
                        self._notify_status(True, "DUKASCOPY LIVE (XAUUSD)")
                else:
                    # Check if market might be closed (e.g. weekend)
                    # Friday 22:00 UTC to Sunday 22:00 UTC
                    weekday = now.weekday()
                    if weekday == 5 or (weekday == 4 and now.hour >= 22) or (weekday == 6 and now.hour < 22):
                        self._notify_status(True, "Market Closed (Weekend) - Showing Last Known State")
                    elif not self.is_connected:
                        self._notify_status(True, "DUKASCOPY LIVE (Awaiting New Ticks)")

                # Check official candle closure every ~3 seconds or on candle intervals (low latency)
                candle_sync_counter += 1
                if candle_sync_counter >= 3:
                    candle_sync_counter = 0
                    self._sync_latest_candle(now)

            except Exception as e:
                logger.warning(f"Dukascopy feed polling error: {e}")
                self._notify_status(False, f"Reconnecting to Dukascopy: {str(e)[:40]}")
                time.sleep(2.0)

            # Sleep remaining poll interval
            elapsed = time.time() - loop_start
            sleep_time = max(0.2, self.poll_interval_s - elapsed)
            time.sleep(sleep_time)

    def _sync_latest_candle(self, now: datetime):
        """Checks for official closed candles on Dukascopy and dispatches all missing closed bars sequentially."""
        try:
            for tf in ("M5", "M1"):
                interval_min = 5 if tf == "M5" else 1
                prev_ts = self.last_candle_timestamp.get(tf)
                
                # P1 Fix: Search window begins from previous cursor backward, covering connection drops
                if prev_ts is not None:
                    fetch_start = max(
                        prev_ts - timedelta(minutes=interval_min),
                        now - timedelta(minutes=interval_min * 60)
                    )
                else:
                    fetch_start = now - timedelta(minutes=interval_min * 10)

                # Ensure start is strictly before end
                if (now - fetch_start).total_seconds() < (interval_min * 60):
                    fetch_start = now - timedelta(minutes=interval_min * 2)

                recent = list(duka.fetch_candles(
                    instrument=I_XAU_USD,
                    interval=interval_min,
                    time_unit=duka.TimeUnit.MINUTE,
                    offer_side=duka.OfferSide.BID,
                    start=fetch_start,
                    end=now
                ))
                if recent:
                    recent.sort(key=lambda x: x.timestamp)
                    # Filter strictly closed candles: candle duration must be completely finished
                    closed_candidates = [
                        c for c in recent
                        if (c.timestamp + timedelta(minutes=interval_min)) <= now
                    ]
                    # P1 Fix: Dispatch ALL candles that arrived or were missed after prev_ts in chronological order
                    new_candles = [
                        c for c in closed_candidates
                        if prev_ts is None or c.timestamp > prev_ts
                    ]
                    for bar in new_candles:
                        c_obj = Candle(
                            timestamp=bar.timestamp,
                            open=float(bar.open),
                            high=float(bar.high),
                            low=float(bar.low),
                            close=float(bar.close),
                            tick_volume=float(bar.volume),
                            symbol=self.symbol,
                            timeframe=tf,
                            is_closed=True
                        )
                        with self._lock:
                            self.last_candle_timestamp[tf] = bar.timestamp
                            if tf == self.timeframe:
                                self.last_price = float(bar.close)
                        self.total_candles_received += 1
                        if self.on_bar_completed:
                            self.on_bar_completed(c_obj, False)
        except Exception as e:
            logger.debug(f"Candle sync check notice: {e}")
