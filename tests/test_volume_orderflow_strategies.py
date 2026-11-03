"""Automated Verification Suite for Volume & Order Flow Entry Strategy Families (41 - 56)."""
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
from entrystrategy.engine.registry import PatternRegistry
from entrystrategy.engine.grading import (
    GradingEngine,
    GradeTier,
    EVALUATOR_MAPPING,
    get_evaluator_for_pattern,
)
from entrystrategy.engine.volume_analytics import (
    calculate_rvol_and_zscore,
    estimate_candle_delta,
    calculate_cvd_series,
    calculate_volume_profile,
    calculate_footprint_imbalance,
)


def _make_candle(
    timeframe: str,
    timestamp: datetime,
    open_px: float,
    high_px: float,
    low_px: float,
    close_px: float,
    tick_volume: int = 100,
    is_closed: bool = True,
) -> Candle:
    return Candle(
        timestamp=timestamp,
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


def _populate_volume_buffer(
    buffer: MarketBuffer,
    timeframe: str,
    count: int = 25,
    base_volume: int = 100,
    base_price: float = 2750.0,
):
    step_minutes = 15 if timeframe == "M15" else (5 if timeframe == "M5" else 1)
    now = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(count, 0, -1):
        t = now - timedelta(minutes=i * step_minutes)
        c = _make_candle(
            timeframe=timeframe,
            timestamp=t,
            open_px=base_price,
            high_px=base_price + 1.0,
            low_px=base_price - 1.0,
            close_px=base_price + 0.2,
            tick_volume=base_volume,
            is_closed=True,
        )
        buffer.add_completed_candle(c)


# ---------------------------------------------------------------------
# 1. Registry Architecture & Backward Compatibility
# ---------------------------------------------------------------------
def test_registry_backward_compatibility_default_40():
    reg = PatternRegistry()
    assert len(reg.get_all_patterns()) == 40
    assert len(reg.get_price_action_patterns()) == 40
    assert len(reg.get_volume_patterns()) == 0


def test_registry_with_volume_strategies_contains_56():
    reg = PatternRegistry(include_volume_strategies=True)
    patterns = reg.get_all_patterns()
    assert len(patterns) == 56

    ids = [p.pattern_id for p in patterns]
    assert ids == list(range(1, 57))

    pa = reg.get_price_action_patterns()
    assert len(pa) == 40
    assert [p.pattern_id for p in pa] == list(range(1, 41))

    vol = reg.get_volume_patterns()
    assert len(vol) == 16
    assert [p.pattern_id for p in vol] == list(range(41, 57))


def test_registry_dynamic_enable_volume_strategies():
    reg = PatternRegistry()
    assert len(reg.get_all_patterns()) == 40
    reg.register_volume_orderflow_families()
    assert len(reg.get_all_patterns()) == 56
    assert reg.get_pattern(41) is not None
    assert reg.get_pattern(56) is not None


# ---------------------------------------------------------------------
# 2. No Duplicate Patterns & Unique Identification
# ---------------------------------------------------------------------
def test_volume_strategy_unique_names_and_ids():
    reg = PatternRegistry(include_volume_strategies=True)
    vol_patterns = reg.get_volume_patterns()
    assert len(vol_patterns) == 16

    names = [p.name for p in vol_patterns]
    assert len(names) == len(set(names)), "Found duplicate strategy names in volume families"

    ids = [p.pattern_id for p in vol_patterns]
    assert len(ids) == len(set(ids)), "Found duplicate strategy IDs in volume families"
    assert min(ids) == 41
    assert max(ids) == 56


# ---------------------------------------------------------------------
# 3. Data Integrity & Explicit Proxy Transparency Tags
# ---------------------------------------------------------------------
def test_volume_and_delta_proxy_transparency_tags():
    reg = PatternRegistry(include_volume_strategies=True)

    # Observed Tick Volume strategies
    observed_ids = [41, 42, 43, 44, 53, 54, 55, 56]
    for pid in observed_ids:
        pat = reg.get_pattern(pid)
        assert "[OBSERVED_TICK_VOLUME]" in pat.phenomenon or "[OBSERVED_TICK_VOLUME]" in pat.description

    # Estimated Delta Proxy strategies
    delta_ids = [45, 46, 47, 48, 49, 50]
    for pid in delta_ids:
        pat = reg.get_pattern(pid)
        assert "[ESTIMATED_DELTA_PROXY]" in pat.phenomenon or "[PROXY_ABSORPTION]" in pat.phenomenon

    # Footprint Proxy strategies
    footprint_ids = [51, 52]
    for pid in footprint_ids:
        pat = reg.get_pattern(pid)
        assert "[PROXY_PRICE_LEVEL_FOOTPRINT]" in pat.phenomenon


# ---------------------------------------------------------------------
# 4. Multi-Timeframe Independence (M1, M5, M15)
# ---------------------------------------------------------------------
@pytest.mark.parametrize("tf", ["M1", "M5", "M15"])
def test_pattern_41_rvol_triggers_per_timeframe(tf):
    buf = MarketBuffer(active_timeframe=tf)
    _populate_volume_buffer(buf, tf, count=25, base_volume=100, base_price=2750.0)

    # Add high-volume expansion candle
    now = datetime(2026, 11, 3, 10, 1, 0, tzinfo=timezone.utc)
    c_trigger = _make_candle(
        timeframe=tf,
        timestamp=now,
        open_px=2750.0,
        high_px=2756.0,
        low_px=2749.8,
        close_px=2755.5,
        tick_volume=350,  # RVOL = 3.5x
        is_closed=True,
    )
    buf.add_completed_candle(c_trigger)

    reg = PatternRegistry(include_volume_strategies=True)
    p41 = reg.get_pattern(41)
    sig = p41.check(buf)

    assert sig is not None
    assert sig.direction == SignalDirection.BUY
    assert any("[OBSERVED_TICK_VOLUME]" in r for r in sig.reasons)
    assert sig.metrics["rvol"] >= 2.0


# ---------------------------------------------------------------------
# 5. Closed-Candle Only & Strict Lookahead Bias Prevention
# ---------------------------------------------------------------------
def test_unclosed_candle_never_evaluated_by_volume_patterns():
    buf = MarketBuffer(active_timeframe="M5")
    _populate_volume_buffer(buf, "M5", count=25, base_volume=100)

    # Attempt to inject unclosed candle with extreme volume
    unclosed = _make_candle(
        timeframe="M5",
        timestamp=datetime.now(timezone.utc),
        open_px=2750.0,
        high_px=2770.0,
        low_px=2750.0,
        close_px=2769.0,
        tick_volume=5000,
        is_closed=False,  # Still forming!
    )
    buf.add_completed_candle(unclosed)

    # Buffer must filter it out
    candles = buf.get_recent_candles(10, timeframe="M5")
    assert all(c.is_closed for c in candles)
    assert not any(c.tick_volume == 5000 for c in candles)

    reg = PatternRegistry(include_volume_strategies=True)
    p41 = reg.get_pattern(41)
    sig = p41.check(buf)
    # Must NOT trigger on the unclosed candle
    assert sig is None


# ---------------------------------------------------------------------
# 6. Dedicated Evaluators and Tier Grading for All 16 Volume Strategies
# ---------------------------------------------------------------------
def test_all_16_volume_strategies_have_evaluators():
    for pid in range(41, 57):
        assert pid in EVALUATOR_MAPPING, f"Pattern #{pid} missing from EVALUATOR_MAPPING"
        evaluator = get_evaluator_for_pattern(pid, f"VolumeStrategy_{pid}")
        assert evaluator is not None
        assert evaluator.pattern_id == pid


@pytest.mark.parametrize("tf", ["M1", "M5", "M15"])
def test_all_16_volume_evaluators_grade_cleanly_on_all_timeframes(tf):
    engine = GradingEngine()
    buf = MarketBuffer(active_timeframe=tf)
    _populate_volume_buffer(buf, tf, count=25, base_volume=120, base_price=2750.0)

    recent = buf.get_recent_candles(1, tf)
    sig_ts = int(recent[0].timestamp.timestamp() * 1000) + 1000 if recent else int(time.time() * 1000)

    for pid in range(41, 57):
        sig = EntrySignal(
            pattern_id=pid,
            family_name=f"VolumeStrategy_{pid}",
            direction=SignalDirection.BUY if pid % 2 == 1 else SignalDirection.SELL,
            reference_price=2750.0,
            trigger_price=2753.0 if pid % 2 == 1 else 2747.0,
            timestamp_ms=sig_ts,
            invalidation_price=2746.0 if pid % 2 == 1 else 2754.0,
            metrics={"rvol": 2.5, "zscore": 2.6, "stacked_levels": 3},
        )
        res = engine.grade_signal(sig, buf, tf)
        assert res is not None
        assert res.timeframe == tf
        assert 0.0 <= res.score <= 100.0
        assert res.tier in (GradeTier.SSS, GradeTier.SS, GradeTier.S, GradeTier.A, GradeTier.B, GradeTier.C, GradeTier.D)
        # Verify proxy / observed integrity in reasons
        all_text = " ".join(res.reasons + res.penalties)
        if pid in (41, 42, 43, 44, 53, 54, 55, 56):
            assert "[OBSERVED_TICK_VOLUME]" in all_text or "volume" in all_text.lower()
        elif pid in (45, 46, 47, 50):
            assert "[ESTIMATED_DELTA_PROXY]" in all_text
        elif pid in (48, 49):
            assert "[PROXY_ABSORPTION]" in all_text or "[ESTIMATED_DELTA_PROXY]" in all_text
        elif pid in (51, 52):
            assert "[PROXY_PRICE_LEVEL_FOOTPRINT]" in all_text


# ---------------------------------------------------------------------
# 7. Volume Profile Analytics Correctness
# ---------------------------------------------------------------------
def test_volume_profile_poc_vah_val_calculation():
    now = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    candles = [
        _make_candle("M5", now - timedelta(minutes=15), 2750.0, 2755.0, 2748.0, 2752.0, 200),
        _make_candle("M5", now - timedelta(minutes=10), 2752.0, 2754.0, 2751.0, 2753.0, 300),
        _make_candle("M5", now - timedelta(minutes=5), 2753.0, 2756.0, 2752.0, 2755.0, 150),
    ]
    prof = calculate_volume_profile(candles, lookback=3, bin_size=0.25)

    assert prof["poc"] > 0.0
    assert prof["vah"] >= prof["poc"]
    assert prof["val"] <= prof["poc"]
    assert prof["vah"] >= prof["val"]
    assert prof["total_volume"] == 650


# ---------------------------------------------------------------------
# 8. Footprint Imbalance Decomposition Correctness
# ---------------------------------------------------------------------
def test_footprint_imbalance_diagonal_calculation():
    now = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    c = _make_candle("M5", now, 2750.0, 2754.0, 2750.0, 2753.5, 400)
    fp = calculate_footprint_imbalance(c, bin_size=0.25, imbalance_ratio=3.0)

    assert fp["total_levels"] > 0
    assert fp["imbalance_ratio_threshold"] == 3.0
    assert "stacked_buy_imbalances" in fp
    assert "stacked_sell_imbalances" in fp
    assert isinstance(fp["stacked_buy_imbalances"], list)
