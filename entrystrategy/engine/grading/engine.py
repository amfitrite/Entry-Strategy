"""Core Tier Grading Engine coordinating evaluators, gating rules, and signal attribution."""
from typing import Optional, List
from entrystrategy.core.models import EntrySignal
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.engine.grading.models import (
    GradeTier,
    GradingWeights,
    ComponentBreakdown,
    GradingResult,
    DataSufficiencyStatus,
)
from entrystrategy.engine.grading.evaluators import get_evaluator_for_pattern
from entrystrategy.engine.grading.thresholds import TIER_GATING


class GradingEngine:
    """Evaluates EntrySignals post-trigger across M1, M5, and M15 timeframes.

    Strictly adheres to:
    - Zero look-ahead bias (evaluates at signal.timestamp_ms snapshot).
    - Closed-candle-only data.
    - Explicit missing data handling and normalized effective weighting.
    - Prerequisites and gating rules for SSS, SS, and S tiers.
    - Transparent validation labeling ('NOT VALIDATED' until tested out-of-sample).
    """

    def __init__(self, weights: Optional[GradingWeights] = None, version: str = "2.0.0"):
        self.weights = weights or GradingWeights()
        self.version = version

    def grade_signal(
        self,
        signal: EntrySignal,
        buffer: MarketBuffer,
        timeframe: Optional[str] = None,
    ) -> GradingResult:
        """Grades an EntrySignal dynamically based strictly on closed-candle conditions.
        Enforces tier gating, missing-data normalization, and writes grade attributes to the signal.
        """
        tf = (timeframe or buffer.active_timeframe or "M5").upper()
        evaluator = get_evaluator_for_pattern(signal.pattern_id, signal.family_name)

        # Snapshot timestamp strictly from signal (prevents future candle leakage)
        snapshot_ts = signal.timestamp_ms

        try:
            breakdown, reasons, penalties, confidence, has_critical = evaluator.evaluate(
                signal, buffer, tf, snapshot_ts
            )
        except TypeError:
            breakdown, reasons, penalties, confidence, has_critical = evaluator.evaluate(
                signal, buffer, tf
            )

        raw_score, effective_weight_sum, effective_weights, is_insufficient = (
            breakdown.calculate_normalized_score(self.weights)
        )
        capped_reason: Optional[str] = None
        data_sufficiency = (
            DataSufficiencyStatus.INSUFFICIENT_DATA.value
            if (is_insufficient or confidence < 0.35 or breakdown.available_components < 3)
            else DataSufficiencyStatus.SUFFICIENT.value
        )

        tier = GradeTier.from_score(raw_score)

        # -------------------------------------------------------------
        # 1. Insufficient Data Gate: Never allow High Tiers without sufficient data
        # -------------------------------------------------------------
        if data_sufficiency == DataSufficiencyStatus.INSUFFICIENT_DATA.value:
            penalties.append("DATA_GATE: Kelengkapan data tidak mencukupi untuk penilaian penuh (INSUFFICIENT_DATA)")
            if tier in (GradeTier.SSS, GradeTier.SS, GradeTier.S, GradeTier.A):
                tier = GradeTier.C if raw_score >= 50.0 else GradeTier.D
                raw_score = min(raw_score, 64.0 if tier == GradeTier.C else 49.0)
                capped_reason = "Grade dibatasi karena kelengkapan/kecukupan data tidak memadai (INSUFFICIENT_DATA)"
                penalties.append(f"DATA_GATE: {capped_reason}")

        # -------------------------------------------------------------
        # 2. Critical Contradiction Gate: Severe structural conflict caps tier to B max
        # -------------------------------------------------------------
        elif has_critical:
            if raw_score >= 75.0:
                tier = GradeTier.B
                raw_score = min(raw_score, 74.5)
                capped_reason = "Grade dibatasi ke B karena terdapat kontradiksi struktural kritis"
                penalties.append(f"GATING: {capped_reason}")

        # -------------------------------------------------------------
        # 3. High Tier Gating Rules (Strict criteria beyond total score)
        # -------------------------------------------------------------
        elif tier == GradeTier.SSS:
            gate = TIER_GATING["SSS"]
            reasons_fail: List[str] = []
            if breakdown.pattern_quality < gate["min_pattern_quality"]:
                reasons_fail.append(f"Pattern Quality ({breakdown.pattern_quality:.1f} < {gate['min_pattern_quality']})")
            if breakdown.market_structure < gate["min_market_structure"]:
                reasons_fail.append(f"Market Structure ({breakdown.market_structure:.1f} < {gate['min_market_structure']})")
            if breakdown.candle_confirmation < gate["min_candle_confirmation"]:
                reasons_fail.append(f"Candle Confirmation ({breakdown.candle_confirmation:.1f} < {gate['min_candle_confirmation']})")
            if breakdown.execution_quality < gate["min_execution_quality"]:
                reasons_fail.append(f"Execution Quality ({breakdown.execution_quality:.1f} < {gate['min_execution_quality']})")
            if confidence < gate["min_confidence"]:
                reasons_fail.append(f"Data sufficiency/confidence ({confidence:.2f} < {gate['min_confidence']})")

            if reasons_fail:
                tier = GradeTier.SS
                raw_score = min(raw_score, 94.0)
                capped_reason = f"Diturunkan dari SSS ke SS: {', '.join(reasons_fail)}"
                penalties.append(f"GATING: {capped_reason}")

        elif tier == GradeTier.SS:
            gate = TIER_GATING["SS"]
            min_floor = gate["min_component_floor"]
            low_components = [
                k for k, v in breakdown.to_dict().items() if v < min_floor
            ]
            if low_components or confidence < gate["min_confidence"]:
                tier = GradeTier.S
                raw_score = min(raw_score, 89.0)
                capped_reason = f"Diturunkan dari SS ke S: Komponen di bawah ambang minimal ({', '.join(low_components)})"
                penalties.append(f"GATING: {capped_reason}")

        elif tier == GradeTier.S:
            gate = TIER_GATING["S"]
            min_floor = gate["min_component_floor"]
            low_components = [
                k for k, v in breakdown.to_dict().items() if v < min_floor
            ]
            if low_components or confidence < gate["min_confidence"]:
                tier = GradeTier.A
                raw_score = min(raw_score, 84.0)
                capped_reason = f"Diturunkan dari S ke A: Komponen di bawah batas minimal ({', '.join(low_components)})"
                penalties.append(f"GATING: {capped_reason}")

        # Final result creation
        result = GradingResult(
            tier=tier,
            score=round(raw_score, 2),
            confidence=round(confidence, 2),
            timeframe=tf,
            version=self.version,
            breakdown=breakdown,
            reasons=reasons,
            penalties=penalties,
            capped_reason=capped_reason,
            data_sufficiency=data_sufficiency,
            effective_weights=effective_weights,
            validation_status="NOT VALIDATED",  # Transparent empirical label per requirement 12
        )

        # Attach seamlessly to EntrySignal for downstream consumers
        signal.grade = result.tier.value
        signal.grade_score = result.score
        signal.grade_confidence = result.confidence
        signal.grade_timeframe = result.timeframe
        signal.grade_version = result.version
        signal.grade_breakdown = result.breakdown.to_dict()
        signal.grade_reasons = result.reasons
        signal.grade_penalties = result.penalties
        setattr(signal, "grade_data_sufficiency", result.data_sufficiency)
        setattr(signal, "grade_effective_weights", result.effective_weights)
        setattr(signal, "grade_validation_status", result.validation_status)

        return result
