"""Regression tests for the 40 candle-only M1/M5 strategy families."""
import pytest
from datetime import datetime, timezone, timedelta
from entrystrategy.core.models import Candle, TickData, SignalDirection, PatternRole
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.engine.registry import PatternRegistry


def create_candle(dt: datetime, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(
        timestamp=dt,
        open=o,
        high=h,
        low=l,
        close=c,
        tick_volume=100,
        spread=1.4,
        symbol="XAUUSD",
        timeframe="M5",
        is_closed=True,
    )


def create_tick(ts_ms: int, mid_px: float, spread: float = 0.20) -> TickData:
    half = spread / 2.0
    return TickData(
        ts_ms=ts_ms,
        bid=round(mid_px - half, 2),
        ask=round(mid_px + half, 2),
        last=mid_px,
        volume=1.0,
        symbol="XAUUSD",
    )


@pytest.fixture
def registry():
    return PatternRegistry()


# ==============================================================================
# 1. CANDLESTICK PATTERNS (Pola 1 - 6, 21, 25 - 27, 38, 39)
# ==============================================================================

def test_pola_01_candlestick_reversal(registry):
    """Pola 1: Engulfing Reversal."""
    p = registry.get_pattern(1)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY (Bullish Engulfing)
    buf_pos = MarketBuffer()
    c1 = create_candle(now - timedelta(minutes=1), 2744.0, 2744.2, 2741.0, 2741.2)  # Bearish body 2.8
    c0 = create_candle(now, 2741.0, 2745.5, 2740.8, 2745.2)  # Bullish body 4.2 > 1.1 * 2.8
    buf_pos.add_completed_candle(c1)
    buf_pos.add_completed_candle(c0)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2745.2))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.reference_price == 2744.0  # c1.open
    assert sig.trigger_price > 0
    assert sig.pattern_role == PatternRole.ENTRY

    # Deduplication test: re-checking on same bar must return None
    dup_sig = p.check(buf_pos)
    assert dup_sig is None

    # Negative test (c0 does not engulf c1)
    p.reset()
    buf_neg = MarketBuffer()
    c1_neg = create_candle(now - timedelta(minutes=1), 2744.0, 2744.5, 2740.0, 2740.5)  # body 3.5
    c0_neg = create_candle(now, 2740.5, 2742.0, 2740.2, 2741.5)  # body 1.0 (insufficient)
    buf_neg.add_completed_candle(c1_neg)
    buf_neg.add_completed_candle(c0_neg)
    assert p.evaluate(buf_neg) is None


def test_pola_02_candlestick_continuation(registry):
    """Pola 2: Three White Soldiers / Black Crows."""
    p = registry.get_pattern(2)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY
    buf_pos = MarketBuffer()
    c2 = create_candle(now - timedelta(minutes=2), 2740.0, 2742.0, 2739.8, 2741.8)
    c1 = create_candle(now - timedelta(minutes=1), 2741.8, 2744.0, 2741.5, 2743.8)
    c0 = create_candle(now, 2743.8, 2746.0, 2743.5, 2745.8)
    for c in [c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2745.8))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.pattern_role == PatternRole.CONFIRMATION
    assert p.check(buf_pos) is None  # Deduplicated

    # Negative test (c1 is bearish -> broken sequence)
    p.reset()
    buf_neg = MarketBuffer()
    c1_bear = create_candle(now - timedelta(minutes=1), 2744.0, 2744.5, 2741.0, 2741.2)
    for c in [c2, c1_bear, c0]:
        buf_neg.add_completed_candle(c)
    assert p.evaluate(buf_neg) is None


def test_pola_03_multi_candle_reversal(registry):
    """Pola 3: Two-Bar Reversal."""
    p = registry.get_pattern(3)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY (Bearish candle followed by >= 85% recovery bullish candle)
    buf_pos = MarketBuffer()
    c1 = create_candle(now - timedelta(minutes=1), 2744.0, 2744.2, 2741.0, 2741.2)  # body 2.8
    c0 = create_candle(now, 2741.2, 2744.2, 2741.0, 2743.9)  # body 2.7 (96% recovery)
    buf_pos.add_completed_candle(c1)
    buf_pos.add_completed_candle(c0)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2743.9))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test (weak recovery < 85%)
    p.reset()
    buf_neg = MarketBuffer()
    c0_weak = create_candle(now, 2741.2, 2742.5, 2741.0, 2742.0)
    buf_neg.add_completed_candle(c1)
    buf_neg.add_completed_candle(c0_weak)
    assert p.evaluate(buf_neg) is None


def test_pola_04_inside_bar_breakout(registry):
    """Pola 4: Inside Bar Breakout."""
    p = registry.get_pattern(4)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: c2 Mother bar, c1 Inside bar, c0 breaks above mother bar
    buf_pos = MarketBuffer()
    c2 = create_candle(now - timedelta(minutes=2), 2740.0, 2745.0, 2739.0, 2743.0)  # Mother bar
    c1 = create_candle(now - timedelta(minutes=1), 2742.0, 2744.0, 2741.0, 2743.0)  # Inside bar
    c0 = create_candle(now, 2743.0, 2746.5, 2742.8, 2746.0)  # Breakout high > c2.high
    for c in [c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2746.0))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.reference_price == 2745.0
    assert p.check(buf_pos) is None

    # Negative test (c1 is not an inside bar)
    p.reset()
    buf_neg = MarketBuffer()
    c1_not_inside = create_candle(now - timedelta(minutes=1), 2738.0, 2746.0, 2737.5, 2745.0)
    for c in [c2, c1_not_inside, c0]:
        buf_neg.add_completed_candle(c)
    assert p.evaluate(buf_neg) is None


def test_pola_05_outside_bar_breakout(registry):
    """Pola 5: Outside Bar Breakout."""
    p = registry.get_pattern(5)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: c2 regular bar, c1 Outside bar engulfing c2, c0 breaks above c1.high
    buf_pos = MarketBuffer()
    c2 = create_candle(now - timedelta(minutes=2), 2742.0, 2744.0, 2741.0, 2743.0)
    c1 = create_candle(now - timedelta(minutes=1), 2741.0, 2745.5, 2740.0, 2745.0)  # Outside bar
    c0 = create_candle(now, 2745.0, 2747.0, 2744.8, 2746.8)  # Break above c1.high
    for c in [c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2746.8))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.reference_price == 2745.5
    assert p.check(buf_pos) is None

    # Negative test (c0 does not break c1 high)
    p.reset()
    buf_neg = MarketBuffer()
    c0_fail = create_candle(now, 2745.0, 2745.2, 2744.0, 2744.2)
    for c in [c2, c1, c0_fail]:
        buf_neg.add_completed_candle(c)
    assert p.evaluate(buf_neg) is None


def test_pola_06_momentum(registry):
    """Pola 6: Momentum Candle."""
    p = registry.get_pattern(6)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: large body >= 70% of range and range >= 1.5x average
    buf_pos = MarketBuffer()
    c4 = create_candle(now - timedelta(minutes=4), 2740.0, 2741.0, 2739.5, 2740.5)
    c3 = create_candle(now - timedelta(minutes=3), 2740.5, 2741.5, 2740.0, 2741.0)
    c2 = create_candle(now - timedelta(minutes=2), 2741.0, 2742.0, 2740.5, 2741.5)
    c1 = create_candle(now - timedelta(minutes=1), 2741.5, 2742.5, 2741.0, 2742.0)
    c0 = create_candle(now, 2742.0, 2747.0, 2741.8, 2746.8)  # range 5.2, body 4.8
    for c in [c4, c3, c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2746.8))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test (small range doji)
    p.reset()
    buf_neg = MarketBuffer()
    c0_doji = create_candle(now, 2742.0, 2742.2, 2741.8, 2742.0)
    for c in [c4, c3, c2, c1, c0_doji]:
        buf_neg.add_completed_candle(c)
    assert p.evaluate(buf_neg) is None


def test_pola_21_volatility_contraction(registry):
    """Pola 21: Volatility Contraction."""
    p = registry.get_pattern(21)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: 3 contracting bars (c3 > c2 > c1), then c0 breaks above c1.high
    buf_pos = MarketBuffer()
    c3 = create_candle(now - timedelta(minutes=3), 2740.0, 2745.0, 2739.0, 2742.0)  # range 6.0
    c2 = create_candle(now - timedelta(minutes=2), 2741.0, 2744.0, 2741.0, 2743.0)  # range 3.0
    c1 = create_candle(now - timedelta(minutes=1), 2742.0, 2743.2, 2742.0, 2742.8)  # range 1.2
    c0 = create_candle(now, 2742.8, 2744.5, 2742.6, 2744.0)  # breaks c1.high 2743.2
    for c in [c3, c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2744.0))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test (no contraction, range expanding)
    p.reset()
    buf_neg = MarketBuffer()
    c1_exp = create_candle(now - timedelta(minutes=1), 2740.0, 2747.0, 2739.0, 2746.0)
    for c in [c3, c2, c1_exp, c0]:
        buf_neg.add_completed_candle(c)
    assert p.evaluate(buf_neg) is None


def test_pola_25_wick_pattern(registry):
    """Pola 25: Wick Pattern (Pin Bar)."""
    p = registry.get_pattern(25)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: Pin bar with lower wick >= 60% of range
    buf_pos = MarketBuffer()
    c0 = create_candle(now, 2744.0, 2744.5, 2740.0, 2744.2)  # range 4.5, lower wick = 2744.0 - 2740.0 = 4.0 (88%)
    buf_pos.add_completed_candle(c0)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2744.2))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test (neutral candle with equal tiny wicks)
    p.reset()
    buf_neg = MarketBuffer()
    c0_neutral = create_candle(now, 2742.0, 2743.0, 2741.0, 2742.0)
    buf_neg.add_completed_candle(c0_neutral)
    assert p.evaluate(buf_neg) is None


def test_pola_26_body_expansion(registry):
    """Pola 26: Body Expansion."""
    p = registry.get_pattern(26)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: 3 consecutive bullish bars with expanding bodies
    buf_pos = MarketBuffer()
    c2 = create_candle(now - timedelta(minutes=2), 2740.0, 2741.2, 2739.8, 2741.0)  # body 1.0
    c1 = create_candle(now - timedelta(minutes=1), 2741.0, 2743.0, 2740.8, 2742.8)  # body 1.8 > 1.2 * 1.0
    c0 = create_candle(now, 2742.8, 2746.0, 2742.5, 2745.8)  # body 3.0 > 1.2 * 1.8
    for c in [c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2745.8))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test (c0 body smaller than c1)
    p.reset()
    buf_neg = MarketBuffer()
    c0_shrink = create_candle(now, 2742.8, 2743.5, 2742.5, 2743.2)
    for c in [c2, c1, c0_shrink]:
        buf_neg.add_completed_candle(c)
    assert p.evaluate(buf_neg) is None


def test_pola_27_body_contraction(registry):
    """Pola 27: Body Contraction."""
    p = registry.get_pattern(27)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: Bullish impulse fading in c2 and c1, c0 reversal breaks below c1.low
    buf_pos = MarketBuffer()
    c3 = create_candle(now - timedelta(minutes=3), 2740.0, 2744.0, 2739.8, 2743.5)  # body 3.5
    c2 = create_candle(now - timedelta(minutes=2), 2743.5, 2745.5, 2743.2, 2745.0)  # body 1.5
    c1 = create_candle(now - timedelta(minutes=1), 2745.0, 2745.8, 2744.8, 2745.5)  # body 0.5
    c0 = create_candle(now, 2745.5, 2745.6, 2744.0, 2744.2)  # breaks c1.low 2744.8 downward
    for c in [c3, c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2744.2))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.SELL
    assert p.check(buf_pos) is None

    # Negative test (no contraction)
    p.reset()
    buf_neg = MarketBuffer()
    c1_large = create_candle(now - timedelta(minutes=1), 2745.0, 2750.0, 2744.8, 2749.5)
    for c in [c3, c2, c1_large, c0]:
        buf_neg.add_completed_candle(c)
    assert p.evaluate(buf_neg) is None


def test_pola_38_staircase(registry):
    """Pola 38: Staircase Pattern."""
    p = registry.get_pattern(38)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: 4 consecutive higher highs and higher lows
    buf_pos = MarketBuffer()
    c3 = create_candle(now - timedelta(minutes=3), 2740.0, 2742.0, 2739.5, 2741.5)
    c2 = create_candle(now - timedelta(minutes=2), 2741.5, 2743.5, 2741.0, 2743.0)
    c1 = create_candle(now - timedelta(minutes=1), 2743.0, 2745.0, 2742.5, 2744.5)
    c0 = create_candle(now, 2744.5, 2746.5, 2744.0, 2746.0)
    for c in [c3, c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2746.0))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test (lower low breaks staircase)
    p.reset()
    buf_neg = MarketBuffer()
    c0_broken = create_candle(now, 2744.5, 2746.5, 2741.0, 2743.0)  # low < c1.low
    for c in [c3, c2, c1, c0_broken]:
        buf_neg.add_completed_candle(c)
    assert p.evaluate(buf_neg) is None


def test_pola_39_candle_sequence(registry):
    """Pola 39: Candle Sequence (Trend -> Equilibrium -> Expansion Reversal)."""
    p = registry.get_pattern(39)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: c3 & c2 bearish impulse, c1 doji/equilibrium, c0 strong bullish reversal expansion
    buf_pos = MarketBuffer()
    c3 = create_candle(now - timedelta(minutes=3), 2748.0, 2748.5, 2745.0, 2745.2)  # body 2.8 bearish
    c2 = create_candle(now - timedelta(minutes=2), 2745.0, 2745.2, 2741.0, 2741.5)  # body 3.5 bearish
    c1 = create_candle(now - timedelta(minutes=1), 2741.50, 2742.2, 2741.0, 2741.55)  # body 0.05 doji (<= 0.12)
    c0 = create_candle(now, 2741.7, 2745.5, 2741.5, 2745.0)  # body 3.3 bullish expansion
    for c in [c3, c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2745.0))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test (c1 is not doji)
    p.reset()
    buf_neg = MarketBuffer()
    c1_large = create_candle(now - timedelta(minutes=1), 2741.5, 2744.0, 2741.0, 2743.8)
    for c in [c3, c2, c1_large, c0]:
        buf_neg.add_completed_candle(c)
    assert p.evaluate(buf_neg) is None


# ==============================================================================


def _latest_first_buffer(rows, timeframe="M5"):
    """Build a MarketBuffer from OHLC rows ordered newest to oldest."""
    now = datetime.now(timezone.utc)
    buf = MarketBuffer(enable_ticks=False, active_timeframe=timeframe)
    for i, (o, h, l, close) in reversed(list(enumerate(rows))):
        buf.add_completed_candle(create_candle(now - timedelta(minutes=i), o, h, l, close))
    return buf


def test_candle_only_buffer_never_exposes_ticks_to_strategies():
    buf = MarketBuffer(enable_ticks=True)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    for i in range(25):
        buf.add_tick(create_tick(now_ms + i, 2745.0 + i * 0.05))
    assert buf.latest_tick is None
    assert buf.get_recent_ticks(50) == []
    assert buf.latest_quote_tick is not None  # Quote telemetry remains available for execution pricing.


def test_pola_11_choch_requires_confirmed_countertrend_swing_break():
    registry = PatternRegistry()
    p = registry.get_pattern(11)
    # Newest first. Confirmed recent LH=98 and LL=92, older LH=101 and LL=95.
    rows = [
        (98.6, 100.5, 98.4, 100.3),
        (96.0, 97.0, 95.6, 96.5),
        (94.0, 96.5, 92.0, 95.0),
        (96.0, 98.0, 95.0, 97.5),
        (95.0, 96.0, 95.5, 95.8),
        (96.0, 97.0, 95.5, 96.5),
        (96.5, 97.5, 95.0, 96.0),
        (99.0, 101.0, 97.0, 100.0),
        (98.0, 99.0, 96.5, 98.0),
        (99.0, 100.0, 96.0, 99.0),
        (98.0, 99.0, 94.0, 95.0),
        (97.0, 98.0, 95.0, 96.0),
        (96.0, 97.0, 94.0, 95.0),
        (95.0, 96.0, 93.0, 94.0),
        (94.0, 95.0, 92.5, 93.0),
        (93.0, 94.0, 91.5, 92.0),
    ]
    buf = _latest_first_buffer(rows)
    sig = p.evaluate(buf)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.metrics["prior_trend"] == "BEARISH"
    assert sig.reference_price == 98.0

    # A wick through the protected high without a bullish close is not CHoCH.
    rows[0] = (98.6, 100.5, 98.4, 97.8)
    assert p.evaluate(_latest_first_buffer(rows)) is None


def test_pola_12_bos_requires_continuation_of_hh_hl_structure():
    registry = PatternRegistry()
    p = registry.get_pattern(12)
    rows = [
        (104.8, 106.2, 104.6, 106.0),
        (103.0, 104.0, 101.5, 103.5),
        (101.0, 103.0, 100.0, 102.0),
        (103.0, 105.0, 101.0, 104.0),
        (102.0, 103.0, 101.5, 102.5),
        (101.5, 102.0, 100.0, 101.5),
        (100.5, 102.5, 98.0, 101.0),
        (101.0, 103.0, 99.0, 102.0),
        (100.0, 102.0, 99.5, 101.0),
        (100.0, 101.0, 99.0, 100.0),
        (99.0, 100.0, 97.0, 98.0),
        (98.0, 99.0, 96.0, 97.0),
        (97.0, 98.0, 95.0, 96.0),
        (96.0, 97.0, 94.0, 95.0),
        (95.0, 96.0, 93.0, 94.0),
        (94.0, 95.0, 92.0, 93.0),
    ]
    sig = p.evaluate(_latest_first_buffer(rows))
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.metrics["structure"] == "HH_HL"


def test_pola_13_displacement_is_closed_candle_only():
    registry = PatternRegistry()
    p = registry.get_pattern(13)
    now = datetime.now(timezone.utc)
    buf = MarketBuffer()
    for i, row in enumerate([
        (100.0, 104.2, 99.8, 103.8),
        (99.6, 100.2, 99.3, 99.9),
        (99.4, 100.0, 99.1, 99.7),
        (99.5, 100.0, 99.2, 99.8),
        (99.4, 99.9, 99.1, 99.6),
    ][::-1]):
        buf.add_completed_candle(create_candle(now - timedelta(minutes=i), *row))
    sig = p.evaluate(buf)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.metrics["body_ratio"] >= 0.65


def test_pola_14_breakout_retest_requires_level_reclaim():
    registry = PatternRegistry()
    p = registry.get_pattern(14)
    rows = [
        (99.9, 101.0, 99.8, 100.7),  # retest/hold
        (99.5, 101.5, 99.4, 101.2),  # confirmed breakout
    ] + [(98.5, 100.0, 95.0, 99.0)] * 6
    sig = p.evaluate(_latest_first_buffer(rows))
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.reference_price == 100.0


def test_pola_15_bullish_fvg_uses_three_candle_imbalance():
    registry = PatternRegistry()
    p = registry.get_pattern(15)
    rows = [
        (102.0, 102.6, 101.3, 102.4),  # third candle leaves gap
        (99.5, 102.0, 99.3, 101.8),    # displacement candle
        (99.0, 100.0, 98.8, 99.6),     # first candle
        (99.0, 99.6, 98.9, 99.4),
        (99.2, 99.7, 99.0, 99.5),
    ]
    sig = p.evaluate(_latest_first_buffer(rows))
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.metrics["fvg_size"] > 0.0


def test_pola_16_fvg_retest_requires_touch_and_rejection():
    registry = PatternRegistry()
    p = registry.get_pattern(16)
    rows = [
        (101.0, 101.5, 100.8, 101.3),  # retest
        (101.5, 102.0, 101.2, 101.6),  # gap remains open before retest
        (102.0, 102.6, 101.0, 102.4),  # third
        (99.5, 102.0, 99.3, 101.8),    # middle displacement
        (99.0, 100.0, 98.8, 99.6),     # first
        (99.0, 99.6, 98.9, 99.4),
    ]
    sig = p.evaluate(_latest_first_buffer(rows))
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.metrics["retest_low"] <= sig.metrics["fvg_high"]


def test_pola_17_order_block_retest_requires_break_and_retest():
    registry = PatternRegistry()
    p = registry.get_pattern(17)
    rows = [
        (100.5, 102.0, 99.5, 101.5),   # retest and bullish close above OB open
        (98.5, 103.0, 98.0, 102.5),    # displacement/break
        (100.0, 101.0, 98.0, 99.0),    # last bearish candle = demand OB
    ] + [(99.0, 100.0, 98.0, 99.5)] * 5
    sig = p.evaluate(_latest_first_buffer(rows))
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.metrics["ob_low"] < sig.metrics["ob_high"]


def test_pola_22_trend_pullback_needs_retracement_and_reclaim():
    registry = PatternRegistry()
    p = registry.get_pattern(22)
    rows = [
        (102.0, 104.0, 101.5, 103.5),  # trigger close above pullback high
        (102.8, 103.0, 100.0, 101.0),  # pullback
        (101.0, 104.0, 99.0, 103.0),   # impulse
        (99.0, 102.0, 98.0, 101.5),
        (96.0, 100.0, 95.0, 99.0),
        (95.0, 98.0, 94.0, 97.0),
    ]
    sig = p.evaluate(_latest_first_buffer(rows))
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert 0.25 <= sig.metrics["retracement_ratio"] <= 0.75


def test_pola_23_donchian_breakout_needs_close_outside_range():
    registry = PatternRegistry()
    p = registry.get_pattern(23)
    rows = [(105.0, 107.0, 104.8, 106.8)] + [(102.0, 105.0, 101.0, 103.0)] * 10
    sig = p.evaluate(_latest_first_buffer(rows))
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.reference_price == 105.0

    # Intrabar wick above range with close back inside does not count.
    rows[0] = (104.0, 106.0, 103.0, 104.5)
    assert p.evaluate(_latest_first_buffer(rows)) is None


def test_all_40_candle_patterns_evaluate_safely_without_tick_input():
    registry = PatternRegistry()
    buf = MarketBuffer(enable_ticks=False)
    for pattern in registry.get_all_patterns():
        assert pattern.evaluate(buf) is None

    now = datetime.now(timezone.utc)
    price = 2745.0
    for i in range(30):
        o = price
        c = price + (0.20 if i % 2 == 0 else -0.15)
        h = max(o, c) + 0.30
        l = min(o, c) - 0.30
        buf.add_completed_candle(create_candle(now - timedelta(minutes=30-i), o, h, l, c))
        price = c
    fired = registry.evaluate_all(buf)
    assert isinstance(fired, list)
