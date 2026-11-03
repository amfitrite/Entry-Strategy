"""Comprehensive Audit Verification Suite for Tier Grading Engine (XAUUSD M1/M5/M15).

Tests:
1. Strict Tier Boundaries (SSS - D)
2. Configurable Weights Summing to 1.0
3. No Fabricated ATR Fallback (None returned when no closed bars)
4. ATR Closed-Candle Only Enforcement
5. Unclosed / In-Progress Candles Never Affect Grade
6. Look-Ahead Bias Prevention (Future candles never leak into historical signal score)
7. HTF Unclosed Candles Never Leak into MTF Context
8. No MTF Positive Baseline Without Valid Closed Evidence
9. Strategy-Specific Location Quality Formulas
10. FVG Derived from Real OHLC Geometry (No Fabricated Fallback)
11. Dynamic Confidence (Never Fixed Constants)
12. Insufficient Data produces INSUFFICIENT_DATA and Tier Caps
13. All 40 Strategy IDs Have Dedicated Evaluator Mapping
14. Deterministic Scoring for Identical Snapshot Input
15. Historical Validation Foundation & NOT VALIDATED Labels
"""
import time
from datetime import datetime, timezone, timedelta
import pytest
from entrystrategy.core.models import (
    Candle,
    EntrySignal,
    SignalDirection,
    SignalStatus,
)
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.engine.grading import (
    GradingEngine,
    GradeTier,
    GradingWeights,
    ComponentBreakdown,
    DataStatus,
    DataSufficiencyStatus,
    EVALUATOR_MAPPING,
    get_evaluator_for_pattern,
    calculate_atr,
    TIER_THRESHOLDS,
    TIER_GATING,
    TierPerformanceMetrics,
    HistoricalTierValidator,
)


def _make_closed_candle(
    timeframe: str,
    dt: datetime,
    open_px: float,
    high_px: float,
    low_px: float,
    close_px: float,
    tick_volume: int = 100,
    is_closed: bool = True,
) -> Candle:
    return Candle(
        timestamp=dt,
        open=open_px,
        high=high_px,
        low=low_px,
        close=close_px,
        tick_volume=tick_volume,
        spread=0.20,
        symbol="XAUUSD",
        timeframe=timeframe,
        is_closed=is_closed,
    )


def _populate_buffer(
    buf: MarketBuffer,
    tf: str,
    count: int = 20,
    base_px: float = 2750.0,
    end_dt: Optional[datetime] = None,
):
    ref_dt = end_dt or datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
    step_sec = 900 if tf == "M15" else (300 if tf == "M5" else 60)
    for i in range(count, 0, -1):
        t = ref_dt - timedelta(seconds=i * step_sec)
        c = _make_closed_candle(
            timeframe=tf,
            dt=t,
            open_px=base_px + (count - i) * 0.2,
            high_px=base_px + (count - i) * 0.2 + 1.0,
            low_px=base_px + (count - i) * 0.2 - 0.5,
            close_px=base_px + (count - i) * 0.2 + 0.8,
            is_closed=True,
        )
        buf.add_completed_candle(c)


# ---------------------------------------------------------------------
# 1. Tier Boundaries Correctness
# ---------------------------------------------------------------------
def test_all_tier_boundaries():
    assert GradeTier.from_score(100.0) == GradeTier.SSS
    assert GradeTier.from_score(95.0) == GradeTier.SSS
    assert GradeTier.from_score(94.99) == GradeTier.SS
    assert GradeTier.from_score(90.0) == GradeTier.SS
    assert GradeTier.from_score(89.99) == GradeTier.S
    assert GradeTier.from_score(85.0) == GradeTier.S
    assert GradeTier.from_score(84.99) == GradeTier.A
    assert GradeTier.from_score(75.0) == GradeTier.A
    assert GradeTier.from_score(74.99) == GradeTier.B
    assert GradeTier.from_score(65.0) == GradeTier.B
    assert GradeTier.from_score(64.99) == GradeTier.C
    assert GradeTier.from_score(50.0) == GradeTier.C
    assert GradeTier.from_score(49.99) == GradeTier.D
    assert GradeTier.from_score(0.0) == GradeTier.D


# ---------------------------------------------------------------------
# 2. Configurable Weights Summing to 1.0
# ---------------------------------------------------------------------
def test_grading_weights_sum_to_one():
    weights = GradingWeights(
        pattern_quality=0.30,
        market_structure=0.20,
        location_quality=0.20,
        candle_confirmation=0.15,
        execution_quality=0.15,
    )
    total = sum(weights.to_dict().values())
    assert abs(total - 1.0) < 1e-4

    with pytest.raises(ValueError):
        GradingWeights(pattern_quality=0.50, market_structure=0.50, location_quality=0.50)


# ---------------------------------------------------------------------
# 3. No Fabricated ATR Fallback (Returns None if no closed bars)
# ---------------------------------------------------------------------
def test_calculate_atr_no_fabricated_fallback():
    # Empty list must return None, NOT 1.5!
    assert calculate_atr([]) is None

    # List of unclosed candles only must return None
    now = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    unclosed = [_make_closed_candle("M5", now, 2750.0, 2755.0, 2748.0, 2752.0, is_closed=False)]
    assert calculate_atr(unclosed) is None


# ---------------------------------------------------------------------
# 4. ATR Uses Only Closed Candles
# ---------------------------------------------------------------------
def test_calculate_atr_uses_only_closed_candles():
    now = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    c1 = _make_closed_candle("M5", now - timedelta(minutes=5), 2750.0, 2754.0, 2748.0, 2752.0, is_closed=True)
    c_unclosed = _make_closed_candle("M5", now, 2752.0, 2800.0, 2700.0, 2790.0, is_closed=False)

    # When unclosed candle is mixed in, only the closed bar (range = 6.0) is measured
    atr = calculate_atr([c_unclosed, c1])
    assert atr == 6.0


# ---------------------------------------------------------------------
# 5. Unclosed / In-Progress Candles Never Affect Grade
# ---------------------------------------------------------------------
def test_unclosed_candle_never_affects_grading():
    engine = GradingEngine()
    buf = MarketBuffer(active_timeframe="M5")
    _populate_buffer(buf, "M5", count=20)

    sig = EntrySignal(
        pattern_id=11,
        family_name="CHoCH",
        direction=SignalDirection.BUY,
        reference_price=2750.0,
        trigger_price=2755.0,
        timestamp_ms=int(datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000),
        invalidation_price=2746.0,
    )

    res_clean = engine.grade_signal(sig, buf, "M5")

    # Inject massive unclosed candle
    unclosed = _make_closed_candle(
        "M5",
        datetime(2026, 11, 3, 12, 5, 0, tzinfo=timezone.utc),
        2750.0, 2900.0, 2600.0, 2850.0,
        is_closed=False,
    )
    buf.add_completed_candle(unclosed)

    res_with_unclosed = engine.grade_signal(sig, buf, "M5")

    assert res_clean.score == res_with_unclosed.score
    assert res_clean.breakdown.to_dict() == res_with_unclosed.breakdown.to_dict()


# ---------------------------------------------------------------------
# 6. Look-Ahead Bias Prevention (Future Candles Never Leak into Grade)
# ---------------------------------------------------------------------
def test_future_candles_never_affect_historical_grade():
    engine = GradingEngine()
    buf = MarketBuffer(active_timeframe="M5")

    t_signal = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
    _populate_buffer(buf, "M5", count=20, end_dt=t_signal)

    sig = EntrySignal(
        pattern_id=12,
        family_name="BOS",
        direction=SignalDirection.BUY,
        reference_price=2750.0,
        trigger_price=2754.0,
        timestamp_ms=int(t_signal.timestamp() * 1000),
        invalidation_price=2745.0,
    )

    # Initial grade at signal time
    res_initial = engine.grade_signal(sig, buf, "M5")

    # Simulate 5 subsequent bars forming in the future (after 12:00:00)
    for i in range(1, 6):
        t_future = t_signal + timedelta(minutes=i * 5)
        c_future = _make_closed_candle(
            "M5", t_future, 2754.0 - i * 5, 2755.0, 2730.0, 2732.0, is_closed=True
        )
        buf.add_completed_candle(c_future)

    # Re-grade the historical signal with future bars in buffer
    res_regraded = engine.grade_signal(sig, buf, "M5")

    # Scores must remain strictly identical
    assert res_initial.score == res_regraded.score
    assert res_initial.tier == res_regraded.tier
    assert res_initial.breakdown.to_dict() == res_regraded.breakdown.to_dict()


# ---------------------------------------------------------------------
# 7. HTF Unclosed Candles Never Leak into MTF Context
# ---------------------------------------------------------------------
def test_htf_unclosed_candles_never_leak_into_mtf_context():
    buf = MarketBuffer(active_timeframe="M1")
    t_sig = datetime(2026, 11, 3, 12, 7, 0, tzinfo=timezone.utc)
    sig_ms = int(t_sig.timestamp() * 1000)

    # Add closed M5 bar for 12:00 - 12:05 (completed before 12:07)
    c_m5_closed = _make_closed_candle(
        "M5", datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc),
        2750.0, 2755.0, 2749.0, 2754.0, is_closed=True
    )
    buf.add_completed_candle(c_m5_closed)

    # Add unclosed/forming M5 bar for 12:05 - 12:10 (in progress at 12:07)
    c_m5_forming = _make_closed_candle(
        "M5", datetime(2026, 11, 3, 12, 5, 0, tzinfo=timezone.utc),
        2754.0, 2730.0, 2720.0, 2722.0, is_closed=False
    )
    buf.add_completed_candle(c_m5_forming)

    evaluator = get_evaluator_for_pattern(11)
    score, reasons, penalties = evaluator.evaluate_mtf_confluence(
        buf, "M1", SignalDirection.BUY, snapshot_timestamp_ms=sig_ms
    )

    # Forming candle (bearish 2722) must NOT be used
    assert not any("2722" in p for p in penalties)


# ---------------------------------------------------------------------
# 8. No MTF Positive Baseline Without Valid Closed Evidence
# ---------------------------------------------------------------------
def test_no_mtf_positive_baseline_without_evidence():
    buf = MarketBuffer(active_timeframe="M1")
    evaluator = get_evaluator_for_pattern(11)

    # Empty buffer: MTF score must be None (UNAVAILABLE), never a fake +75 or +80!
    score, reasons, penalties = evaluator.evaluate_mtf_confluence(buf, "M1", SignalDirection.BUY)
    assert score is None
    assert any("belum memiliki riwayat" in r for r in reasons)

    # M15 standalone: must be None (UNAVAILABLE / independent), never a fake +80!
    score_m15, reasons_m15, _ = evaluator.evaluate_mtf_confluence(buf, "M15", SignalDirection.BUY)
    assert score_m15 is None
    assert any("mandiri" in r for r in reasons_m15)


# ---------------------------------------------------------------------
# 9. Strategy-Specific Location Quality Formulas
# ---------------------------------------------------------------------
def test_location_quality_strategy_specific_formulas():
    buf = MarketBuffer(active_timeframe="M5")
    _populate_buffer(buf, "M5", count=20, base_px=2750.0)
    candles = buf.get_recent_candles(20, "M5")

    evaluator = get_evaluator_for_pattern(11)

    # 1. Breakout clearance formula (CHoCH / BOS)
    score_bo, _, _ = evaluator.assess_location_breakout_clearance(
        candles, SignalDirection.BUY, trigger_px=2755.0, breakout_level=2753.0, atr=2.0
    )
    assert score_bo is not None and score_bo >= 80.0

    # 2. Premium / Discount formula (Reversal / SFP)
    score_pd, _, _ = evaluator.assess_location_premium_discount(
        candles, SignalDirection.BUY, trigger_px=2749.0
    )
    assert score_pd is not None and score_pd >= 80.0

    # 3. Fibonacci Retracement formula (Pullbacks / Retests)
    score_fib, _, _ = evaluator.assess_location_retracement(
        candles, SignalDirection.BUY, trigger_px=2752.0, origin_low=2750.0, origin_high=2754.0
    )
    assert score_fib is not None and score_fib >= 80.0


# ---------------------------------------------------------------------
# 10. FVG Derived from Real OHLC Geometry (Zero Gap = 0.0, No Fabricated Fallback)
# ---------------------------------------------------------------------
def test_fvg_real_ohlc_geometry_no_fabricated_fallback():
    evaluator = get_evaluator_for_pattern(15)
    buf = MarketBuffer(active_timeframe="M5")

    now = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    # Candles with overlapping wicks (NO REAL GAP)
    c3 = _make_closed_candle("M5", now - timedelta(minutes=15), 2748.0, 2751.0, 2747.0, 2750.0)
    c2 = _make_closed_candle("M5", now - timedelta(minutes=10), 2750.0, 2754.0, 2749.0, 2753.0)
    c1 = _make_closed_candle("M5", now - timedelta(minutes=5), 2753.0, 2756.0, 2752.0, 2755.0)
    c0 = _make_closed_candle("M5", now, 2754.0, 2755.0, 2753.0, 2754.5)  # c0.low (2753.0) <= c2.high (2754.0)

    buf.add_completed_candle(c3)
    buf.add_completed_candle(c2)
    buf.add_completed_candle(c1)
    buf.add_completed_candle(c0)

    sig = EntrySignal(
        pattern_id=15,
        family_name="Fair Value Gap",
        direction=SignalDirection.BUY,
        reference_price=2753.0,
        trigger_price=2754.5,
        timestamp_ms=int(now.timestamp() * 1000),
    )

    bd, reasons, penalties, conf, _ = evaluator.evaluate(sig, buf, "M5")
    # Must flag invalid FVG and NOT fabricate c1.range * 0.6!
    assert any("gap = 0.0" in p for p in penalties)
    assert bd.pattern_quality <= 60.0


# ---------------------------------------------------------------------
# 11. Dynamic Confidence Reflects Data Sufficiency (Never a Hardcoded Constant)
# ---------------------------------------------------------------------
def test_dynamic_confidence_calculation():
    evaluator = get_evaluator_for_pattern(11)

    # 1. Very few bars (< 3)
    c_scarce = evaluator.calculate_dynamic_confidence(closed_candle_count=2, required_bars=15)
    assert c_scarce == 0.20

    # 2. Moderate bars (7 bars)
    c_moderate = evaluator.calculate_dynamic_confidence(closed_candle_count=7, required_bars=15)
    assert 0.40 <= c_moderate <= 0.75

    # 3. Full bars (20 bars)
    c_full = evaluator.calculate_dynamic_confidence(closed_candle_count=20, required_bars=15)
    assert c_full >= 0.85

    # Values must vary dynamically with data count
    assert c_scarce < c_moderate < c_full


# ---------------------------------------------------------------------
# 12. Insufficient Data Produces INSUFFICIENT_DATA and Tier Caps
# ---------------------------------------------------------------------
def test_insufficient_data_produces_tier_cap():
    engine = GradingEngine()
    buf = MarketBuffer(active_timeframe="M5")

    # Buffer with only 2 candles (severely insufficient)
    now = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    buf.add_completed_candle(_make_closed_candle("M5", now - timedelta(minutes=5), 2750.0, 2752.0, 2749.0, 2751.0))
    buf.add_completed_candle(_make_closed_candle("M5", now, 2751.0, 2753.0, 2750.0, 2752.5))

    sig = EntrySignal(
        pattern_id=11,
        family_name="CHoCH",
        direction=SignalDirection.BUY,
        reference_price=2750.0,
        trigger_price=2752.5,
        timestamp_ms=int(now.timestamp() * 1000),
    )

    res = engine.grade_signal(sig, buf, "M5")
    assert res.data_sufficiency == DataSufficiencyStatus.INSUFFICIENT_DATA.value
    # Tier must be capped to C or D; never SSS, SS, S, or A!
    assert res.tier in (GradeTier.C, GradeTier.D)
    assert any("INSUFFICIENT_DATA" in p for p in res.penalties)


# ---------------------------------------------------------------------
# 13. All 40 Strategy IDs Have Dedicated Evaluator Mapping
# ---------------------------------------------------------------------
def test_all_40_strategies_have_evaluator_mapping():
    for pid in range(1, 41):
        assert pid in EVALUATOR_MAPPING
        evaluator = get_evaluator_for_pattern(pid)
        assert evaluator is not None
        assert evaluator.pattern_id == pid


# ---------------------------------------------------------------------
# 14. Deterministic Scoring for Identical Snapshot Input
# ---------------------------------------------------------------------
def test_deterministic_scoring():
    engine = GradingEngine()
    buf1 = MarketBuffer(active_timeframe="M5")
    buf2 = MarketBuffer(active_timeframe="M5")

    t_now = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    _populate_buffer(buf1, "M5", count=20, end_dt=t_now)
    _populate_buffer(buf2, "M5", count=20, end_dt=t_now)

    sig1 = EntrySignal(
        pattern_id=1, family_name="Reversal", direction=SignalDirection.BUY,
        reference_price=2750.0, trigger_price=2752.0, timestamp_ms=int(t_now.timestamp() * 1000),
        invalidation_price=2748.0,
    )
    sig2 = EntrySignal(
        pattern_id=1, family_name="Reversal", direction=SignalDirection.BUY,
        reference_price=2750.0, trigger_price=2752.0, timestamp_ms=int(t_now.timestamp() * 1000),
        invalidation_price=2748.0,
    )

    res1 = engine.grade_signal(sig1, buf1, "M5")
    res2 = engine.grade_signal(sig2, buf2, "M5")

    assert res1.score == res2.score
    assert res1.tier == res2.tier
    assert res1.confidence == res2.confidence
    assert res1.breakdown.to_dict() == res2.breakdown.to_dict()


# ---------------------------------------------------------------------
# 15. Historical Validation Foundation & NOT VALIDATED Labels
# ---------------------------------------------------------------------
def test_historical_validation_foundation_and_unvalidated_label():
    engine = GradingEngine()
    buf = MarketBuffer(active_timeframe="M5")
    t_now = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    _populate_buffer(buf, "M5", count=20, end_dt=t_now)

    sig = EntrySignal(
        pattern_id=11, family_name="CHoCH", direction=SignalDirection.BUY,
        reference_price=2750.0, trigger_price=2752.0, timestamp_ms=int(t_now.timestamp() * 1000),
    )
    res = engine.grade_signal(sig, buf, "M5")

    # Newly graded signal MUST carry validation_status = 'NOT VALIDATED'
    assert res.validation_status == "NOT VALIDATED"
    assert getattr(sig, "grade_validation_status") == "NOT VALIDATED"

    # Test historical validator metrics calculation
    validator = HistoricalTierValidator(is_out_of_sample=True)
    sample_outcomes = [
        {"r_multiple": 2.5, "is_win": True, "mae": 0.5, "mfe": 2.8},
        {"r_multiple": -1.0, "is_win": False, "mae": 1.2, "mfe": 0.3},
        {"r_multiple": 3.0, "is_win": True, "mae": 0.4, "mfe": 3.5},
    ]
    metrics = validator.evaluate_signals(strategy_id=11, timeframe="M5", tier="SSS", signals_with_outcomes=sample_outcomes)

    assert metrics.signal_count == 3
    assert metrics.win_count == 2
    assert metrics.loss_count == 1
    assert round(metrics.win_rate, 1) == 66.7
    assert metrics.expectancy > 0.0
    # Because n < 30, it is properly labeled as insufficient sample
    assert "NOT VALIDATED" in metrics.validation_status
