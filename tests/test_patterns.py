"""Automated Verification Suite for All 40 Entry Strategy Families."""
import pytest
from datetime import datetime, timezone, timedelta
from entrystrategy.core.models import Candle, TickData, SignalDirection
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.engine.registry import PatternRegistry


def create_mock_candle(
    dt: datetime,
    open_px: float,
    high_px: float,
    low_px: float,
    close_px: float,
) -> Candle:
    return Candle(
        timestamp=dt,
        open=open_px,
        high=high_px,
        low=low_px,
        close=close_px,
        tick_volume=100,
        spread=1.4,
        symbol="XAUUSD",
        timeframe="M5",
        is_closed=True,
    )


def create_mock_tick(ts_ms: int, mid_px: float, spread: float = 0.20) -> TickData:
    half = spread / 2.0
    return TickData(
        ts_ms=ts_ms,
        bid=round(mid_px - half, 2),
        ask=round(mid_px + half, 2),
        last=mid_px,
        volume=1.0,
        symbol="XAUUSD",
    )


def test_registry_contains_exactly_40_families():
    registry = PatternRegistry()
    patterns = registry.get_all_patterns()
    assert len(patterns) == 40
    
    # Check IDs 1 to 40 are all present
    ids = [p.pattern_id for p in patterns]
    assert ids == list(range(1, 41))


def test_pola_01_candlestick_reversal_bullish():
    registry = PatternRegistry()
    pattern = registry.get_pattern(1)
    buf = MarketBuffer()
    
    now = datetime.now(timezone.utc)
    # c1: Bearish
    c1 = create_mock_candle(now - timedelta(minutes=1), 2744.0, 2744.5, 2741.0, 2741.5)  # body 2.5
    # c0: Bullish Engulfing
    c0 = create_mock_candle(now, 2741.0, 2745.5, 2740.8, 2745.2)  # body 4.2 > 1.1 * 2.5
    
    buf.add_completed_candle(c1)
    buf.add_completed_candle(c0)
    
    
    sig = pattern.evaluate(buf)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.pattern_id == 1
    assert len(sig.reasons) > 0


def test_pola_02_continuation_three_soldiers():
    registry = PatternRegistry()
    pattern = registry.get_pattern(2)
    buf = MarketBuffer()
    
    now = datetime.now(timezone.utc)
    c2 = create_mock_candle(now - timedelta(minutes=2), 2740.0, 2742.0, 2739.5, 2741.8)
    c1 = create_mock_candle(now - timedelta(minutes=1), 2741.5, 2744.0, 2741.2, 2743.8)
    c0 = create_mock_candle(now, 2743.2, 2746.0, 2743.0, 2745.9)
    
    buf.add_completed_candle(c2)
    buf.add_completed_candle(c1)
    buf.add_completed_candle(c0)
    
    
    sig = pattern.evaluate(buf)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY


def test_pola_13_candle_displacement_buy():
    registry = PatternRegistry()
    pattern = registry.get_pattern(13)
    buf = MarketBuffer(enable_ticks=False)
    now = datetime.now(timezone.utc)

    # Three small preceding candles, then a wide bullish close beyond local high.
    candles = [
        create_mock_candle(now - timedelta(minutes=4), 2745.0, 2746.0, 2744.5, 2745.5),
        create_mock_candle(now - timedelta(minutes=3), 2745.5, 2746.1, 2745.0, 2745.8),
        create_mock_candle(now - timedelta(minutes=2), 2745.8, 2746.2, 2745.1, 2745.9),
        create_mock_candle(now - timedelta(minutes=1), 2745.8, 2749.0, 2745.6, 2748.7),
    ]
    for candle in candles:
        buf.add_completed_candle(candle)

    sig = pattern.evaluate(buf)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.metrics["body_ratio"] >= 0.65


def test_pola_35_three_push_needs_closed_reversal_confirmation():
    registry = PatternRegistry()
    pattern = registry.get_pattern(35)
    buf = MarketBuffer(enable_ticks=False)

    now = datetime.now(timezone.utc)
    # Pushes 1, 2, 3 have highs 2740.0, 2744.0, 2745.5.
    # The second thrust is smaller than 75% of the first. A final bearish
    # candle closes below the third push base (2742.5).
    candles = [
        create_mock_candle(now - timedelta(minutes=5), 2738.0, 2740.0, 2737.0, 2739.0),
        create_mock_candle(now - timedelta(minutes=4), 2739.0, 2741.0, 2738.5, 2740.5),
        create_mock_candle(now - timedelta(minutes=3), 2740.5, 2744.0, 2740.0, 2743.5),
        create_mock_candle(now - timedelta(minutes=2), 2743.5, 2744.5, 2743.0, 2743.8),
        create_mock_candle(now - timedelta(minutes=1), 2743.0, 2745.5, 2742.5, 2745.0),
        create_mock_candle(now, 2743.0, 2743.5, 2741.0, 2741.5),
    ]
    for candle in candles:
        buf.add_completed_candle(candle)

    sig = pattern.evaluate(buf)
    assert sig is not None
    assert sig.direction == SignalDirection.SELL


def test_all_40_patterns_run_safely_on_dynamic_feed():
    registry = PatternRegistry()
    buf = MarketBuffer()
    
    # 1. Test on empty buffer
    for p in registry.get_all_patterns():
        res = p.evaluate(buf)
        # Must return None safely
        assert res is None or res.direction == SignalDirection.NONE

    # 2. Add some realistic random ticks and candles
    now = datetime.now(timezone.utc)
    base_px = 2745.0
    for i in range(15):
        c = create_mock_candle(now - timedelta(minutes=15 - i), base_px, base_px + 1.0, base_px - 1.0, base_px + 0.2)
        buf.add_completed_candle(c)
        base_px += 0.2

    ts = int(now.timestamp() * 1000)
    for i in range(50):
        ts += 150
        buf.add_tick(create_mock_tick(ts, base_px + (i * 0.02)))

    # All 40 must evaluate without throwing
    fired = registry.evaluate_all(buf)
    assert isinstance(fired, list)
