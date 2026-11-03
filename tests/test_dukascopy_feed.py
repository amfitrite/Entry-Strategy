"""Tests for Dukascopy Bank Live Feed, Cursor Isolation, Candle Completion, and Execution Price."""
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from entrystrategy.core.models import Candle, TickData, SignalStatus, SignalDirection
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.data.dukascopy_feed import DukascopyFeed, DUKASCOPY_AVAILABLE
from entrystrategy.service import EntryStrategyService
from entrystrategy.config import AppConfig
from entrystrategy.engine.registry import PatternRegistry


def test_dukascopy_feed_init():
    feed = DukascopyFeed(
        symbol="XAUUSD",
        timeframe="M5",
        warmup_candles=50,
        poll_interval_s=1.0,
    )
    assert feed.symbol == "XAUUSD"
    assert feed.timeframe == "M5"
    assert feed.warmup_candles == 50
    assert feed.poll_interval_s == 1.0
    assert feed.is_connected is False
    assert isinstance(feed.last_candle_timestamp, dict)
    assert feed.last_candle_timestamp["M1"] is None
    assert feed.last_candle_timestamp["M5"] is None


def test_dukascopy_feed_dual_cursor_m1_m5_isolation():
    """Verify M1 and M5 candle cursors are strictly isolated and do not overwrite each other."""
    feed = DukascopyFeed(symbol="XAUUSD", timeframe="M5")
    
    t_m5 = datetime(2026, 11, 3, 1, 40, tzinfo=timezone.utc)
    t_m1 = datetime(2026, 11, 3, 1, 47, tzinfo=timezone.utc)
    
    feed.last_candle_timestamp["M5"] = t_m5
    feed.last_candle_timestamp["M1"] = t_m1

    assert feed.last_candle_timestamp["M5"] == t_m5
    assert feed.last_candle_timestamp["M1"] == t_m1
    assert feed.last_candle_timestamp["M5"] < feed.last_candle_timestamp["M1"]


def test_dukascopy_feed_filters_unclosed_candles():
    """Verify that ongoing/unclosed candles are NOT accepted as completed bars."""
    feed = DukascopyFeed(symbol="XAUUSD", timeframe="M5")
    now = datetime(2026, 11, 3, 1, 48, 30, tzinfo=timezone.utc)

    # 1. Candle starting at 01:40 -> ends at 01:45 (closed, because 01:45 <= 01:48:30)
    c_closed = MagicMock()
    c_closed.timestamp = datetime(2026, 11, 3, 1, 40, tzinfo=timezone.utc)
    c_closed.open = 3950.0
    c_closed.high = 3955.0
    c_closed.low = 3949.0
    c_closed.close = 3954.0
    c_closed.volume = 100.0

    # 2. Candle starting at 01:45 -> ends at 01:50 (UNCLOSED, because 01:50 > 01:48:30)
    c_unclosed = MagicMock()
    c_unclosed.timestamp = datetime(2026, 11, 3, 1, 45, tzinfo=timezone.utc)
    c_unclosed.open = 3954.0
    c_unclosed.high = 3958.0
    c_unclosed.low = 3953.0
    c_unclosed.close = 3957.0
    c_unclosed.volume = 40.0

    with patch("entrystrategy.data.dukascopy_feed.duka.fetch_candles", return_value=[c_closed, c_unclosed]):
        with patch("entrystrategy.data.dukascopy_feed.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            bars = feed.fetch_warmup_candles(timeframe="M5", count=10)
            
            # Only the closed candle (01:40) should be returned!
            assert len(bars) == 1
            assert bars[0].timestamp == c_closed.timestamp
            assert bars[0].is_closed is True
            assert feed.last_candle_timestamp["M5"] == c_closed.timestamp


def test_market_buffer_never_exposes_ticks_to_strategy_patterns():
    """Tick quote telemetry remains available, but strategy-facing tick APIs stay disabled."""
    buf = MarketBuffer(enable_ticks=False)
    now = datetime.now(timezone.utc)
    ts_ms = int(now.timestamp() * 1000)
    
    tick = TickData(ts_ms=ts_ms, bid=3950.0, ask=3950.30, symbol="XAUUSD")
    buf.add_tick(tick)

    # When enable_ticks is False:
    assert buf.latest_tick is None
    assert buf.get_recent_ticks() == []
    # But quote tick is preserved for telemetry/spread
    assert buf.latest_quote_tick is not None
    assert buf.latest_quote_tick.bid == 3950.0
    assert round(buf.current_spread, 2) == 0.30

    # Compatibility toggles cannot reactivate tick-based strategy evaluation.
    buf.set_enable_ticks(True)
    assert buf.latest_tick is None
    assert buf.get_recent_ticks() == []
    assert buf.latest_quote_tick.bid == 3950.0


def test_execution_price_bid_ask_spread_calculation():
    """Verify BUY signals estimate execution at Ask and SELL at Bid."""
    buf = MarketBuffer(enable_ticks=False)
    now = datetime.now(timezone.utc)
    
    # Tick with spread 0.30 (Bid 3950.0, Ask 3950.30)
    buf.add_tick(TickData(ts_ms=int(time.time() * 1000), bid=3950.0, ask=3950.30, symbol="XAUUSD"))
    
    ref_close = 3952.00
    exec_buy = buf.get_execution_price(SignalDirection.BUY, ref_close)
    exec_sell = buf.get_execution_price(SignalDirection.SELL, ref_close)

    assert exec_buy == round(3952.00 + 0.30, 2)
    assert exec_sell == 3952.00


def test_patterns_pure_candle_evaluation_in_candle_only_mode():
    """Verify Breakout (#7), Swing Break (#33), Double Top (#31), and Three-Push (#35)
    strictly evaluate on candle closes without executing tick branch when enable_ticks=False.
    """
    buf = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    # Even if ticks are pushed into buffer
    now = datetime.now(timezone.utc)
    buf.add_tick(TickData(ts_ms=1000, bid=3960.0, ask=3960.30, symbol="XAUUSD"))

    registry = PatternRegistry()

    # Pattern 7: Breakout
    p7 = registry.get_pattern(7)
    c1 = Candle(timestamp=now - timedelta(minutes=10), open=3940.0, high=3945.0, low=3939.0, close=3944.0, timeframe="M5")
    c0 = Candle(timestamp=now - timedelta(minutes=5), open=3944.0, high=3949.0, low=3943.5, close=3948.5, timeframe="M5")
    buf.add_completed_candle(c1)
    buf.add_completed_candle(c0)

    sig7 = p7.evaluate(buf)
    assert sig7 is not None
    assert sig7.direction == SignalDirection.BUY
    # Trigger price is the candle close, not the tick price (3960.0)
    assert sig7.trigger_price == 3948.5
    # Timestamp represents detection time (fresh, not stale candle open 300s ago)
    assert abs(sig7.timestamp_ms - int(time.time() * 1000)) < 2000
    assert "Breakout High Candle C[1] M5" in sig7.reasons[0]


def test_dukascopy_service_integration():
    """Verify service correctly uses Dukascopy feed and reports state."""
    config = AppConfig(
        symbol="XAUUSD",
        timeframe="M5",
        enable_ticks=False,
        enable_simulation=False,
    )
    svc = EntryStrategyService(config, start_servers=False)
    
    state = svc.get_matrix_state()
    assert "feed" in state
    assert state["feed"]["source"] == "DUKASCOPY_ECN"
    assert state["config"]["timeframe"] == "M5"
    assert state["config"]["enable_ticks"] is False

    # Simulate arrival of a completed M5 candle
    now = datetime.now(timezone.utc)
    c1 = Candle(
        timestamp=now - timedelta(minutes=5),
        open=3940.0,
        high=3950.0,
        low=3938.0,
        close=3948.0,
        tick_volume=150.0,
        symbol="XAUUSD",
        timeframe="M5",
        is_closed=True,
    )
    svc._on_bar_completed(c1, is_history=False)
    assert svc.buffer.total_candles == 1
    assert svc.latest_price == 3948.0


def test_dukascopy_live_timeframe_switch():
    """Verify switching timeframe updates both service and Dukascopy feed."""
    config = AppConfig(symbol="XAUUSD", timeframe="M5", enable_ticks=False, enable_simulation=False)
    svc = EntryStrategyService(config, start_servers=False)
    
    res = svc.set_timeframe("M1")
    assert res["success"] is True
    assert res["timeframe"] == "M1"
    assert svc.active_timeframe == "M1"
    assert svc.dukascopy_feed.timeframe == "M1"

    # Unsupported timeframe
    res_bad = svc.set_timeframe("H1")
    assert res_bad["success"] is False


def test_p0_signal_detection_timestamp_freshness_and_lifetime():
    """P0 Audit Verification:
    Candle patterns must set timestamp_ms to actual detection time, not candle open time.
    If candle open is 5 mins ago, signal lifetime of 300s must NOT immediately expire.
    """
    buf = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    # Feed spread of 0.25
    buf.add_tick(TickData(ts_ms=int(time.time() * 1000), bid=3950.0, ask=3950.25, symbol="XAUUSD"))
    
    # Candle open was 5 minutes ago (02:00 for bar closing at 02:05)
    now = datetime.now(timezone.utc)
    c1 = Candle(timestamp=now - timedelta(minutes=10), open=3940.0, high=3945.0, low=3939.0, close=3944.0, timeframe="M5")
    c0 = Candle(timestamp=now - timedelta(minutes=5), open=3944.0, high=3949.0, low=3943.5, close=3948.5, timeframe="M5")
    buf.add_completed_candle(c1)
    buf.add_completed_candle(c0)

    registry = PatternRegistry()
    signals = registry.evaluate_all(buf)
    
    # Find pattern 7 (Breakout)
    sig7 = next((s for s in signals if s.pattern_id == 7), None)
    assert sig7 is not None
    assert sig7.direction == SignalDirection.BUY
    
    # 1. Detection time must be fresh (~now), NOT 5 minutes old!
    now_ms = int(time.time() * 1000)
    candle_open_ms = int(c0.timestamp.timestamp() * 1000)
    assert abs(sig7.timestamp_ms - now_ms) < 2000
    assert (sig7.timestamp_ms - candle_open_ms) >= 290_000  # At least ~5 mins newer than bar open

    # 2. Max age for M5 is 300s
    assert sig7.max_age_sec == 300.0

    # 3. When immediate lifecycle update occurs on next tick, signal is ACTIVE (not EXPIRED!)
    sig7.update_lifecycle(current_price=3948.5, current_ts_ms=now_ms, spread=0.25)
    assert sig7.status != SignalStatus.EXPIRED
    assert sig7.is_alive is True

    # 4. Only after 301 seconds elapse does it expire
    sig7.update_lifecycle(current_price=3948.5, current_ts_ms=now_ms + 301_000, spread=0.25)
    assert sig7.status == SignalStatus.EXPIRED


def test_p0_execution_price_spread_adjustment():
    """P0 Audit Verification:
    Every signal emitted must have execution_price reflecting Bid/Ask spread:
    BUY fills at Ask (trigger_price + spread)
    SELL fills at Bid (trigger_price)
    """
    buf = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    # Live spread = 0.35 pts
    buf.add_tick(TickData(ts_ms=int(time.time() * 1000), bid=3950.0, ask=3950.35, symbol="XAUUSD"))
    assert round(buf.current_spread, 2) == 0.35

    now = datetime.now(timezone.utc)
    c1 = Candle(timestamp=now - timedelta(minutes=10), open=3940.0, high=3945.0, low=3939.0, close=3944.0, timeframe="M5")
    c0 = Candle(timestamp=now - timedelta(minutes=5), open=3944.0, high=3949.0, low=3943.5, close=3948.5, timeframe="M5")
    buf.add_completed_candle(c1)
    buf.add_completed_candle(c0)

    registry = PatternRegistry()
    signals = registry.evaluate_all(buf)

    sig_buy = next((s for s in signals if s.direction == SignalDirection.BUY), None)
    assert sig_buy is not None
    # BUY: execution price = trigger_price + 0.35
    expected_exec_buy = round(sig_buy.trigger_price + 0.35, 2)
    assert sig_buy.execution_price == expected_exec_buy
    
    # Test dictionary serialization carries execution_price
    d = sig_buy.to_dict()
    assert d["execution_price"] == expected_exec_buy
    assert d["trigger_price"] == round(sig_buy.trigger_price, 2)

    # Now test SELL execution price
    exec_sell = buf.get_execution_price(SignalDirection.SELL, 3940.00)
    assert exec_sell == 3940.00  # SELL fills at Bid without adding spread


def test_p1_service_timeframe_isolation_evaluation():
    """P1 Audit Verification:
    Incoming candles from non-active timeframe (e.g. M1 bar while active is M5)
    must update the buffer but MUST NOT trigger pattern evaluation!
    """
    config = AppConfig(symbol="XAUUSD", timeframe="M5", enable_ticks=False, enable_simulation=False)
    svc = EntryStrategyService(config, start_servers=False)
    assert svc.active_timeframe == "M5"

    eval_mock = MagicMock()
    svc._evaluate_patterns = eval_mock

    now = datetime.now(timezone.utc)
    c_m1 = Candle(timestamp=now - timedelta(minutes=1), open=3940.0, high=3942.0, low=3939.5, close=3941.0, timeframe="M1")
    
    # Deliver M1 bar
    svc._on_bar_completed(c_m1, is_history=False)
    
    # M1 bar must be stored in buffer
    assert svc.buffer.total_candles_m1 == 1
    # But pattern evaluation must NOT be called for off-timeframe bar!
    assert eval_mock.call_count == 0

    # Deliver M5 bar matching active timeframe
    c_m5 = Candle(timestamp=now - timedelta(minutes=5), open=3940.0, high=3946.0, low=3939.0, close=3945.0, timeframe="M5")
    svc._on_bar_completed(c_m5, is_history=False)
    
    # Now evaluation MUST be called!
    assert eval_mock.call_count == 1


def test_p1_dukascopy_feed_sequential_missing_candles_catchup():
    """P1 Audit Verification:
    After connection drop where multiple closed candles were produced,
    _sync_latest_candle must dispatch ALL missed closed bars in chronological order.
    """
    feed = DukascopyFeed(symbol="XAUUSD", timeframe="M5")
    feed.last_candle_timestamp["M5"] = datetime(2026, 11, 3, 1, 30, tzinfo=timezone.utc)

    # 3 missing closed bars: 01:35, 01:40, 01:45, plus 1 ongoing/unclosed bar: 01:50
    now = datetime(2026, 11, 3, 1, 52, 0, tzinfo=timezone.utc)
    
    def make_mock_candle(t_str, close_px):
        c = MagicMock()
        c.timestamp = datetime.fromisoformat(t_str).replace(tzinfo=timezone.utc)
        c.open = close_px - 1.0
        c.high = close_px + 2.0
        c.low = close_px - 2.0
        c.close = close_px
        c.volume = 50.0
        return c

    c_30 = make_mock_candle("2026-11-03T01:30:00", 3940.0) # already processed
    c_35 = make_mock_candle("2026-11-03T01:35:00", 3942.0) # missed 1
    c_40 = make_mock_candle("2026-11-03T01:40:00", 3945.0) # missed 2
    c_45 = make_mock_candle("2026-11-03T01:45:00", 3948.0) # missed 3
    c_50 = make_mock_candle("2026-11-03T01:50:00", 3950.0) # unclosed (ends at 01:55 > 01:52)

    received_bars = []
    feed.on_bar_completed = lambda bar, is_hist: received_bars.append(bar)

    with patch("entrystrategy.data.dukascopy_feed.duka.fetch_candles", return_value=[c_30, c_35, c_40, c_45, c_50]):
        feed._sync_latest_candle(now)

    # Filter received M5 bars
    m5_bars = [b for b in received_bars if b.timeframe == "M5"]

    # All 3 missing closed candles must be dispatched sequentially in order!
    assert len(m5_bars) == 3
    assert m5_bars[0].timestamp == c_35.timestamp
    assert m5_bars[0].close == 3942.0
    assert m5_bars[1].timestamp == c_40.timestamp
    assert m5_bars[1].close == 3945.0
    assert m5_bars[2].timestamp == c_45.timestamp
    assert m5_bars[2].close == 3948.0

    # Cursor must end at the latest closed bar (01:45)
    assert feed.last_candle_timestamp["M5"] == c_45.timestamp
    assert feed.last_price == 3948.0

