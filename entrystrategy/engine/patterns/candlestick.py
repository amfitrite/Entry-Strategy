"""Candlestick Category Entry Patterns (Pola 1-6, 21, 25-27, 38, 39) with event deduplication and price separation."""
from typing import Optional, List
from entrystrategy.engine.base import BasePattern
from entrystrategy.core.models import EntrySignal, SignalDirection, PatternRole, Candle
from entrystrategy.core.buffer import MarketBuffer


class CandlestickReversalPattern(BasePattern):
    """Pola 1: Candlestick Reversal (Engulfing)."""
    def __init__(self):
        super().__init__(
            pattern_id=1,
            name="Candlestick Reversal",
            category="Candle",
            description="Reversal formasi engulfing di mana body bar saat ini menelan penuh bar sebelumnya.",
            role=PatternRole.ENTRY,
            phenomenon="Pembalikan arah bar di mana body candle saat ini menelan penuh body bar berlawanan sebelumnya.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(3)
        if len(candles) < 2:
            return None
        c0, c1 = candles[0], candles[1]
        ts = buffer.current_time_ms

        # Bullish Engulfing
        if c1.is_bearish and c0.is_bullish and c1.body >= 0.20:
            if c0.body >= (c1.body * 1.1) and c0.close > c1.open and c0.open <= (c1.close + 0.10):
                if c0.upper_wick <= (c0.range * 0.35):
                    ref_px = c1.open
                    trig_px = c0.close
                    inv_px = min(c0.low, c1.low)
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.BUY,
                        reference_price=ref_px,
                        trigger_price=trig_px,
                        invalidation_price=inv_px,
                        timestamp_ms=ts,
                        pattern_role=self.role,
                        phenomenon=self.phenomenon,
                        event_id=f"c_engulf_buy_{c0.timestamp.isoformat()}",
                        reasons=[
                            f"C[1] Bearish body: {c1.body:.2f} pts ({c1.open:.2f} -> {c1.close:.2f})",
                            f"C[0] Bullish body: {c0.body:.2f} pts menelan C[1] (Rasio: {c0.body / max(0.01, c1.body):.2f}x)",
                            f"C[0] Close ({c0.close:.2f}) berhasil melampaui C[1] Open ({ref_px:.2f})",
                        ],
                        metrics={"ratio": round(c0.body / max(0.01, c1.body), 2), "c0_range": round(c0.range, 2)},
                    )

        # Bearish Engulfing
        if c1.is_bullish and c0.is_bearish and c1.body >= 0.20:
            if c0.body >= (c1.body * 1.1) and c0.close < c1.open and c0.open >= (c1.close - 0.10):
                if c0.lower_wick <= (c0.range * 0.35):
                    ref_px = c1.open
                    trig_px = c0.close
                    inv_px = max(c0.high, c1.high)
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.SELL,
                        reference_price=ref_px,
                        trigger_price=trig_px,
                        invalidation_price=inv_px,
                        timestamp_ms=ts,
                        pattern_role=self.role,
                        phenomenon=self.phenomenon,
                        event_id=f"c_engulf_sell_{c0.timestamp.isoformat()}",
                        reasons=[
                            f"C[1] Bullish body: {c1.body:.2f} pts ({c1.open:.2f} -> {c1.close:.2f})",
                            f"C[0] Bearish body: {c0.body:.2f} pts menelan C[1] (Rasio: {c0.body / max(0.01, c1.body):.2f}x)",
                            f"C[0] Close ({c0.close:.2f}) berhasil menembus ke bawah C[1] Open ({ref_px:.2f})",
                        ],
                        metrics={"ratio": round(c0.body / max(0.01, c1.body), 2), "c0_range": round(c0.range, 2)},
                    )
        return None


class CandlestickContinuationPattern(BasePattern):
    """Pola 2: Candlestick Continuation (Three White Soldiers / Three Black Crows)."""
    def __init__(self):
        super().__init__(
            pattern_id=2,
            name="Candlestick Continuation",
            category="Candle",
            description="Tiga candle berturut-turut searah dengan progressive close bertingkat tanpa ekor kelelahan ekstrim.",
            role=PatternRole.CONFIRMATION,
            phenomenon="Kelanjutan momentum progresif 3 bar berturut-turut searah tanpa ekor penolakan besar.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(4)
        if len(candles) < 3:
            return None
        c0, c1, c2 = candles[0], candles[1], candles[2]
        ts = buffer.current_time_ms

        # Three White Soldiers: healthy progressive closes, controlled wicks, non-blowoff body
        if c0.is_bullish and c1.is_bullish and c2.is_bullish:
            if c0.close > c1.close > c2.close and c0.open >= c1.open:
                # Anti-exhaustion check: upper wick must not exceed 25% of bar, and bar not 3x larger than previous
                if c0.upper_wick <= (c0.range * 0.25) and c0.body <= (c1.body * 2.5):
                    ref_px = c1.close
                    trig_px = c0.close
                    inv_px = c2.open
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.BUY,
                        reference_price=ref_px,
                        trigger_price=trig_px,
                        invalidation_price=inv_px,
                        timestamp_ms=ts,
                        pattern_role=self.role,
                        phenomenon=self.phenomenon,
                        event_id=f"c_continuation_buy_{c0.timestamp.isoformat()}",
                        reasons=[
                            "3 Bar Bullish berturut-turut (Three White Soldiers)",
                            f"Close meningkat bertahap: {c2.close:.2f} -> {c1.close:.2f} -> {c0.close:.2f}",
                            f"Ekor atas C[0] terkendali ({c0.upper_wick:.2f} pts <= 25%), bukan blow-off overextended",
                        ],
                    )

        # Three Black Crows
        if c0.is_bearish and c1.is_bearish and c2.is_bearish:
            if c0.close < c1.close < c2.close and c0.open <= c1.open:
                if c0.lower_wick <= (c0.range * 0.25) and c0.body <= (c1.body * 2.5):
                    ref_px = c1.close
                    trig_px = c0.close
                    inv_px = c2.open
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.SELL,
                        reference_price=ref_px,
                        trigger_price=trig_px,
                        invalidation_price=inv_px,
                        timestamp_ms=ts,
                        pattern_role=self.role,
                        phenomenon=self.phenomenon,
                        event_id=f"c_continuation_sell_{c0.timestamp.isoformat()}",
                        reasons=[
                            "3 Bar Bearish berturut-turut (Three Black Crows)",
                            f"Close menurun bertahap: {c2.close:.2f} -> {c1.close:.2f} -> {c0.close:.2f}",
                            f"Ekor bawah C[0] terkendali ({c0.lower_wick:.2f} pts <= 25%), bukan blow-off overextended",
                        ],
                    )
        return None


class MultiCandleReversalPattern(BasePattern):
    """Pola 3: Multi-Candle Reversal (Two-Bar Reversal)."""
    def __init__(self):
        super().__init__(
            pattern_id=3,
            name="Multi-Candle Reversal",
            category="Candle",
            description="Pembalikan tajam 2 bar di mana bar kedua memulihkan setidaknya 80% dari pergerakan bar pertama.",
            role=PatternRole.ENTRY,
            phenomenon="Reversal 2 bar bertolak belakang dengan ukuran seimbang membatalkan impuls bar sebelumnya.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(3)
        if len(candles) < 2:
            return None
        c0, c1 = candles[0], candles[1]
        ts = buffer.current_time_ms

        # Bullish 2-Bar Reversal: c1 dropped with substantial body, c0 recovers >= 85%
        if c1.is_bearish and c1.body >= 0.35 and c0.is_bullish:
            body_ratio = c0.body / max(0.01, c1.body)
            if 0.85 <= body_ratio <= 1.45 and c0.close >= c1.open - (0.2 * c1.body):
                ref_px = c1.open
                trig_px = c0.close
                inv_px = min(c0.low, c1.low)
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    reference_price=ref_px,
                    trigger_price=trig_px,
                    invalidation_price=inv_px,
                    timestamp_ms=ts,
                    pattern_role=self.role,
                    phenomenon=self.phenomenon,
                    event_id=f"c_multirev_buy_{c0.timestamp.isoformat()}",
                    reasons=[
                        "Formasi Two-Bar Reversal Bullish",
                        f"Keseimbangan body C[0] ({c0.body:.2f} pts) vs C[1] ({c1.body:.2f} pts): rasio {body_ratio:.2f}",
                        f"Close C[0] ({c0.close:.2f}) memulihkan penurunan bar sebelumnya",
                    ],
                )

        # Bearish 2-Bar Reversal
        if c1.is_bullish and c1.body >= 0.35 and c0.is_bearish:
            body_ratio = c0.body / max(0.01, c1.body)
            if 0.85 <= body_ratio <= 1.45 and c0.close <= c1.open + (0.2 * c1.body):
                ref_px = c1.open
                trig_px = c0.close
                inv_px = max(c0.high, c1.high)
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    reference_price=ref_px,
                    trigger_price=trig_px,
                    invalidation_price=inv_px,
                    timestamp_ms=ts,
                    pattern_role=self.role,
                    phenomenon=self.phenomenon,
                    event_id=f"c_multirev_sell_{c0.timestamp.isoformat()}",
                    reasons=[
                        "Formasi Two-Bar Reversal Bearish",
                        f"Keseimbangan body C[0] ({c0.body:.2f} pts) vs C[1] ({c1.body:.2f} pts): rasio {body_ratio:.2f}",
                        f"Close C[0] ({c0.close:.2f}) memulihkan kenaikan bar sebelumnya",
                    ],
                )
        return None


class InsideBarBreakoutPattern(BasePattern):
    """Pola 4: Inside Bar Breakout."""
    def __init__(self):
        super().__init__(
            pattern_id=4,
            name="Inside Bar",
            category="Candle",
            description="Breakout penembusan batas High atau Low dari Mother Bar setelah konsolidasi Inside Bar.",
            role=PatternRole.SETUP_TRIGGER,
            phenomenon="Kompresi rentang harga di dalam Mother Bar yang kemudian terlepas melalui penembusan batas luar.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(3)
        if len(candles) < 3:
            return None
        c0, c1, c2 = candles[0], candles[1], candles[2]  # c2: mother bar, c1: inside bar, c0: breakout bar
        ts = buffer.current_time_ms

        is_c1_inside = (c1.high <= c2.high) and (c1.low >= c2.low) and (c2.range >= 0.40)
        if not is_c1_inside:
            return None

        # Breakout to the upside
        if c0.close > c2.high:
            ref_px = c2.high
            trig_px = c0.close
            inv_px = c2.low
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inv_px,
                timestamp_ms=ts,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=f"c_inside_buy_{c0.timestamp.isoformat()}",
                reasons=[
                    f"Inside Bar C[1] terkurung dalam Mother Bar C[2] ({c2.low:.2f} - {c2.high:.2f})",
                    f"Breakout ke atas terkonfirmasi: Close C[0] ({c0.close:.2f}) > High Mother Bar ({ref_px:.2f})",
                ],
            )

        # Breakout to the downside
        if c0.close < c2.low:
            ref_px = c2.low
            trig_px = c0.close
            inv_px = c2.high
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inv_px,
                timestamp_ms=ts,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=f"c_inside_sell_{c0.timestamp.isoformat()}",
                reasons=[
                    f"Inside Bar C[1] terkurung dalam Mother Bar C[2] ({c2.low:.2f} - {c2.high:.2f})",
                    f"Breakout ke bawah terkonfirmasi: Close C[0] ({c0.close:.2f}) < Low Mother Bar ({ref_px:.2f})",
                ],
            )
        return None


class OutsideBarBreakoutPattern(BasePattern):
    """Pola 5: Outside Bar Breakout."""
    def __init__(self):
        super().__init__(
            pattern_id=5,
            name="Outside Bar",
            category="Candle",
            description="Ekspansi rentang menelan bar sebelumnya, dengan trigger penembusan lanjutan di luar batas Outside Bar.",
            role=PatternRole.STRUCTURE,
            phenomenon="Ekspansi volatilitas menelan bar sebelumnya yang kemudian melanjutkan terobosan searah.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(3)
        if len(candles) < 3:
            return None
        c0, c1, c2 = candles[0], candles[1], candles[2]  # c1: outside bar engulfing c2, c0: trigger bar
        ts = buffer.current_time_ms

        is_c1_outside = (c1.high > c2.high) and (c1.low < c2.low) and (c1.range >= 0.50)
        if not is_c1_outside:
            return None

        # Continuation breakout above outside bar
        if c0.close > c1.high:
            ref_px = c1.high
            trig_px = c0.close
            inv_px = (c1.high + c1.low) / 2.0
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inv_px,
                timestamp_ms=ts,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=f"c_outside_buy_{c0.timestamp.isoformat()}",
                reasons=[
                    f"Outside Bar C[1] menelan range C[2] ({c1.low:.2f} - {c1.high:.2f})",
                    f"Lanjutan Breakout Bullish: Close C[0] ({c0.close:.2f}) > High Outside Bar ({ref_px:.2f})",
                ],
            )

        # Continuation breakdown below outside bar
        if c0.close < c1.low:
            ref_px = c1.low
            trig_px = c0.close
            inv_px = (c1.high + c1.low) / 2.0
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inv_px,
                timestamp_ms=ts,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=f"c_outside_sell_{c0.timestamp.isoformat()}",
                reasons=[
                    f"Outside Bar C[1] menelan range C[2] ({c1.low:.2f} - {c1.high:.2f})",
                    f"Lanjutan Breakdown Bearish: Close C[0] ({c0.close:.2f}) < Low Outside Bar ({ref_px:.2f})",
                ],
            )
        return None


class MomentumPattern(BasePattern):
    """Pola 6: Momentum Candle."""
    def __init__(self):
        super().__init__(
            pattern_id=6,
            name="Momentum",
            category="Candle",
            description="Candle berbadan sangat besar dengan wick minimal mencerminkan ekspansi impuls kuat.",
            role=PatternRole.ENTRY,
            phenomenon="Ekspansi harga satu bar yang signifikan di atas rata-rata historis dengan dominasi body >= 70%.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(6)
        if len(candles) < 4:
            return None
        c0 = candles[0]
        avg_range = sum(c.range for c in candles[1:4]) / 3.0
        ts = buffer.current_time_ms

        # Bullish Momentum
        if c0.is_bullish and c0.range >= (avg_range * 1.5) and c0.body >= (c0.range * 0.70):
            if c0.upper_wick <= (c0.range * 0.18):
                ref_px = c0.open
                trig_px = c0.close
                inv_px = c0.low
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    reference_price=ref_px,
                    trigger_price=trig_px,
                    invalidation_price=inv_px,
                    timestamp_ms=ts,
                    pattern_role=self.role,
                    phenomenon=self.phenomenon,
                    event_id=f"c_momentum_buy_{c0.timestamp.isoformat()}",
                    reasons=[
                        f"Bullish Momentum Candle: Range {c0.range:.2f} pts (> 1.5x avg {avg_range:.2f} pts)",
                        f"Dominasi Body: {c0.body / c0.range * 100:.1f}% dari total rentang bar",
                        f"Ekor atas minimal ({c0.upper_wick:.2f} pts) membuktikan tekanan pembeli dominan",
                    ],
                )

        # Bearish Momentum
        if c0.is_bearish and c0.range >= (avg_range * 1.5) and c0.body >= (c0.range * 0.70):
            if c0.lower_wick <= (c0.range * 0.18):
                ref_px = c0.open
                trig_px = c0.close
                inv_px = c0.high
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    reference_price=ref_px,
                    trigger_price=trig_px,
                    invalidation_price=inv_px,
                    timestamp_ms=ts,
                    pattern_role=self.role,
                    phenomenon=self.phenomenon,
                    event_id=f"c_momentum_sell_{c0.timestamp.isoformat()}",
                    reasons=[
                        f"Bearish Momentum Candle: Range {c0.range:.2f} pts (> 1.5x avg {avg_range:.2f} pts)",
                        f"Dominasi Body: {c0.body / c0.range * 100:.1f}% dari total rentang bar",
                        f"Ekor bawah minimal ({c0.lower_wick:.2f} pts) membuktikan tekanan penjual dominan",
                    ],
                )
        return None


class VolatilityContractionPattern(BasePattern):
    """Pola 21: Volatility Contraction."""
    def __init__(self):
        super().__init__(
            pattern_id=21,
            name="Volatility Contraction",
            category="Candle",
            description="Penyusutan volatilitas 3 bar berturut-turut (Setup) yang terpicu oleh penembusan terarah (Trigger).",
            role=PatternRole.SETUP_TRIGGER,
            phenomenon="Penciutan rentang harga bertahap mengindikasikan kompresi energi pasar sebelum pelepasan arah.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(5)
        if len(candles) < 4:
            return None
        c0, c1, c2, c3 = candles[0], candles[1], candles[2], candles[3]
        ts = buffer.current_time_ms

        # Setup: Contraction in previous 3 bars (c3 > c2 > c1)
        is_contracting = (c3.range > c2.range > c1.range) and (c1.range <= c3.range * 0.55)
        if not is_contracting:
            return None

        # Trigger: c0 breaks out of the contracted mother bar c1
        if c0.close > c1.high:
            ref_px = c1.high
            trig_px = c0.close
            inv_px = c1.low
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inv_px,
                timestamp_ms=ts,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=f"c_volcontract_buy_{c0.timestamp.isoformat()}",
                reasons=[
                    f"Setup Kontraksi 3 Bar: {c3.range:.2f} -> {c2.range:.2f} -> {c1.range:.2f} pts (Susut > 45%)",
                    f"Trigger Breakout Atas: Close C[0] ({c0.close:.2f}) menembus High bar kontraksi C[1] ({ref_px:.2f})",
                ],
            )

        if c0.close < c1.low:
            ref_px = c1.low
            trig_px = c0.close
            inv_px = c1.high
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inv_px,
                timestamp_ms=ts,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=f"c_volcontract_sell_{c0.timestamp.isoformat()}",
                reasons=[
                    f"Setup Kontraksi 3 Bar: {c3.range:.2f} -> {c2.range:.2f} -> {c1.range:.2f} pts (Susut > 45%)",
                    f"Trigger Breakdown Bawah: Close C[0] ({c0.close:.2f}) menembus Low bar kontraksi C[1] ({ref_px:.2f})",
                ],
            )
        return None


class WickPattern(BasePattern):
    """Pola 25: Wick Pattern (Pin Bar / Rejection Wick)."""
    def __init__(self):
        super().__init__(
            pattern_id=25,
            name="Wick Pattern",
            category="Candle",
            description="Penolakan harga ekstrim satu arah meninggalkan ekor panjang >= 60% dari rentang bar.",
            role=PatternRole.ENTRY,
            phenomenon="Rejection intra-bar di level ekstrim meninggalkan wick panjang dengan penutupan di sepertiga berlawanan.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(2)
        if not candles:
            return None
        c0 = candles[0]
        ts = buffer.current_time_ms

        if c0.range < 0.35:
            return None

        # Hammer / Bullish Wick Rejection
        if c0.lower_wick >= (c0.range * 0.60) and c0.upper_wick <= (c0.range * 0.20):
            ref_px = c0.low
            trig_px = c0.close
            inv_px = c0.low
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inv_px,
                timestamp_ms=ts,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=f"c_wick_buy_{c0.timestamp.isoformat()}",
                reasons=[
                    f"Lower Wick Dominan: {c0.lower_wick:.2f} pts ({c0.lower_wick / c0.range * 100:.1f}% dari bar)",
                    f"Penolakan harga di level rendah {ref_px:.2f} terkonfirmasi oleh close di sepertiga atas",
                ],
            )

        # Shooting Star / Bearish Wick Rejection
        if c0.upper_wick >= (c0.range * 0.60) and c0.lower_wick <= (c0.range * 0.20):
            ref_px = c0.high
            trig_px = c0.close
            inv_px = c0.high
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inv_px,
                timestamp_ms=ts,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=f"c_wick_sell_{c0.timestamp.isoformat()}",
                reasons=[
                    f"Upper Wick Dominan: {c0.upper_wick:.2f} pts ({c0.upper_wick / c0.range * 100:.1f}% dari bar)",
                    f"Penolakan harga di level tinggi {ref_px:.2f} terkonfirmasi oleh close di sepertiga bawah",
                ],
            )
        return None


class BodyExpansionPattern(BasePattern):
    """Pola 26: Body Expansion."""
    def __init__(self):
        super().__init__(
            pattern_id=26,
            name="Body Expansion",
            category="Candle",
            description="Peningkatan ukuran body candle berturut-turut searah (> 20% per bar) mencerminkan eskalasi minat pasar.",
            role=PatternRole.CONFIRMATION,
            phenomenon="Akselerasi ukuran body bar berturut-turut searah mengonfirmasi penguatan dorongan pasar.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(4)
        if len(candles) < 3:
            return None
        c0, c1, c2 = candles[0], candles[1], candles[2]
        ts = buffer.current_time_ms

        # Bullish Expansion
        if c0.is_bullish and c1.is_bullish and c2.is_bullish and c2.body >= 0.20:
            if c0.body >= (c1.body * 1.20) and c1.body >= (c2.body * 1.20):
                ref_px = c1.high
                trig_px = c0.close
                inv_px = c0.low
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    reference_price=ref_px,
                    trigger_price=trig_px,
                    invalidation_price=inv_px,
                    timestamp_ms=ts,
                    pattern_role=self.role,
                    phenomenon=self.phenomenon,
                    event_id=f"c_bodyexp_buy_{c0.timestamp.isoformat()}",
                    reasons=[
                        f"Ekspansi Body Bullish: {c2.body:.2f} -> {c1.body:.2f} -> {c0.body:.2f} pts",
                        f"Pertumbuhan body konsisten > 20% per bar mengonfirmasi eskalasi pergerakan",
                    ],
                )

        # Bearish Expansion
        if c0.is_bearish and c1.is_bearish and c2.is_bearish and c2.body >= 0.20:
            if c0.body >= (c1.body * 1.20) and c1.body >= (c2.body * 1.20):
                ref_px = c1.low
                trig_px = c0.close
                inv_px = c0.high
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    reference_price=ref_px,
                    trigger_price=trig_px,
                    invalidation_price=inv_px,
                    timestamp_ms=ts,
                    pattern_role=self.role,
                    phenomenon=self.phenomenon,
                    event_id=f"c_bodyexp_sell_{c0.timestamp.isoformat()}",
                    reasons=[
                        f"Ekspansi Body Bearish: {c2.body:.2f} -> {c1.body:.2f} -> {c0.body:.2f} pts",
                        f"Pertumbuhan body konsisten > 20% per bar mengonfirmasi eskalasi tekanan jual",
                    ],
                )
        return None


class BodyContractionPattern(BasePattern):
    """Pola 27: Body Contraction."""
    def __init__(self):
        super().__init__(
            pattern_id=27,
            name="Body Contraction",
            category="Candle",
            description="Kehilangan daya dorong candle berturut-turut (Setup) yang dikonfirmasi oleh penembusan reversal (Trigger).",
            role=PatternRole.SETUP_TRIGGER,
            phenomenon="Menyusutnya body candle berturut-turut setelah pergerakan panjang, memicu reversal saat batas bar terpecah.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(5)
        if len(candles) < 4:
            return None
        c0, c1, c2, c3 = candles[0], candles[1], candles[2], candles[3]
        ts = buffer.current_time_ms

        # Setup Bullish Diminishing: c3 > c2 > c1 (all bullish, but bodies contracting sharply)
        if c3.is_bullish and c2.is_bullish and c1.is_bullish and c3.body >= 0.50:
            is_exhausting = (c1.body <= c2.body * 0.65) and (c2.body <= c3.body * 0.65)
            # Trigger: c0 breaks below the low of contracted bar c1
            if is_exhausting and c0.close < c1.low:
                ref_px = c1.low
                trig_px = c0.close
                inv_px = c1.high
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    reference_price=ref_px,
                    trigger_price=trig_px,
                    invalidation_price=inv_px,
                    timestamp_ms=ts,
                    pattern_role=self.role,
                    phenomenon=self.phenomenon,
                    event_id=f"c_bodycontract_sell_{c0.timestamp.isoformat()}",
                    reasons=[
                        f"Setup Kontraksi Body Bullish: {c3.body:.2f} -> {c2.body:.2f} -> {c1.body:.2f} pts (Kelelahan dorongan)",
                        f"Trigger Reversal: Close C[0] ({c0.close:.2f}) menembus di bawah Low C[1] ({ref_px:.2f})",
                    ],
                )

        # Setup Bearish Diminishing: c3 > c2 > c1 (all bearish, but bodies contracting sharply)
        if c3.is_bearish and c2.is_bearish and c1.is_bearish and c3.body >= 0.50:
            is_exhausting = (c1.body <= c2.body * 0.65) and (c2.body <= c3.body * 0.65)
            # Trigger: c0 breaks above the high of contracted bar c1
            if is_exhausting and c0.close > c1.high:
                ref_px = c1.high
                trig_px = c0.close
                inv_px = c1.low
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    reference_price=ref_px,
                    trigger_price=trig_px,
                    invalidation_price=inv_px,
                    timestamp_ms=ts,
                    pattern_role=self.role,
                    phenomenon=self.phenomenon,
                    event_id=f"c_bodycontract_buy_{c0.timestamp.isoformat()}",
                    reasons=[
                        f"Setup Kontraksi Body Bearish: {c3.body:.2f} -> {c2.body:.2f} -> {c1.body:.2f} pts (Kelelahan dorongan)",
                        f"Trigger Reversal: Close C[0] ({c0.close:.2f}) menembus di atas High C[1] ({ref_px:.2f})",
                    ],
                )
        return None


class StaircasePattern(BasePattern):
    """Pola 38: Staircase Pattern."""
    def __init__(self):
        super().__init__(
            pattern_id=38,
            name="Staircase Pattern",
            category="Candle",
            description="Pergerakan bertahap searah seperti anak tangga dengan higher highs & higher lows beruntun.",
            role=PatternRole.STRUCTURE,
            phenomenon="Struktur harga bertingkat teratur dengan pergeseran progresif High dan Low 4 bar beruntun.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(5)
        if len(candles) < 4:
            return None
        c0, c1, c2, c3 = candles[0], candles[1], candles[2], candles[3]
        ts = buffer.current_time_ms

        # Bullish staircase: strict higher highs and higher lows across 4 bars
        if (c0.high > c1.high > c2.high > c3.high) and (c0.low > c1.low > c2.low > c3.low):
            ref_px = c1.high
            trig_px = c0.close
            inv_px = c0.low
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inv_px,
                timestamp_ms=ts,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=f"c_staircase_buy_{c0.timestamp.isoformat()}",
                reasons=[
                    "Struktur Anak Tangga Naik (Bullish Staircase) 4 Bar",
                    f"Urutan High: {c3.high:.2f} -> {c2.high:.2f} -> {c1.high:.2f} -> {c0.high:.2f}",
                    f"Urutan Low: {c3.low:.2f} -> {c2.low:.2f} -> {c1.low:.2f} -> {c0.low:.2f}",
                ],
            )

        # Bearish staircase: strict lower highs and lower lows across 4 bars
        if (c0.high < c1.high < c2.high < c3.high) and (c0.low < c1.low < c2.low < c3.low):
            ref_px = c1.low
            trig_px = c0.close
            inv_px = c0.high
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inv_px,
                timestamp_ms=ts,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=f"c_staircase_sell_{c0.timestamp.isoformat()}",
                reasons=[
                    "Struktur Anak Tangga Turun (Bearish Staircase) 4 Bar",
                    f"Urutan High: {c3.high:.2f} -> {c2.high:.2f} -> {c1.high:.2f} -> {c0.high:.2f}",
                    f"Urutan Low: {c3.low:.2f} -> {c2.low:.2f} -> {c1.low:.2f} -> {c0.low:.2f}",
                ],
            )
        return None


class CandleSequencePattern(BasePattern):
    """Pola 39: Candle Sequence."""
    def __init__(self):
        super().__init__(
            pattern_id=39,
            name="Candle Sequence",
            category="Candle",
            description="Sekuens transisi perilaku harga: Tekanan beruntun -> Jeda Doji/Kompresi -> Ekspansi Pembalikan Kuat.",
            role=PatternRole.ENTRY,
            phenomenon="Pembalikan sekuensial yang membuktikan pergantian dominasi harga setelah titik jeda ekuilibrium.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(5)
        if len(candles) < 4:
            return None
        c0, c1, c2, c3 = candles[0], candles[1], candles[2], candles[3]
        ts = buffer.current_time_ms

        # Bullish Turnaround Sequence: Bear -> Bear -> Doji/Small Bar -> Strong Bull Rebound
        if c3.is_bearish and c2.is_bearish and c1.is_doji and c0.is_bullish:
            if c0.body >= (c1.range * 1.4) and c0.close > c2.close:
                ref_px = c1.high
                trig_px = c0.close
                inv_px = c1.low
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    reference_price=ref_px,
                    trigger_price=trig_px,
                    invalidation_price=inv_px,
                    timestamp_ms=ts,
                    pattern_role=self.role,
                    phenomenon=self.phenomenon,
                    event_id=f"c_seq_buy_{c0.timestamp.isoformat()}",
                    reasons=[
                        "Sekuens Pembalikan Bullish: [Bear] -> [Bear] -> [Doji] -> [Strong Bull Expansion]",
                        f"C[0] Bullish ({c0.body:.2f} pts) membongkar titik jeda C[1] ({c1.high:.2f})",
                    ],
                )

        # Bearish Turnaround Sequence: Bull -> Bull -> Doji/Small Bar -> Strong Bear Rebound
        if c3.is_bullish and c2.is_bullish and c1.is_doji and c0.is_bearish:
            if c0.body >= (c1.range * 1.4) and c0.close < c2.close:
                ref_px = c1.low
                trig_px = c0.close
                inv_px = c1.high
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    reference_price=ref_px,
                    trigger_price=trig_px,
                    invalidation_price=inv_px,
                    timestamp_ms=ts,
                    pattern_role=self.role,
                    phenomenon=self.phenomenon,
                    event_id=f"c_seq_sell_{c0.timestamp.isoformat()}",
                    reasons=[
                        "Sekuens Pembalikan Bearish: [Bull] -> [Bull] -> [Doji] -> [Strong Bear Expansion]",
                        f"C[0] Bearish ({c0.body:.2f} pts) membongkar titik jeda C[1] ({c1.low:.2f})",
                    ],
                )
        return None
