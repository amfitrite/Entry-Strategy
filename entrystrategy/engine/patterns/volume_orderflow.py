"""Volume and Order Flow Entry Strategy Families (Pola 41 - 56).

Provides 16 institutional volume and order flow strategies for XAUUSD across M1, M5, and M15:
- 41: Relative Volume Expansion (RVOL)
- 42: Large Volume Bubble (Z-Score Anomaly)
- 43: Volume Climax Reversal
- 44: Volume Breakout
- 45: CVD Divergence (Estimated Delta Proxy)
- 46: CVD Reversal
- 47: CVD Trend Continuation
- 48: Bullish Absorption
- 49: Bearish Absorption
- 50: Delta Exhaustion
- 51: Bid/Ask Imbalance (Micro-Price Footprint Proxy)
- 52: Stacked Imbalance
- 53: POC Reclaim (Volume Profile)
- 54: VAH Rejection
- 55: VAL Rejection
- 56: HVN/LVN Reaction

DATA TRANSPARENCY:
- Observed tick volume from Dukascopy is tagged [OBSERVED_TICK_VOLUME].
- Delta and CVD derived from price decomposition are tagged [ESTIMATED_DELTA_PROXY].
- Footprint imbalance metrics are tagged [PROXY_PRICE_LEVEL_FOOTPRINT].
- Unfinished/unclosed candles are strictly ignored.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from entrystrategy.engine.base import BasePattern
from entrystrategy.core.models import EntrySignal, SignalDirection, PatternRole, SignalStatus
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.engine.volume_analytics import (
    calculate_rvol_and_zscore,
    estimate_candle_delta,
    calculate_cvd_series,
    calculate_volume_profile,
    calculate_footprint_imbalance,
)


def _get_timeframe_params(tf: str) -> Dict[str, float]:
    """Returns calibrated volatility and volume parameters per timeframe."""
    clean_tf = (tf or "M5").upper()
    if clean_tf == "M15":
        return {
            "atr_baseline": 4.5,
            "rvol_expansion_th": 1.8,
            "bubble_z_th": 2.0,
            "inval_buffer": 2.5,
            "max_age_sec": 900.0,
        }
    elif clean_tf == "M1":
        return {
            "atr_baseline": 1.2,
            "rvol_expansion_th": 2.2,
            "bubble_z_th": 2.4,
            "inval_buffer": 0.8,
            "max_age_sec": 60.0,
        }
    else:  # M5
        return {
            "atr_baseline": 2.5,
            "rvol_expansion_th": 2.0,
            "bubble_z_th": 2.2,
            "inval_buffer": 1.5,
            "max_age_sec": 300.0,
        }


# =====================================================================
# 41. Relative Volume Expansion
# =====================================================================
class RelativeVolumeExpansionPattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=41,
            name="Relative Volume Expansion",
            category="Volume",
            description="Ekspansi volume relatif signifikan (RVOL >= 1.8x - 2.2x) yang mengonfirmasi candle impulsif terarah.",
            role=PatternRole.ENTRY,
            phenomenon="Partisipasi likuiditas abnormal [OBSERVED_TICK_VOLUME] mengonfirmasi inisiasi pergerakan harga.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(25)
        if len(candles) < 21:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        vol_info = calculate_rvol_and_zscore(candles, lookback=20)
        rvol = vol_info["rvol"]

        if rvol < params["rvol_expansion_th"]:
            return None

        c_rng = max(c0.high - c0.low, 0.01)
        body = abs(c0.close - c0.open)

        # Require meaningful body expansion (>= 55% of range)
        if body / c_rng < 0.55:
            return None

        direction = SignalDirection.NONE
        reasons = []

        if c0.close > c0.open and (c0.close - c0.low) / c_rng >= 0.70:
            direction = SignalDirection.BUY
            invalidation = round(c0.low - params["inval_buffer"] * 0.25, 2)
            reasons.append(f"[OBSERVED_TICK_VOLUME] RVOL {rvol:.2f}x melebihi threshold ({params['rvol_expansion_th']}x)")
            reasons.append(f"Dominasi body bullish ({body / c_rng * 100:.0f}% dari range) dengan close dekat high")
        elif c0.close < c0.open and (c0.high - c0.close) / c_rng >= 0.70:
            direction = SignalDirection.SELL
            invalidation = round(c0.high + params["inval_buffer"] * 0.25, 2)
            reasons.append(f"[OBSERVED_TICK_VOLUME] RVOL {rvol:.2f}x melebihi threshold ({params['rvol_expansion_th']}x)")
            reasons.append(f"Dominasi body bearish ({body / c_rng * 100:.0f}% dari range) dengan close dekat low")

        if direction == SignalDirection.NONE:
            return None

        if self._is_candle_deduplicated(c0.timestamp, direction):
            return None
        self.last_candle_ts = c0.timestamp
        self.last_direction = direction

        now_ms = buffer.current_time_ms
        return EntrySignal(
            pattern_id=self.pattern_id,
            family_name=self.name,
            direction=direction,
            reference_price=c0.close,
            trigger_price=c0.close,
            invalidation_price=invalidation,
            execution_price=buffer.get_execution_price(direction, c0.close),
            pattern_role=self.role,
            status=SignalStatus.ACTIVE,
            status_reason="Kondisi Relative Volume Expansion terpenuhi",
            phenomenon=self.phenomenon,
            timestamp_ms=now_ms,
            event_id=f"rvol:{self.pattern_id}:{c0.timestamp.isoformat()}:{direction.value}",
            reasons=reasons,
            metrics={"rvol": rvol, "current_vol": vol_info["current_vol"], "baseline_mean": vol_info["baseline_mean"]},
            max_age_sec=params["max_age_sec"],
        )


# =====================================================================
# 42. Large Volume Bubble
# =====================================================================
class LargeVolumeBubblePattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=42,
            name="Large Volume Bubble",
            category="Order Flow",
            description="Lonjakan volume ekstrim secara statistik (Z-Score >= 2.2) pada level breakout atau pengujian struktur swing.",
            role=PatternRole.ENTRY,
            phenomenon="Konsentrasi likuiditas masif [OBSERVED_TICK_VOLUME] pada titik harga kunci memicu dorongan ekspansi.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(25)
        if len(candles) < 21:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        vol_info = calculate_rvol_and_zscore(candles, lookback=20)
        z_score = vol_info["z_score"]

        if z_score < params["bubble_z_th"]:
            return None

        recent_highs = [c.high for c in candles[1:11]]
        recent_lows = [c.low for c in candles[1:11]]
        prior_max_h = max(recent_highs) if recent_highs else c0.high
        prior_min_l = min(recent_lows) if recent_lows else c0.low

        direction = SignalDirection.NONE
        reasons = []

        if c0.close > c0.open and (c0.close >= prior_max_h or c0.low <= prior_min_l):
            direction = SignalDirection.BUY
            invalidation = round(c0.low - params["inval_buffer"] * 0.3, 2)
            reasons.append(f"[OBSERVED_TICK_VOLUME] Volume Bubble Z-Score {z_score:.2f} (>= {params['bubble_z_th']})")
            reasons.append("Bubble terkonfirmasi pada pengujian struktur swing kunci dengan reaksi bullish")
        elif c0.close < c0.open and (c0.close <= prior_min_l or c0.high >= prior_max_h):
            direction = SignalDirection.SELL
            invalidation = round(c0.high + params["inval_buffer"] * 0.3, 2)
            reasons.append(f"[OBSERVED_TICK_VOLUME] Volume Bubble Z-Score {z_score:.2f} (>= {params['bubble_z_th']})")
            reasons.append("Bubble terkonfirmasi pada pengujian struktur swing kunci dengan reaksi bearish")

        if direction == SignalDirection.NONE:
            return None

        if self._is_candle_deduplicated(c0.timestamp, direction):
            return None
        self.last_candle_ts = c0.timestamp
        self.last_direction = direction

        now_ms = buffer.current_time_ms
        return EntrySignal(
            pattern_id=self.pattern_id,
            family_name=self.name,
            direction=direction,
            reference_price=c0.close,
            trigger_price=c0.close,
            invalidation_price=invalidation,
            execution_price=buffer.get_execution_price(direction, c0.close),
            pattern_role=self.role,
            status=SignalStatus.ACTIVE,
            status_reason="Kondisi Large Volume Bubble terpenuhi",
            phenomenon=self.phenomenon,
            timestamp_ms=now_ms,
            event_id=f"bubble:{self.pattern_id}:{c0.timestamp.isoformat()}:{direction.value}",
            reasons=reasons,
            metrics={"z_score": z_score, "rvol": vol_info["rvol"], "current_vol": vol_info["current_vol"]},
            max_age_sec=params["max_age_sec"],
        )


# =====================================================================
# 43. Volume Climax Reversal
# =====================================================================
class VolumeClimaxReversalPattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=43,
            name="Volume Climax Reversal",
            category="Volume",
            description="Volume klimaks tertinggi (>= 2.5x baseline) di ekstrim tren disertai rejection wick panjang (>= 40% range).",
            role=PatternRole.ENTRY,
            phenomenon="Keletihan agresor tren dan penyerapan likuiditas oleh pemain institusi berlawanan arah [OBSERVED_TICK_VOLUME].",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(25)
        if len(candles) < 21:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        vol_info = calculate_rvol_and_zscore(candles, lookback=20)
        rvol = vol_info["rvol"]

        # Ultra-high climax threshold >= 2.5x
        if rvol < 2.4:
            return None

        c_rng = max(c0.high - c0.low, 0.01)
        lower_wick = max(0.0, min(c0.open, c0.close) - c0.low)
        upper_wick = max(0.0, c0.high - max(c0.open, c0.close))

        recent_lows = [c.low for c in candles[1:11]]
        recent_highs = [c.high for c in candles[1:11]]
        is_new_low = c0.low <= min(recent_lows) if recent_lows else False
        is_new_high = c0.high >= max(recent_highs) if recent_highs else False

        direction = SignalDirection.NONE
        reasons = []

        if is_new_low and (lower_wick / c_rng) >= 0.40 and c0.close >= (c0.high + c0.low) / 2.0:
            direction = SignalDirection.BUY
            invalidation = round(c0.low - params["inval_buffer"] * 0.25, 2)
            reasons.append(f"[OBSERVED_TICK_VOLUME] Climax volume {rvol:.2f}x di new low lokal")
            reasons.append(f"Penolakan bawah kuat (Lower wick {lower_wick / c_rng * 100:.0f}% range), penutupan di paruh atas")
        elif is_new_high and (upper_wick / c_rng) >= 0.40 and c0.close <= (c0.high + c0.low) / 2.0:
            direction = SignalDirection.SELL
            invalidation = round(c0.high + params["inval_buffer"] * 0.25, 2)
            reasons.append(f"[OBSERVED_TICK_VOLUME] Climax volume {rvol:.2f}x di new high lokal")
            reasons.append(f"Penolakan atas kuat (Upper wick {upper_wick / c_rng * 100:.0f}% range), penutupan di paruh bawah")

        if direction == SignalDirection.NONE:
            return None

        if self._is_candle_deduplicated(c0.timestamp, direction):
            return None
        self.last_candle_ts = c0.timestamp
        self.last_direction = direction

        now_ms = buffer.current_time_ms
        return EntrySignal(
            pattern_id=self.pattern_id,
            family_name=self.name,
            direction=direction,
            reference_price=c0.close,
            trigger_price=c0.close,
            invalidation_price=invalidation,
            execution_price=buffer.get_execution_price(direction, c0.close),
            pattern_role=self.role,
            status=SignalStatus.ACTIVE,
            status_reason="Kondisi Volume Climax Reversal terpenuhi",
            phenomenon=self.phenomenon,
            timestamp_ms=now_ms,
            event_id=f"climax:{self.pattern_id}:{c0.timestamp.isoformat()}:{direction.value}",
            reasons=reasons,
            metrics={"rvol": rvol, "lower_wick_ratio": lower_wick / c_rng, "upper_wick_ratio": upper_wick / c_rng},
            max_age_sec=params["max_age_sec"],
        )


# =====================================================================
# 44. Volume Breakout
# =====================================================================
class VolumeBreakoutPattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=44,
            name="Volume Breakout",
            category="Volume",
            description="Penembusan batas rentang 20-bar Donchian yang divalidasi oleh ekspansi volume (RVOL >= 1.6x).",
            role=PatternRole.ENTRY,
            phenomenon="Penembusan level rentang konsolidasi yang didukung konfirmasi likuiditas baru [OBSERVED_TICK_VOLUME].",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(25)
        if len(candles) < 21:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        vol_info = calculate_rvol_and_zscore(candles, lookback=20)
        rvol = vol_info["rvol"]

        if rvol < 1.6:
            return None

        range_highs = [c.high for c in candles[1:21]]
        range_lows = [c.low for c in candles[1:21]]
        donchian_high = max(range_highs)
        donchian_low = min(range_lows)

        direction = SignalDirection.NONE
        reasons = []

        if c0.close > donchian_high:
            direction = SignalDirection.BUY
            invalidation = round(donchian_high - params["inval_buffer"] * 0.4, 2)
            reasons.append(f"[OBSERVED_TICK_VOLUME] Volume breakout RVOL {rvol:.2f}x mengonfirmasi tembus Donchian High {donchian_high:.2f}")
        elif c0.close < donchian_low:
            direction = SignalDirection.SELL
            invalidation = round(donchian_low + params["inval_buffer"] * 0.4, 2)
            reasons.append(f"[OBSERVED_TICK_VOLUME] Volume breakout RVOL {rvol:.2f}x mengonfirmasi tembus Donchian Low {donchian_low:.2f}")

        if direction == SignalDirection.NONE:
            return None

        if self._is_candle_deduplicated(c0.timestamp, direction):
            return None
        self.last_candle_ts = c0.timestamp
        self.last_direction = direction

        now_ms = buffer.current_time_ms
        return EntrySignal(
            pattern_id=self.pattern_id,
            family_name=self.name,
            direction=direction,
            reference_price=c0.close,
            trigger_price=c0.close,
            invalidation_price=invalidation,
            execution_price=buffer.get_execution_price(direction, c0.close),
            pattern_role=self.role,
            status=SignalStatus.ACTIVE,
            status_reason="Kondisi Volume Breakout terpenuhi",
            phenomenon=self.phenomenon,
            timestamp_ms=now_ms,
            event_id=f"volbreak:{self.pattern_id}:{c0.timestamp.isoformat()}:{direction.value}",
            reasons=reasons,
            metrics={"rvol": rvol, "donchian_high": donchian_high, "donchian_low": donchian_low},
            max_age_sec=params["max_age_sec"],
        )


# =====================================================================
# 45. CVD Divergence
# =====================================================================
class CVDDivergencePattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=45,
            name="CVD Divergence",
            category="Order Flow",
            description="Divergensi arah antara pergerakan harga dan Cumulative Volume Delta (CVD) [ESTIMATED_DELTA_PROXY].",
            role=PatternRole.ENTRY,
            phenomenon="[ESTIMATED_DELTA_PROXY] Ketidakselarasan harga baru dan delta bersih, menandakan kelemahan agresi dan penyerapan pasif.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(25)
        if len(candles) < 15:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        cvd_series = calculate_cvd_series(candles, count=15)
        if len(cvd_series) < 15:
            return None

        # cvd_series is oldest to newest, so cvd_series[-1] is c0
        cvd_current = cvd_series[-1]
        prior_cvd_min = min(cvd_series[:-3])
        prior_cvd_max = max(cvd_series[:-3])

        recent_lows = [c.low for c in candles[1:11]]
        recent_highs = [c.high for c in candles[1:11]]
        prior_low = min(recent_lows)
        prior_high = max(recent_highs)

        direction = SignalDirection.NONE
        reasons = []

        # Bullish Divergence: Price creates Lower Low, but CVD creates Higher Low
        if c0.low < prior_low and cvd_current > prior_cvd_min and c0.close > c0.open:
            direction = SignalDirection.BUY
            invalidation = round(c0.low - params["inval_buffer"] * 0.3, 2)
            reasons.append(f"[ESTIMATED_DELTA_PROXY] Bullish CVD Divergence: Harga tembus new low ({c0.low:.2f} < {prior_low:.2f}) tapi CVD membentuk Higher Low")
            reasons.append("Seller agresif kehilangan momentum, penyerapan order oleh pembeli pasif")
        # Bearish Divergence: Price creates Higher High, but CVD creates Lower High
        elif c0.high > prior_high and cvd_current < prior_cvd_max and c0.close < c0.open:
            direction = SignalDirection.SELL
            invalidation = round(c0.high + params["inval_buffer"] * 0.3, 2)
            reasons.append(f"[ESTIMATED_DELTA_PROXY] Bearish CVD Divergence: Harga tembus new high ({c0.high:.2f} > {prior_high:.2f}) tapi CVD membentuk Lower High")
            reasons.append("Buyer agresif kehilangan momentum, penyerapan order oleh penjual pasif")

        if direction == SignalDirection.NONE:
            return None

        if self._is_candle_deduplicated(c0.timestamp, direction):
            return None
        self.last_candle_ts = c0.timestamp
        self.last_direction = direction

        now_ms = buffer.current_time_ms
        return EntrySignal(
            pattern_id=self.pattern_id,
            family_name=self.name,
            direction=direction,
            reference_price=c0.close,
            trigger_price=c0.close,
            invalidation_price=invalidation,
            execution_price=buffer.get_execution_price(direction, c0.close),
            pattern_role=self.role,
            status=SignalStatus.ACTIVE,
            status_reason="Kondisi CVD Divergence terpenuhi",
            phenomenon=self.phenomenon,
            timestamp_ms=now_ms,
            event_id=f"cvddiv:{self.pattern_id}:{c0.timestamp.isoformat()}:{direction.value}",
            reasons=reasons,
            metrics={"cvd_current": cvd_current, "prior_cvd_min": prior_cvd_min, "prior_cvd_max": prior_cvd_max},
            max_age_sec=params["max_age_sec"],
        )


# =====================================================================
# 46. CVD Reversal
# =====================================================================
class CVDReversalPattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=46,
            name="CVD Reversal",
            category="Order Flow",
            description="Pembalikan tajam net delta candle (>= 1.5x rata-rata delta) setelah 3+ candle delta searah [ESTIMATED_DELTA_PROXY].",
            role=PatternRole.ENTRY,
            phenomenon="[ESTIMATED_DELTA_PROXY] Pergeseran mendadak dominasi inisiatif beli/jual di pasar.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(15)
        if len(candles) < 6:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        deltas = [estimate_candle_delta(c)["est_delta"] for c in candles[:6]]
        avg_abs_delta = sum(abs(d) for d in deltas[1:]) / max(len(deltas[1:]), 1)

        direction = SignalDirection.NONE
        reasons = []

        # Bullish CVD Reversal: prior 3 candles had negative deltas, c0 prints huge positive delta
        if all(d < 0 for d in deltas[1:4]) and deltas[0] >= 1.5 * max(avg_abs_delta, 1.0) and c0.close > c0.open:
            direction = SignalDirection.BUY
            invalidation = round(c0.low - params["inval_buffer"] * 0.25, 2)
            reasons.append(f"[ESTIMATED_DELTA_PROXY] Bullish CVD Reversal: Delta berbalik positif tajam (+{deltas[0]:.1f}) setelah 3 candle delta negatif")
        # Bearish CVD Reversal: prior 3 candles had positive deltas, c0 prints huge negative delta
        elif all(d > 0 for d in deltas[1:4]) and deltas[0] <= -1.5 * max(avg_abs_delta, 1.0) and c0.close < c0.open:
            direction = SignalDirection.SELL
            invalidation = round(c0.high + params["inval_buffer"] * 0.25, 2)
            reasons.append(f"[ESTIMATED_DELTA_PROXY] Bearish CVD Reversal: Delta berbalik negatif tajam ({deltas[0]:.1f}) setelah 3 candle delta positif")

        if direction == SignalDirection.NONE:
            return None

        if self._is_candle_deduplicated(c0.timestamp, direction):
            return None
        self.last_candle_ts = c0.timestamp
        self.last_direction = direction

        now_ms = buffer.current_time_ms
        return EntrySignal(
            pattern_id=self.pattern_id,
            family_name=self.name,
            direction=direction,
            reference_price=c0.close,
            trigger_price=c0.close,
            invalidation_price=invalidation,
            execution_price=buffer.get_execution_price(direction, c0.close),
            pattern_role=self.role,
            status=SignalStatus.ACTIVE,
            status_reason="Kondisi CVD Reversal terpenuhi",
            phenomenon=self.phenomenon,
            timestamp_ms=now_ms,
            event_id=f"cvdrev:{self.pattern_id}:{c0.timestamp.isoformat()}:{direction.value}",
            reasons=reasons,
            metrics={"delta_0": deltas[0], "avg_abs_delta": avg_abs_delta},
            max_age_sec=params["max_age_sec"],
        )


# =====================================================================
# 47. CVD Trend Continuation
# =====================================================================
class CVDTrendContinuationPattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=47,
            name="CVD Trend Continuation",
            category="Order Flow",
            description="Konfirmasi kelanjutan tren: breakout harga didukung penuh oleh lonjakan CVD searah [ESTIMATED_DELTA_PROXY].",
            role=PatternRole.ENTRY,
            phenomenon="[ESTIMATED_DELTA_PROXY] Inisiator pasar agresif terus menyuntikkan volume searah tren utama.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(20)
        if len(candles) < 12:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        cvd_series = calculate_cvd_series(candles, count=10)
        if len(cvd_series) < 10:
            return None

        d0_info = estimate_candle_delta(c0)
        recent_highs = [c.high for c in candles[1:10]]
        recent_lows = [c.low for c in candles[1:10]]

        direction = SignalDirection.NONE
        reasons = []

        # Bullish Continuation: Breakout above recent high and CVD ascending
        if c0.close > max(recent_highs) and d0_info["est_delta"] > 0 and cvd_series[-1] > cvd_series[-3] > cvd_series[-5]:
            direction = SignalDirection.BUY
            invalidation = round(c0.low - params["inval_buffer"] * 0.3, 2)
            reasons.append(f"[ESTIMATED_DELTA_PROXY] CVD Trend Continuation: Breakout high didukung delta positif (+{d0_info['est_delta']:.1f}) dan CVD konsisten naik")
        # Bearish Continuation: Breakdown below recent low and CVD descending
        elif c0.close < min(recent_lows) and d0_info["est_delta"] < 0 and cvd_series[-1] < cvd_series[-3] < cvd_series[-5]:
            direction = SignalDirection.SELL
            invalidation = round(c0.high + params["inval_buffer"] * 0.3, 2)
            reasons.append(f"[ESTIMATED_DELTA_PROXY] CVD Trend Continuation: Breakdown low didukung delta negatif ({d0_info['est_delta']:.1f}) dan CVD konsisten turun")

        if direction == SignalDirection.NONE:
            return None

        if self._is_candle_deduplicated(c0.timestamp, direction):
            return None
        self.last_candle_ts = c0.timestamp
        self.last_direction = direction

        now_ms = buffer.current_time_ms
        return EntrySignal(
            pattern_id=self.pattern_id,
            family_name=self.name,
            direction=direction,
            reference_price=c0.close,
            trigger_price=c0.close,
            invalidation_price=invalidation,
            execution_price=buffer.get_execution_price(direction, c0.close),
            pattern_role=self.role,
            status=SignalStatus.ACTIVE,
            status_reason="Kondisi CVD Trend Continuation terpenuhi",
            phenomenon=self.phenomenon,
            timestamp_ms=now_ms,
            event_id=f"cvdcont:{self.pattern_id}:{c0.timestamp.isoformat()}:{direction.value}",
            reasons=reasons,
            metrics={"delta_0": d0_info["est_delta"], "cvd_current": cvd_series[-1]},
            max_age_sec=params["max_age_sec"],
        )


# =====================================================================
# 48. Bullish Absorption
# =====================================================================
class BullishAbsorptionPattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=48,
            name="Bullish Absorption",
            category="Order Flow",
            description="Penyerapan volume jual tinggi di zona support oleh pembeli pasif, membentuk penolakan bawah [PROXY_ABSORPTION].",
            role=PatternRole.ENTRY,
            phenomenon="[PROXY_ABSORPTION] [ESTIMATED_DELTA_PROXY] Seller agresif gagal menekan harga turun karena diserap tuntas oleh limit buyer pasif.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(25)
        if len(candles) < 21:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        vol_info = calculate_rvol_and_zscore(candles, lookback=20)
        rvol = vol_info["rvol"]

        if rvol < 1.7:
            return None

        c_rng = max(c0.high - c0.low, 0.01)
        lower_wick = max(0.0, min(c0.open, c0.close) - c0.low)
        recent_lows = [c.low for c in candles[1:11]]
        prior_support = min(recent_lows) if recent_lows else c0.low

        # Tested near or swept below support, but closed in upper half with large lower wick
        if c0.low <= prior_support + (params["inval_buffer"] * 0.2) and (lower_wick / c_rng) >= 0.35 and c0.close >= (c0.high + c0.low) / 2.0:
            invalidation = round(c0.low - params["inval_buffer"] * 0.25, 2)
            direction = SignalDirection.BUY
            reasons = [
                f"[PROXY_ABSORPTION] Bullish Absorption: Volume tinggi RVOL {rvol:.2f}x pada pengujian support {prior_support:.2f}",
                f"Tekanan jual masif diserap tuntas, membentuk lower wick {lower_wick / c_rng * 100:.0f}%",
            ]

            if self._is_candle_deduplicated(c0.timestamp, direction):
                return None
            self.last_candle_ts = c0.timestamp
            self.last_direction = direction

            now_ms = buffer.current_time_ms
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=direction,
                reference_price=c0.close,
                trigger_price=c0.close,
                invalidation_price=invalidation,
                execution_price=buffer.get_execution_price(direction, c0.close),
                pattern_role=self.role,
                status=SignalStatus.ACTIVE,
                status_reason="Kondisi Bullish Absorption terpenuhi",
                phenomenon=self.phenomenon,
                timestamp_ms=now_ms,
                event_id=f"bullabs:{self.pattern_id}:{c0.timestamp.isoformat()}:BUY",
                reasons=reasons,
                metrics={"rvol": rvol, "lower_wick_ratio": lower_wick / c_rng, "prior_support": prior_support},
                max_age_sec=params["max_age_sec"],
            )
        return None


# =====================================================================
# 49. Bearish Absorption
# =====================================================================
class BearishAbsorptionPattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=49,
            name="Bearish Absorption",
            category="Order Flow",
            description="Penyerapan volume beli tinggi di zona resistance oleh penjual pasif, membentuk penolakan atas [PROXY_ABSORPTION].",
            role=PatternRole.ENTRY,
            phenomenon="[PROXY_ABSORPTION] [ESTIMATED_DELTA_PROXY] Buyer agresif gagal mendongkrak harga naik karena diserap tuntas oleh limit seller pasif.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(25)
        if len(candles) < 21:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        vol_info = calculate_rvol_and_zscore(candles, lookback=20)
        rvol = vol_info["rvol"]

        if rvol < 1.7:
            return None

        c_rng = max(c0.high - c0.low, 0.01)
        upper_wick = max(0.0, c0.high - max(c0.open, c0.close))
        recent_highs = [c.high for c in candles[1:11]]
        prior_resistance = max(recent_highs) if recent_highs else c0.high

        # Tested near or swept above resistance, but closed in lower half with large upper wick
        if c0.high >= prior_resistance - (params["inval_buffer"] * 0.2) and (upper_wick / c_rng) >= 0.35 and c0.close <= (c0.high + c0.low) / 2.0:
            invalidation = round(c0.high + params["inval_buffer"] * 0.25, 2)
            direction = SignalDirection.SELL
            reasons = [
                f"[PROXY_ABSORPTION] Bearish Absorption: Volume tinggi RVOL {rvol:.2f}x pada pengujian resistance {prior_resistance:.2f}",
                f"Tekanan beli masif diserap tuntas, membentuk upper wick {upper_wick / c_rng * 100:.0f}%",
            ]

            if self._is_candle_deduplicated(c0.timestamp, direction):
                return None
            self.last_candle_ts = c0.timestamp
            self.last_direction = direction

            now_ms = buffer.current_time_ms
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=direction,
                reference_price=c0.close,
                trigger_price=c0.close,
                invalidation_price=invalidation,
                execution_price=buffer.get_execution_price(direction, c0.close),
                pattern_role=self.role,
                status=SignalStatus.ACTIVE,
                status_reason="Kondisi Bearish Absorption terpenuhi",
                phenomenon=self.phenomenon,
                timestamp_ms=now_ms,
                event_id=f"bearabs:{self.pattern_id}:{c0.timestamp.isoformat()}:SELL",
                reasons=reasons,
                metrics={"rvol": rvol, "upper_wick_ratio": upper_wick / c_rng, "prior_resistance": prior_resistance},
                max_age_sec=params["max_age_sec"],
            )
        return None


# =====================================================================
# 50. Delta Exhaustion
# =====================================================================
class DeltaExhaustionPattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=50,
            name="Delta Exhaustion",
            category="Order Flow",
            description="Penurunan drastis net delta (|Delta|/Vol <= 0.15) saat menguji ekstrim harga, menandakan hilangnya agresor [ESTIMATED_DELTA_PROXY].",
            role=PatternRole.ENTRY,
            phenomenon="[ESTIMATED_DELTA_PROXY] Pergerakan harga melambat dan terhenti akibat ketiadaan inisiator agresif lanjutan.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(20)
        if len(candles) < 12:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        d0_info = estimate_candle_delta(c0)

        # Delta ratio near zero (|Delta| / Vol <= 0.15) despite noticeable price range
        c_rng = max(c0.high - c0.low, 0.01)
        if c_rng < params["atr_baseline"] * 0.7:
            return None

        if abs(d0_info["delta_ratio"]) > 0.15:
            return None

        recent_lows = [c.low for c in candles[1:10]]
        recent_highs = [c.high for c in candles[1:10]]

        direction = SignalDirection.NONE
        reasons = []

        if c0.low <= min(recent_lows):
            direction = SignalDirection.BUY
            invalidation = round(c0.low - params["inval_buffer"] * 0.25, 2)
            reasons.append(f"[ESTIMATED_DELTA_PROXY] Delta Exhaustion Seller: Delta ratio menciut ke {d0_info['delta_ratio'] * 100:.1f}% di titik terendah")
        elif c0.high >= max(recent_highs):
            direction = SignalDirection.SELL
            invalidation = round(c0.high + params["inval_buffer"] * 0.25, 2)
            reasons.append(f"[ESTIMATED_DELTA_PROXY] Delta Exhaustion Buyer: Delta ratio menciut ke {d0_info['delta_ratio'] * 100:.1f}% di titik tertinggi")

        if direction == SignalDirection.NONE:
            return None

        if self._is_candle_deduplicated(c0.timestamp, direction):
            return None
        self.last_candle_ts = c0.timestamp
        self.last_direction = direction

        now_ms = buffer.current_time_ms
        return EntrySignal(
            pattern_id=self.pattern_id,
            family_name=self.name,
            direction=direction,
            reference_price=c0.close,
            trigger_price=c0.close,
            invalidation_price=invalidation,
            execution_price=buffer.get_execution_price(direction, c0.close),
            pattern_role=self.role,
            status=SignalStatus.ACTIVE,
            status_reason="Kondisi Delta Exhaustion terpenuhi",
            phenomenon=self.phenomenon,
            timestamp_ms=now_ms,
            event_id=f"deltaex:{self.pattern_id}:{c0.timestamp.isoformat()}:{direction.value}",
            reasons=reasons,
            metrics={"delta_ratio": d0_info["delta_ratio"], "range": c_rng},
            max_age_sec=params["max_age_sec"],
        )


# =====================================================================
# 51. Bid/Ask Imbalance
# =====================================================================
class BidAskImbalancePattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=51,
            name="Bid/Ask Imbalance",
            category="Order Flow",
            description="Ketidakseimbangan buying vs selling (>= 3.0x) pada 2+ level harga mikro candle [PROXY_PRICE_LEVEL_FOOTPRINT].",
            role=PatternRole.ENTRY,
            phenomenon="[PROXY_PRICE_LEVEL_FOOTPRINT] Dominasi sepihak penawaran vs permintaan pada eksekusi level harga mikro.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(15)
        if len(candles) < 10:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        fp_info = calculate_footprint_imbalance(c0, bin_size=0.25, imbalance_ratio=3.0)

        direction = SignalDirection.NONE
        reasons = []

        if fp_info["buy_imbalance_count"] >= 2 and c0.close > c0.open:
            direction = SignalDirection.BUY
            invalidation = round(c0.low - params["inval_buffer"] * 0.25, 2)
            reasons.append(f"[PROXY_PRICE_LEVEL_FOOTPRINT] Terdeteksi {fp_info['buy_imbalance_count']} level Buying Imbalance (>= 3.0x)")
        elif fp_info["sell_imbalance_count"] >= 2 and c0.close < c0.open:
            direction = SignalDirection.SELL
            invalidation = round(c0.high + params["inval_buffer"] * 0.25, 2)
            reasons.append(f"[PROXY_PRICE_LEVEL_FOOTPRINT] Terdeteksi {fp_info['sell_imbalance_count']} level Selling Imbalance (>= 3.0x)")

        if direction == SignalDirection.NONE:
            return None

        if self._is_candle_deduplicated(c0.timestamp, direction):
            return None
        self.last_candle_ts = c0.timestamp
        self.last_direction = direction

        now_ms = buffer.current_time_ms
        return EntrySignal(
            pattern_id=self.pattern_id,
            family_name=self.name,
            direction=direction,
            reference_price=c0.close,
            trigger_price=c0.close,
            invalidation_price=invalidation,
            execution_price=buffer.get_execution_price(direction, c0.close),
            pattern_role=self.role,
            status=SignalStatus.ACTIVE,
            status_reason="Kondisi Bid/Ask Imbalance terpenuhi",
            phenomenon=self.phenomenon,
            timestamp_ms=now_ms,
            event_id=f"imbal:{self.pattern_id}:{c0.timestamp.isoformat()}:{direction.value}",
            reasons=reasons,
            metrics={"buy_imbalance_count": fp_info["buy_imbalance_count"], "sell_imbalance_count": fp_info["sell_imbalance_count"]},
            max_age_sec=params["max_age_sec"],
        )


# =====================================================================
# 52. Stacked Imbalance
# =====================================================================
class StackedImbalancePattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=52,
            name="Stacked Imbalance",
            category="Order Flow",
            description="Imbalance bertumpuk pada 3+ level harga berurutan membentuk zona inisiasi institusional [PROXY_PRICE_LEVEL_FOOTPRINT].",
            role=PatternRole.ENTRY,
            phenomenon="[PROXY_PRICE_LEVEL_FOOTPRINT] Inisiasi agresif beruntun di berbagai level harga mikro menciptakan zona momentum tak tertandingi.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(15)
        if len(candles) < 10:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        fp_info = calculate_footprint_imbalance(c0, bin_size=0.25, imbalance_ratio=3.0)

        direction = SignalDirection.NONE
        reasons = []

        if fp_info["has_stacked_buy"] and c0.close > c0.open:
            direction = SignalDirection.BUY
            invalidation = round(min(fp_info["stacked_buy_levels"]) - params["inval_buffer"] * 0.2, 2)
            reasons.append(f"[PROXY_PRICE_LEVEL_FOOTPRINT] Stacked Buying Imbalance ({fp_info['max_stacked_buy']} level berurutan)")
            reasons.append(f"Penutupan candle ({c0.close:.2f}) bertahan di atas zona stacked imbalance")
        elif fp_info["has_stacked_sell"] and c0.close < c0.open:
            direction = SignalDirection.SELL
            invalidation = round(max(fp_info["stacked_sell_levels"]) + params["inval_buffer"] * 0.2, 2)
            reasons.append(f"[PROXY_PRICE_LEVEL_FOOTPRINT] Stacked Selling Imbalance ({fp_info['max_stacked_sell']} level berurutan)")
            reasons.append(f"Penutupan candle ({c0.close:.2f}) bertahan di bawah zona stacked imbalance")

        if direction == SignalDirection.NONE:
            return None

        if self._is_candle_deduplicated(c0.timestamp, direction):
            return None
        self.last_candle_ts = c0.timestamp
        self.last_direction = direction

        now_ms = buffer.current_time_ms
        return EntrySignal(
            pattern_id=self.pattern_id,
            family_name=self.name,
            direction=direction,
            reference_price=c0.close,
            trigger_price=c0.close,
            invalidation_price=invalidation,
            execution_price=buffer.get_execution_price(direction, c0.close),
            pattern_role=self.role,
            status=SignalStatus.ACTIVE,
            status_reason="Kondisi Stacked Imbalance terpenuhi",
            phenomenon=self.phenomenon,
            timestamp_ms=now_ms,
            event_id=f"stacked:{self.pattern_id}:{c0.timestamp.isoformat()}:{direction.value}",
            reasons=reasons,
            metrics={"max_stacked_buy": fp_info["max_stacked_buy"], "max_stacked_sell": fp_info["max_stacked_sell"]},
            max_age_sec=params["max_age_sec"],
        )


# =====================================================================
# 53. POC Reclaim
# =====================================================================
class POCReclaimPattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=53,
            name="POC Reclaim",
            category="Volume Profile",
            description="Reclaim kembali Point of Control (POC) setelah deviasi harga di luar konsentrasi volume tertinggi.",
            role=PatternRole.ENTRY,
            phenomenon="Rejection terhadap harga ekstrem di luar konsentrasi likuiditas POC dan kembali ke fair value [OBSERVED_TICK_VOLUME].",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(30)
        if len(candles) < 25:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        # Profile calculated on preceding candles (excluding c0 to prevent look-ahead)
        vp_info = calculate_volume_profile(candles[1:25], bin_size=0.25)
        poc = vp_info["poc_price"]

        direction = SignalDirection.NONE
        reasons = []

        # Bullish POC Reclaim: c0 dipped below POC but closed back above POC
        if c0.low < poc and c0.close > poc and c0.close > c0.open:
            direction = SignalDirection.BUY
            invalidation = round(c0.low - params["inval_buffer"] * 0.25, 2)
            reasons.append(f"[OBSERVED_TICK_VOLUME] Bullish POC Reclaim: Harga menyapu level POC {poc:.2f} lalu ditutup kembali di atasnya ({c0.close:.2f})")
        # Bearish POC Reclaim: c0 spiked above POC but closed back below POC
        elif c0.high > poc and c0.close < poc and c0.close < c0.open:
            direction = SignalDirection.SELL
            invalidation = round(c0.high + params["inval_buffer"] * 0.25, 2)
            reasons.append(f"[OBSERVED_TICK_VOLUME] Bearish POC Reclaim: Harga menyapu level POC {poc:.2f} lalu ditutup kembali di bawahnya ({c0.close:.2f})")

        if direction == SignalDirection.NONE:
            return None

        if self._is_candle_deduplicated(c0.timestamp, direction):
            return None
        self.last_candle_ts = c0.timestamp
        self.last_direction = direction

        now_ms = buffer.current_time_ms
        return EntrySignal(
            pattern_id=self.pattern_id,
            family_name=self.name,
            direction=direction,
            reference_price=poc,
            trigger_price=c0.close,
            invalidation_price=invalidation,
            execution_price=buffer.get_execution_price(direction, c0.close),
            pattern_role=self.role,
            status=SignalStatus.ACTIVE,
            status_reason="Kondisi POC Reclaim terpenuhi",
            phenomenon=self.phenomenon,
            timestamp_ms=now_ms,
            event_id=f"pocreclaim:{self.pattern_id}:{c0.timestamp.isoformat()}:{direction.value}",
            reasons=reasons,
            metrics={"poc_price": poc, "close": c0.close},
            max_age_sec=params["max_age_sec"],
        )


# =====================================================================
# 54. VAH Rejection
# =====================================================================
class VAHRejectionPattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=54,
            name="VAH Rejection",
            category="Volume Profile",
            description="Penolakan harga di batas atas Value Area High (VAH) dengan rejection wick atas menuju kembali ke POC.",
            role=PatternRole.ENTRY,
            phenomenon="Harga dinilai unfairly expensive di atas Value Area dan ditolak kembali ke zona 70% volume [OBSERVED_TICK_VOLUME].",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(30)
        if len(candles) < 25:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        vp_info = calculate_volume_profile(candles[1:25], bin_size=0.25)
        vah = vp_info["vah_price"]
        poc = vp_info["poc_price"]

        c_rng = max(c0.high - c0.low, 0.01)
        upper_wick = max(0.0, c0.high - max(c0.open, c0.close))

        # Rejection: touched or pierced VAH, upper wick >= 35%, closed inside Value Area (below VAH)
        if c0.high >= vah - 0.20 and c0.close < vah and (upper_wick / c_rng) >= 0.35 and c0.close < c0.open:
            invalidation = round(c0.high + params["inval_buffer"] * 0.25, 2)
            direction = SignalDirection.SELL
            reasons = [
                f"[OBSERVED_TICK_VOLUME] VAH Rejection: Pengujian Value Area High {vah:.2f} ditolak tegas",
                f"Upper wick {upper_wick / c_rng * 100:.0f}% menunjukkan rejection kembali menuju POC {poc:.2f}",
            ]

            if self._is_candle_deduplicated(c0.timestamp, direction):
                return None
            self.last_candle_ts = c0.timestamp
            self.last_direction = direction

            now_ms = buffer.current_time_ms
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=direction,
                reference_price=vah,
                trigger_price=c0.close,
                invalidation_price=invalidation,
                execution_price=buffer.get_execution_price(direction, c0.close),
                pattern_role=self.role,
                status=SignalStatus.ACTIVE,
                status_reason="Kondisi VAH Rejection terpenuhi",
                phenomenon=self.phenomenon,
                timestamp_ms=now_ms,
                event_id=f"vahrej:{self.pattern_id}:{c0.timestamp.isoformat()}:SELL",
                reasons=reasons,
                metrics={"vah_price": vah, "poc_price": poc, "upper_wick_ratio": upper_wick / c_rng},
                max_age_sec=params["max_age_sec"],
            )
        return None


# =====================================================================
# 55. VAL Rejection
# =====================================================================
class VALRejectionPattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=55,
            name="VAL Rejection",
            category="Volume Profile",
            description="Penolakan harga di batas bawah Value Area Low (VAL) dengan rejection wick bawah menuju kembali ke POC.",
            role=PatternRole.ENTRY,
            phenomenon="Harga dinilai unfairly cheap di bawah Value Area dan dipantulkan kembali ke zona 70% volume [OBSERVED_TICK_VOLUME].",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(30)
        if len(candles) < 25:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        vp_info = calculate_volume_profile(candles[1:25], bin_size=0.25)
        val = vp_info["val_price"]
        poc = vp_info["poc_price"]

        c_rng = max(c0.high - c0.low, 0.01)
        lower_wick = max(0.0, min(c0.open, c0.close) - c0.low)

        # Rejection: touched or pierced VAL, lower wick >= 35%, closed inside Value Area (above VAL)
        if c0.low <= val + 0.20 and c0.close > val and (lower_wick / c_rng) >= 0.35 and c0.close > c0.open:
            invalidation = round(c0.low - params["inval_buffer"] * 0.25, 2)
            direction = SignalDirection.BUY
            reasons = [
                f"[OBSERVED_TICK_VOLUME] VAL Rejection: Pengujian Value Area Low {val:.2f} dipantulkan tegas",
                f"Lower wick {lower_wick / c_rng * 100:.0f}% menunjukkan rebound kembali menuju POC {poc:.2f}",
            ]

            if self._is_candle_deduplicated(c0.timestamp, direction):
                return None
            self.last_candle_ts = c0.timestamp
            self.last_direction = direction

            now_ms = buffer.current_time_ms
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=direction,
                reference_price=val,
                trigger_price=c0.close,
                invalidation_price=invalidation,
                execution_price=buffer.get_execution_price(direction, c0.close),
                pattern_role=self.role,
                status=SignalStatus.ACTIVE,
                status_reason="Kondisi VAL Rejection terpenuhi",
                phenomenon=self.phenomenon,
                timestamp_ms=now_ms,
                event_id=f"valrej:{self.pattern_id}:{c0.timestamp.isoformat()}:BUY",
                reasons=reasons,
                metrics={"val_price": val, "poc_price": poc, "lower_wick_ratio": lower_wick / c_rng},
                max_age_sec=params["max_age_sec"],
            )
        return None


# =====================================================================
# 56. HVN/LVN Reaction
# =====================================================================
class HVNLVNReactionPattern(BasePattern):
    def __init__(self):
        super().__init__(
            pattern_id=56,
            name="HVN/LVN Reaction",
            category="Volume Profile",
            description="Reaksi pantulan dari High Volume Node (HVN) atau akselerasi cepat menembus Low Volume Node (LVN) tipis.",
            role=PatternRole.ENTRY,
            phenomenon="Penerimaan harga di zona likuiditas padat (HVN) atau slippage cepat di zona vakum likuiditas (LVN) [OBSERVED_TICK_VOLUME].",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(30)
        if len(candles) < 25:
            return None

        c0 = candles[0]
        params = _get_timeframe_params(c0.timeframe)
        vp_info = calculate_volume_profile(candles[1:25], bin_size=0.25)
        hvn_nodes = vp_info["hvn_nodes"]
        lvn_nodes = vp_info["lvn_nodes"]

        direction = SignalDirection.NONE
        reasons = []
        ref_price = c0.close

        # Test bounce from HVN Support below
        hvn_supports = [p for p in hvn_nodes if p < c0.close]
        if hvn_supports and c0.low <= max(hvn_supports) + 0.30 and c0.close > max(hvn_supports) and c0.close > c0.open:
            direction = SignalDirection.BUY
            ref_price = max(hvn_supports)
            invalidation = round(ref_price - params["inval_buffer"] * 0.3, 2)
            reasons.append(f"[OBSERVED_TICK_VOLUME] Pantulan dari High Volume Node (HVN) {ref_price:.2f}")

        # Test bounce from HVN Resistance above
        hvn_resists = [p for p in hvn_nodes if p > c0.close]
        if not reasons and hvn_resists and c0.high >= min(hvn_resists) - 0.30 and c0.close < min(hvn_resists) and c0.close < c0.open:
            direction = SignalDirection.SELL
            ref_price = min(hvn_resists)
            invalidation = round(ref_price + params["inval_buffer"] * 0.3, 2)
            reasons.append(f"[OBSERVED_TICK_VOLUME] Penolakan dari High Volume Node (HVN) {ref_price:.2f}")

        # Test breakthrough LVN vacuum zone
        if not reasons and lvn_nodes:
            nearest_lvn = min(lvn_nodes, key=lambda p: abs(p - c0.close))
            if abs(nearest_lvn - c0.close) <= 0.50:
                if c0.close > c0.open:
                    direction = SignalDirection.BUY
                    ref_price = nearest_lvn
                    invalidation = round(c0.low - params["inval_buffer"] * 0.25, 2)
                    reasons.append(f"[OBSERVED_TICK_VOLUME] Akselerasi menembus Low Volume Node (LVN) {nearest_lvn:.2f}")
                elif c0.close < c0.open:
                    direction = SignalDirection.SELL
                    ref_price = nearest_lvn
                    invalidation = round(c0.high + params["inval_buffer"] * 0.25, 2)
                    reasons.append(f"[OBSERVED_TICK_VOLUME] Akselerasi menembus Low Volume Node (LVN) {nearest_lvn:.2f}")

        if direction == SignalDirection.NONE:
            return None

        if self._is_candle_deduplicated(c0.timestamp, direction):
            return None
        self.last_candle_ts = c0.timestamp
        self.last_direction = direction

        now_ms = buffer.current_time_ms
        return EntrySignal(
            pattern_id=self.pattern_id,
            family_name=self.name,
            direction=direction,
            reference_price=ref_price,
            trigger_price=c0.close,
            invalidation_price=invalidation,
            execution_price=buffer.get_execution_price(direction, c0.close),
            pattern_role=self.role,
            status=SignalStatus.ACTIVE,
            status_reason="Kondisi HVN/LVN Reaction terpenuhi",
            phenomenon=self.phenomenon,
            timestamp_ms=now_ms,
            event_id=f"hvnlvn:{self.pattern_id}:{c0.timestamp.isoformat()}:{direction.value}",
            reasons=reasons,
            metrics={"hvn_nodes": hvn_nodes, "lvn_nodes": lvn_nodes, "ref_price": ref_price},
            max_age_sec=params["max_age_sec"],
        )
