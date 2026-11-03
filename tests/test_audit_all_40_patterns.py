"""Exhaustive Positive, Negative, and Deduplication Unit Tests for All 40 Patterns.
Audited and verified in accordance with strict market microstructure definitions.
"""
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
# 2. PURE TICK MICROSTRUCTURE PATTERNS (Pola 11 - 17, 22, 23)
# ==============================================================================

def test_pola_11_tick_momentum(registry):
    """Pola 11: Tick Momentum."""
    p = registry.get_pattern(11)
    p.reset()
    ts = 1700000000000
    
    # Positive BUY: >= 0.50 pts shift in <= 2.5s
    buf_pos = MarketBuffer()
    for i in range(20):
        buf_pos.add_tick(create_tick(ts + i * 50, 2745.0 + i * 0.03))  # shift = +0.57 in 0.95s
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.reference_price == 2745.0
    assert p.check(buf_pos) is None  # Cooldown/event deduplicated

    # Negative test: flat ticks (< 0.20 pts)
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(20):
        buf_neg.add_tick(create_tick(ts + i * 50, 2745.0 + (i % 2) * 0.02))
    assert p.evaluate(buf_neg) is None


def test_pola_12_tick_reversal(registry):
    """Pola 12: Tick Reversal (V-reversal)."""
    p = registry.get_pattern(12)
    p.reset()
    ts = 1700000000000
    
    # Positive BUY: drop >= 0.40 then rebound >= 0.35
    buf_pos = MarketBuffer()
    for i in range(12):
        buf_pos.add_tick(create_tick(ts + i * 50, 2745.0 - i * 0.04))  # -0.44 pts
    for i in range(12):
        buf_pos.add_tick(create_tick(ts + 600 + i * 50, 2744.56 + i * 0.04))  # +0.44 pts
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: monotonic drift
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(24):
        buf_neg.add_tick(create_tick(ts + i * 50, 2745.0 + i * 0.02))
    assert p.evaluate(buf_neg) is None


def test_pola_13_tick_imbalance(registry):
    """Pola 13: Tick Imbalance (Quote Direction Dominance)."""
    p = registry.get_pattern(13)
    p.reset()
    ts = 1700000000000
    
    # Positive BUY: >= 75% upticks
    buf_pos = MarketBuffer()
    px = 2745.0
    for i in range(21):
        if i % 6 != 0:
            px += 0.04
        else:
            px -= 0.01
        buf_pos.add_tick(create_tick(ts + i * 60, round(px, 2)))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.pattern_role == PatternRole.CONFIRMATION
    assert p.check(buf_pos) is None

    # Negative test: 50-50 balance
    p.reset()
    buf_neg = MarketBuffer()
    px = 2745.0
    for i in range(21):
        px += 0.02 if i % 2 == 0 else -0.02
        buf_neg.add_tick(create_tick(ts + i * 60, round(px, 2)))
    assert p.evaluate(buf_neg) is None


def test_pola_14_tick_burst(registry):
    """Pola 14: Tick Burst."""
    p = registry.get_pattern(14)
    p.reset()
    ts = 1700000000000
    
    # Positive BUY: 20 ticks in 400ms (50 ticks/sec) and +0.35 pts shift
    buf_pos = MarketBuffer()
    for i in range(20):
        buf_pos.add_tick(create_tick(ts + i * 20, 2745.0 + i * 0.02))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: slow arrival (1 tick per second)
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(20):
        buf_neg.add_tick(create_tick(ts + i * 1000, 2745.0 + i * 0.02))
    assert p.evaluate(buf_neg) is None


def test_pola_15_tick_exhaustion(registry):
    """Pola 15: Tick Exhaustion."""
    p = registry.get_pattern(15)
    p.reset()
    ts = 1700000000000
    
    # Positive SELL: Fast rally (+0.50), high-rate stall in last 10 ticks (< 0.08 shift), latest tick drops
    buf_pos = MarketBuffer()
    for i in range(15):
        buf_pos.add_tick(create_tick(ts + i * 50, 2745.0 + i * 0.04))  # rally +0.56 pts
    for i in range(12):
        buf_pos.add_tick(create_tick(ts + 800 + i * 40, 2745.56 + (i % 2) * 0.02))  # stall
    # Latest tick turns down
    buf_pos.add_tick(create_tick(ts + 1350, 2745.50))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.SELL
    assert sig.pattern_role == PatternRole.SETUP_TRIGGER
    assert p.check(buf_pos) is None

    # Negative test: strong ongoing breakout (no stall)
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(28):
        buf_neg.add_tick(create_tick(ts + i * 50, 2745.0 + i * 0.05))
    assert p.evaluate(buf_neg) is None


def test_pola_16_price_velocity(registry):
    """Pola 16: Price Velocity."""
    p = registry.get_pattern(16)
    p.reset()
    ts = 1700000000000
    
    # Positive BUY: velocity >= 0.40 pts/sec
    buf_pos = MarketBuffer()
    for i in range(15):
        buf_pos.add_tick(create_tick(ts + i * 50, 2745.0 + i * 0.04))  # +0.56 in 0.7s = 0.80 pts/s
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: slow drift (0.05 pts/s)
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(15):
        buf_neg.add_tick(create_tick(ts + i * 200, 2745.0 + i * 0.01))
    assert p.evaluate(buf_neg) is None


def test_pola_17_price_acceleration(registry):
    """Pola 17: Price Acceleration."""
    p = registry.get_pattern(17)
    p.reset()
    ts = 1700000000000
    
    # Positive BUY: velocity jumping from slow to fast
    buf_pos = MarketBuffer()
    # First half: 10 ticks, slow (+0.05 in 1.0s)
    for i in range(10):
        buf_pos.add_tick(create_tick(ts + i * 100, 2745.0 + i * 0.005))
    # Second half: 10 ticks, fast jump (+0.50 in 0.5s)
    for i in range(10):
        buf_pos.add_tick(create_tick(ts + 1000 + i * 50, 2745.05 + i * 0.05))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: constant velocity (no acceleration)
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(20):
        buf_neg.add_tick(create_tick(ts + i * 100, 2745.0 + i * 0.02))
    assert p.evaluate(buf_neg) is None


def test_pola_22_consecutive_price_movement(registry):
    """Pola 22: Consecutive Price Movement."""
    p = registry.get_pattern(22)
    p.reset()
    ts = 1700000000000
    
    # Positive BUY: 6 consecutive upticks
    buf_pos = MarketBuffer()
    for i in range(10):
        buf_pos.add_tick(create_tick(ts + i * 50, 2745.0 + i * 0.03))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: zigzag
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(10):
        buf_neg.add_tick(create_tick(ts + i * 50, 2745.0 + (i % 2) * 0.02))
    assert p.evaluate(buf_neg) is None


def test_pola_23_alternating_tick(registry):
    """Pola 23: Alternating Tick Pattern."""
    p = registry.get_pattern(23)
    p.reset()
    ts = 1700000000000
    
    # Positive BUY: ping-pong alternating in tight range, then 2 consecutive upticks breaking out
    buf_pos = MarketBuffer()
    # Ping-pong: 2745.00, 2745.05, 2745.00, 2745.05, 2745.00, 2745.05
    for i in range(6):
        px = 2745.05 if i % 2 == 1 else 2745.00
        buf_pos.add_tick(create_tick(ts + i * 50, px))
    # Breakout: 2745.10, 2745.18
    buf_pos.add_tick(create_tick(ts + 350, 2745.10))
    buf_pos.add_tick(create_tick(ts + 400, 2745.18))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: still alternating, no breakout
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(8):
        px = 2745.05 if i % 2 == 1 else 2745.00
        buf_neg.add_tick(create_tick(ts + i * 50, px))
    assert p.evaluate(buf_neg) is None


# ==============================================================================
# 3. HYBRID TICK-CANDLE PATTERNS (Pola 7-10, 18-20, 24, 28-30, 36, 37, 40)
# ==============================================================================

def test_pola_07_breakout(registry):
    """Pola 7: Breakout."""
    p = registry.get_pattern(7)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: tick mid > c1.high + 0.10
    buf_pos = MarketBuffer()
    c1 = create_candle(now - timedelta(minutes=1), 2740.0, 2745.0, 2739.0, 2744.0)
    buf_pos.add_completed_candle(c1)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2745.30))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.reference_price == 2745.0
    assert p.check(buf_pos) is None

    # Negative test: tick inside candle
    p.reset()
    buf_neg = MarketBuffer()
    buf_neg.add_completed_candle(c1)
    buf_neg.add_tick(create_tick(int(now.timestamp() * 1000), 2742.0))
    assert p.evaluate(buf_neg) is None


def test_pola_08_failed_breakout(registry):
    """Pola 8: Failed Breakout (Trap)."""
    p = registry.get_pattern(8)
    p.reset()
    now = datetime.now(timezone.utc)
    ts = int(now.timestamp() * 1000)
    
    # Positive SELL (Bull trap): probed above c1.high (2745.0), then collapsed to 2744.50
    buf_pos = MarketBuffer()
    c1 = create_candle(now - timedelta(minutes=1), 2740.0, 2745.0, 2739.0, 2744.0)
    buf_pos.add_completed_candle(c1)
    for i in range(8):
        buf_pos.add_tick(create_tick(ts + i * 50, 2744.5 + i * 0.10))  # peaks at 2745.20
    buf_pos.add_tick(create_tick(ts + 500, 2744.70))
    buf_pos.add_tick(create_tick(ts + 550, 2744.50))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.SELL
    assert p.check(buf_pos) is None

    # Negative test: clean breakout holding above high
    p.reset()
    buf_neg = MarketBuffer()
    buf_neg.add_completed_candle(c1)
    for i in range(12):
        buf_neg.add_tick(create_tick(ts + i * 50, 2745.50 + i * 0.05))
    assert p.evaluate(buf_neg) is None


def test_pola_09_micro_pullback(registry):
    """Pola 9: Micro Pullback."""
    p = registry.get_pattern(9)
    p.reset()
    now = datetime.now(timezone.utc)
    ts = int(now.timestamp() * 1000)
    
    # Positive BUY: c1 bullish (open 2740, close 2744, mid 2742), ticks retest 2742.0 then bounce to 2742.40
    buf_pos = MarketBuffer()
    c1 = create_candle(now - timedelta(minutes=1), 2740.0, 2744.2, 2739.8, 2744.0)
    buf_pos.add_completed_candle(c1)
    buf_pos.add_tick(create_tick(ts, 2743.0))
    buf_pos.add_tick(create_tick(ts + 50, 2742.0))  # touch 50%
    for i in range(8):
        buf_pos.add_tick(create_tick(ts + 100 + i * 50, 2742.10 + i * 0.05))  # bounce to 2742.45
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: dump straight through 50% without bounce
    p.reset()
    buf_neg = MarketBuffer()
    buf_neg.add_completed_candle(c1)
    for i in range(10):
        buf_neg.add_tick(create_tick(ts + i * 50, 2743.0 - i * 0.40))
    assert p.evaluate(buf_neg) is None


def test_pola_10_micro_trend_reversal(registry):
    """Pola 10: Micro Trend Reversal."""
    p = registry.get_pattern(10)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: 3 lower highs (c3 > c2 > c1), higher low formed (c1.low > c2.low), tick breaks above c1.high
    buf_pos = MarketBuffer()
    c3 = create_candle(now - timedelta(minutes=3), 2746.0, 2748.0, 2743.0, 2744.0)  # high 2748
    c2 = create_candle(now - timedelta(minutes=2), 2744.0, 2746.0, 2740.0, 2742.0)  # high 2746, low 2740
    c1 = create_candle(now - timedelta(minutes=1), 2742.0, 2744.0, 2741.0, 2743.5)  # high 2744, higher low 2741
    for c in [c3, c2, c1]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2744.30))  # breaks c1.high
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.pattern_role == PatternRole.STRUCTURE
    assert p.check(buf_pos) is None

    # Negative test: no higher low
    p.reset()
    buf_neg = MarketBuffer()
    c1_lower = create_candle(now - timedelta(minutes=1), 2742.0, 2744.0, 2739.0, 2741.0)
    for c in [c3, c2, c1_lower]:
        buf_neg.add_completed_candle(c)
    buf_neg.add_tick(create_tick(int(now.timestamp() * 1000), 2744.30))
    assert p.evaluate(buf_neg) is None


def test_pola_18_micro_range_expansion(registry):
    """Pola 18: Micro Range Expansion."""
    p = registry.get_pattern(18)
    p.reset()
    now = datetime.now(timezone.utc)
    ts = int(now.timestamp() * 1000)
    
    # Positive BUY: 3 bars avg range 1.0 pts, ticks move 1.6 pts (> 1.3x)
    buf_pos = MarketBuffer()
    for i in range(3):
        buf_pos.add_completed_candle(create_candle(now - timedelta(minutes=3 - i), 2740.0, 2741.0, 2740.0, 2740.8))
    for i in range(15):
        buf_pos.add_tick(create_tick(ts + i * 50, 2740.0 + i * 0.11))  # +1.54 pts
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: tiny tick span (< 0.50 pts)
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(3):
        buf_neg.add_completed_candle(create_candle(now - timedelta(minutes=3 - i), 2740.0, 2742.0, 2740.0, 2741.5))
    for i in range(15):
        buf_neg.add_tick(create_tick(ts + i * 50, 2741.0 + (i % 2) * 0.05))
    assert p.evaluate(buf_neg) is None


def test_pola_19_micro_range_compression(registry):
    """Pola 19: Micro Range Compression."""
    p = registry.get_pattern(19)
    p.reset()
    ts = 1700000000000
    
    # Positive BUY: historical 24 ticks compressed in span <= 0.22, 25th tick breaks out
    buf_pos = MarketBuffer()
    for i in range(24):
        buf_pos.add_tick(create_tick(ts + i * 50, 2745.0 + (i % 3) * 0.05))  # high 2745.10, low 2745.00 (span 0.10)
    # Breakout tick
    buf_pos.add_tick(create_tick(ts + 1250, 2745.18))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.pattern_role == PatternRole.SETUP_TRIGGER
    assert p.check(buf_pos) is None

    # Negative test: wide volatility (> 0.50 pts)
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(25):
        buf_neg.add_tick(create_tick(ts + i * 50, 2745.0 + i * 0.05))
    assert p.evaluate(buf_neg) is None


def test_pola_20_volatility_burst(registry):
    """Pola 20: Volatility Burst."""
    p = registry.get_pattern(20)
    p.reset()
    ts = 1700000000000
    
    # Positive BUY: freq >= 20 t/s and abs(displacement) >= 0.50 pts
    buf_pos = MarketBuffer()
    for i in range(25):
        buf_pos.add_tick(create_tick(ts + i * 30, 2745.0 + i * 0.03))  # 25 ticks in 720ms (34.7 t/s) and +0.72 pts
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: slow frequency
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(25):
        buf_neg.add_tick(create_tick(ts + i * 200, 2745.0 + i * 0.03))
    assert p.evaluate(buf_neg) is None


def test_pola_24_rejection(registry):
    """Pola 24: Rejection Pattern."""
    p = registry.get_pattern(24)
    p.reset()
    ts = 1700000000000
    
    # Positive BUY (Lower Rejection): tested min 2744.0 then bounced to 2744.40 (>= 0.35)
    buf_pos = MarketBuffer()
    for i in range(10):
        buf_pos.add_tick(create_tick(ts + i * 50, 2745.0 - i * 0.10))  # down to 2744.10
    buf_pos.add_tick(create_tick(ts + 550, 2744.00))  # min
    for i in range(8):
        buf_pos.add_tick(create_tick(ts + 600 + i * 50, 2744.05 + i * 0.06))  # up to 2744.47
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: price stays at extreme without rejection
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(18):
        buf_neg.add_tick(create_tick(ts + i * 50, 2745.0 - i * 0.05))
    assert p.evaluate(buf_neg) is None


def test_pola_28_gap(registry):
    """Pola 28: Gap Pattern."""
    p = registry.get_pattern(28)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: gap up >= 0.40 within 60s
    buf_pos = MarketBuffer()
    c1 = create_candle(now - timedelta(minutes=1), 2740.0, 2742.0, 2739.5, 2741.0)
    c0 = create_candle(now, 2741.5, 2743.0, 2741.4, 2742.5)  # gap = 2741.5 - 2741.0 = +0.50 pts
    buf_pos.add_completed_candle(c1)
    buf_pos.add_completed_candle(c0)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2741.5))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: weekend / multi-hour gap (> 180s)
    p.reset()
    buf_neg = MarketBuffer()
    c1_weekend = create_candle(now - timedelta(hours=48), 2740.0, 2742.0, 2739.5, 2741.0)
    buf_neg.add_completed_candle(c1_weekend)
    buf_neg.add_completed_candle(c0)
    assert p.evaluate(buf_neg) is None


def test_pola_29_failed_momentum(registry):
    """Pola 29: Failed Momentum."""
    p = registry.get_pattern(29)
    p.reset()
    ts = 1700000000000
    
    # Positive SELL: leg1 up +0.55, leg2 down -0.55
    buf_pos = MarketBuffer()
    for i in range(13):
        buf_pos.add_tick(create_tick(ts + i * 50, 2745.0 + i * 0.05))  # +0.60
    for i in range(15):
        buf_pos.add_tick(create_tick(ts + 650 + i * 50, 2745.60 - i * 0.05))  # -0.70
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.SELL
    assert p.check(buf_pos) is None

    # Negative test: momentum continued
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(28):
        buf_neg.add_tick(create_tick(ts + i * 50, 2745.0 + i * 0.04))
    assert p.evaluate(buf_neg) is None


def test_pola_30_momentum_exhaustion(registry):
    """Pola 30: Momentum Exhaustion."""
    p = registry.get_pattern(30)
    p.reset()
    now = datetime.now(timezone.utc)
    ts = int(now.timestamp() * 1000)
    
    # Positive SELL: c1 large bullish (range 2.0), ticks stall at high, then drop
    buf_pos = MarketBuffer()
    c1 = create_candle(now - timedelta(minutes=1), 2740.0, 2746.0, 2739.8, 2745.8)  # range 6.2
    buf_pos.add_completed_candle(c1)
    for i in range(18):
        buf_pos.add_tick(create_tick(ts + i * 50, 2745.90 + (i % 2) * 0.08))  # stall span 0.08
    buf_pos.add_tick(create_tick(ts + 950, 2745.65))  # drops below c1.high - 0.20
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.SELL
    assert p.check(buf_pos) is None

    # Negative test: small bar (range < 1.5)
    p.reset()
    buf_neg = MarketBuffer()
    c1_small = create_candle(now - timedelta(minutes=1), 2745.0, 2745.5, 2744.8, 2745.4)
    buf_neg.add_completed_candle(c1_small)
    buf_neg.add_tick(create_tick(ts, 2745.4))
    assert p.evaluate(buf_neg) is None


def test_pola_36_v_reversal(registry):
    """Pola 36: V-Reversal."""
    p = registry.get_pattern(36)
    p.reset()
    ts = 1700000000000
    
    # Positive BUY: drop >= 0.50 pts, rebound >= 80%
    buf_pos = MarketBuffer()
    for i in range(15):
        buf_pos.add_tick(create_tick(ts + i * 50, 2745.0 - i * 0.05))  # -0.70 pts to 2744.30
    for i in range(15):
        buf_pos.add_tick(create_tick(ts + 750 + i * 50, 2744.30 + i * 0.05))  # +0.70 pts rebound
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: no rebound
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(30):
        buf_neg.add_tick(create_tick(ts + i * 50, 2745.0 - i * 0.03))
    assert p.evaluate(buf_neg) is None


def test_pola_37_inverted_v_reversal(registry):
    """Pola 37: Inverted V-Reversal."""
    p = registry.get_pattern(37)
    p.reset()
    ts = 1700000000000
    
    # Positive SELL: rally >= 0.50 pts, slump >= 80%
    buf_pos = MarketBuffer()
    for i in range(15):
        buf_pos.add_tick(create_tick(ts + i * 50, 2745.0 + i * 0.05))  # +0.70 pts to 2745.70
    for i in range(15):
        buf_pos.add_tick(create_tick(ts + 750 + i * 50, 2745.70 - i * 0.05))  # slump back
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.SELL
    assert p.check(buf_pos) is None

    # Negative test: ongoing rally
    p.reset()
    buf_neg = MarketBuffer()
    for i in range(30):
        buf_neg.add_tick(create_tick(ts + i * 50, 2745.0 + i * 0.03))
    assert p.evaluate(buf_neg) is None


def test_pola_40_hybrid_tick_candle(registry):
    """Pola 40: Hybrid Tick-Candle."""
    p = registry.get_pattern(40)
    p.reset()
    now = datetime.now(timezone.utc)
    ts = int(now.timestamp() * 1000)
    
    # Positive BUY: c1 lower wick >= 45% of range, and tick imbalance >= 70% upticks
    buf_pos = MarketBuffer()
    c1 = create_candle(now - timedelta(minutes=1), 2743.0, 2743.5, 2740.0, 2743.2)  # range 3.5, lower wick = 3.0 (85%)
    buf_pos.add_completed_candle(c1)
    px = 2743.2
    for i in range(18):
        px += 0.04 if i % 5 != 0 else -0.01
        buf_pos.add_tick(create_tick(ts + i * 50, round(px, 2)))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: flat candle wick
    p.reset()
    buf_neg = MarketBuffer()
    c1_flat = create_candle(now - timedelta(minutes=1), 2740.0, 2742.0, 2739.8, 2741.8)
    buf_neg.add_completed_candle(c1_flat)
    buf_neg.add_tick(create_tick(ts, 2741.8))
    assert p.evaluate(buf_neg) is None


# ==============================================================================
# 4. SWING GEOMETRY PATTERNS (Pola 31 - 35)
# ==============================================================================

def test_pola_31_micro_double_top(registry):
    """Pola 31: Micro Double Top."""
    p = registry.get_pattern(31)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive SELL: peak 1 at 2746.0, valley at 2744.0 (depth 2.0), peak 2 at 2746.10, tick rejected
    buf_pos = MarketBuffer()
    c5 = create_candle(now - timedelta(minutes=5), 2743.0, 2744.0, 2742.0, 2743.5)
    c4 = create_candle(now - timedelta(minutes=4), 2743.5, 2746.0, 2743.0, 2745.5)  # Peak 1 (2746.0)
    c3 = create_candle(now - timedelta(minutes=3), 2745.5, 2745.8, 2744.0, 2744.2)  # Valley (2744.0)
    c2 = create_candle(now - timedelta(minutes=2), 2744.2, 2744.8, 2744.0, 2744.5)
    c1 = create_candle(now - timedelta(minutes=1), 2744.5, 2745.5, 2744.2, 2745.2)
    c0 = create_candle(now, 2745.2, 2746.1, 2744.8, 2745.5)  # Peak 2 (2746.1)
    for c in [c5, c4, c3, c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2745.70))  # < 2746.10 - 0.15
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.SELL
    assert sig.pattern_role == PatternRole.STRUCTURE
    assert p.check(buf_pos) is None

    # Negative test: ascending tops (trending up)
    p.reset()
    buf_neg = MarketBuffer()
    c0_trend = create_candle(now, 2745.2, 2749.0, 2745.0, 2748.5)
    for c in [c5, c4, c3, c2, c1, c0_trend]:
        buf_neg.add_completed_candle(c)
    buf_neg.add_tick(create_tick(int(now.timestamp() * 1000), 2748.5))
    assert p.evaluate(buf_neg) is None


def test_pola_32_micro_double_bottom(registry):
    """Pola 32: Micro Double Bottom."""
    p = registry.get_pattern(32)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: bottom 1 at 2740.0, peak at 2742.0 (height 2.0), bottom 2 at 2740.10, tick bounced
    buf_pos = MarketBuffer()
    c5 = create_candle(now - timedelta(minutes=5), 2743.0, 2744.0, 2742.0, 2742.5)
    c4 = create_candle(now - timedelta(minutes=4), 2742.5, 2743.0, 2740.0, 2740.5)  # Bottom 1 (2740.0)
    c3 = create_candle(now - timedelta(minutes=3), 2740.5, 2742.0, 2740.2, 2741.8)  # Peak (2742.0)
    c2 = create_candle(now - timedelta(minutes=2), 2741.8, 2742.0, 2741.2, 2741.5)
    c1 = create_candle(now - timedelta(minutes=1), 2741.5, 2741.8, 2740.8, 2741.0)
    c0 = create_candle(now, 2741.0, 2741.5, 2740.1, 2740.8)  # Bottom 2 (2740.1)
    for c in [c5, c4, c3, c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2740.40))  # > 2740.10 + 0.15
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: descending bottoms (trending down)
    p.reset()
    buf_neg = MarketBuffer()
    c0_trend = create_candle(now, 2741.0, 2741.5, 2737.0, 2737.5)
    for c in [c5, c4, c3, c2, c1, c0_trend]:
        buf_neg.add_completed_candle(c)
    buf_neg.add_tick(create_tick(int(now.timestamp() * 1000), 2737.5))
    assert p.evaluate(buf_neg) is None


def test_pola_33_micro_swing_break(registry):
    """Pola 33: Micro Swing Break."""
    p = registry.get_pattern(33)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive BUY: swing high of bars 1-5 is 2745.0, tick breaks above 2745.20
    buf_pos = MarketBuffer()
    c5 = create_candle(now - timedelta(minutes=5), 2740.0, 2742.0, 2739.0, 2741.0)
    c4 = create_candle(now - timedelta(minutes=4), 2741.0, 2745.0, 2740.0, 2744.0)  # max high 2745.0
    c3 = create_candle(now - timedelta(minutes=3), 2744.0, 2744.5, 2742.0, 2743.0)
    c2 = create_candle(now - timedelta(minutes=2), 2743.0, 2744.0, 2742.0, 2743.5)
    c1 = create_candle(now - timedelta(minutes=1), 2743.5, 2744.5, 2743.0, 2744.0)
    c0 = create_candle(now, 2744.0, 2744.8, 2743.8, 2744.5)
    for c in [c5, c4, c3, c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2745.25))
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert p.check(buf_pos) is None

    # Negative test: tick inside swing range
    p.reset()
    buf_neg = MarketBuffer()
    for c in [c5, c4, c3, c2, c1, c0]:
        buf_neg.add_completed_candle(c)
    buf_neg.add_tick(create_tick(int(now.timestamp() * 1000), 2743.0))
    assert p.evaluate(buf_neg) is None


def test_pola_34_micro_swing_failure(registry):
    """Pola 34: Micro Swing Failure."""
    p = registry.get_pattern(34)
    p.reset()
    now = datetime.now(timezone.utc)
    ts = int(now.timestamp() * 1000)
    
    # Positive SELL: swing high is 2745.0, ticks test 2745.10 then collapse to 2744.60
    buf_pos = MarketBuffer()
    c5 = create_candle(now - timedelta(minutes=5), 2740.0, 2742.0, 2739.0, 2741.0)
    c4 = create_candle(now - timedelta(minutes=4), 2741.0, 2745.0, 2740.0, 2744.0)  # swing high 2745.0
    c3 = create_candle(now - timedelta(minutes=3), 2744.0, 2744.5, 2742.0, 2743.0)
    c2 = create_candle(now - timedelta(minutes=2), 2743.0, 2744.0, 2742.0, 2743.5)
    c1 = create_candle(now - timedelta(minutes=1), 2743.5, 2744.5, 2743.0, 2744.0)
    c0 = create_candle(now, 2744.0, 2744.8, 2743.8, 2744.5)
    for c in [c5, c4, c3, c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    for i in range(8):
        buf_pos.add_tick(create_tick(ts + i * 50, 2744.5 + i * 0.08))  # reaches 2745.06
    buf_pos.add_tick(create_tick(ts + 500, 2744.70))
    buf_pos.add_tick(create_tick(ts + 550, 2744.60))  # collapsed
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.SELL
    assert p.check(buf_pos) is None

    # Negative test: tick stays above swing high
    p.reset()
    buf_neg = MarketBuffer()
    for c in [c5, c4, c3, c2, c1, c0]:
        buf_neg.add_completed_candle(c)
    for i in range(10):
        buf_neg.add_tick(create_tick(ts + i * 50, 2745.50 + i * 0.05))
    assert p.evaluate(buf_neg) is None


def test_pola_35_three_push(registry):
    """Pola 35: Three-Push Pattern."""
    p = registry.get_pattern(35)
    p.reset()
    now = datetime.now(timezone.utc)
    
    # Positive SELL: 3 upward pushes with diminishing thrusts, reversal break below push 3 base
    # Push 1: high 2740.0
    # Push 2: high 2744.0 (+4.0)
    # Push 3: high 2746.0 (+2.0 < 4.0 * 0.75), low of c0 is 2743.5
    buf_pos = MarketBuffer()
    c4 = create_candle(now - timedelta(minutes=4), 2738.0, 2740.0, 2737.0, 2739.0)
    c3 = create_candle(now - timedelta(minutes=3), 2739.0, 2741.0, 2738.5, 2740.5)
    c2 = create_candle(now - timedelta(minutes=2), 2740.5, 2744.0, 2740.0, 2743.5)
    c1 = create_candle(now - timedelta(minutes=1), 2743.5, 2744.5, 2743.0, 2743.8)
    c0 = create_candle(now, 2743.8, 2746.0, 2743.5, 2744.5)
    for c in [c4, c3, c2, c1, c0]:
        buf_pos.add_completed_candle(c)
    buf_pos.add_tick(create_tick(int(now.timestamp() * 1000), 2743.30))  # < c0.low - 0.05
    
    sig = p.check(buf_pos)
    assert sig is not None
    assert sig.direction == SignalDirection.SELL
    assert sig.pattern_role == PatternRole.STRUCTURE
    assert p.check(buf_pos) is None

    # Negative test: thrusts increasing (strong breakout, not wedge)
    p.reset()
    buf_neg = MarketBuffer()
    c0_strong = create_candle(now, 2743.8, 2750.0, 2743.5, 2749.5)  # thrust2 = 6.0 > 4.0
    for c in [c4, c3, c2, c1, c0_strong]:
        buf_neg.add_completed_candle(c)
    buf_neg.add_tick(create_tick(int(now.timestamp() * 1000), 2743.30))
    assert p.evaluate(buf_neg) is None
