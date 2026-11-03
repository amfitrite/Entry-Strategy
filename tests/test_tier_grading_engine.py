"""Comprehensive unit and integration test suite for Strategy Tier Grading Engine."""
import time
from datetime import datetime
import pytest
from typing import List
from entrystrategy.core.models import (
    EntrySignal,
    SignalDirection,
    SignalStatus,
    PatternRole,
    Candle,
    TickData,
)
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.core.persistence import save_session_state, load_session_state
from entrystrategy.engine.grading import (
    GradingEngine,
    GradeTier,
    GradingWeights,
    ComponentBreakdown,
    EVALUATOR_MAPPING,
    get_evaluator_for_pattern,
    TIER_THRESHOLDS,
    TIER_GATING,
)


def _make_closed_candle(
    timeframe: str,
    open_px: float,
    high_px: float,
    low_px: float,
    close_px: float,
    ts_ms: int,
    is_closed: bool = True,
) -> Candle:
    dt = datetime.fromtimestamp(ts_ms / 1000.0)
    return Candle(
        timestamp=dt,
        open=open_px,
        high=high_px,
        low=low_px,
        close=close_px,
        spread=0.25,
        timeframe=timeframe,
        is_closed=is_closed,
    )


def _populate_test_buffer(buffer: MarketBuffer, tf: str, count: int = 20, trend: str = "bullish"):
    base_px = 2750.0
    now_ms = int(time.time() * 1000)
    for i in range(count):
        # i=0 is oldest candle, i=count-1 is newest candle (candles[0])
        dist_from_end = count - 1 - i
        if trend == "bullish":
            px = base_px - (dist_from_end * 0.8)
            open_px = px - 0.4
            close_px = px + 0.4
        else:
            px = base_px + (dist_from_end * 0.8)
            open_px = px + 0.4
            close_px = px - 0.4

        c = _make_closed_candle(
            timeframe=tf,
            open_px=open_px,
            high_px=max(open_px, close_px) + 0.5,
            low_px=min(open_px, close_px) - 0.5,
            close_px=close_px,
            ts_ms=now_ms - (dist_from_end * 60_000),
            is_closed=True,
        )
        buffer.add_completed_candle(c)


# ---------------------------------------------------------------------
# 1. All 40 strategies have dedicated evaluators
# ---------------------------------------------------------------------
def test_all_40_strategies_have_evaluators():
    for pid in range(1, 41):
        assert pid in EVALUATOR_MAPPING, f"Pattern #{pid} missing from EVALUATOR_MAPPING"
        evaluator = get_evaluator_for_pattern(pid, f"Pattern_{pid}")
        assert evaluator is not None
        assert evaluator.pattern_id == pid


# ---------------------------------------------------------------------
# 2. Score bounds 0.0 - 100.0
# ---------------------------------------------------------------------
def test_score_bounds_and_breakdown():
    engine = GradingEngine()
    buffer = MarketBuffer(active_timeframe="M5")
    _populate_test_buffer(buffer, "M5", 20, "bullish")

    for pid in range(1, 41):
        sig = EntrySignal(
            pattern_id=pid,
            family_name=f"Strategy_{pid}",
            direction=SignalDirection.BUY,
            reference_price=2750.0,
            trigger_price=2752.0,
            timestamp_ms=int(time.time() * 1000),
            invalidation_price=2748.0,
        )
        res = engine.grade_signal(sig, buffer, "M5")
        assert 0.0 <= res.score <= 100.0
        bd = res.breakdown
        assert 0.0 <= bd.pattern_quality <= 100.0
        assert 0.0 <= bd.market_structure <= 100.0
        assert 0.0 <= bd.location_quality <= 100.0
        assert 0.0 <= bd.candle_confirmation <= 100.0
        assert 0.0 <= bd.execution_quality <= 100.0


# ---------------------------------------------------------------------
# 3. Score to Tier conversion mapping
# ---------------------------------------------------------------------
def test_tier_mapping_correctness():
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
# 4. Dynamic grading: Same strategy can produce different grades
# ---------------------------------------------------------------------
def test_single_strategy_dynamic_different_grades():
    engine = GradingEngine()
    
    # Setup A: Strong alignment, great displacement, discount location
    buf_good = MarketBuffer(active_timeframe="M5")
    _populate_test_buffer(buf_good, "M5", 25, "bullish")
    sig_good = EntrySignal(
        pattern_id=11,  # CHoCH
        family_name="CHoCH",
        direction=SignalDirection.BUY,
        reference_price=2745.0,
        trigger_price=2752.0,
        timestamp_ms=int(time.time() * 1000),
        invalidation_price=2746.0,
        metrics={"displacement_pts": 3.5},
    )
    res_good = engine.grade_signal(sig_good, buf_good, "M5")

    # Setup B: Counter-trend, marginal break, tight invalidation
    buf_poor = MarketBuffer(active_timeframe="M5")
    _populate_test_buffer(buf_poor, "M5", 25, "bearish")
    sig_poor = EntrySignal(
        pattern_id=11,  # CHoCH
        family_name="CHoCH",
        direction=SignalDirection.BUY,
        reference_price=2750.0,
        trigger_price=2750.02,  # barely touching
        timestamp_ms=int(time.time() * 1000),
        invalidation_price=2750.01,  # 0.01 pts away
    )
    res_poor = engine.grade_signal(sig_poor, buf_poor, "M5")

    assert res_good.score > res_poor.score
    assert res_good.tier != res_poor.tier, f"Expected different tiers, got {res_good.tier} and {res_poor.tier}"


# ---------------------------------------------------------------------
# 5. Independent evaluation across M1, M5, and M15
# ---------------------------------------------------------------------
def test_timeframe_independence_m1_m5_m15():
    engine = GradingEngine()
    buf = MarketBuffer(default_timeframe="M5")
    
    # Populate M1 as bullish, M5 as neutral, M15 as bearish
    _populate_test_buffer(buf, "M1", 20, "bullish")
    _populate_test_buffer(buf, "M5", 20, "bearish")
    _populate_test_buffer(buf, "M15", 15, "bullish")

    sig_m1 = EntrySignal(
        pattern_id=12, family_name="BOS", direction=SignalDirection.BUY,
        reference_price=2748.0, trigger_price=2751.0, timestamp_ms=int(time.time() * 1000),
    )
    sig_m5 = EntrySignal(
        pattern_id=12, family_name="BOS", direction=SignalDirection.BUY,
        reference_price=2748.0, trigger_price=2751.0, timestamp_ms=int(time.time() * 1000),
    )
    sig_m15 = EntrySignal(
        pattern_id=12, family_name="BOS", direction=SignalDirection.BUY,
        reference_price=2748.0, trigger_price=2751.0, timestamp_ms=int(time.time() * 1000),
    )

    res_m1 = engine.grade_signal(sig_m1, buf, "M1")
    res_m5 = engine.grade_signal(sig_m5, buf, "M5")
    res_m15 = engine.grade_signal(sig_m15, buf, "M15")

    assert res_m1.timeframe == "M1"
    assert res_m5.timeframe == "M5"
    assert res_m15.timeframe == "M15"
    # M1 and M5 should differ because M1 buffer is bullish and M5 is bearish
    assert res_m1.score != res_m5.score


# ---------------------------------------------------------------------
# 6. Missing data does not automatically grant high tier
# ---------------------------------------------------------------------
def test_missing_data_handling_and_penalties():
    engine = GradingEngine()
    empty_buf = MarketBuffer(active_timeframe="M5")  # zero candles
    sig = EntrySignal(
        pattern_id=7, family_name="Breakout", direction=SignalDirection.BUY,
        reference_price=2750.0, trigger_price=2752.0, timestamp_ms=int(time.time() * 1000),
    )
    res = engine.grade_signal(sig, empty_buf, "M5")
    assert res.confidence < 0.60
    assert res.tier not in (GradeTier.SSS, GradeTier.SS)
    assert any("terbatas" in p.lower() or "tidak mencukupi" in p.lower() or "tidak ada" in p.lower() for p in res.penalties)


# ---------------------------------------------------------------------
# 7. Critical contradiction caps the grade
# ---------------------------------------------------------------------
def test_critical_contradiction_capping():
    engine = GradingEngine()
    buf = MarketBuffer(active_timeframe="M5")
    # Massive downtrend
    _populate_test_buffer(buf, "M5", 25, "bearish")
    
    # Check that latest candles are at the bottom of the range
    candles = buf.get_recent_candles(20, "M5")
    c0 = candles[0]
    
    # BUY signal at the bottom of a heavy downtrend without reversal structure
    sig = EntrySignal(
        pattern_id=1, family_name="Candlestick Reversal", direction=SignalDirection.BUY,
        reference_price=2750.0, trigger_price=c0.close, timestamp_ms=int(time.time() * 1000),
        invalidation_price=c0.close - 2.0,
    )
    res = engine.grade_signal(sig, buf, "M5")
    # Severe structural conflict caps tier to B or lower
    assert res.tier in (GradeTier.B, GradeTier.C, GradeTier.D)
    assert any("CRITICAL" in p or "kontradiksi" in p.lower() for p in res.penalties)


# ---------------------------------------------------------------------
# 8. SSS Gating rules: Minimum requirements enforcement
# ---------------------------------------------------------------------
def test_sss_gating_rules_prerequisites():
    engine = GradingEngine()
    buf = MarketBuffer(active_timeframe="M5")
    _populate_test_buffer(buf, "M5", 25, "bullish")
    
    sig = EntrySignal(
        pattern_id=11, family_name="CHoCH", direction=SignalDirection.BUY,
        reference_price=2750.0, trigger_price=2752.0, timestamp_ms=int(time.time() * 1000),
    )
    evaluator = get_evaluator_for_pattern(11)
    breakdown, reasons, penalties, conf, crit = evaluator.evaluate(sig, buf, "M5")
    
    # Set raw score >= 95 (100*0.30 + 100*0.20 + 100*0.20 + 75*0.15 + 100*0.15 = 96.25 >= 95.0),
    # but candle confirmation = 75.0 (< 85.0 minimum requirement for SSS)
    breakdown.pattern_quality = 100.0
    breakdown.market_structure = 100.0
    breakdown.location_quality = 100.0
    breakdown.candle_confirmation = 75.0  # Fails 85 min threshold!
    breakdown.execution_quality = 100.0
    
    original_cls = EVALUATOR_MAPPING[11]
    class MockEvaluator(original_cls):
        def evaluate(self, s, b, tf):
            return breakdown, reasons, penalties, 0.95, False

    EVALUATOR_MAPPING[11] = MockEvaluator
    try:
        res = engine.grade_signal(sig, buf, "M5")
        # Should be gated from SSS to SS because CC < 85!
        assert res.tier == GradeTier.SS
        assert res.capped_reason is not None
        assert "Candle Confirmation" in res.capped_reason
    finally:
        EVALUATOR_MAPPING[11] = original_cls


# ---------------------------------------------------------------------
# 9. No look-ahead bias & 10. Unclosed candles ignored
# ---------------------------------------------------------------------
def test_unclosed_candles_strictly_ignored():
    buf = MarketBuffer(active_timeframe="M5")
    _populate_test_buffer(buf, "M5", 10, "bullish")
    
    # Add an unclosed candle with wild prices
    unclosed = _make_closed_candle(
        timeframe="M5", open_px=3000.0, high_px=3500.0, low_px=2900.0, close_px=3400.0,
        ts_ms=int(time.time() * 1000), is_closed=False,
    )
    buf.add_completed_candle(unclosed)

    evaluator = get_evaluator_for_pattern(11)
    closed = evaluator.get_closed_candles(buf, "M5", 20)
    # The unclosed candle must NOT appear in closed candles
    for c in closed:
        assert c.is_closed is True
        assert c.close < 3000.0


# ---------------------------------------------------------------------
# 11. Backward compatibility of EntrySignal to_dict and from_dict
# ---------------------------------------------------------------------
def test_entrysignal_to_from_dict_compatibility():
    old_data = {
        "pattern_id": 15,
        "family_name": "FVG",
        "direction": "BUY",
        "reference_price": 2750.0,
        "trigger_price": 2751.5,
        "timestamp_ms": 1730612345000,
        "pattern_role": "ENTRY",
    }
    sig = EntrySignal.from_dict(old_data)
    assert sig.grade is None
    assert sig.grade_score is None

    # Serialization must include grading keys with backward-compatible defaults
    d = sig.to_dict()
    assert "grade" in d
    assert "grade_score" in d
    assert "grade_breakdown" in d
    assert "grade_reasons" in d
    assert "grade_penalties" in d


# ---------------------------------------------------------------------
# 12. Session persistence preserves grading fields
# ---------------------------------------------------------------------
def test_session_persistence_preserves_grade(tmp_path):
    sig = EntrySignal(
        pattern_id=14,
        family_name="Breakout Retest",
        direction=SignalDirection.SELL,
        reference_price=2755.0,
        trigger_price=2754.0,
        timestamp_ms=int(time.time() * 1000),
        invalidation_price=2757.0,
        grade="SS",
        grade_score=92.5,
        grade_confidence=0.92,
        grade_timeframe="M15",
        grade_version="1.0.0",
        grade_breakdown={"pattern_quality": 94.0, "market_structure": 90.0, "location_quality": 92.0, "candle_confirmation": 91.0, "execution_quality": 95.0},
        grade_reasons=["+ Strong retest hold", "+ Clean displacement"],
        grade_penalties=[],
    )

    state_file = tmp_path / "test_user_state.json"
    session_data = {
        "recent_signals": [sig.to_dict()],
    }
    assert save_session_state(session_data, state_file) is True

    loaded = load_session_state(state_file)
    assert loaded is not None
    sig_reconstructed = EntrySignal.from_dict(loaded["recent_signals"][0])
    assert sig_reconstructed.grade == "SS"
    assert sig_reconstructed.grade_score == 92.5
    assert sig_reconstructed.grade_timeframe == "M15"
    assert sig_reconstructed.grade_breakdown["pattern_quality"] == 94.0
    assert len(sig_reconstructed.grade_reasons) == 2


# ---------------------------------------------------------------------
# 13. Lifecycle unaltered by grading
# ---------------------------------------------------------------------
def test_lifecycle_unaltered_by_grading():
    engine = GradingEngine()
    buf = MarketBuffer(active_timeframe="M5")
    _populate_test_buffer(buf, "M5", 15, "bullish")

    sig = EntrySignal(
        pattern_id=1, family_name="Candlestick Reversal", direction=SignalDirection.BUY,
        reference_price=2750.0, trigger_price=2750.0, timestamp_ms=int(time.time() * 1000),
        invalidation_price=2748.0,
    )
    engine.grade_signal(sig, buf, "M5")
    assert sig.status == SignalStatus.ACTIVE

    # Confirmation test: Price surges above trigger
    now_ms = sig.timestamp_ms + 1000
    changed = sig.update_lifecycle(current_price=2751.5, current_ts_ms=now_ms, spread=0.25, confirmation_threshold=0.20)
    assert changed is True
    assert sig.status == SignalStatus.CONFIRMED

    # Invalidation test
    sig2 = EntrySignal(
        pattern_id=1, family_name="Candlestick Reversal", direction=SignalDirection.BUY,
        reference_price=2750.0, trigger_price=2750.0, timestamp_ms=int(time.time() * 1000),
        invalidation_price=2748.0,
    )
    engine.grade_signal(sig2, buf, "M5")
    changed2 = sig2.update_lifecycle(current_price=2747.5, current_ts_ms=now_ms)
    assert changed2 is True
    assert sig2.status == SignalStatus.INVALIDATED


# ---------------------------------------------------------------------
# 14. Trigger & Entry prices never altered by grading
# ---------------------------------------------------------------------
def test_prices_never_altered_by_grading():
    engine = GradingEngine()
    buf = MarketBuffer(active_timeframe="M5")
    _populate_test_buffer(buf, "M5", 15, "bullish")

    orig_trig = 2750.85
    orig_ref = 2749.20
    orig_exec = 2751.10
    orig_inval = 2747.50

    sig = EntrySignal(
        pattern_id=20, family_name="Volatility Burst", direction=SignalDirection.BUY,
        reference_price=orig_ref, trigger_price=orig_trig, timestamp_ms=int(time.time() * 1000),
        execution_price=orig_exec, invalidation_price=orig_inval,
    )
    engine.grade_signal(sig, buf, "M5")

    assert sig.trigger_price == orig_trig
    assert sig.reference_price == orig_ref
    assert sig.execution_price == orig_exec
    assert sig.invalidation_price == orig_inval


# ---------------------------------------------------------------------
# 15. No tick dependency on grading
# ---------------------------------------------------------------------
def test_no_tick_dependency():
    engine = GradingEngine()
    buf_no_ticks = MarketBuffer(active_timeframe="M5")
    buf_with_ticks = MarketBuffer(active_timeframe="M5")

    _populate_test_buffer(buf_no_ticks, "M5", 20, "bullish")
    _populate_test_buffer(buf_with_ticks, "M5", 20, "bullish")

    now_ms = int(time.time() * 1000)
    for i in range(10):
        buf_with_ticks.add_tick(TickData(ts_ms=now_ms, bid=2750.0 + (i * 0.1), ask=2750.25 + (i * 0.1)))

    sig1 = EntrySignal(
        pattern_id=13, family_name="Candle Displacement", direction=SignalDirection.BUY,
        reference_price=2748.0, trigger_price=2752.0, timestamp_ms=now_ms, invalidation_price=2746.0,
    )
    sig2 = EntrySignal(
        pattern_id=13, family_name="Candle Displacement", direction=SignalDirection.BUY,
        reference_price=2748.0, trigger_price=2752.0, timestamp_ms=now_ms, invalidation_price=2746.0,
    )

    res1 = engine.grade_signal(sig1, buf_no_ticks, "M5")
    res2 = engine.grade_signal(sig2, buf_with_ticks, "M5")

    # Score and breakdown must be identical regardless of ticks
    assert res1.score == res2.score
    assert res1.breakdown.to_dict() == res2.breakdown.to_dict()


# ---------------------------------------------------------------------
# 16. Multi-Timeframe (MTF) Context strictly uses closed candles
# ---------------------------------------------------------------------
def test_mtf_context_uses_only_closed_candles():
    engine = GradingEngine()
    buf = MarketBuffer(active_timeframe="M1")
    _populate_test_buffer(buf, "M1", 20, "bullish")
    _populate_test_buffer(buf, "M5", 10, "bullish")
    _populate_test_buffer(buf, "M15", 8, "bullish")

    evaluator = get_evaluator_for_pattern(11)
    score, reasons, penalties = evaluator.evaluate_mtf_confluence(buf, "M1", SignalDirection.BUY)
    assert score >= 80.0
    assert any("M5" in r and "closed" in r for r in reasons)
    assert any("M15" in r and "closed" in r for r in reasons)


# ---------------------------------------------------------------------
# 17. All 40 strategies evaluate cleanly on M1, M5, and M15 (120 combos)
# ---------------------------------------------------------------------
def test_all_40_evaluators_run_on_m1_m5_m15():
    engine = GradingEngine()
    buf = MarketBuffer(active_timeframe="M5")
    _populate_test_buffer(buf, "M1", 20, "bullish")
    _populate_test_buffer(buf, "M5", 20, "bullish")
    _populate_test_buffer(buf, "M15", 15, "bullish")

    for tf in ("M1", "M5", "M15"):
        for pid in range(1, 41):
            sig = EntrySignal(
                pattern_id=pid,
                family_name=f"Strategy_{pid}",
                direction=SignalDirection.BUY if pid % 2 == 1 else SignalDirection.SELL,
                reference_price=2750.0,
                trigger_price=2752.0 if pid % 2 == 1 else 2748.0,
                timestamp_ms=int(time.time() * 1000),
                invalidation_price=2747.0 if pid % 2 == 1 else 2753.0,
            )
            res = engine.grade_signal(sig, buf, tf)
            assert res is not None
            assert res.timeframe == tf
            assert res.tier in (GradeTier.SSS, GradeTier.SS, GradeTier.S, GradeTier.A, GradeTier.B, GradeTier.C, GradeTier.D)
            assert 0.0 <= res.score <= 100.0
