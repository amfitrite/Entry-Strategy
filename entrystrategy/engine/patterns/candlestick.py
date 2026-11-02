"""Candlestick Category Entry Patterns (Pola 1-6, 21, 25-27, 38, 39)."""
from typing import Optional, List
from entrystrategy.engine.base import BasePattern
from entrystrategy.core.models import EntrySignal, SignalDirection, Candle
from entrystrategy.core.buffer import MarketBuffer


class CandlestickReversalPattern(BasePattern):
    """Pola 1: Candlestick Reversal (Engulfing)."""
    def __init__(self):
        super().__init__(
            pattern_id=1,
            name="Candlestick Reversal",
            category="Candle",
            description="Reversal formasi engulfing di mana body bar saat ini menelan penuh bar sebelumnya.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(3)
        if len(candles) < 2:
            return None
        c0, c1 = candles[0], candles[1]  # c0 is latest completed, c1 is previous
        tick = buffer.latest_tick
        ts = tick.ts_ms if tick else int(c0.timestamp.timestamp() * 1000)
        px = c0.close

        # Bullish Engulfing
        if c1.is_bearish and c0.is_bullish and c0.body >= (c1.body * 1.1) and c0.close > c1.open:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=px,
                timestamp_ms=ts,
                reasons=[
                    f"C[1] Bearish body: {c1.body:.2f} pts ({c1.open:.2f} -> {c1.close:.2f})",
                    f"C[0] Bullish body: {c0.body:.2f} pts menelan C[1] (Rasio: {c0.body / max(0.01, c1.body):.2f}x)",
                    f"C[0] Close ({c0.close:.2f}) > C[1] Open ({c1.open:.2f})",
                    f"Upper wick C[0] terkendali: {c0.upper_wick:.2f} pts",
                ],
                metrics={"ratio": round(c0.body / max(0.01, c1.body), 2), "c0_range": round(c0.range, 2)},
            )

        # Bearish Engulfing
        if c1.is_bullish and c0.is_bearish and c0.body >= (c1.body * 1.1) and c0.close < c1.open:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=px,
                timestamp_ms=ts,
                reasons=[
                    f"C[1] Bullish body: {c1.body:.2f} pts ({c1.open:.2f} -> {c1.close:.2f})",
                    f"C[0] Bearish body: {c0.body:.2f} pts menelan C[1] (Rasio: {c0.body / max(0.01, c1.body):.2f}x)",
                    f"C[0] Close ({c0.close:.2f}) < C[1] Open ({c1.open:.2f})",
                    f"Lower wick C[0] terkendali: {c0.lower_wick:.2f} pts",
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
            description="Tiga candle berturut-turut searah dengan progressive close bertingkat.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(4)
        if len(candles) < 3:
            return None
        c0, c1, c2 = candles[0], candles[1], candles[2]
        tick = buffer.latest_tick
        ts = tick.ts_ms if tick else int(c0.timestamp.timestamp() * 1000)

        # Three White Soldiers
        if c0.is_bullish and c1.is_bullish and c2.is_bullish:
            if c0.close > c1.close > c2.close and c0.open > c1.open > c2.open:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    price=c0.close,
                    timestamp_ms=ts,
                    reasons=[
                        "3 Bar Bullish berturut-turut (Three White Soldiers)",
                        f"Close meningkat bertahap: {c2.close:.2f} -> {c1.close:.2f} -> {c0.close:.2f}",
                        f"Total kenaikan 3 bar: {c0.close - c2.open:.2f} pts",
                    ],
                )

        # Three Black Crows
        if c0.is_bearish and c1.is_bearish and c2.is_bearish:
            if c0.close < c1.close < c2.close and c0.open < c1.open < c2.open:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    price=c0.close,
                    timestamp_ms=ts,
                    reasons=[
                        "3 Bar Bearish berturut-turut (Three Black Crows)",
                        f"Close menurun bertahap: {c2.close:.2f} -> {c1.close:.2f} -> {c0.close:.2f}",
                        f"Total penurunan 3 bar: {c2.open - c0.close:.2f} pts",
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
            description="Pembalikan tajam 2 bar bertolak belakang dengan ukuran body seimbang.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(3)
        if len(candles) < 2:
            return None
        c0, c1 = candles[0], candles[1]
        tick = buffer.latest_tick
        ts = tick.ts_ms if tick else int(c0.timestamp.timestamp() * 1000)

        # Bullish 2-Bar Reversal
        if c1.is_bearish and c0.is_bullish:
            body_ratio = c0.body / max(0.01, c1.body)
            if 0.85 <= body_ratio <= 1.4 and c0.close >= c1.open - (0.2 * c1.body):
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    price=c0.close,
                    timestamp_ms=ts,
                    reasons=[
                        "Formasi Two-Bar Reversal Bullish",
                        f"Keseimbangan body C[0] vs C[1]: rasio {body_ratio:.2f}",
                        f"Rebound penuh memulihkan drop bar sebelumnya",
                    ],
                )

        # Bearish 2-Bar Reversal
        if c1.is_bullish and c0.is_bearish:
            body_ratio = c0.body / max(0.01, c1.body)
            if 0.85 <= body_ratio <= 1.4 and c0.close <= c1.open + (0.2 * c1.body):
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    price=c0.close,
                    timestamp_ms=ts,
                    reasons=[
                        "Formasi Two-Bar Reversal Bearish",
                        f"Keseimbangan body C[0] vs C[1]: rasio {body_ratio:.2f}",
                        f"Reversal penuh membatalkan rally bar sebelumnya",
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
            description="Breakout penembusan batas High atau Low dari mother bar.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(3)
        if len(candles) < 2:
            return None
        c0, c1 = candles[0], candles[1]  # c0 is breakout bar, c1 was inside mother bar c2
        tick = buffer.latest_tick
        px = tick.mid if tick else c0.close
        ts = tick.ts_ms if tick else int(c0.timestamp.timestamp() * 1000)

        if len(candles) >= 3:
            c2 = candles[2]  # Mother bar
            is_c1_inside = (c1.high <= c2.high) and (c1.low >= c2.low)
            if is_c1_inside:
                if px > c2.high:
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.BUY,
                        price=px,
                        timestamp_ms=ts,
                        reasons=[
                            f"Inside Bar terdeteksi pada C[1] di dalam range Mother Bar C[2] ({c2.low:.2f} - {c2.high:.2f})",
                            f"Breakout ke atas terkonfirmasi: Harga ({px:.2f}) > High ({c2.high:.2f})",
                        ],
                    )
                if px < c2.low:
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.SELL,
                        price=px,
                        timestamp_ms=ts,
                        reasons=[
                            f"Inside Bar terdeteksi pada C[1] di dalam range Mother Bar C[2] ({c2.low:.2f} - {c2.high:.2f})",
                            f"Breakout ke bawah terkonfirmasi: Harga ({px:.2f}) < Low ({c2.low:.2f})",
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
            description="Mother bar menelan penuh bar sebelumnya lalu melanjutkan ekspansi.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(3)
        if len(candles) < 2:
            return None
        c0, c1 = candles[0], candles[1]
        tick = buffer.latest_tick
        ts = tick.ts_ms if tick else int(c0.timestamp.timestamp() * 1000)

        # c0 is outside bar engulfing high and low of c1
        if c0.high > c1.high and c0.low < c1.low:
            if c0.is_bullish and (c0.close - c0.open) >= (c0.range * 0.5):
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    price=c0.close,
                    timestamp_ms=ts,
                    reasons=[
                        f"Outside Bar Bullish menelan range C[1] ({c1.low:.2f} - {c1.high:.2f})",
                        f"C[0] High ({c0.high:.2f}) > C[1] High & Close mendominasi di pucuk atas",
                    ],
                )
            if c0.is_bearish and (c0.open - c0.close) >= (c0.range * 0.5):
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    price=c0.close,
                    timestamp_ms=ts,
                    reasons=[
                        f"Outside Bar Bearish menelan range C[1] ({c1.low:.2f} - {c1.high:.2f})",
                        f"C[0] Low ({c0.low:.2f}) < C[1] Low & Close mendominasi di dasar bawah",
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
            description="Candle berbadan sangat besar dengan wick minimal mencerminkan dorongan kuat.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(6)
        if len(candles) < 4:
            return None
        c0 = candles[0]
        avg_range = sum(c.range for c in candles[1:4]) / 3.0
        tick = buffer.latest_tick
        ts = tick.ts_ms if tick else int(c0.timestamp.timestamp() * 1000)

        if c0.is_bullish and c0.range >= (avg_range * 1.6) and c0.body >= (c0.range * 0.7):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=c0.close,
                timestamp_ms=ts,
                reasons=[
                    f"Bullish Momentum Candle: Range {c0.range:.2f} pts (> 1.6x avg {avg_range:.2f} pts)",
                    f"Dominasi Body: {c0.body / c0.range * 100:.1f}% dari total rentang bar",
                ],
            )
        if c0.is_bearish and c0.range >= (avg_range * 1.6) and c0.body >= (c0.range * 0.7):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=c0.close,
                timestamp_ms=ts,
                reasons=[
                    f"Bearish Momentum Candle: Range {c0.range:.2f} pts (> 1.6x avg {avg_range:.2f} pts)",
                    f"Dominasi Body: {c0.body / c0.range * 100:.1f}% dari total rentang bar",
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
            description="Penyusutan volatilitas 3 bar berturut-turut menjelang ledakan harga.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(4)
        if len(candles) < 3:
            return None
        c0, c1, c2 = candles[0], candles[1], candles[2]
        tick = buffer.latest_tick
        ts = tick.ts_ms if tick else int(c0.timestamp.timestamp() * 1000)

        if c0.range < c1.range < c2.range and c0.range <= (c2.range * 0.5):
            dir_choice = SignalDirection.BUY if c0.close >= c0.open else SignalDirection.SELL
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=dir_choice,
                price=c0.close,
                timestamp_ms=ts,
                reasons=[
                    f"Kompresi Rentang 3 Bar: {c2.range:.2f} -> {c1.range:.2f} -> {c0.range:.2f} pts",
                    f"Volatilitas menciut > 50% bersiap untuk ekspansi searah close terakhir",
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
            description="Perbandingan ekstrem antara wick penolakan dan body candle (Hammer/Shooting Star).",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(2)
        if not candles:
            return None
        c0 = candles[0]
        tick = buffer.latest_tick
        ts = tick.ts_ms if tick else int(c0.timestamp.timestamp() * 1000)

        # Hammer / Bullish Wick Rejection
        if c0.lower_wick >= (c0.range * 0.60) and c0.upper_wick <= (c0.range * 0.20):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=c0.close,
                timestamp_ms=ts,
                reasons=[
                    f"Ekor Bawah (Lower Wick) Dominan: {c0.lower_wick:.2f} pts ({c0.lower_wick / c0.range * 100:.1f}% dari bar)",
                    f"Ekor Atas minimal: {c0.upper_wick:.2f} pts (Rejection buyer kuat di dasar)",
                ],
            )

        # Shooting Star / Bearish Wick Rejection
        if c0.upper_wick >= (c0.range * 0.60) and c0.lower_wick <= (c0.range * 0.20):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=c0.close,
                timestamp_ms=ts,
                reasons=[
                    f"Ekor Atas (Upper Wick) Dominan: {c0.upper_wick:.2f} pts ({c0.upper_wick / c0.range * 100:.1f}% dari bar)",
                    f"Ekor Bawah minimal: {c0.lower_wick:.2f} pts (Rejection seller kuat di pucuk)",
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
            description="Body candle membesar berturut-turut menunjukkan akselerasi minat pasar.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(4)
        if len(candles) < 3:
            return None
        c0, c1, c2 = candles[0], candles[1], candles[2]
        tick = buffer.latest_tick
        ts = tick.ts_ms if tick else int(c0.timestamp.timestamp() * 1000)

        if c0.is_bullish and c1.is_bullish and c2.is_bullish:
            if c0.body > (c1.body * 1.2) > (c2.body * 1.44):
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    price=c0.close,
                    timestamp_ms=ts,
                    reasons=[
                        f"Ekspansi Body Bullish: {c2.body:.2f} -> {c1.body:.2f} -> {c0.body:.2f} pts",
                        f"Akselerasi ukuran candle meningkat bertahap > 20% per bar",
                    ],
                )

        if c0.is_bearish and c1.is_bearish and c2.is_bearish:
            if c0.body > (c1.body * 1.2) > (c2.body * 1.44):
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    price=c0.close,
                    timestamp_ms=ts,
                    reasons=[
                        f"Ekspansi Body Bearish: {c2.body:.2f} -> {c1.body:.2f} -> {c0.body:.2f} pts",
                        f"Akselerasi tekanan jual meningkat bertahap > 20% per bar",
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
            description="Body candle mengecil berturut-turut menandakan hilangnya momentum.",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(4)
        if len(candles) < 3:
            return None
        c0, c1, c2 = candles[0], candles[1], candles[2]
        tick = buffer.latest_tick
        ts = tick.ts_ms if tick else int(c0.timestamp.timestamp() * 1000)

        if c0.body < (c1.body * 0.7) < (c2.body * 0.49):
            # Exhaustion fade signal
            if c2.is_bullish:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    price=c0.close,
                    timestamp_ms=ts,
                    reasons=[
                        f"Kontraksi Body Bullish: {c2.body:.2f} -> {c1.body:.2f} -> {c0.body:.2f} pts",
                        "Kekuatan buyer mengecil drastis, sinyal exhaustion reversal",
                    ],
                )
            elif c2.is_bearish:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    price=c0.close,
                    timestamp_ms=ts,
                    reasons=[
                        f"Kontraksi Body Bearish: {c2.body:.2f} -> {c1.body:.2f} -> {c0.body:.2f} pts",
                        "Kekuatan seller mengecil drastis, sinyal exhaustion reversal",
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
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(5)
        if len(candles) < 4:
            return None
        c0, c1, c2, c3 = candles[0], candles[1], candles[2], candles[3]
        tick = buffer.latest_tick
        ts = tick.ts_ms if tick else int(c0.timestamp.timestamp() * 1000)

        # Bullish staircase
        if (c0.high > c1.high > c2.high > c3.high) and (c0.low > c1.low > c2.low > c3.low):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=c0.close,
                timestamp_ms=ts,
                reasons=[
                    "Anak Tangga Naik (Bullish Staircase) 4 Bar",
                    f"Urutan High: {c3.high:.2f} -> {c2.high:.2f} -> {c1.high:.2f} -> {c0.high:.2f}",
                    f"Urutan Low: {c3.low:.2f} -> {c2.low:.2f} -> {c1.low:.2f} -> {c0.low:.2f}",
                ],
            )

        # Bearish staircase
        if (c0.high < c1.high < c2.high < c3.high) and (c0.low < c1.low < c2.low < c3.low):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=c0.close,
                timestamp_ms=ts,
                reasons=[
                    "Anak Tangga Turun (Bearish Staircase) 4 Bar",
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
            description="Sekuens khusus urutan warna dan ukuran candle (misal Bear-Bear-Doji-Bull).",
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(5)
        if len(candles) < 4:
            return None
        c0, c1, c2, c3 = candles[0], candles[1], candles[2], candles[3]
        tick = buffer.latest_tick
        ts = tick.ts_ms if tick else int(c0.timestamp.timestamp() * 1000)

        # Bullish Turnaround Sequence: Bear -> Bear -> Small Bar/Doji -> Strong Bull
        if c3.is_bearish and c2.is_bearish and c1.is_doji and c0.is_bullish and c0.body > (c1.range * 1.5):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=c0.close,
                timestamp_ms=ts,
                reasons=[
                    "Sekuens Pembalikan Bullish: [Bear] -> [Bear] -> [Doji] -> [Strong Bull]",
                    f"C[0] Bullish ({c0.body:.2f} pts) membongkar jeda Doji C[1]",
                ],
            )

        # Bearish Turnaround Sequence: Bull -> Bull -> Small Bar/Doji -> Strong Bear
        if c3.is_bullish and c2.is_bullish and c1.is_doji and c0.is_bearish and c0.body > (c1.range * 1.5):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=c0.close,
                timestamp_ms=ts,
                reasons=[
                    "Sekuens Pembalikan Bearish: [Bull] -> [Bull] -> [Doji] -> [Strong Bear]",
                    f"C[0] Bearish ({c0.body:.2f} pts) membongkar jeda Doji C[1]",
                ],
            )
        return None
