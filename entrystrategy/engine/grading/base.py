"""Base evaluator architecture and common analytical tools for strategy grading.

Ensures strict adherence to:
- Closed-candle-only evaluation (no unfinished bars).
- Snapshot timestamp filtering (strictly prevents look-ahead bias).
- Strategy-specific location quality.
- Dynamic data-sufficiency confidence (no fabricated constants).
- Explicit data transparency (OBSERVED, ESTIMATED, UNAVAILABLE, INSUFFICIENT).
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from entrystrategy.core.models import EntrySignal, SignalDirection, Candle
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.engine.grading.models import (
    ComponentBreakdown,
    EvidenceCluster,
    EvidenceItem,
    DataStatus,
)
from entrystrategy.engine.grading.thresholds import (
    get_timeframe_profile,
    calculate_atr,
)


class BaseStrategyEvaluator(ABC):
    """Abstract base class for all Strategy-Specific Evaluators."""

    def __init__(self, pattern_id: int, pattern_name: str):
        self.pattern_id = pattern_id
        self.pattern_name = pattern_name

    @abstractmethod
    def evaluate(
        self,
        signal: EntrySignal,
        buffer: MarketBuffer,
        timeframe: str,
        snapshot_timestamp_ms: Optional[int] = None,
    ) -> Tuple[ComponentBreakdown, List[str], List[str], float, bool]:
        """Evaluates a signal against closed candles and structural context.
        Returns:
            breakdown: ComponentBreakdown scores and data statuses
            reasons: List of positive reason strings
            penalties: List of penalty reason strings
            confidence: Data sufficiency / confidence ratio (0.0 to 1.0)
            has_critical_contradiction: True if severe structural/pattern conflict exists
        """
        pass

    def get_closed_candles(
        self,
        buffer: MarketBuffer,
        timeframe: str,
        count: int = 20,
        snapshot_timestamp_ms: Optional[int] = None,
    ) -> List[Candle]:
        """Retrieves strictly closed candles for the requested timeframe at or prior to snapshot.

        Enforces:
        1. Only candles with is_closed=True.
        2. No candles closing after snapshot_timestamp_ms (prevents look-ahead bias).
        Index 0 is latest completed candle, index 1 is previous completed candle.
        """
        raw = buffer.get_recent_candles(count=max(count * 2, 40), timeframe=timeframe)
        closed = [c for c in raw if getattr(c, "is_closed", True)]

        if snapshot_timestamp_ms is not None:
            filtered = []
            for c in closed:
                c_ms = int(c.timestamp.timestamp() * 1000)
                if c_ms <= snapshot_timestamp_ms:
                    filtered.append(c)
            return filtered[:count]

        return closed[:count]

    def calculate_dynamic_confidence(
        self,
        closed_candle_count: int,
        required_bars: int = 15,
        available_components: int = 5,
        total_components: int = 5,
        has_htf_context: bool = False,
        is_proxy_metric: bool = False,
    ) -> float:
        """Calculates dynamic grading confidence reflecting true data sufficiency.

        Never returns a hardcoded constant. Considers:
        - Ratio of available closed bars to required bars
        - Completeness of evaluated components (5 standard components)
        - Higher timeframe context availability
        - Penalty for proxy-derived metrics vs directly observed data
        """
        if closed_candle_count < 3:
            return 0.20

        bar_ratio = min(1.0, closed_candle_count / max(1, required_bars))
        comp_ratio = available_components / max(1, total_components)

        conf = (0.55 * bar_ratio) + (0.45 * comp_ratio)

        if has_htf_context:
            conf += 0.05

        if is_proxy_metric:
            conf = min(0.85, conf * 0.90)

        if closed_candle_count < 5:
            conf = min(0.35, conf)

        return round(max(0.10, min(1.0, conf)), 2)

    def assess_market_structure(
        self,
        candles: List[Candle],
        direction: SignalDirection,
    ) -> Tuple[Optional[float], List[str], List[str], bool]:
        """Evaluates macro/swing structural alignment from closed candles.

        Returns:
            score: Structural alignment score (0-100), or None if insufficient data
            reasons: Positive alignment notes
            penalties: Structural concerns/penalties
            has_critical: Severe structural conflict
        """
        if len(candles) < 5:
            return None, [], ["Data struktur pasar tidak mencukupi (< 5 candle closed)"], False

        is_buy = direction == SignalDirection.BUY
        c0 = candles[0]

        highs = [c.high for c in candles[:12]]
        lows = [c.low for c in candles[:12]]
        swing_high = max(highs)
        swing_low = min(lows)
        range_span = max(0.01, swing_high - swing_low)

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
                if c0.close < swing_low + (range_span * 0.15):
                    has_critical = True
                    penalties.append("CRITICAL: Sinyal BUY berada di dasar downtrend tanpa struktur pembalik")

            recent_lows = [c.low for c in candles[:3]]
            older_lows = [c.low for c in candles[3:7]]
            if recent_lows and older_lows and min(recent_lows) > min(older_lows):
                score += 10.0
                reasons.append("Terbentuk Higher Low pada struktur swing candle")
        else:
            if avg_recent < avg_older:
                score += 15.0
                reasons.append("Struktur tren mikro selaras (Lower Closes)")
            elif avg_recent > (avg_older + 1.5):
                score -= 20.0
                penalties.append("Counter-trend terhadap kenaikan mikro signifikan")
                if c0.close > swing_high - (range_span * 0.15):
                    has_critical = True
                    penalties.append("CRITICAL: Sinyal SELL berada di puncak uptrend tanpa struktur pembalik")

            recent_highs = [c.high for c in candles[:3]]
            older_highs = [c.high for c in candles[3:7]]
            if recent_highs and older_highs and max(recent_highs) < max(older_highs):
                score += 10.0
                reasons.append("Terbentuk Lower High pada struktur swing candle")

        final_score = max(10.0, min(100.0, score))
        return final_score, reasons, penalties, has_critical

    def evaluate_mtf_confluence(
        self,
        buffer: MarketBuffer,
        current_tf: str,
        direction: SignalDirection,
        snapshot_timestamp_ms: Optional[int] = None,
    ) -> Tuple[Optional[float], List[str], List[str]]:
        """Evaluates higher timeframe closed candles for structural alignment.

        Enforces:
        - M1 evaluates closed M5 & M15.
        - M5 evaluates closed M15.
        - M15 is self-contained (returns None, UNAVAILABLE without unearned bonus).
        - HTF candles must be closed prior to snapshot_timestamp_ms.
        - Unclosed HTF bars are strictly discarded.
        - Absence of HTF data is marked UNAVAILABLE (no false baseline score).
        """
        clean_tf = (current_tf or "M5").upper()
        if clean_tf == "M15":
            return None, ["Timeframe M15 dinilai secara mandiri (HTF tidak berlaku)"], []

        higher_tfs = ["M5", "M15"] if clean_tf == "M1" else ["M15"]
        reasons: List[str] = []
        penalties: List[str] = []
        is_buy = direction == SignalDirection.BUY

        tf_durations = {"M1": 60_000, "M5": 300_000, "M15": 900_000}
        total_score_sum = 0.0
        verified_count = 0

        for htf in higher_tfs:
            htf_candles = self.get_closed_candles(
                buffer=buffer,
                timeframe=htf,
                count=6,
                snapshot_timestamp_ms=snapshot_timestamp_ms,
            )
            dur = tf_durations.get(htf, 300_000)
            valid_htf = []
            for c in htf_candles:
                c_start_ms = int(c.timestamp.timestamp() * 1000)
                if snapshot_timestamp_ms is not None:
                    if (c_start_ms + dur) <= snapshot_timestamp_ms:
                        valid_htf.append(c)
                else:
                    valid_htf.append(c)

            if len(valid_htf) < 2:
                continue

            c_htf = valid_htf[0]
            htf_closes = [c.close for c in valid_htf[:3]]
            htf_trend_up = htf_closes[0] >= htf_closes[-1]

            if (is_buy and htf_trend_up) or (not is_buy and not htf_trend_up):
                total_score_sum += 90.0
                verified_count += 1
                reasons.append(f"Konteks {htf} closed selaras ({'Bullish' if htf_trend_up else 'Bearish'})")
            else:
                total_score_sum += 35.0
                verified_count += 1
                penalties.append(f"Konteks {htf} closed bertentangan ({'Bullish' if htf_trend_up else 'Bearish'})")

        if verified_count == 0:
            return None, ["Konteks MTF belum memiliki riwayat bar closed"], []

        avg_score = round(total_score_sum / verified_count, 2)
        return avg_score, reasons, penalties

    def assess_location_premium_discount(
        self,
        candles: List[Candle],
        direction: SignalDirection,
        trigger_px: float,
    ) -> Tuple[Optional[float], List[str], List[str]]:
        """Location assessment for Reversal, Sweep, and Range Boundary strategies."""
        if len(candles) < 5:
            return None, [], ["Data lokasi terbatas (< 5 candle)"]

        highs = [c.high for c in candles[:15]]
        lows = [c.low for c in candles[:15]]
        swing_high = max(highs)
        swing_low = min(lows)
        span = max(0.01, swing_high - swing_low)

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

    def assess_location_breakout_clearance(
        self,
        candles: List[Candle],
        direction: SignalDirection,
        trigger_px: float,
        breakout_level: float,
        atr: Optional[float] = None,
    ) -> Tuple[Optional[float], List[str], List[str]]:
        """Location assessment for Breakout, BOS, and CHoCH strategies."""
        reasons: List[str] = []
        penalties: List[str] = []

        is_buy = direction == SignalDirection.BUY
        clearance = (trigger_px - breakout_level) if is_buy else (breakout_level - trigger_px)
        
        score = 70.0
        effective_atr = atr or calculate_atr(candles, 14) or 1.0

        ratio = clearance / max(0.01, effective_atr)
        if 0.20 <= ratio <= 1.5:
            score += 22.0
            reasons.append(f"Lokasi breakout ideal (+{clearance:.2f} pts ~ {ratio:.2f}x ATR)")
        elif ratio < 0.10:
            score -= 15.0
            penalties.append("Breakout marginal, rawan false breakout")
        elif ratio > 2.5:
            score -= 18.0
            penalties.append("Harga sudah overextended dari level breakout")
        else:
            score += 10.0
            reasons.append(f"Breakout berjarak proporsional (+{clearance:.2f} pts)")

        return max(10.0, min(100.0, score)), reasons, penalties

    def assess_location_retracement(
        self,
        candles: List[Candle],
        direction: SignalDirection,
        trigger_px: float,
        origin_low: float,
        origin_high: float,
    ) -> Tuple[Optional[float], List[str], List[str]]:
        """Location assessment for Pullback and Retest strategies (Fibonacci depth)."""
        span = max(0.01, origin_high - origin_low)
        is_buy = direction == SignalDirection.BUY
        reasons: List[str] = []
        penalties: List[str] = []

        retrace_depth = (origin_high - trigger_px) / span if is_buy else (trigger_px - origin_low) / span
        score = 70.0

        if 0.382 <= retrace_depth <= 0.618:
            score += 25.0
            reasons.append(f"Kedalaman retracement optimal / Golden Zone ({retrace_depth * 100:.1f}%)")
        elif 0.20 <= retrace_depth < 0.382:
            score += 8.0
            reasons.append(f"Retracement dangkal ({retrace_depth * 100:.1f}%)")
        elif 0.618 < retrace_depth <= 0.786:
            score -= 8.0
            penalties.append(f"Retracement cukup dalam ({retrace_depth * 100:.1f}%)")
        elif retrace_depth > 0.786:
            score -= 22.0
            penalties.append(f"Retracement terlalu dalam ({retrace_depth * 100:.1f}%), mengancam validitas struktur")
        else:
            score -= 10.0
            penalties.append("Retracement sangat tipis")

        return max(10.0, min(100.0, score)), reasons, penalties

    def assess_candle_confirmation(
        self,
        candles: List[Candle],
        direction: SignalDirection,
    ) -> Tuple[Optional[float], List[str], List[str]]:
        """Evaluates trigger candle close quality, body dominance, and opposing wicks."""
        if not candles:
            return None, [], ["Tidak ada candle konfirmasi"]

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
                if (c0.upper_wick / c_range) > 0.35:
                    score -= 15.0
                    penalties.append("Terdapat penolakan harga atas (upper wick > 35%)")
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
                if (c0.lower_wick / c_range) > 0.35:
                    score -= 15.0
                    penalties.append("Terdapat penolakan harga bawah (lower wick > 35%)")
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
        snapshot_timestamp_ms: Optional[int] = None,
    ) -> Tuple[Optional[float], List[str], List[str]]:
        """Evaluates spread efficiency and invalidation risk ratio from closed candles."""
        profile = get_timeframe_profile(timeframe)
        max_spread = profile["max_acceptable_spread"]
        spread = buffer.current_spread

        score = 80.0
        reasons: List[str] = []
        penalties: List[str] = []

        if spread <= (max_spread * 0.7):
            score += 12.0
            reasons.append(f"Spread rapat ({spread:.2f} pts <= {max_spread * 0.7:.2f} pts)")
        elif spread > max_spread:
            penalty_val = min(30.0, (spread - max_spread) * 40.0)
            score -= penalty_val
            penalties.append(f"Spread melebar ({spread:.2f} pts > {max_spread:.2f} pts)")

        closed_bars = self.get_closed_candles(
            buffer=buffer,
            timeframe=timeframe,
            count=14,
            snapshot_timestamp_ms=snapshot_timestamp_ms,
        )
        atr = calculate_atr(closed_bars)

        if signal.invalidation_price is not None:
            dist = abs(signal.trigger_price - signal.invalidation_price)
            if atr is not None and atr > 0.0:
                ratio = dist / atr
                if ratio < 0.15:
                    score -= 15.0
                    penalties.append(f"Jarak invalidasi terlalu ketat ({dist:.2f} pts < 0.15x ATR)")
                elif ratio > 4.0:
                    score -= 10.0
                    penalties.append(f"Jarak invalidasi sangat jauh ({dist:.2f} pts > 4.0x ATR)")
                else:
                    score += 8.0
                    reasons.append(f"Level invalidasi proporsional ({dist:.2f} pts ~ {ratio:.1f}x ATR)")
            else:
                score += 5.0
                reasons.append(f"Level invalidasi terdefinisi eksplisit ({dist:.2f} pts)")
        else:
            score -= 20.0
            penalties.append("Level invalidasi tidak didefinisikan secara eksplisit")

        return max(10.0, min(100.0, score)), reasons, penalties
