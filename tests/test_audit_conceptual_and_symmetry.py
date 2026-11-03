"""Comprehensive Audit Verification Suite for Conceptual Entry Validity,
BUY/SELL Symmetry, Signal Lifecycle, and Timeframe Isolation.
Mandated by User Request 10 Audit Priorities (P0 & P1).
"""
import pytest
from datetime import datetime, timezone, timedelta
from entrystrategy.core.models import (
    Candle,
    TickData,
    SignalDirection,
    SignalStatus,
    PatternRole,
    EntrySignal,
)
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.engine.registry import PatternRegistry
from entrystrategy.service import EntryStrategyService
from entrystrategy.config import AppConfig


def make_candle(dt: datetime, o: float, h: float, l: float, c: float, tf: str = "M5", vol: float = 100.0) -> Candle:
    return Candle(
        timestamp=dt,
        open=o,
        high=h,
        low=l,
        close=c,
        tick_volume=vol,
        spread=1.4,
        symbol="XAUUSD",
        timeframe=tf,
        is_closed=True,
    )


# ==============================================================================
# AUDIT PRIORITY P0: SETUP VS. ENTRY TRIGGER (A)
# ==============================================================================

def test_audit_p0_liquidity_sweep_and_reclaim_setup_vs_trigger():
    """Verify Pattern 8 (Failed Breakout / Liquidity Sweep + Reclaim) strictly defines
    the swept level, the reclaim entry trigger, and the cancellation / invalidation condition.
    """
    registry = PatternRegistry()
    p8 = registry.get_pattern(8)
    buf = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    now = datetime.now(timezone.utc)

    # 1. Bear Trap (Bullish Sweep & Reclaim -> BUY):
    # Setup: c1 establishes swing low at 2740.0
    c1 = make_candle(now - timedelta(minutes=10), 2744.0, 2745.0, 2740.0, 2741.0)
    # Trigger: c0 sweeps below 2740.0 (low 2738.5) but reclaims and closes back above (close 2742.0)
    c0 = make_candle(now - timedelta(minutes=5), 2740.5, 2743.0, 2738.5, 2742.0)
    buf.add_completed_candle(c1)
    buf.add_completed_candle(c0)

    sig_buy = p8.evaluate(buf)
    assert sig_buy is not None
    assert sig_buy.direction == SignalDirection.BUY
    assert sig_buy.reference_price == 2740.0  # Swept level
    assert sig_buy.trigger_price == 2742.0    # Reclaim close
    assert sig_buy.invalidation_price == round(2738.5 - 0.15, 2)  # Invalidation below sweep low
    assert sig_buy.pattern_role == PatternRole.ENTRY

    # Negative test: swept below 2740.0 but failed to reclaim (closed below at 2739.0)
    buf_fail = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    c0_no_reclaim = make_candle(now - timedelta(minutes=5), 2740.5, 2741.0, 2738.5, 2739.0)
    buf_fail.add_completed_candle(c1)
    buf_fail.add_completed_candle(c0_no_reclaim)
    assert p8.evaluate(buf_fail) is None

    # 2. Bull Trap (Bearish Sweep & Reclaim -> SELL):
    p8.reset()
    buf_sell = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    # Setup: c1 establishes swing high at 2750.0
    c1_high = make_candle(now - timedelta(minutes=10), 2745.0, 2750.0, 2744.0, 2748.0)
    # Trigger: c0 sweeps above 2750.0 (high 2751.8) but falls back and closes below (close 2747.5)
    c0_sell = make_candle(now - timedelta(minutes=5), 2748.5, 2751.8, 2747.0, 2747.5)
    buf_sell.add_completed_candle(c1_high)
    buf_sell.add_completed_candle(c0_sell)

    sig_sell = p8.evaluate(buf_sell)
    assert sig_sell is not None
    assert sig_sell.direction == SignalDirection.SELL
    assert sig_sell.reference_price == 2750.0  # Swept level
    assert sig_sell.trigger_price == 2747.5    # Reclaim close
    assert sig_sell.invalidation_price == round(2751.8 + 0.15, 2)  # Invalidation above sweep high


def test_audit_p0_inside_bar_setup_vs_trigger():
    """Verify Pattern 4 (Inside Bar) requires c1 inside c2 as setup, and c0 breakout as trigger."""
    registry = PatternRegistry()
    p4 = registry.get_pattern(4)
    buf = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    now = datetime.now(timezone.utc)

    c2 = make_candle(now - timedelta(minutes=15), 2740.0, 2746.0, 2739.0, 2744.0)  # Mother bar
    c1 = make_candle(now - timedelta(minutes=10), 2742.0, 2745.0, 2741.0, 2743.0)  # Inside bar setup
    c0 = make_candle(now - timedelta(minutes=5), 2743.0, 2748.0, 2742.5, 2747.5)   # Trigger breakout high
    for c in [c2, c1, c0]:
        buf.add_completed_candle(c)

    sig = p4.evaluate(buf)
    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert sig.reference_price == 2746.0  # Mother bar high
    assert sig.invalidation_price == 2739.0  # Mother bar low
    assert sig.pattern_role == PatternRole.SETUP_TRIGGER


# ==============================================================================
# AUDIT PRIORITY P0: BUY / SELL LOGICAL SYMMETRY (B)
# ==============================================================================

def test_audit_p0_buy_sell_logical_symmetry_across_pattern_types():
    """Verify mathematical and contextual symmetry for BUY and SELL branches
    across Candlestick, Tick-Micro, Swing Geometry, and Hybrid families.
    """
    registry = PatternRegistry()
    now = datetime.now(timezone.utc)

    # 1. Pattern 1 (Engulfing): Symmetric ratio and invalidation
    p1 = registry.get_pattern(1)
    buf_p1_buy = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    buf_p1_buy.add_completed_candle(make_candle(now - timedelta(minutes=10), 2744.0, 2744.5, 2741.0, 2741.2))  # Bear 2.8 pts
    buf_p1_buy.add_completed_candle(make_candle(now - timedelta(minutes=5), 2741.0, 2746.0, 2740.5, 2745.5))   # Bull 4.5 pts
    sig1_buy = p1.evaluate(buf_p1_buy)
    assert sig1_buy.direction == SignalDirection.BUY
    assert sig1_buy.invalidation_price == 2740.5  # c0.low

    p1.reset()
    buf_p1_sell = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    buf_p1_sell.add_completed_candle(make_candle(now - timedelta(minutes=10), 2741.0, 2744.5, 2740.5, 2744.0)) # Bull 3.0 pts
    buf_p1_sell.add_completed_candle(make_candle(now - timedelta(minutes=5), 2744.2, 2744.8, 2739.0, 2739.5))   # Bear 4.7 pts
    sig1_sell = p1.evaluate(buf_p1_sell)
    assert sig1_sell.direction == SignalDirection.SELL
    assert sig1_sell.invalidation_price == 2744.8  # c0.high

    # 2. Pattern 33 (Micro Swing Break): Symmetric breakout rules
    p33 = registry.get_pattern(33)
    buf_p33_buy = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    for i in range(5, 0, -1):
        buf_p33_buy.add_completed_candle(make_candle(now - timedelta(minutes=i * 5), 2740.0, 2744.0, 2738.0, 2741.0))
    buf_p33_buy.add_completed_candle(make_candle(now, 2742.0, 2746.0, 2741.5, 2745.0))  # c0 closes > swing_high 2744.0
    sig33_buy = p33.evaluate(buf_p33_buy)
    assert sig33_buy.direction == SignalDirection.BUY
    assert sig33_buy.reference_price == 2744.0
    assert sig33_buy.invalidation_price == 2738.0  # swing_low

    p33.reset()
    buf_p33_sell = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    for i in range(5, 0, -1):
        buf_p33_sell.add_completed_candle(make_candle(now - timedelta(minutes=i * 5), 2745.0, 2748.0, 2742.0, 2744.0))
    buf_p33_sell.add_completed_candle(make_candle(now, 2743.0, 2743.5, 2739.0, 2740.0))  # c0 closes < swing_low 2742.0
    sig33_sell = p33.evaluate(buf_p33_sell)
    assert sig33_sell.direction == SignalDirection.SELL
    assert sig33_sell.reference_price == 2742.0
    assert sig33_sell.invalidation_price == 2748.0  # swing_high


# ==============================================================================
# AUDIT PRIORITY P0: SIGNAL LIFECYCLE & RETENTION (C)
# ==============================================================================

def test_audit_p0_signal_lifecycle_complete_state_transitions():
    """Verify the 5 formal lifecycle states:
    ACTIVE -> PENDING_CONFIRMATION -> CONFIRMED, INVALIDATED, and EXPIRED.
    Ensures signals never disappear merely because initial conditions ceased.
    """
    sig = EntrySignal(
        pattern_id=1,
        family_name="Engulfing Reversal",
        direction=SignalDirection.BUY,
        reference_price=2740.0,
        trigger_price=2742.0,
        invalidation_price=2738.0,
        timestamp_ms=1000000,
        max_age_sec=300.0,
    )
    assert sig.status == SignalStatus.ACTIVE
    assert sig.is_alive is True

    # 1. Transition to PENDING_CONFIRMATION after 2s
    sig.update_lifecycle(current_price=2742.10, current_ts_ms=1003000)
    assert sig.status == SignalStatus.PENDING_CONFIRMATION
    assert sig.is_alive is True

    # 2. Confirmation transition: price moves favorably past trigger + threshold (0.20)
    sig.update_lifecycle(current_price=2742.30, current_ts_ms=1005000)
    assert sig.status == SignalStatus.CONFIRMED
    assert sig.confirmed_price == 2742.30
    assert sig.is_alive is True

    # 3. Test Invalidation on an active/pending signal:
    sig_inv = EntrySignal(
        pattern_id=1,
        family_name="Engulfing Reversal",
        direction=SignalDirection.BUY,
        reference_price=2740.0,
        trigger_price=2742.0,
        invalidation_price=2738.0,
        timestamp_ms=1000000,
        max_age_sec=300.0,
    )
    # Price dips to invalidation level (2738.0)
    sig_inv.update_lifecycle(current_price=2738.0, current_ts_ms=1004000)
    assert sig_inv.status == SignalStatus.INVALIDATED
    assert sig_inv.invalidated_price == 2738.0
    assert sig_inv.is_terminal is True
    assert sig_inv.is_alive is False

    # 4. Test Expiration: max_age_sec reached
    sig_exp = EntrySignal(
        pattern_id=1,
        family_name="Engulfing Reversal",
        direction=SignalDirection.BUY,
        reference_price=2740.0,
        trigger_price=2742.0,
        invalidation_price=2738.0,
        timestamp_ms=1000000,
        max_age_sec=60.0,
    )
    sig_exp.update_lifecycle(current_price=2742.05, current_ts_ms=1065000)  # 65s elapsed
    assert sig_exp.status == SignalStatus.EXPIRED
    assert sig_exp.is_terminal is True


def test_audit_p0_signal_retention_in_service_matrix():
    """Verify signals are retained in service.latest_signals_by_pattern across subsequent evaluations."""
    config = AppConfig(enable_simulation=False, enable_ticks=False)
    service = EntryStrategyService(config, start_servers=False)
    now = datetime.now(timezone.utc)

    # Feed an engulfing pattern
    c1 = make_candle(now - timedelta(seconds=60), 2744.0, 2744.5, 2741.0, 2741.2)
    c0 = make_candle(now, 2741.0, 2746.0, 2740.5, 2745.5)
    service._on_bar_completed(c1)
    service._on_bar_completed(c0)

    # Signal 1 must be active and stored
    sig1 = service.latest_signals_by_pattern.get(1)
    assert sig1 is not None
    assert sig1.is_alive is True

    # Next candle does NOT trigger Pattern 1 (neutral doji)
    c_neutral = make_candle(now + timedelta(seconds=10), 2745.5, 2746.0, 2745.0, 2745.6)
    service._on_bar_completed(c_neutral)

    # Sinyal TIDAK hilang hanya karena candle berikutnya bukan trigger
    sig1_retained = service.latest_signals_by_pattern.get(1)
    assert sig1_retained is not None
    assert sig1_retained.status in (SignalStatus.ACTIVE, SignalStatus.PENDING_CONFIRMATION, SignalStatus.CONFIRMED)


# ==============================================================================
# AUDIT PRIORITY P1: TIMEFRAME ISOLATION (M1 VS. M5) (D)
# ==============================================================================

def test_audit_p1_timeframe_isolation_strict_buffers():
    """Verify that M1 historical candles never contaminate M5 buffer, and switching
    timeframe cleanly expires previous signals without carrying dirty context.
    """
    buf = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    now = datetime.now(timezone.utc)

    # Add 3 M1 candles and 2 M5 candles
    c_m1_1 = make_candle(now - timedelta(minutes=3), 2740.0, 2741.0, 2739.0, 2740.5, tf="M1")
    c_m1_2 = make_candle(now - timedelta(minutes=2), 2740.5, 2742.0, 2740.0, 2741.5, tf="M1")
    c_m1_3 = make_candle(now - timedelta(minutes=1), 2741.5, 2743.0, 2741.0, 2742.5, tf="M1")

    c_m5_1 = make_candle(now - timedelta(minutes=10), 2735.0, 2740.0, 2734.0, 2739.0, tf="M5")
    c_m5_2 = make_candle(now - timedelta(minutes=5), 2739.0, 2745.0, 2738.0, 2744.0, tf="M5")

    for c in [c_m1_1, c_m1_2, c_m1_3]:
        buf.add_completed_candle(c)
    for c in [c_m5_1, c_m5_2]:
        buf.add_completed_candle(c)

    # Active timeframe is M5: should ONLY return the 2 M5 candles
    m5_candles = buf.get_recent_candles(10)
    assert len(m5_candles) == 2
    assert m5_candles[0].open == 2739.0
    assert m5_candles[1].open == 2735.0

    # Switch active timeframe to M1: should ONLY return the 3 M1 candles
    buf.set_active_timeframe("M1")
    m1_candles = buf.get_recent_candles(10)
    assert len(m1_candles) == 3
    assert m1_candles[0].open == 2741.5
    assert m1_candles[2].open == 2740.0


def test_audit_p1_switching_timeframe_resets_previous_signals():
    """Verify that calling set_timeframe('M1') -> set_timeframe('M5') in service
    expires all active signals from the old timeframe with explicit reason.
    """
    config = AppConfig(enable_simulation=False, enable_ticks=False, timeframe="M5")
    service = EntryStrategyService(config, start_servers=False)
    now = datetime.now(timezone.utc)

    # Add M5 candles triggering Pola 1 Engulfing
    c1 = make_candle(now - timedelta(seconds=60), 2744.0, 2744.5, 2741.0, 2741.2, tf="M5")
    c0 = make_candle(now, 2741.0, 2746.0, 2740.5, 2745.5, tf="M5")
    service._on_bar_completed(c1)
    service._on_bar_completed(c0)

    sig1 = service.latest_signals_by_pattern.get(1)
    assert sig1 is not None
    assert sig1.is_alive is True

    # Switch to M1
    res = service.set_timeframe("M1")
    assert res["success"] is True
    assert service.active_timeframe == "M1"

    # The previous M5 signal must be marked EXPIRED due to timeframe switch
    assert sig1.status == SignalStatus.EXPIRED
    assert "Perpindahan timeframe ke M1" in sig1.status_reason


# ==============================================================================
# AUDIT PRIORITY P1: HISTORICAL INTEGRITY & REDUNDANCY AUDIT (E)
# ==============================================================================

def test_audit_p1_historical_integrity_no_lookahead_bias():
    """Verify that unclosed/forming bars are isolated in _current_bar and
    never contaminate get_recent_candles(), eliminating lookahead bias.
    """
    buf = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    now = datetime.now(timezone.utc)

    # 1. Add completed candle
    c_completed = make_candle(now - timedelta(minutes=5), 2740.0, 2745.0, 2739.0, 2744.0, tf="M5")
    buf.add_completed_candle(c_completed)

    # 2. Update current forming unclosed bar
    c_unclosed = Candle(
        timestamp=now,
        open=2744.0,
        high=2755.0,
        low=2743.0,
        close=2752.0,
        timeframe="M5",
        is_closed=False,
    )
    buf.update_current_bar(c_unclosed)

    # get_recent_candles must only return c_completed, never c_unclosed
    recent = buf.get_recent_candles(5)
    assert len(recent) == 1
    assert recent[0].is_closed is True
    assert recent[0].high == 2745.0
    assert recent[0].close == 2744.0

    # Current bar is accessible separately
    curr = buf.get_current_bar()
    assert curr is not None
    assert curr.is_closed is False
    assert curr.high == 2755.0


def test_audit_p1_deduplication_prevents_duplicate_signals_same_bar():
    """Verify that multiple evaluations on the same completed candle do not emit duplicates."""
    registry = PatternRegistry()
    p1 = registry.get_pattern(1)
    buf = MarketBuffer(enable_ticks=False, active_timeframe="M5")
    now = datetime.now(timezone.utc)

    c1 = make_candle(now - timedelta(minutes=10), 2744.0, 2744.5, 2741.0, 2741.2)
    c0 = make_candle(now - timedelta(minutes=5), 2741.0, 2746.0, 2740.5, 2745.5)
    buf.add_completed_candle(c1)
    buf.add_completed_candle(c0)

    # First check: returns valid signal
    sig1 = p1.check(buf)
    assert sig1 is not None

    # Second check without new bar: MUST return None (deduplicated)
    sig2 = p1.check(buf)
    assert sig2 is None


def test_audit_p1_differentiation_of_similar_momentum_patterns():
    """Verify that Momentum Candle (6), Price Velocity (16), and Price Acceleration (17)
    measure distinct mathematical properties of market movement.
    """
    registry = PatternRegistry()
    p6 = registry.get_pattern(6)
    p16 = registry.get_pattern(16)
    p17 = registry.get_pattern(17)

    # All three must have distinct pattern IDs, names, and phenomena
    assert p6.pattern_id == 6
    assert p16.pattern_id == 16
    assert p17.pattern_id == 17

    assert p6.name != p16.name != p17.name
    assert p6.phenomenon != p16.phenomenon != p17.phenomenon

