"""Core Tier Grading Engine coordinating evaluators, gating rules, and signal attribution."""
from typing import Optional, List
from entrystrategy.core.models import EntrySignal
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.engine.grading.models import (
    GradeTier,
    GradingWeights,
    ComponentBreakdown,
    GradingResult,
)
from entrystrategy.engine.grading.evaluators import get_evaluator_for_pattern
from entrystrategy.engine.grading.thresholds import TIER_GATING


class GradingEngine:
    """Evaluates EntrySignals post-trigger across M1, M5, and M15 timeframes."""

    def __init__(self, weights: Optional[GradingWeights] = None, version: str = "1.0.0"):
        self.weights = weights or GradingWeights()
        self.version = version

    def grade_signal(
        self,
        signal: EntrySignal,
        buffer: MarketBuffer,
        timeframe: Optional[str] = None,
    ) -> GradingResult:
        """Grades an EntrySignal dynamically based on closed-candle conditions.
        Enforces tier gating and writes grade attributes to the signal.
        """
        tf = (timeframe or buffer.active_timeframe or "M5").upper()
        evaluator = get_evaluator_for_pattern(signal.pattern_id, signal.family_name)

        breakdown, reasons, penalties, confidence, has_critical = evaluator.evaluate(
            signal, buffer, tf
        )

        raw_score = breakdown.calculate_total_score(self.weights)
        capped_reason: Optional[str] = None
        tier = GradeTier.from_score(raw_score)

        # -------------------------------------------------------------
        # High Tier Gating Rules (Strict criteria beyond total score)
        # -------------------------------------------------------------
        # 1. Critical Contradiction Gate: Severe structural conflict caps tier to B max
        if has_critical:
            if raw_score >= 75.0:
                tier = GradeTier.B
                raw_score = min(raw_score, 74.5)
                capped_reason = "Grade dibatasi ke B karena terdapat kontradiksi struktural kritis"
                penalties.append(f"GATING: {capped_reason}")

        # 2. SSS Gating Rules
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

        # 3. SS Gating Rules
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

        # 4. S Gating Rules
        elif tier == GradeTier.S:
            gate = TIER_GATING["S"]
            min_floor = gate["min_component_floor"]
            low_components = [
                k for k, v in breakdown.to_dict().items() if v < min_floor
            ]
            if low_components:
                tier = GradeTier.A
                raw_score = min(raw_score, 84.0)
                capped_reason = f"Diturunkan dari S ke A: Komponen di bawah batas 50 ({', '.join(low_components)})"
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

        return result
