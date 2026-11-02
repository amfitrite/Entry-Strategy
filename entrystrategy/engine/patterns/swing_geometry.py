"""Micro-Swing Geometry Entry Patterns (Pola 31-35)."""
from typing import Optional, List
from entrystrategy.engine.base import BasePattern
from entrystrategy.core.models import EntrySignal, SignalDirection, PatternRole, Candle, TickData
from entrystrategy.core.buffer import MarketBuffer


class MicroDoubleTopPattern(BasePattern):
    """Pola 31: Micro Double Top.
    Dua puncak harga lokal sejajar yang gagal ditembus ke atas.
    """
    def __init__(self):
        super().__init__(
            pattern_id=31,
            name="Micro Double Top",
            category="Swing",
            description="Dua puncak harga lokal sejajar yang gagal ditembus ke atas.",
            role=PatternRole.STRUCTURE,
            phenomenon="Dua puncak harga lokal sejajar yang gagal ditembus ke atas (double top)",
            cooldown_ms=4000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(10)
        tick = buffer.latest_tick
        if len(candles) < 6 or not tick:
            return None
        highs = [c.high for c in candles]
        
        p2 = highs[0]
        for i in range(2, min(7, len(highs))):
            p1 = highs[i]
            if abs(p1 - p2) <= 0.25:  # Double top within 0.25 pts tolerance
                valley = min(candles[k].low for k in range(1, i))
                depth = min(p1, p2) - valley
                if depth >= 0.50 and tick.mid < (p2 - 0.15):
                    ref_px = round(p2, 2)
                    trig_px = round(tick.bid, 2)
                    inval_px = round(max(p1, p2) + 0.15, 2)
                    event_id = f"micro_double_top_{tick.ts_ms}_{ref_px}"
                    if self._is_event_deduplicated(event_id):
                        return None
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.SELL,
                        reference_price=ref_px,
                        trigger_price=trig_px,
                        invalidation_price=inval_px,
                        pattern_role=self.role,
                        phenomenon=self.phenomenon,
                        event_id=event_id,
                        price=trig_px,
                        timestamp_ms=tick.ts_ms,
                        reasons=[
                            f"Micro Double Top: Puncak 1 ({p1:.2f}) & Puncak 2 ({p2:.2f}) selisih {abs(p1 - p2):.2f} pts",
                            f"Neckline Valley di {valley:.2f} (Kedalaman {depth:.2f} pts)",
                            "Penolakan di puncak kedua terkonfirmasi",
                        ],
                        metrics={"peak1": round(p1, 2), "peak2": ref_px, "valley": round(valley, 2)},
                    )
        return None


class MicroDoubleBottomPattern(BasePattern):
    """Pola 32: Micro Double Bottom.
    Dua lembah harga lokal sejajar yang gagal ditembus ke bawah.
    """
    def __init__(self):
        super().__init__(
            pattern_id=32,
            name="Micro Double Bottom",
            category="Swing",
            description="Dua lembah harga lokal sejajar yang gagal ditembus ke bawah.",
            role=PatternRole.STRUCTURE,
            phenomenon="Dua lembah harga lokal sejajar yang gagal ditembus ke bawah (double bottom)",
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
                    ref_px = round(b2, 2)
                    trig_px = round(tick.ask, 2)
                    inval_px = round(min(b1, b2) - 0.15, 2)
                    event_id = f"micro_double_bottom_{tick.ts_ms}_{ref_px}"
                    if self._is_event_deduplicated(event_id):
                        return None
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.BUY,
                        reference_price=ref_px,
                        trigger_price=trig_px,
                        invalidation_price=inval_px,
                        pattern_role=self.role,
                        phenomenon=self.phenomenon,
                        event_id=event_id,
                        price=trig_px,
                        timestamp_ms=tick.ts_ms,
                        reasons=[
                            f"Micro Double Bottom: Lembah 1 ({b1:.2f}) & Lembah 2 ({b2:.2f}) selisih {abs(b1 - b2):.2f} pts",
                            f"Neckline Peak di {peak:.2f} (Tinggi {height:.2f} pts)",
                            "Pantulan di lembah kedua terkonfirmasi",
                        ],
                        metrics={"bottom1": round(b1, 2), "bottom2": ref_px, "peak": round(peak, 2)},
                    )
        return None


class MicroSwingBreakPattern(BasePattern):
    """Pola 33: Micro Swing Break.
    Penembusan swing lokal terdekat (High/Low 5 bar terakhir).
    """
    def __init__(self):
        super().__init__(
            pattern_id=33,
            name="Micro Swing Break",
            category="Swing",
            description="Penembusan swing lokal terdekat (High/Low 5 bar terakhir).",
            role=PatternRole.ENTRY,
            phenomenon="Penembusan swing lokal terdekat (High/Low 5 bar terakhir)",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(7)
        tick = buffer.latest_tick
        if len(candles) < 5 or not tick:
            return None
        swing_high = max(c.high for c in candles[1:6])
        swing_low = min(c.low for c in candles[1:6])
        px = tick.mid

        if px > (swing_high + 0.15):
            ref_px = round(swing_high, 2)
            trig_px = round(tick.ask, 2)
            inval_px = round(swing_low, 2)
            event_id = f"swing_break_buy_{tick.ts_ms}_{ref_px}"
            if self._is_event_deduplicated(event_id):
                return None
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inval_px,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=event_id,
                price=trig_px,
                timestamp_ms=tick.ts_ms,
                reasons=[
                    f"Micro Swing High 5 Bar ({ref_px:.2f}) Berhasil Ditembus",
                    f"Harga saat ini ({px:.2f}) melanjutkan ekspansi",
                ],
                metrics={"swing_high": ref_px, "penetration": round(px - swing_high, 2)},
            )
        if px < (swing_low - 0.15):
            ref_px = round(swing_low, 2)
            trig_px = round(tick.bid, 2)
            inval_px = round(swing_high, 2)
            event_id = f"swing_break_sell_{tick.ts_ms}_{ref_px}"
            if self._is_event_deduplicated(event_id):
                return None
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inval_px,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=event_id,
                price=trig_px,
                timestamp_ms=tick.ts_ms,
                reasons=[
                    f"Micro Swing Low 5 Bar ({ref_px:.2f}) Berhasil Ditembus",
                    f"Harga saat ini ({px:.2f}) melanjutkan penurunan",
                ],
                metrics={"swing_low": ref_px, "penetration": round(swing_low - px, 2)},
            )
        return None


class MicroSwingFailurePattern(BasePattern):
    """Pola 34: Micro Swing Failure.
    Kegagalan menembus swing lokal terdekat memicu pembalikan cepat.
    """
    def __init__(self):
        super().__init__(
            pattern_id=34,
            name="Micro Swing Failure",
            category="Swing",
            description="Kegagalan menembus swing lokal terdekat memicu pembalikan cepat.",
            role=PatternRole.ENTRY,
            phenomenon="Kegagalan menembus swing lokal terdekat memicu pembalikan cepat",
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
        max_probe = max(t.mid for t in ticks)
        if max_probe >= swing_high and t_now.mid < (swing_high - 0.20):
            ref_px = round(swing_high, 2)
            trig_px = round(t_now.bid, 2)
            inval_px = round(max_probe + 0.15, 2)
            event_id = f"swing_fail_sell_{t_now.ts_ms}_{ref_px}"
            if self._is_event_deduplicated(event_id):
                return None
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inval_px,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=event_id,
                price=trig_px,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Kegagalan Tembus Swing High ({ref_px:.2f})",
                    f"Uji coba breakout ditolak, harga terseret turun ke {round(t_now.mid, 2):.2f}",
                ],
                metrics={"swing_high": ref_px, "probe_max": round(max_probe, 2)},
            )
        # Probed swing low then bounced
        min_probe = min(t.mid for t in ticks)
        if min_probe <= swing_low and t_now.mid > (swing_low + 0.20):
            ref_px = round(swing_low, 2)
            trig_px = round(t_now.ask, 2)
            inval_px = round(min_probe - 0.15, 2)
            event_id = f"swing_fail_buy_{t_now.ts_ms}_{ref_px}"
            if self._is_event_deduplicated(event_id):
                return None
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                reference_price=ref_px,
                trigger_price=trig_px,
                invalidation_price=inval_px,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=event_id,
                price=trig_px,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Kegagalan Tembus Swing Low ({ref_px:.2f})",
                    f"Uji coba breakdown ditolak, harga memantul naik ke {round(t_now.mid, 2):.2f}",
                ],
                metrics={"swing_low": ref_px, "probe_min": round(min_probe, 2)},
            )
        return None


class ThreePushPattern(BasePattern):
    """Pola 35: Three-Push Pattern.
    Tiga dorongan searah bertahap dengan daya dorong mengecil (exhaustion wedge),
    dikonfirmasi oleh patahnya base dorongan terakhir.
    """
    def __init__(self):
        super().__init__(
            pattern_id=35,
            name="Three-Push Pattern",
            category="Swing",
            description="Tiga dorongan searah bertahap dengan daya dorong mengecil disusul penembusan pembalikan.",
            role=PatternRole.STRUCTURE,
            phenomenon="Tiga dorongan bertahap dengan daya dorong mengecil disusul patahnya base dorongan terakhir",
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
            # Reversal confirmation: tick breaks below the low of candle[0] (base of push 3)
            if tick.mid < candles[0].low - 0.05:
                ref_px = round(h1, 2)
                trig_px = round(tick.bid, 2)
                inval_px = round(h1 + 0.15, 2)
                event_id = f"three_push_sell_{tick.ts_ms}_{ref_px}"
                if self._is_event_deduplicated(event_id):
                    return None
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    reference_price=ref_px,
                    trigger_price=trig_px,
                    invalidation_price=inval_px,
                    pattern_role=self.role,
                    phenomenon=self.phenomenon,
                    event_id=event_id,
                    price=trig_px,
                    timestamp_ms=tick.ts_ms,
                    reasons=[
                        "Three-Push Pattern Bullish Exhaustion (3 Dorongan Naik)",
                        f"Dorongan 1 (+{thrust1:.2f} pts) -> Dorongan 2 (+{thrust2:.2f} pts, susut > 25%)",
                        f"Puncak ke-3 ({ref_px:.2f}) gagal lanjut dan base ditembus ke bawah",
                    ],
                    metrics={"thrust1": round(thrust1, 2), "thrust2": round(thrust2, 2), "peak3": ref_px},
                )

        # Three pushes to the downside (Lower Lows with diminishing thrusts)
        l3, l2, l1 = candles[4].low, candles[2].low, candles[0].low
        drop1 = l3 - l2
        drop2 = l2 - l1
        if (l1 < l2 < l3) and (drop1 > 0) and (drop2 > 0) and (drop2 < drop1 * 0.75):
            # Reversal confirmation: tick breaks above the high of candle[0] (top of push 3)
            if tick.mid > candles[0].high + 0.05:
                ref_px = round(l1, 2)
                trig_px = round(tick.ask, 2)
                inval_px = round(l1 - 0.15, 2)
                event_id = f"three_push_buy_{tick.ts_ms}_{ref_px}"
                if self._is_event_deduplicated(event_id):
                    return None
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    reference_price=ref_px,
                    trigger_price=trig_px,
                    invalidation_price=inval_px,
                    pattern_role=self.role,
                    phenomenon=self.phenomenon,
                    event_id=event_id,
                    price=trig_px,
                    timestamp_ms=tick.ts_ms,
                    reasons=[
                        "Three-Push Pattern Bearish Exhaustion (3 Dorongan Turun)",
                        f"Dorongan 1 ({drop1:.2f} pts) -> Dorongan 2 ({drop2:.2f} pts, susut > 25%)",
                        f"Lembah ke-3 ({ref_px:.2f}) gagal lanjut dan top ditembus ke atas",
                    ],
                    metrics={"drop1": round(drop1, 2), "drop2": round(drop2, 2), "bottom3": ref_px},
                )
        return None
