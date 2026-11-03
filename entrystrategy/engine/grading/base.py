"""Base evaluator architecture and common analytical tools for strategy grading."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from entrystrategy.core.models import EntrySignal, SignalDirection, Candle
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.engine.grading.models import (
    ComponentBreakdown,
    EvidenceCluster,
    EvidenceItem,
)
from entrystrategy.engine.grading.thresholds import (
    get_timeframe_profile,
    calculate_atr,
)


class BaseStrategyEvaluator(ABC):
    """Abstract base class for all 40 Strategy-Specific Evaluators."""

    def __init__(self, pattern_id: int, pattern_name: str):
        self.pattern_id = pattern_id
        self.pattern_name = pattern_name

    @abstractmethod
    def evaluate(
        self,
        signal: EntrySignal,
        buffer: MarketBuffer,
        timeframe: str,
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        """Evaluates a signal against closed candles and structural context.
        Returns:
            breakdown: ComponentBreakdown scores (0-100)
            reasons: List of positive reason strings
            penalties: List of penalty reason strings
            confidence: Data sufficiency / confidence ratio (0.0 to 1.0)
            has_critical_contradiction: True if severe structural/pattern conflict exists
        """
        pass

    def get_closed_candles(
        self, buffer: MarketBuffer, timeframe: str, count: int = 20
    ) -> List[Candle]:
        """Retrieves strictly closed candles for the requested timeframe.
        Index 0 is latest completed candle, index 1 is previous completed candle.
        """
        candles = buffer.get_recent_candles(count=count, timeframe=timeframe)
        return [c for c in candles if c.is_closed]

    def deduplicate_cluster_scores(
        self, items: List[EvidenceItem]
    ) -> Dict[EvidenceCluster, float]:
        """Prevents double-counting by combining correlated evidence with diminishing returns:
        score = max_score + 0.25 * (remaining_positive_evidence)
        """
        clustered: Dict[EvidenceCluster, List[float]] = {}
        for item in items:
            clustered.setdefault(item.cluster, []).append(item.score)

        deduped: Dict[EvidenceCluster, float] = {}
        for cluster, scores in clustered.items():
            if not scores:
                continue
            sorted_scores = sorted(scores, reverse=True)
            primary = sorted_scores[0]
            secondary_boost = sum(max(0.0, s - 50.0) * 0.25 for s in sorted_scores[1:])
            deduped[cluster] = min(100.0, primary + secondary_boost)
        return deduped

    def assess_market_structure(
        self, candles: List[Candle], direction: SignalDirection
    ) -> Tuple[float, List[str], List[str], bool]:
        """Evaluates macro/swing structural alignment from closed candles."""
        if len(candles) < 5:
            return 50.0, [], ["Data struktur pasar terbatas (< 5 candle)"], False

        is_buy = direction == SignalDirection.BUY
        c0 = candles[0]
        
        # Highs and lows of recent 10 bars
        highs = [c.high for c in candles[:10]]
        lows = [c.low for c in candles[:10]]
        
        max_h = max(highs)
        min_l = min(lows)
        range_span = max(0.01, max_h - min_l)
        
        # Trend flow across bars: compare oldest half to newest half
        mid_idx = min(5, len(candles) // 2)
        recent_closes = [c.close for c in candles[:mid_idx]]
        older_closes = [c.close for c in candles[mid_idx:mid_idx * 2]]
        
        avg_recent = sum(recent_closes) / len(recent_closes)
        avg_older = sum(older_closes) / len(older_closes) if older_closes else avg_recent

        score = 70.0
        reasons: List[str] = []
        penalties: List[str] = []
        has_critical = False

        if is_buy:
            if avg_recent > avg_older:
                score += 15.0
                reasons.append("Struktur tren mikro selaras (Higher Closes)")
            elif avg_recent < (avg_older - 1.5):
                score -= 20.0
                penalties.append("Counter-trend terhadap penurunan mikro signifikan")
                if c0.close < min_l + (range_span * 0.15):
                    has_critical = True
                    penalties.append("CRITICAL: Sinyal BUY berada di dasar downtrend tanpa struktur pembalik")

            # Check for swing higher low
            recent_lows = [c.low for c in candles[:3]]
            older_lows = [c.low for c in candles[3:7]]
            if recent_lows and older_lows and min(recent_lows) > min(older_lows):
                score += 10.0
                reasons.append("Terbentuk Higher Low pada struktur candle")
        else:
            if avg_recent < avg_older:
                score += 15.0
                reasons.append("Struktur tren mikro selaras (Lower Closes)")
            elif avg_recent > (avg_older + 1.5):
                score -= 20.0
                penalties.append("Counter-trend terhadap kenaikan mikro signifikan")
                if c0.close > max_h - (range_span * 0.15):
                    has_critical = True
                    penalties.append("CRITICAL: Sinyal SELL berada di puncak uptrend tanpa struktur pembalik")

            # Check for swing lower high
            recent_highs = [c.high for c in candles[:3]]
            older_highs = [c.high for c in candles[3:7]]
            if recent_highs and older_highs and max(recent_highs) < max(older_highs):
                score += 10.0
                reasons.append("Terbentuk Lower High pada struktur candle")

        return max(10.0, min(100.0, score)), reasons, penalties, has_critical

    def assess_location_quality(
        self,
        candles: List[Candle],
        direction: SignalDirection,
        trigger_px: float,
    ) -> Tuple[float, List[str], List[str]]:
        """Evaluates Premium/Discount location and proximity to structural extremes."""
        if len(candles) < 5:
            return 50.0, [], ["Data lokasi terbatas (< 5 candle)"]

        highs = [c.high for c in candles[:15]]
        lows = [c.low for c in candles[:15]]
        swing_high = max(highs)
        swing_low = min(lows)
        span = max(0.01, swing_high - swing_low)

        # Relative position: 0.0 = at swing low (Deep Discount), 1.0 = at swing high (Deep Premium)
        rel_pos = max(0.0, min(1.0, (trigger_px - swing_low) / span))
        
        score = 70.0
        reasons: List[str] = []
        penalties: List[str] = []

        is_buy = direction == SignalDirection.BUY
        if is_buy:
            if rel_pos <= 0.40:
                score += 22.0
                reasons.append(f"Entry di Discount Zone ({rel_pos * 100:.0f}% dari range)")
            elif rel_pos >= 0.85:
                score -= 25.0
                penalties.append(f"Entry BUY terlalu dekat dengan resistensi tertinggi ({rel_pos * 100:.0f}%)")
            else:
                score += 5.0
                reasons.append("Lokasi harga seimbang (Equilibrium Range)")
        else:
            if rel_pos >= 0.60:
                score += 22.0
                reasons.append(f"Entry di Premium Zone ({rel_pos * 100:.0f}% dari range)")
            elif rel_pos <= 0.15:
                score -= 25.0
                penalties.append(f"Entry SELL terlalu dekat dengan support terendah ({rel_pos * 100:.0f}%)")
            else:
                score += 5.0
                reasons.append("Lokasi harga seimbang (Equilibrium Range)")

        return max(10.0, min(100.0, score)), reasons, penalties

    def assess_candle_confirmation(
        self, candles: List[Candle], direction: SignalDirection
    ) -> Tuple[float, List[str], List[str]]:
        """Evaluates the trigger candle close quality, body dominance, and opposing wicks."""
        if not candles:
            return 50.0, [], ["Tidak ada candle konfirmasi"]

        c0 = candles[0]
        c_range = max(0.01, c0.range)
        body = c0.body
        body_ratio = body / c_range
        is_buy = direction == SignalDirection.BUY

        score = 65.0
        reasons: List[str] = []
        penalties: List[str] = []

        if is_buy:
            if c0.is_bullish:
                score += 15.0
                reasons.append("Candle konfirmasi bullish searah sinyal")
                if body_ratio >= 0.65:
                    score += 15.0
                    reasons.append(f"Dominasi body kuat ({body_ratio * 100:.0f}% dari range)")
                # Upper wick rejection check
                if (c0.upper_wick / c_range) > 0.35:
                    score -= 15.0
                    penalties.append("Terdapat penolakan harga atas (upper wick > 35%)")
                # Lower wick support
                if (c0.lower_wick / c_range) >= 0.25:
                    score += 5.0
                    reasons.append("Rejection wick bawah menandakan penyerapan buyer")
            else:
                score -= 25.0
                penalties.append("Candle pemicu berlawanan arah (bearish candle pada BUY)")
        else:
            if c0.is_bearish:
                score += 15.0
                reasons.append("Candle konfirmasi bearish searah sinyal")
                if body_ratio >= 0.65:
                    score += 15.0
                    reasons.append(f"Dominasi body kuat ({body_ratio * 100:.0f}% dari range)")
                # Lower wick rejection check
                if (c0.lower_wick / c_range) > 0.35:
                    score -= 15.0
                    penalties.append("Terdapat penolakan harga bawah (lower wick > 35%)")
                # Upper wick resistance
                if (c0.upper_wick / c_range) >= 0.25:
                    score += 5.0
                    reasons.append("Rejection wick atas menandakan penyerapan seller")
            else:
                score -= 25.0
                penalties.append("Candle pemicu berlawanan arah (bullish candle pada SELL)")

        return max(10.0, min(100.0, score)), reasons, penalties

    def assess_execution_quality(
        self,
        signal: EntrySignal,
        buffer: MarketBuffer,
        timeframe: str,
    ) -> Tuple[float, List[str], List[str]]:
        """Evaluates spread efficiency, execution slippage estimate, and invalidation risk ratio."""
        profile = get_timeframe_profile(timeframe)
        max_spread = profile["max_acceptable_spread"]
        spread = buffer.current_spread

        score = 80.0
        reasons: List[str] = []
        penalties: List[str] = []

        # Spread impact
        if spread <= (max_spread * 0.7):
            score += 12.0
            reasons.append(f"Spread sangat rapat ({spread:.2f} pts)")
        elif spread > max_spread:
            penalty_val = min(30.0, (spread - max_spread) * 40.0)
            score -= penalty_val
            penalties.append(f"Spread melebar ({spread:.2f} pts > {max_spread:.2f} pts)")

        # Invalidation definition
        if signal.invalidation_price is not None:
            dist = abs(signal.trigger_price - signal.invalidation_price)
            atr = calculate_atr(buffer.get_recent_candles(14, timeframe))
            if dist < (atr * 0.15):
                score -= 15.0
                penalties.append("Jarak invalidasi terlalu ketat terhadap noise ATR")
            elif dist > (atr * 4.0):
                score -= 10.0
                penalties.append("Jarak invalidasi sangat jauh terhadap pergerakan normal ATR")
            else:
                score += 8.0
                reasons.append(f"Level invalidasi proporsional ({dist:.2f} pts ~ {dist / max(0.01, atr):.1f}x ATR)")
        else:
            score -= 12.0
            penalties.append("Level invalidasi tidak didefinisikan secara eksplisit")

        return max(10.0, min(100.0, score)), reasons, penalties

    def evaluate_mtf_confluence(
        self,
        buffer: MarketBuffer,
        current_tf: str,
        direction: SignalDirection,
    ) -> Tuple[float, List[str], List[str]]:
        """Evaluates higher timeframe closed candles for structural alignment.
        M1 evaluates closed M5 & M15. M5 evaluates closed M15. M15 is self-contained.
        Only closed candles are used; unfinished bars are never touched.
        """
        reasons: List[str] = []
        penalties: List[str] = []
        higher_tfs: List[str] = []

        if current_tf == "M1":
            higher_tfs = ["M5", "M15"]
        elif current_tf == "M5":
            higher_tfs = ["M15"]
        else:
            return 80.0, ["Timeframe M15 mandiri (independen)"], []

        confluences = 0
        conflicts = 0

        is_buy = direction == SignalDirection.BUY

        for htf in higher_tfs:
            htf_candles = [c for c in buffer.get_recent_candles(count=5, timeframe=htf) if c.is_closed]
            if not htf_candles:
                continue

            c_htf = htf_candles[0]
            htf_aligned = (is_buy and c_htf.is_bullish) or (not is_buy and c_htf.is_bearish)
            
            if htf_aligned:
                confluences += 1
                reasons.append(f"Konteks {htf} closed selaras ({c_htf.close > c_htf.open and 'Bullish' or 'Bearish'})")
            else:
                conflicts += 1
                penalties.append(f"Konteks {htf} closed bertentangan ({c_htf.is_bullish and 'Bullish' or 'Bearish'})")

        base_score = 75.0
        if confluences > 0 and conflicts == 0:
            return min(100.0, base_score + (confluences * 10.0)), reasons, penalties
        elif conflicts > 0 and confluences == 0:
            return max(35.0, base_score - (conflicts * 15.0)), reasons, penalties
        elif confluences > 0 and conflicts > 0:
            return base_score, reasons, penalties
        else:
            return base_score, ["Konteks MTF belum memiliki riwayat bar closed"], []
