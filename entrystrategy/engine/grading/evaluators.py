"""Strategy-Specific Evaluators for all 40 Entry Strategy Families."""
from typing import Dict, List, Optional, Tuple, Type
from entrystrategy.core.models import EntrySignal, SignalDirection, Candle
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.engine.grading.models import ComponentBreakdown, EvidenceCluster, EvidenceItem
from entrystrategy.engine.grading.base import BaseStrategyEvaluator
from entrystrategy.engine.grading.thresholds import get_timeframe_profile, calculate_atr
from entrystrategy.engine.volume_analytics import (
    calculate_rvol_and_zscore,
    calculate_volume_profile,
    calculate_footprint_imbalance,
    estimate_candle_delta,
)



# =====================================================================
# 1. STRUCTURE STRATEGY EVALUATORS (CHoCH, BOS, Swing Breaks)
# =====================================================================

class ChangeOfCharacterEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #11: CHoCH (Change of Character)."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=25)
        reasons: List[str] = []
        penalties: List[str] = []
        has_critical = False

        if len(candles) < 5:
            penalties.append("Data candle tidak mencukupi untuk evaluasi penuh CHoCH")
            return ComponentBreakdown(40, 40, 40, 40, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        atr = calculate_atr(candles, 14)
        is_buy = signal.direction == SignalDirection.BUY

        # 1. Pattern Quality (Displacement & Swing Break clearance)
        pq = 70.0
        ref_px = signal.reference_price
        clearance = (c0.close - ref_px) if is_buy else (ref_px - c0.close)
        
        if clearance > (atr * 0.4):
            pq += 18.0
            reasons.append(f"Breakout CHoCH bersih (+{clearance:.2f} pts di luar swing level)")
        elif clearance <= 0.05:
            pq -= 20.0
            penalties.append("Candle close nyaris tidak melewati level protected swing")

        body_atr_ratio = c0.body / max(0.01, atr)
        if body_atr_ratio >= 1.2:
            pq += 12.0
            reasons.append(f"Displacement kuat saat CHoCH ({body_atr_ratio:.1f}x ATR)")
        elif body_atr_ratio < 0.6:
            pq -= 15.0
            penalties.append("Displacement lemah saat menembus struktur")

        # 2. Market Structure & MTF
        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        mtf_score, mtf_r, mtf_p = self.evaluate_mtf_confluence(buffer, timeframe, signal.direction)
        ms = (ms_score * 0.7) + (mtf_score * 0.3)
        reasons.extend(ms_r)
        reasons.extend(mtf_r)
        penalties.extend(ms_p)
        penalties.extend(mtf_p)
        if ms_crit:
            has_critical = True

        # 3. Location Quality
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        reasons.extend(lq_r)
        penalties.extend(lq_p)

        # 4. Candle Confirmation
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        reasons.extend(cc_r)
        penalties.extend(cc_p)

        # 5. Execution Quality
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)
        reasons.extend(eq_r)
        penalties.extend(eq_p)

        confidence = 0.95 if len(candles) >= 15 else 0.70
        breakdown = ComponentBreakdown(pq, ms, lq, cc, eq)
        return breakdown, reasons, penalties, confidence, has_critical


class BreakOfStructureEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #12: BOS (Break of Structure)."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=25)
        reasons: List[str] = []
        penalties: List[str] = []
        has_critical = False

        if len(candles) < 5:
            penalties.append("Data candle tidak mencukupi untuk evaluasi BOS")
            return ComponentBreakdown(40, 40, 40, 40, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        atr = calculate_atr(candles, 14)
        is_buy = signal.direction == SignalDirection.BUY

        pq = 72.0
        ref_px = signal.reference_price
        clearance = (c0.close - ref_px) if is_buy else (ref_px - c0.close)
        
        if clearance > (atr * 0.35):
            pq += 18.0
            reasons.append(f"BOS terkonfirmasi dengan candle close jelas (+{clearance:.2f} pts)")
        else:
            pq -= 12.0
            penalties.append("Penembusan swing level marginal")

        if (is_buy and c0.is_bullish and c0.close > c0.open) or (not is_buy and c0.is_bearish and c0.close < c0.open):
            pq += 10.0
            reasons.append("Follow-through candle selaras dengan arah BOS")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        mtf_score, mtf_r, mtf_p = self.evaluate_mtf_confluence(buffer, timeframe, signal.direction)
        ms = (ms_score * 0.7) + (mtf_score * 0.3)
        reasons.extend(ms_r)
        reasons.extend(mtf_r)
        penalties.extend(ms_p)
        penalties.extend(mtf_p)
        if ms_crit:
            has_critical = True

        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        reasons.extend(lq_r)
        penalties.extend(lq_p)

        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        reasons.extend(cc_r)
        penalties.extend(cc_p)

        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)
        reasons.extend(eq_r)
        penalties.extend(eq_p)

        confidence = 0.95 if len(candles) >= 15 else 0.70
        breakdown = ComponentBreakdown(pq, ms, lq, cc, eq)
        return breakdown, reasons, penalties, confidence, has_critical


class MicroSwingBreakEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #33: Micro Swing Break."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=20)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 5:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        atr = calculate_atr(candles, 14)
        pq = 70.0
        ref_px = signal.reference_price
        is_buy = signal.direction == SignalDirection.BUY
        diff = (c0.close - ref_px) if is_buy else (ref_px - c0.close)

        if diff > (atr * 0.25):
            pq += 20.0
            reasons.append("Micro swing ditembus dengan decisive close")
        else:
            pq -= 15.0
            penalties.append("Breakout swing tipis berisiko false break")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.90, ms_crit


class MicroSwingFailureEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #34: Micro Swing Failure (SFP)."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=20)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 3:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        is_buy = signal.direction == SignalDirection.BUY
        pq = 75.0

        # Liquidity sweep evaluation
        wick_ratio = (c0.lower_wick / c0.range) if is_buy else (c0.upper_wick / c0.range)
        if wick_ratio >= 0.50:
            pq += 20.0
            reasons.append(f"Rejection tail dominan ({wick_ratio * 100:.0f}% dari total range)")
        elif wick_ratio < 0.30:
            pq -= 20.0
            penalties.append("Wick penolakan likuiditas kurang tajam (< 30%)")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.90, ms_crit


# =====================================================================
# 2. SMART MONEY / LIQUIDITY EVALUATORS (FVG, Displacement, OB, Sweep)
# =====================================================================

class FairValueGapEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #15: Fair Value Gap (FVG)."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=20)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 4:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c1 = candles[1]
        atr = calculate_atr(candles, 14)
        pq = 75.0
        
        # FVG width relative to ATR
        fvg_size = signal.metrics.get("fvg_size", c1.range * 0.6)
        size_ratio = fvg_size / max(0.01, atr)
        if size_ratio >= 0.6:
            pq += 18.0
            reasons.append(f"Ukuran FVG signifikan ({size_ratio:.1f}x ATR)")
        elif size_ratio < 0.25:
            pq -= 15.0
            penalties.append("Imbalance FVG sempit / rentan tertutup segera")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.92, ms_crit


class FairValueGapRetestEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #16: FVG Retest."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=20)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 4:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        is_buy = signal.direction == SignalDirection.BUY
        pq = 75.0

        # Retest reaction: rejection wick from FVG zone
        wick = c0.lower_wick if is_buy else c0.upper_wick
        if (wick / c0.range) >= 0.40:
            pq += 20.0
            reasons.append("Reaksi rejection tajam saat mitigasi zona FVG")
        else:
            pq -= 10.0
            penalties.append("Reaksi mitigasi FVG belum menunjukkan rejection wick tegas")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.92, ms_crit


class OrderBlockRetestEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #17: Order Block Retest."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=20)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 5:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        is_buy = signal.direction == SignalDirection.BUY
        pq = 76.0

        # Check if OB level held firmly
        if is_buy and c0.close > signal.reference_price:
            pq += 16.0
            reasons.append("Level Order Block dipertahankan di atas open candle origin")
        elif not is_buy and c0.close < signal.reference_price:
            pq += 16.0
            reasons.append("Level Order Block dipertahankan di bawah open candle origin")
        else:
            pq -= 15.0
            penalties.append("Retest menusuk melewati batas validitas Order Block")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.92, ms_crit


class CandleDisplacementEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #13: Candle Displacement."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=20)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 3:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        atr = calculate_atr(candles, 14)
        body_atr = c0.body / max(0.01, atr)
        pq = 70.0

        if body_atr >= 1.8:
            pq += 25.0
            reasons.append(f"Ekspansi displacement masif ({body_atr:.1f}x ATR)")
        elif body_atr >= 1.2:
            pq += 15.0
            reasons.append(f"Displacement solid ({body_atr:.1f}x ATR)")
        else:
            pq -= 15.0
            penalties.append("Displacement kurang impulsif terhadap rata-rata ATR")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.95, ms_crit


# =====================================================================
# 3. BREAKOUT & RANGE EVALUATORS (#4, #5, #7, #8, #14, #23)
# =====================================================================

class BreakoutEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #7: Breakout & #23: Donchian Range Breakout."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=25)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 5:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        atr = calculate_atr(candles, 14)
        is_buy = signal.direction == SignalDirection.BUY
        pq = 70.0

        pts = signal.metrics.get("breakout_pts", (c0.close - signal.reference_price) if is_buy else (signal.reference_price - c0.close))
        if pts > (atr * 0.4):
            pq += 20.0
            reasons.append(f"Breakout berjarak aman dari boundary (+{pts:.2f} pts)")
        elif pts <= 0.05:
            pq -= 15.0
            penalties.append("Penutupan harga menempel pada boundary (rawan fakeout)")

        if (c0.body / c0.range) >= 0.65:
            pq += 10.0
            reasons.append("Breakout didukung body candle solid")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.92, ms_crit


class BreakoutRetestEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #14: Breakout Retest."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=25)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 5:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        is_buy = signal.direction == SignalDirection.BUY
        pq = 75.0

        # Retest hold verification
        held = (is_buy and c0.close >= signal.reference_price) or (not is_buy and c0.close <= signal.reference_price)
        if held:
            pq += 18.0
            reasons.append("Broken level berhasil bertahan dan berperan sebagai S/R baru")
        else:
            pq -= 20.0
            penalties.append("Harga gagal bertahan di atas broken level")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.92, ms_crit


class FailedBreakoutEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #8: Failed Breakout (Trap)."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=20)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 3:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        is_buy = signal.direction == SignalDirection.BUY
        pq = 75.0

        # In a failed breakout trap, wick beyond range boundary indicates trap depth
        wick_ratio = (c0.lower_wick / c0.range) if is_buy else (c0.upper_wick / c0.range)
        if wick_ratio >= 0.45:
            pq += 20.0
            reasons.append(f"Penolakan false break sangat kuat ({wick_ratio * 100:.0f}% wick)")
        else:
            pq -= 12.0
            penalties.append("Rejection false break kurang tajam")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.90, ms_crit


class InsideOutsideBarEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #4: Inside Bar & #5: Outside Bar."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=20)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 3:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        c1 = candles[1]
        pq = 72.0

        if self.pattern_id == 4:  # Inside bar
            ratio = c1.range / max(0.01, c0.range)
            if ratio >= 1.3:
                pq += 18.0
                reasons.append(f"Mother bar dominan terhadap inside bar ({ratio:.1f}x)")
        else:  # Outside bar
            ratio = c0.range / max(0.01, c1.range)
            if ratio >= 1.5:
                pq += 20.0
                reasons.append(f"Outside bar meng-engulf penuh bar sebelumnya ({ratio:.1f}x)")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.90, ms_crit


# =====================================================================
# 4. PULLBACK & CONTINUATION EVALUATORS (#9, #10, #22)
# =====================================================================

class TrendPullbackEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #22: Trend Pullback & #9: Micro Pullback."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=25)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 5:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        pq = 72.0
        # Optimal pullback depth
        highs = [c.high for c in candles[:10]]
        lows = [c.low for c in candles[:10]]
        span = max(0.01, max(highs) - min(lows))
        is_buy = signal.direction == SignalDirection.BUY
        depth = (max(highs) - c0.low) / span if is_buy else (c0.high - min(lows)) / span

        if 0.35 <= depth <= 0.65:
            pq += 20.0
            reasons.append(f"Kedalaman pullback optimal ({depth * 100:.0f}% golden zone)")
        elif depth > 0.80:
            pq -= 20.0
            penalties.append("Pullback terlalu dalam menembus batas struktur sehat")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.92, ms_crit


class MicroTrendReversalEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #10: Micro Trend Reversal."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=20)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 4:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        c1 = candles[1]
        pq = 70.0
        is_buy = signal.direction == SignalDirection.BUY

        # Break of micro lower high (BUY) or micro higher low (SELL)
        if (is_buy and c0.close > c1.high) or (not is_buy and c0.close < c1.low):
            pq += 20.0
            reasons.append("Pembalikan micro flow terkonfirmasi candle close melampaui bar swing")
        else:
            pq -= 15.0
            penalties.append("Pembalikan mikro belum terkonfirmasi penuh")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.90, ms_crit


# =====================================================================
# 5. CANDLESTICK & REVERSAL EVALUATORS (#1, #2, #3, #24, #25, #38, #39, #40)
# =====================================================================

class CandlestickPatternEvaluator(BaseStrategyEvaluator):
    """Evaluates Candlestick patterns (#1 Reversal, #2 Continuation, #3 Multi, #24 Rejection, #25 Wick, #40 Confluence)."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=20)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 3:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        c1 = candles[1]
        is_buy = signal.direction == SignalDirection.BUY
        pq = 72.0

        if self.pattern_id in (1, 24, 25):  # Reversal / Pinbar / Wick
            wick_ratio = (c0.lower_wick / c0.range) if is_buy else (c0.upper_wick / c0.range)
            if wick_ratio >= 0.60:
                pq += 22.0
                reasons.append(f"Rejection wick sangat dominan ({wick_ratio * 100:.0f}% dari range bar)")
            elif wick_ratio < 0.40:
                pq -= 15.0
                penalties.append("Wick penolakan kurang signifikan (< 40%)")

        elif self.pattern_id == 2:  # Continuation / Marubozu
            body_ratio = c0.body / c0.range
            if body_ratio >= 0.75:
                pq += 22.0
                reasons.append(f"Body marubozu sangat dominan ({body_ratio * 100:.0f}% dari range)")
            else:
                pq -= 15.0
                penalties.append("Body candle continuation terpecah wick besar")

        elif self.pattern_id == 40:  # Rejection Confluence
            pq += 18.0
            reasons.append("Kluster rejection wick pada level harga yang sama")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.92, ms_crit


class CandleSequenceEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #38: Staircase Pattern & #39: Candle Sequence."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=20)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 4:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        is_buy = signal.direction == SignalDirection.BUY
        pq = 75.0

        # Check consecutive sequence consistency
        seq_len = 0
        for c in candles[:4]:
            if (is_buy and c.is_bullish) or (not is_buy and c.is_bearish):
                seq_len += 1
            else:
                break

        if seq_len >= 3:
            pq += 18.0
            reasons.append(f"Sekuens candle terarah beruntun ({seq_len} bar berturut-turut)")
        else:
            pq -= 10.0
            penalties.append("Sekuens candle terganggu bar berlawanan warna")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.90, ms_crit


# =====================================================================
# 6. VOLATILITY & COMPRESSION EVALUATORS (#18, #19, #20, #21, #26, #27, #28)
# =====================================================================

class VolatilityRangeEvaluator(BaseStrategyEvaluator):
    """Evaluates Volatility/Compression strategies (#18, #19, #20, #21, #26, #27, #28)."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=20)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 4:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        atr = calculate_atr(candles, 14)
        pq = 72.0

        if self.pattern_id in (18, 20, 26):  # Expansion / Burst
            exp_ratio = c0.range / max(0.01, atr)
            if exp_ratio >= 1.6:
                pq += 20.0
                reasons.append(f"Volatilitas meledak signifikan ({exp_ratio:.1f}x ATR)")
            else:
                pq -= 12.0
                penalties.append("Ekspansi range belum melampaui ambang batas burst")

        elif self.pattern_id in (19, 21, 27):  # Compression / Contraction
            pq += 15.0
            reasons.append("Kompresi volatilitas ketat sebelum letupan arah")

        elif self.pattern_id == 28:  # Gap
            gap_pts = signal.metrics.get("gap_pts", abs(c0.open - candles[1].close))
            if gap_pts > (atr * 0.3):
                pq += 18.0
                reasons.append(f"Price gap jelas (+{gap_pts:.2f} pts)")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.90, ms_crit


# =====================================================================
# 7. MOMENTUM & REVERSAL GEOMETRY EVALUATORS (#6, #29, #30, #31, #32, #35, #36, #37)
# =====================================================================

class MomentumPatternEvaluator(BaseStrategyEvaluator):
    """Evaluates Momentum strategies (#6 Momentum, #29 Failed Momentum, #30 Exhaustion)."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=20)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 3:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        atr = calculate_atr(candles, 14)
        pq = 72.0

        if self.pattern_id == 6:  # Momentum
            if (c0.body / max(0.01, atr)) >= 1.2:
                pq += 20.0
                reasons.append("Percepatan momentum body candle solid")
        elif self.pattern_id in (29, 30):  # Exhaustion / Failed
            pq += 18.0
            reasons.append("Pelemahan momentum terkonfirmasi setelah dorongan ekstrim")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.90, ms_crit


class GeometryPatternEvaluator(BaseStrategyEvaluator):
    """Evaluates Swing Geometry patterns (#31 Double Top, #32 Double Bottom, #35 Three-Push, #36 V-Rev, #37 Inv V-Rev)."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=25)
        reasons: List[str] = []
        penalties: List[str] = []
        if len(candles) < 5:

            penalties.append('Data candle tidak mencukupi untuk evaluasi penuh (< 5 candle)')

            return ComponentBreakdown(45, 45, 45, 45, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        pq = 74.0

        if self.pattern_id in (31, 32):  # Double Top / Bottom
            pq += 18.0
            reasons.append("Geometri double peak/trough simetris dengan konfirmasi neckline")
        elif self.pattern_id == 35:  # Three-push
            pq += 18.0
            reasons.append("Tiga dorongan sekuensial dengan deselerasi momentum (wedge exhaustion)")
        elif self.pattern_id in (36, 37):  # V-Reversal / Inv V-Reversal
            pq += 20.0
            reasons.append("Pembalikan V-shape tajam tanpa fase konsolidasi berkepanjangan")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)
        return ComponentBreakdown(pq, ms_score, lq, cc, eq), reasons, penalties, 0.92, ms_crit


# =====================================================================

# =====================================================================
# 8. VOLUME & ORDER FLOW STRATEGY EVALUATORS (Pola 41 - 56)
# =====================================================================

class VolumeExpansionEvaluator(BaseStrategyEvaluator):
    """Evaluates Volume Expansion Strategies:
    #41: Relative Volume Expansion
    #42: Large Volume Bubble
    #44: Volume Breakout
    """

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=25)
        reasons: List[str] = []
        penalties: List[str] = []
        has_critical = False

        if len(candles) < 5:
            penalties.append("Data candle terbatas untuk evaluasi volume expansion")
            return ComponentBreakdown(40, 40, 40, 40, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        c_rng = max(0.01, c0.range)
        body_ratio = c0.body / c_rng

        rvol = signal.metrics.get("rvol", 0.0) if signal.metrics else 0.0
        zscore = signal.metrics.get("zscore", 0.0) if signal.metrics else 0.0
        if rvol == 0.0 and len(candles) >= 20:
            v_info = calculate_rvol_and_zscore(candles, 20)
            rvol = v_info["rvol"]
            zscore = v_info["zscore"]

        pq = 70.0
        if self.pattern_id == 41:  # RVOL Expansion
            if rvol >= 2.5:
                pq += 20.0
                reasons.append(f"[OBSERVED_TICK_VOLUME] Ekspansi volume masif (RVOL {rvol:.2f}x)")
            elif rvol >= 1.8:
                pq += 10.0
                reasons.append(f"[OBSERVED_TICK_VOLUME] Ekspansi volume sehat (RVOL {rvol:.2f}x)")
            else:
                pq -= 15.0
                penalties.append(f"Volume relatif kurang memadai ({rvol:.2f}x)")

            if body_ratio >= 0.70:
                pq += 10.0
                reasons.append(f"Dominasi body impulsif ({body_ratio * 100:.0f}%)")
        elif self.pattern_id == 42:  # Large Volume Bubble
            if zscore >= 3.0:
                pq += 25.0
                reasons.append(f"[OBSERVED_TICK_VOLUME] Anomali bubble ekstrim (Z-Score {zscore:.2f})")
            elif zscore >= 2.0:
                pq += 12.0
                reasons.append(f"[OBSERVED_TICK_VOLUME] Volume bubble terdeteksi (Z-Score {zscore:.2f})")
            else:
                pq -= 15.0
                penalties.append(f"Z-score volume di bawah ambang bubble ({zscore:.2f})")
        elif self.pattern_id == 44:  # Volume Breakout
            if rvol >= 2.0 and body_ratio >= 0.60:
                pq += 20.0
                reasons.append(f"[OBSERVED_TICK_VOLUME] Breakout didukung volume tinggi ({rvol:.2f}x) dan body solid")
            else:
                pq += 8.0
                reasons.append("[OBSERVED_TICK_VOLUME] Breakout dengan partisipasi volume")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        mtf_score, mtf_r, mtf_p = self.evaluate_mtf_confluence(buffer, timeframe, signal.direction)
        ms = (ms_score * 0.7) + (mtf_score * 0.3)
        reasons.extend(ms_r + mtf_r)
        penalties.extend(ms_p + mtf_p)
        if ms_crit:
            has_critical = True

        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        reasons.extend(lq_r)
        penalties.extend(lq_p)

        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        reasons.extend(cc_r)
        penalties.extend(cc_p)

        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)
        reasons.extend(eq_r)
        penalties.extend(eq_p)

        confidence = 0.95 if len(candles) >= 15 else 0.70
        breakdown = ComponentBreakdown(pq, ms, lq, cc, eq)
        return breakdown, reasons, penalties, confidence, has_critical


class VolumeClimaxEvaluator(BaseStrategyEvaluator):
    """Evaluates Strategy #43: Volume Climax Reversal."""

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=25)
        reasons: List[str] = []
        penalties: List[str] = []
        has_critical = False

        if len(candles) < 5:
            penalties.append("Data candle terbatas untuk evaluasi climax reversal")
            return ComponentBreakdown(40, 40, 40, 40, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        c_rng = max(0.01, c0.range)
        is_buy = signal.direction == SignalDirection.BUY
        rvol = signal.metrics.get("rvol", 0.0) if signal.metrics else 0.0
        if rvol == 0.0 and len(candles) >= 20:
            v_info = calculate_rvol_and_zscore(candles, 20)
            rvol = v_info["rvol"]

        pq = 72.0
        if rvol >= 3.0:
            pq += 18.0
            reasons.append(f"[OBSERVED_TICK_VOLUME] Volume ultra-tinggi ({rvol:.2f}x) menandakan blow-off climax")
        elif rvol >= 2.0:
            pq += 10.0
            reasons.append(f"[OBSERVED_TICK_VOLUME] Volume signifikan ({rvol:.2f}x) pada candle pembalikan")
        else:
            pq -= 15.0
            penalties.append("Volume relatif kurang memadai untuk klimaks sejati")

        exhaustion_wick = c0.lower_wick if is_buy else c0.upper_wick
        wick_ratio = exhaustion_wick / c_rng
        if wick_ratio >= 0.50:
            pq += 15.0
            reasons.append(f"Exhaustion wick panjang ({wick_ratio * 100:.0f}%) menunjukkan penolakan harga masif")
        elif wick_ratio < 0.30:
            pq -= 12.0
            penalties.append("Wick penolakan terlalu pendek untuk climax reversal")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)

        confidence = 0.95 if len(candles) >= 15 else 0.70
        breakdown = ComponentBreakdown(pq, ms_score, lq, cc, eq)
        return breakdown, reasons, penalties, confidence, ms_crit


class CumulativeDeltaEvaluator(BaseStrategyEvaluator):
    """Evaluates CVD & Delta Strategies:
    #45: CVD Divergence
    #46: CVD Reversal
    #47: CVD Trend Continuation
    #50: Delta Exhaustion
    """

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=25)
        reasons: List[str] = []
        penalties: List[str] = []
        has_critical = False

        if len(candles) < 5:
            penalties.append("Data candle terbatas untuk evaluasi CVD delta")
            return ComponentBreakdown(40, 40, 40, 40, 60), reasons, penalties, 0.40, False

        pq = 72.0
        if self.pattern_id == 45:  # CVD Divergence
            pq += 18.0
            reasons.append("[ESTIMATED_DELTA_PROXY] Divergensi CVD terdeteksi: arah akumulasi delta bertolak belakang dengan harga")
            div_type = signal.metrics.get("divergence", "") if signal.metrics else ""
            if div_type:
                pq += 5.0
                reasons.append(f"Tipe divergensi terkonfirmasi: {div_type}")
        elif self.pattern_id == 46:  # CVD Reversal
            pq += 15.0
            reasons.append("[ESTIMATED_DELTA_PROXY] Perubahan tajam pada tanda delta candle mengindikasikan rotasi aliran pesanan")
        elif self.pattern_id == 47:  # CVD Continuation
            pq += 16.0
            reasons.append("[ESTIMATED_DELTA_PROXY] Aliran CVD searah tren harga mengonfirmasi kelanjutan momentum")
        elif self.pattern_id == 50:  # Delta Exhaustion
            pq += 18.0
            reasons.append("[ESTIMATED_DELTA_PROXY] Delta exhaustion: volume agresif gagal mendorong harga lebih jauh (penyerapan pasif)")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)

        confidence = 0.90 if len(candles) >= 15 else 0.70
        breakdown = ComponentBreakdown(pq, ms_score, lq, cc, eq)
        return breakdown, reasons, penalties, confidence, ms_crit


class VolumeAbsorptionEvaluator(BaseStrategyEvaluator):
    """Evaluates Absorption Strategies:
    #48: Bullish Absorption
    #49: Bearish Absorption
    """

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=25)
        reasons: List[str] = []
        penalties: List[str] = []
        has_critical = False

        if len(candles) < 5:
            penalties.append("Data candle terbatas untuk evaluasi penyerapan volume")
            return ComponentBreakdown(40, 40, 40, 40, 60), reasons, penalties, 0.40, False

        c0 = candles[0]
        c_rng = max(0.01, c0.range)
        pq = 72.0

        if self.pattern_id == 48:  # Bullish Absorption
            wick_ratio = c0.lower_wick / c_rng
            if wick_ratio >= 0.45:
                pq += 18.0
                reasons.append(f"[PROXY_ABSORPTION] Penyerapan agresif seller di level bawah (wick {wick_ratio * 100:.0f}%)")
            else:
                pq += 8.0
                reasons.append("[PROXY_ABSORPTION] Penyerapan volume bawah terdeteksi")
            reasons.append("[ESTIMATED_DELTA_PROXY] Buyer pasif menyerap likuiditas jual pada harga rendah")
        elif self.pattern_id == 49:  # Bearish Absorption
            wick_ratio = c0.upper_wick / c_rng
            if wick_ratio >= 0.45:
                pq += 18.0
                reasons.append(f"[PROXY_ABSORPTION] Penyerapan agresif buyer di level atas (wick {wick_ratio * 100:.0f}%)")
            else:
                pq += 8.0
                reasons.append("[PROXY_ABSORPTION] Penyerapan volume atas terdeteksi")
            reasons.append("[ESTIMATED_DELTA_PROXY] Seller pasif menyerap likuiditas beli pada harga tinggi")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)

        confidence = 0.90 if len(candles) >= 15 else 0.70
        breakdown = ComponentBreakdown(pq, ms_score, lq, cc, eq)
        return breakdown, reasons, penalties, confidence, ms_crit


class FootprintImbalanceEvaluator(BaseStrategyEvaluator):
    """Evaluates Micro-Price Footprint Strategies:
    #51: Bid/Ask Imbalance
    #52: Stacked Imbalance
    """

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=25)
        reasons: List[str] = []
        penalties: List[str] = []
        has_critical = False

        if len(candles) < 5:
            penalties.append("Data candle terbatas untuk evaluasi footprint imbalance")
            return ComponentBreakdown(40, 40, 40, 40, 60), reasons, penalties, 0.40, False

        pq = 72.0
        if self.pattern_id == 51:  # Bid/Ask Imbalance
            pq += 15.0
            reasons.append("[PROXY_PRICE_LEVEL_FOOTPRINT] Ketidakseimbangan bid/ask signifikan terdeteksi pada dekomposisi mikro intra-bar")
        elif self.pattern_id == 52:  # Stacked Imbalance
            stacked = signal.metrics.get("stacked_levels", 3) if signal.metrics else 3
            if stacked >= 4:
                pq += 22.0
                reasons.append(f"[PROXY_PRICE_LEVEL_FOOTPRINT] Stacked imbalance kuat ({stacked} level berurutan) menunjukkan inisiatif institusi")
            else:
                pq += 15.0
                reasons.append(f"[PROXY_PRICE_LEVEL_FOOTPRINT] Stacked imbalance terkonfirmasi pada {stacked} level harga berurutan")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)

        confidence = 0.90 if len(candles) >= 15 else 0.70
        breakdown = ComponentBreakdown(pq, ms_score, lq, cc, eq)
        return breakdown, reasons, penalties, confidence, ms_crit


class VolumeProfileEvaluator(BaseStrategyEvaluator):
    """Evaluates Volume Profile Strategies:
    #53: POC Reclaim
    #54: VAH Rejection
    #55: VAL Rejection
    #56: HVN/LVN Reaction
    """

    def evaluate(
        self, signal: EntrySignal, buffer: MarketBuffer, timeframe: str
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        candles = self.get_closed_candles(buffer, timeframe, count=25)
        reasons: List[str] = []
        penalties: List[str] = []
        has_critical = False

        if len(candles) < 5:
            penalties.append("Data candle terbatas untuk evaluasi volume profile")
            return ComponentBreakdown(40, 40, 40, 40, 60), reasons, penalties, 0.40, False

        pq = 72.0
        if self.pattern_id == 53:  # POC Reclaim
            pq += 18.0
            reasons.append("[OBSERVED_TICK_VOLUME] POC Reclaim: harga berhasil merebut kembali Point of Control profil volume")
        elif self.pattern_id == 54:  # VAH Rejection
            pq += 18.0
            reasons.append("[OBSERVED_TICK_VOLUME] VAH Rejection: penolakan harga pada Value Area High mengonfirmasi zona rotasi ke bawah")
        elif self.pattern_id == 55:  # VAL Rejection
            pq += 18.0
            reasons.append("[OBSERVED_TICK_VOLUME] VAL Rejection: penolakan harga pada Value Area Low mengonfirmasi zona rotasi ke atas")
        elif self.pattern_id == 56:  # HVN/LVN Reaction
            pq += 16.0
            reasons.append("[OBSERVED_TICK_VOLUME] Reaksi node volume: transisi cepat melalui LVN atau pantulan pada HVN node")

        ms_score, ms_r, ms_p, ms_crit = self.assess_market_structure(candles, signal.direction)
        lq, lq_r, lq_p = self.assess_location_quality(candles, signal.direction, signal.trigger_price)
        cc, cc_r, cc_p = self.assess_candle_confirmation(candles, signal.direction)
        eq, eq_r, eq_p = self.assess_execution_quality(signal, buffer, timeframe)

        reasons.extend(ms_r + lq_r + cc_r + eq_r)
        penalties.extend(ms_p + lq_p + cc_p + eq_p)

        confidence = 0.95 if len(candles) >= 15 else 0.70
        breakdown = ComponentBreakdown(pq, ms_score, lq, cc, eq)
        return breakdown, reasons, penalties, confidence, ms_crit

# FACTORY & REGISTRY FOR ALL 40 EVALUATORS
# =====================================================================

EVALUATOR_MAPPING: Dict[int, Type[BaseStrategyEvaluator]] = {
    # 1 - 10
    1: CandlestickPatternEvaluator,      # Candlestick Reversal
    2: CandlestickPatternEvaluator,      # Candlestick Continuation
    3: CandlestickPatternEvaluator,      # Multi-Candle Reversal
    4: InsideOutsideBarEvaluator,        # Inside Bar
    5: InsideOutsideBarEvaluator,        # Outside Bar
    6: MomentumPatternEvaluator,         # Momentum
    7: BreakoutEvaluator,                # Breakout
    8: FailedBreakoutEvaluator,          # Failed Breakout
    9: TrendPullbackEvaluator,           # Micro Pullback
    10: MicroTrendReversalEvaluator,     # Micro Trend Reversal
    # 11 - 20
    11: ChangeOfCharacterEvaluator,      # CHoCH
    12: BreakOfStructureEvaluator,       # BOS
    13: CandleDisplacementEvaluator,     # Candle Displacement
    14: BreakoutRetestEvaluator,         # Breakout Retest
    15: FairValueGapEvaluator,           # Fair Value Gap (FVG)
    16: FairValueGapRetestEvaluator,     # FVG Retest
    17: OrderBlockRetestEvaluator,       # Order Block Retest
    18: VolatilityRangeEvaluator,        # Micro Range Expansion
    19: VolatilityRangeEvaluator,        # Micro Range Compression
    20: VolatilityRangeEvaluator,        # Volatility Burst
    # 21 - 30
    21: VolatilityRangeEvaluator,        # Volatility Contraction
    22: TrendPullbackEvaluator,          # Trend Pullback
    23: BreakoutEvaluator,               # Donchian Range Breakout
    24: CandlestickPatternEvaluator,     # Rejection Pattern
    25: CandlestickPatternEvaluator,     # Wick Pattern
    26: VolatilityRangeEvaluator,        # Body Expansion
    27: VolatilityRangeEvaluator,        # Body Contraction
    28: VolatilityRangeEvaluator,        # Gap Pattern
    29: MomentumPatternEvaluator,        # Failed Momentum
    30: MomentumExhaustionEvaluator if 'MomentumExhaustionEvaluator' in locals() else MomentumPatternEvaluator, # Momentum Exhaustion
    # 31 - 40
    31: GeometryPatternEvaluator,        # Micro Double Top
    32: GeometryPatternEvaluator,        # Micro Double Bottom
    33: MicroSwingBreakEvaluator,        # Micro Swing Break
    34: MicroSwingFailureEvaluator,      # Micro Swing Failure
    35: GeometryPatternEvaluator,        # Three-Push Pattern
    36: GeometryPatternEvaluator,        # V-Reversal
    37: GeometryPatternEvaluator,        # Inverted V-Reversal
    38: CandleSequenceEvaluator,         # Staircase Pattern
    39: CandleSequenceEvaluator,         # Candle Sequence
    40: CandlestickPatternEvaluator,     # Candle Rejection Confluence
    # 41 - 50: Volume & CVD
    41: VolumeExpansionEvaluator,        # Relative Volume Expansion
    42: VolumeExpansionEvaluator,        # Large Volume Bubble
    43: VolumeClimaxEvaluator,           # Volume Climax Reversal
    44: VolumeExpansionEvaluator,        # Volume Breakout
    45: CumulativeDeltaEvaluator,        # CVD Divergence
    46: CumulativeDeltaEvaluator,        # CVD Reversal
    47: CumulativeDeltaEvaluator,        # CVD Trend Continuation
    48: VolumeAbsorptionEvaluator,       # Bullish Absorption
    49: VolumeAbsorptionEvaluator,       # Bearish Absorption
    50: CumulativeDeltaEvaluator,        # Delta Exhaustion
    # 51 - 56: Footprint & Volume Profile
    51: FootprintImbalanceEvaluator,     # Bid/Ask Imbalance
    52: FootprintImbalanceEvaluator,     # Stacked Imbalance
    53: VolumeProfileEvaluator,          # POC Reclaim
    54: VolumeProfileEvaluator,          # VAH Rejection
    55: VolumeProfileEvaluator,          # VAL Rejection
    56: VolumeProfileEvaluator,          # HVN/LVN Reaction
}


def get_evaluator_for_pattern(pattern_id: int, pattern_name: str = "") -> BaseStrategyEvaluator:
    """Returns the dedicated evaluator instance for any of the 40 strategy IDs."""
    eval_cls = EVALUATOR_MAPPING.get(pattern_id, CandlestickPatternEvaluator)
    return eval_cls(pattern_id=pattern_id, pattern_name=pattern_name)
