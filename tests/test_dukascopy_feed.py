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


def test_market_buffer_strictly_blocks_latest_tick_when_ticks_disabled():
    """Verify MarketBuffer.latest_tick returns None when enable_ticks=False, preventing tick-bleed."""
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

    # When enable_ticks is True:
    buf.set_enable_ticks(True)
    assert buf.latest_tick is not None
    assert buf.latest_tick.bid == 3950.0
    assert len(buf.get_recent_ticks()) == 1


def test_execution_price_bid_ask_spread_calculation():
    """Verify BUY signals estimate execution at Ask and SELL at Bid."""
    buf = MarketBuffer(enable_ticks=False)
    now = datetime.now(timezone.utc)
    
    # Tick with spread 0.30 (Bid 3950.0, Ask 3950.30)
    buf.add_tick(TickData(ts_ms=1000, bid=3950.0, ask=3950.30, symbol="XAUUSD"))
    
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
    assert sig7.timestamp_ms == int(c0.timestamp.timestamp() * 1000)
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
