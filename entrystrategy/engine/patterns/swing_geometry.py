"""Micro-Swing Geometry Entry Patterns (Pola 31-35)."""
from typing import Optional, List
from entrystrategy.engine.base import BasePattern
from entrystrategy.core.models import EntrySignal, SignalDirection, Candle, TickData
from entrystrategy.core.buffer import MarketBuffer


class MicroDoubleTopPattern(BasePattern):
    """Pola 31: Micro Double Top."""
    def __init__(self):
        super().__init__(
            pattern_id=31,
            name="Micro Double Top",
            category="Swing",
            description="Dua puncak harga lokal sejajar yang gagal ditembus ke atas.",
            cooldown_ms=4000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(10)
        tick = buffer.latest_tick
        if len(candles) < 6 or not tick:
            return None
        # Look for peak 1 and peak 2 with valley in between
        # c0, c1, c2, c3, c4, c5...
        highs = [c.high for c in candles]
        
        # Check if candles[1] or candles[0] forms a second peak near an earlier peak
        p2 = highs[0]
        for i in range(2, min(7, len(highs))):
            p1 = highs[i]
            if abs(p1 - p2) <= 0.25:  # Double top within 0.25 pts tolerance
                valley = min(candles[k].low for k in range(1, i))
                depth = min(p1, p2) - valley
                if depth >= 0.50 and tick.mid < (p2 - 0.15):
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.SELL,
                        price=tick.bid,
                        timestamp_ms=tick.ts_ms,
                        reasons=[
                            f"Micro Double Top: Puncak 1 ({p1:.2f}) & Puncak 2 ({p2:.2f}) selisih {abs(p1 - p2):.2f} pts",
                            f"Neckline Valley di {valley:.2f} (Kedalaman {depth:.2f} pts)",
                            "Penolakan di puncak kedua terkonfirmasi",
                        ],
                    )
        return None


class MicroDoubleBottomPattern(BasePattern):
    """Pola 32: Micro Double Bottom."""
    def __init__(self):
        super().__init__(
            pattern_id=32,
            name="Micro Double Bottom",
            category="Swing",
            description="Dua lembah harga lokal sejajar yang gagal ditembus ke bawah.",
            cooldown_ms=4000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(10)
        tick = buffer.latest_tick
        if len(candles) < 6 or not tick:
            return None
        lows = [c.low for c in candles]
        
        b2 = lows[0]
        for i in range(2, min(7, len(lows))):
            b1 = lows[i]
            if abs(b1 - b2) <= 0.25:  # Double bottom within 0.25 pts tolerance
                peak = max(candles[k].high for k in range(1, i))
                height = peak - max(b1, b2)
                if height >= 0.50 and tick.mid > (b2 + 0.15):
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.BUY,
                        price=tick.ask,
                        timestamp_ms=tick.ts_ms,
                        reasons=[
                            f"Micro Double Bottom: Lembah 1 ({b1:.2f}) & Lembah 2 ({b2:.2f}) selisih {abs(b1 - b2):.2f} pts",
                            f"Neckline Peak di {peak:.2f} (Tinggi {height:.2f} pts)",
                            "Pantulan di lembah kedua terkonfirmasi",
                        ],
                    )
        return None


class MicroSwingBreakPattern(BasePattern):
    """Pola 33: Micro Swing Break."""
    def __init__(self):
        super().__init__(
            pattern_id=33,
            name="Micro Swing Break",
            category="Swing",
            description="Penembusan swing lokal terdekat (High/Low 5 bar terakhir).",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(7)
        tick = buffer.latest_tick
        if len(candles) < 5 or not tick:
            return None
        # Swing high & low of bars 1 to 5
        swing_high = max(c.high for c in candles[1:6])
        swing_low = min(c.low for c in candles[1:6])
        px = tick.mid

        if px > (swing_high + 0.15):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=tick.ask,
                timestamp_ms=tick.ts_ms,
                reasons=[
                    f"Micro Swing High 5 Bar ({swing_high:.2f}) Berhasil Ditembus",
                    f"Harga saat ini ({px:.2f}) melanjutkan ekspansi",
                ],
            )
        if px < (swing_low - 0.15):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=tick.bid,
                timestamp_ms=tick.ts_ms,
                reasons=[
                    f"Micro Swing Low 5 Bar ({swing_low:.2f}) Berhasil Ditembus",
                    f"Harga saat ini ({px:.2f}) melanjutkan penurunan",
                ],
            )
        return None


class MicroSwingFailurePattern(BasePattern):
    """Pola 34: Micro Swing Failure."""
    def __init__(self):
        super().__init__(
            pattern_id=34,
            name="Micro Swing Failure",
            category="Swing",
            description="Kegagalan menembus swing lokal terdekat memicu pembalikan cepat.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(7)
        ticks = buffer.get_recent_ticks(15)
        if len(candles) < 5 or len(ticks) < 10:
            return None
        swing_high = max(c.high for c in candles[1:6])
        swing_low = min(c.low for c in candles[1:6])
        t_now = ticks[-1]
        
        # Probed swing high then collapsed
        if any(t.mid >= swing_high for t in ticks) and t_now.mid < (swing_high - 0.20):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t_now.bid,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Kegagalan Tembus Swing High ({swing_high:.2f})",
                    f"Uji coba breakout ditolak, harga terseret turun ke {t_now.mid:.2f}",
                ],
            )
        # Probed swing low then bounced
        if any(t.mid <= swing_low for t in ticks) and t_now.mid > (swing_low + 0.20):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t_now.ask,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Kegagalan Tembus Swing Low ({swing_low:.2f})",
                    f"Uji coba breakdown ditolak, harga memantul naik ke {t_now.mid:.2f}",
                ],
            )
        return None


class ThreePushPattern(BasePattern):
    """Pola 35: Three-Push Pattern."""
    def __init__(self):
        super().__init__(
            pattern_id=35,
            name="Three-Push Pattern",
            category="Swing",
            description="Tiga dorongan searah bertahap dengan daya dorong mengecil (Exhaustion Wedge).",
            cooldown_ms=4000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(7)
        tick = buffer.latest_tick
        if len(candles) < 5 or not tick:
            return None
        # Push 1: candles[4], Push 2: candles[2], Push 3: candles[0]
        # Three pushes to the upside (Higher Highs with diminishing thrusts)
        h3, h2, h1 = candles[4].high, candles[2].high, candles[0].high
        thrust1 = h2 - h3
        thrust2 = h1 - h2
        
        if (h1 > h2 > h3) and (thrust1 > 0) and (thrust2 > 0) and (thrust2 < thrust1 * 0.75):
            if tick.mid < candles[0].close - 0.10:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    price=tick.bid,
                    timestamp_ms=tick.ts_ms,
                    reasons=[
                        "Three-Push Pattern Bullish Exhaustion (3 Dorongan Naik)",
                        f"Dorongan 1 (+{thrust1:.2f} pts) -> Dorongan 2 (+{thrust2:.2f} pts, susut > 25%)",
                        f"Puncak ke-3 ({h1:.2f}) kehilangan tenaga, terkonfirmasi reversal",
                    ],
                )

        # Three pushes to the downside (Lower Lows with diminishing thrusts)
        l3, l2, l1 = candles[4].low, candles[2].low, candles[0].low
        drop1 = l3 - l2
        drop2 = l2 - l1
        if (l1 < l2 < l3) and (drop1 > 0) and (drop2 > 0) and (drop2 < drop1 * 0.75):
            if tick.mid > candles[0].close + 0.10:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    price=tick.ask,
                    timestamp_ms=tick.ts_ms,
                    reasons=[
                        "Three-Push Pattern Bearish Exhaustion (3 Dorongan Turun)",
                        f"Dorongan 1 ({drop1:.2f} pts) -> Dorongan 2 ({drop2:.2f} pts, susut > 25%)",
                        f"Lembah ke-3 ({l1:.2f}) kehilangan tenaga, terkonfirmasi rebound",
                    ],
                )
        return None
