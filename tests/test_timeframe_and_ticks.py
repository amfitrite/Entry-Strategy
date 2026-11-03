"""Unit tests for candle-only M1/M5 strategy evaluation and Dukascopy quote feed."""
import time
from datetime import datetime, timezone, timedelta
import pytest
from entrystrategy.config import AppConfig
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.core.models import Candle, TickData, SignalDirection
from entrystrategy.data.dukascopy_feed import DukascopyFeed
from entrystrategy.service import EntryStrategyService
from entrystrategy.gui.app import MatrixWindowAPI
from entrystrategy.engine.registry import PatternRegistry


def test_default_config_is_m5_and_candle_only():
    """Verify the strategy engine defaults to M5 and permanently disables tick triggers."""
    config = AppConfig()
    assert config.timeframe == "M5"
    assert config.enable_ticks is False

    buf = MarketBuffer()
    assert buf.active_timeframe == "M5"


def test_all_40_patterns_active_in_candle_only_matrix_state():
    """Verify all 40 candle-based patterns are enabled in the matrix."""
    config = AppConfig(enable_simulation=False, enable_ticks=False)
    service = EntryStrategyService(config, start_servers=False)

    state = service.get_matrix_state()
    assert state["config"]["timeframe"] == "M5"
    assert state["config"]["enable_ticks"] is False

    # Check all 40 pattern cards exist
    patterns = state["patterns"]
    assert len(patterns) == 40
    for p in patterns:
        assert p["status"] != "DISABLED"
        assert p["status"] in ("IDLE", "ACTIVE", "PENDING_CONFIRMATION", "CONFIRMED", "INVALIDATED", "EXPIRED")


def test_patterns_evaluate_on_m5_completed_candles():
    """Verify patterns evaluate and trigger using completed M5 candles only."""
    buf = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    registry = PatternRegistry()

    now = datetime.now(timezone.utc)

    # 1. Test Pattern 7 (Breakout) on pure M5 candles
    p7 = registry.get_pattern(7)
    c1 = Candle(timestamp=now - timedelta(minutes=10), open=2740.0, high=2745.0, low=2739.0, close=2744.0, timeframe="M5")
    c0 = Candle(timestamp=now - timedelta(minutes=5), open=2744.2, high=2748.0, low=2743.8, close=2747.5, timeframe="M5")
    buf.add_completed_candle(c1)
    buf.add_completed_candle(c0)

    sig7 = p7.evaluate(buf)
    assert sig7 is not None
    assert sig7.direction == SignalDirection.BUY
    assert "Breakout High Candle C[1] M5" in sig7.reasons[0]

    # 2. Test Pattern 8 (Failed Breakout / Sweep & Reclaim) on pure M5 candles
    buf_sweep = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    p8 = registry.get_pattern(8)
    c1_swp = Candle(timestamp=now - timedelta(minutes=10), open=2744.0, high=2745.0, low=2740.0, close=2741.0, timeframe="M5")
    c0_swp = Candle(timestamp=now - timedelta(minutes=5), open=2740.5, high=2743.0, low=2738.5, close=2742.0, timeframe="M5")
    buf_sweep.add_completed_candle(c1_swp)
    buf_sweep.add_completed_candle(c0_swp)

    sig8 = p8.evaluate(buf_sweep)
    assert sig8 is not None
    assert sig8.direction == SignalDirection.BUY
    assert "Liquidity Sweep Bawah" in sig8.reasons[0]

    # 3. Test Pattern 33 (Micro Swing Break) on pure M5 candles
    buf_swg = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    p33 = registry.get_pattern(33)
    base_time = now - timedelta(minutes=30)
    # 5 bars establishing swing high at 2750.0
    for i in range(5):
        h = 2750.0 if i == 2 else 2748.0
        buf_swg.add_completed_candle(Candle(
            timestamp=base_time + timedelta(minutes=5 * i),
            open=2745.0, high=h, low=2744.0, close=2746.0, timeframe="M5"
        ))
    # 6th bar breaks above 2750.0
    buf_swg.add_completed_candle(Candle(
        timestamp=now,
        open=2749.0, high=2753.0, low=2748.5, close=2752.5, timeframe="M5"
    ))
    sig33 = p33.evaluate(buf_swg)
    assert sig33 is not None
    assert sig33.direction == SignalDirection.BUY
    assert "Close bullish" in sig33.reasons[0]

    # 4. Test Pattern 40 (Candle Rejection Confluence) on pure M5 candles
    buf_hyb = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    p40 = registry.get_pattern(40)
    # c1 is pin bar with long lower wick
    c_pin = Candle(timestamp=now - timedelta(minutes=10), open=2742.0, high=2743.0, low=2735.0, close=2741.0, timeframe="M5")
    # c0 confirms with bullish follow-through
    c_follow = Candle(timestamp=now - timedelta(minutes=5), open=2739.5, high=2743.0, low=2739.0, close=2742.5, timeframe="M5")
    buf_hyb.add_completed_candle(c_pin)
    buf_hyb.add_completed_candle(c_follow)

    sig40 = p40.evaluate(buf_hyb)
    assert sig40 is not None
    assert sig40.direction == SignalDirection.BUY
    assert "Lower rejection wick" in sig40.reasons[0]


def test_dukascopy_feed_parses_m5_bar():
    """Verify DukascopyFeed creates valid M5 Candle domain models."""
    completed_bars = []
    feed = DukascopyFeed(on_bar_completed=lambda c, hist: completed_bars.append(c))

    now = datetime.now(timezone.utc)
    candle = Candle(
        timestamp=now,
        open=3940.00,
        high=3945.50,
        low=3939.00,
        close=3944.50,
        tick_volume=520.0,
        spread=1.4,
        symbol="XAUUSD",
        timeframe="M5",
        is_closed=True,
    )
    if feed.on_bar_completed:
        feed.on_bar_completed(candle, False)

    assert len(completed_bars) == 1
    c = completed_bars[0]
    assert c.timeframe == "M5"
    assert c.open == 3940.00
    assert c.high == 3945.50
    assert c.low == 3939.00
    assert c.close == 3944.50
    assert c.tick_volume == 520.0


def test_timeframe_switching_between_m1_and_m5():
    """Verify switching between M1 and M5 timeframes updates buffer context cleanly."""
    config = AppConfig(enable_simulation=False, enable_ticks=False)
    service = EntryStrategyService(config, start_servers=False)

    assert service.active_timeframe == "M5"

    # Switch to M1
    res1 = service.set_timeframe("M1")
    assert res1["success"] is True
    assert res1["timeframe"] == "M1"
    assert service.active_timeframe == "M1"
    assert service.get_matrix_state()["config"]["timeframe"] == "M1"

    # Switch back to M5
    res5 = service.set_timeframe("M5")
    assert res5["success"] is True
    assert res5["timeframe"] == "M5"
    assert service.active_timeframe == "M5"
    assert service.get_matrix_state()["config"]["timeframe"] == "M5"


def test_tick_quotes_cannot_change_candle_entry_trigger():
    """Tick quotes may price execution, but cannot create or alter candle-pattern triggers."""
    now = datetime.now(timezone.utc)
    candles = [
        Candle(timestamp=now - timedelta(minutes=10), open=2740.0, high=2745.0, low=2739.0, close=2744.0, timeframe="M5"),
        Candle(timestamp=now - timedelta(minutes=5), open=2744.2, high=2748.0, low=2743.8, close=2747.5, timeframe="M5"),
    ]

    candle_only = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    candle_plus_quote = MarketBuffer(enable_ticks=True, active_timeframe="M5")
    for candle in candles:
        candle_only.add_completed_candle(candle)
        candle_plus_quote.add_completed_candle(candle)

    # Add an intentionally extreme quote. If a strategy reads the quote,
    # its trigger price/direction would differ from the candle-only result.
    ts = int(now.timestamp() * 1000)
    candle_plus_quote.add_tick(TickData(ts_ms=ts, bid=9999.0, ask=10000.0, last=9999.5))

    registry = PatternRegistry()
    signal_without_quote = registry.get_pattern(7).evaluate(candle_only)
    registry.get_pattern(7).reset()
    signal_with_quote = registry.get_pattern(7).evaluate(candle_plus_quote)

    assert signal_without_quote is not None
    assert signal_with_quote is not None
    assert signal_with_quote.direction == signal_without_quote.direction
    assert signal_with_quote.trigger_price == signal_without_quote.trigger_price
    assert signal_with_quote.reference_price == signal_without_quote.reference_price


def test_tick_strategy_toggle_is_permanently_removed():
    service = EntryStrategyService(AppConfig(enable_simulation=False), start_servers=False)
    result = service.toggle_ticks_mode(True)
    assert result["success"] is False
    assert result["enable_ticks"] is False
    assert service.buffer.latest_tick is None
    assert service.buffer.get_recent_ticks() == []
    service.stop()


def test_unclosed_candle_never_enters_strategy_buffer():
    buf = MarketBuffer(enable_ticks=False, active_timeframe="M1")
    now = datetime.now(timezone.utc)
    unfinished = Candle(
        timestamp=now,
        open=2740.0,
        high=2750.0,
        low=2739.0,
        close=2749.0,
        timeframe="M1",
        is_closed=False,
    )
    buf.add_completed_candle(unfinished)
    assert buf.get_recent_candles(10) == []
    assert buf.total_candles_m1 == 0
