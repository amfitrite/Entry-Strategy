"""Candle-only swing geometry patterns for M1 and M5."""
from typing import Optional
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.core.models import EntrySignal, SignalDirection, PatternRole
from entrystrategy.engine.base import BasePattern


def _signal(pattern, buffer, candle, direction, reference, invalidation, reasons, metrics=None):
    return EntrySignal(
        pattern_id=pattern.pattern_id,
        family_name=pattern.name,
        direction=direction,
        reference_price=round(reference, 2),
        trigger_price=round(candle.close, 2),
        invalidation_price=round(invalidation, 2),
        pattern_role=pattern.role,
        phenomenon=pattern.phenomenon,
        event_id=f"swing:{pattern.pattern_id}:{candle.timestamp.isoformat()}:{direction.value}",
        price=round(candle.close, 2),
        timestamp_ms=buffer.current_time_ms,
        reasons=reasons,
        metrics=metrics or {},
    )


class MicroDoubleTopPattern(BasePattern):
    """31: two comparable swing highs followed by bearish rejection."""

    def __init__(self):
        super().__init__(
            pattern_id=31,
            name="Micro Double Top",
            category="Swing",
            description="Dua puncak lokal dengan toleransi harga rapat dan candle kedua ditolak turun.",
            role=PatternRole.ENTRY,
            phenomenon="Dua pengujian swing high yang gagal menghasilkan high baru secara bermakna",
            cooldown_ms=4000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(10)
        if len(candles) < 6:
            return None
        c0 = candles[0]
        second_high = c0.high
        for i in range(2, min(7, len(candles))):
            first_high = candles[i].high
            if abs(first_high - second_high) > 0.25:
                continue
            valley = min(c.low for c in candles[1:i])
            depth = min(first_high, second_high) - valley
            if depth >= 0.50 and c0.is_bearish and c0.close < second_high - 0.15:
                return _signal(
                    self, buffer, c0, SignalDirection.SELL, second_high, max(first_high, second_high) + 0.15,
                    [
                        f"Dua puncak {first_high:.2f} dan {second_high:.2f} berada dalam toleransi 0.25 pts",
                        f"Neckline/valley {valley:.2f}; kedalaman struktur {depth:.2f} pts",
                        "Candle kedua bearish dan close menjauh dari puncak",
                    ],
                    {"peak_1": round(first_high, 2), "peak_2": round(second_high, 2), "valley": round(valley, 2), "depth": round(depth, 2)},
                )
        return None


class MicroDoubleBottomPattern(BasePattern):
    """32: two comparable swing lows followed by bullish rejection."""

    def __init__(self):
        super().__init__(
            pattern_id=32,
            name="Micro Double Bottom",
            category="Swing",
            description="Dua lembah lokal dengan toleransi harga rapat dan candle kedua ditolak naik.",
            role=PatternRole.ENTRY,
            phenomenon="Dua pengujian swing low yang gagal menghasilkan low baru secara bermakna",
            cooldown_ms=4000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(10)
        if len(candles) < 6:
            return None
        c0 = candles[0]
        second_low = c0.low
        for i in range(2, min(7, len(candles))):
            first_low = candles[i].low
            if abs(first_low - second_low) > 0.25:
                continue
            peak = max(c.high for c in candles[1:i])
            height = peak - max(first_low, second_low)
            if height >= 0.50 and c0.is_bullish and c0.close > second_low + 0.15:
                return _signal(
                    self, buffer, c0, SignalDirection.BUY, second_low, min(first_low, second_low) - 0.15,
                    [
                        f"Dua lembah {first_low:.2f} dan {second_low:.2f} berada dalam toleransi 0.25 pts",
                        f"Neckline/peak {peak:.2f}; tinggi struktur {height:.2f} pts",
                        "Candle kedua bullish dan close menjauh dari lembah",
                    ],
                    {"bottom_1": round(first_low, 2), "bottom_2": round(second_low, 2), "peak": round(peak, 2), "height": round(height, 2)},
                )
        return None


class MicroSwingBreakPattern(BasePattern):
    """33: completed candle close beyond the previous five-bar swing."""

    def __init__(self):
        super().__init__(
            pattern_id=33,
            name="Micro Swing Break",
            category="Swing",
            description="Close candle menembus swing high/low lima candle sebelumnya; wick saja tidak dihitung.",
            role=PatternRole.ENTRY,
            phenomenon="Breakout swing lokal terkonfirmasi oleh penutupan candle",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(7)
        if len(candles) < 6:
            return None
        c0 = candles[0]
        swing_high = max(c.high for c in candles[1:6])
        swing_low = min(c.low for c in candles[1:6])
        if c0.is_bullish and c0.close > swing_high + 0.15:
            return _signal(
                self, buffer, c0, SignalDirection.BUY, swing_high, swing_low,
                [f"Close bullish {c0.close:.2f} menembus swing high {swing_high:.2f}", "Break dikonfirmasi candle close, bukan penetrasi wick intrabar"],
                {"swing_high": round(swing_high, 2), "swing_low": round(swing_low, 2), "penetration": round(c0.close - swing_high, 2)},
            )
        if c0.is_bearish and c0.close < swing_low - 0.15:
            return _signal(
                self, buffer, c0, SignalDirection.SELL, swing_low, swing_high,
                [f"Close bearish {c0.close:.2f} menembus swing low {swing_low:.2f}", "Break dikonfirmasi candle close, bukan penetrasi wick intrabar"],
                {"swing_high": round(swing_high, 2), "swing_low": round(swing_low, 2), "penetration": round(swing_low - c0.close, 2)},
            )
        return None


class MicroSwingFailurePattern(BasePattern):
    """34: wick sweeps a confirmed local swing, but candle closes back inside."""

    def __init__(self):
        super().__init__(
            pattern_id=34,
            name="Micro Swing Failure",
            category="Swing",
            description="Wick menyapu swing high/low lokal lalu candle close kembali ke dalam range.",
            role=PatternRole.ENTRY,
            phenomenon="Swing failure pattern berbasis wick sweep dan candle close reclaim",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(7)
        if len(candles) < 6:
            return None
        c0 = candles[0]
        swing_high = max(c.high for c in candles[1:6])
        swing_low = min(c.low for c in candles[1:6])
        if c0.high > swing_high + 0.05 and c0.close < swing_high - 0.15 and c0.is_bearish:
            return _signal(
                self, buffer, c0, SignalDirection.SELL, swing_high, c0.high + 0.15,
                [f"Wick menyapu swing high {swing_high:.2f} hingga {c0.high:.2f}", f"Close bearish kembali di bawah swing high pada {c0.close:.2f}"],
                {"swing_high": round(swing_high, 2), "sweep_high": round(c0.high, 2)},
            )
        if c0.low < swing_low - 0.05 and c0.close > swing_low + 0.15 and c0.is_bullish:
            return _signal(
                self, buffer, c0, SignalDirection.BUY, swing_low, c0.low - 0.15,
                [f"Wick menyapu swing low {swing_low:.2f} hingga {c0.low:.2f}", f"Close bullish kembali di atas swing low pada {c0.close:.2f}"],
                {"swing_low": round(swing_low, 2), "sweep_low": round(c0.low, 2)},
            )
        return None


class ThreePushPattern(BasePattern):
    """35: three diminishing directional pushes followed by a candle-close reversal."""

    def __init__(self):
        super().__init__(
            pattern_id=35,
            name="Three-Push Pattern",
            category="Swing",
            description="Tiga dorongan dengan thrust mengecil, lalu candle konfirmasi menembus basis push ketiga.",
            role=PatternRole.ENTRY,
            phenomenon="Kelelahan tren setelah tiga dorongan progresif dan reversal candle-close",
            cooldown_ms=4000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(7)
        if len(candles) < 6:
            return None
        trigger = candles[0]
        push3, push2, push1 = candles[1], candles[3], candles[5]

        up1 = push2.high - push1.high
        up2 = push3.high - push2.high
        if (
            push1.high < push2.high < push3.high
            and up1 > 0 and 0 < up2 < up1 * 0.75
            and trigger.is_bearish and trigger.close < push3.low
        ):
            return _signal(
                self, buffer, trigger, SignalDirection.SELL, push3.high, push3.high + 0.15,
                ["Tiga dorongan naik menghasilkan higher high dengan thrust kedua mengecil lebih dari 25%", f"Candle bearish menutup di bawah basis push ketiga {push3.low:.2f}"],
                {"thrust_1": round(up1, 2), "thrust_2": round(up2, 2), "push_3_high": round(push3.high, 2)},
            )

        down1 = push1.low - push2.low
        down2 = push2.low - push3.low
        if (
            push1.low > push2.low > push3.low
            and down1 > 0 and 0 < down2 < down1 * 0.75
            and trigger.is_bullish and trigger.close > push3.high
        ):
            return _signal(
                self, buffer, trigger, SignalDirection.BUY, push3.low, push3.low - 0.15,
                ["Tiga dorongan turun menghasilkan lower low dengan thrust kedua mengecil lebih dari 25%", f"Candle bullish menutup di atas basis push ketiga {push3.high:.2f}"],
                {"thrust_1": round(down1, 2), "thrust_2": round(down2, 2), "push_3_low": round(push3.low, 2)},
            )
        return None
