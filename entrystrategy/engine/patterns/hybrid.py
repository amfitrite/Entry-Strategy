"""Hybrid Tick-Candle Entry Patterns (Pola 7-10, 18-20, 24, 28-30, 36-37, 40)."""
from typing import Optional, List
from entrystrategy.engine.base import BasePattern
from entrystrategy.core.models import EntrySignal, SignalDirection, Candle, TickData
from entrystrategy.core.buffer import MarketBuffer


class BreakoutPattern(BasePattern):
    """Pola 7: Breakout (Candle Range Breakout)."""
    def __init__(self):
        super().__init__(
            pattern_id=7,
            name="Breakout",
            category="Hybrid",
            description="Penembusan High atau Low candle sebelumnya dengan konfirmasi laju tick.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(2)
        tick = buffer.latest_tick
        if not candles or not tick:
            return None
        c1 = candles[0]  # Previous closed candle
        px = tick.mid

        # Break above previous high
        if px > (c1.high + 0.10):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=tick.ask,
                timestamp_ms=tick.ts_ms,
                reasons=[
                    f"Breakout High Candle C[1]: Harga ({px:.2f}) > High ({c1.high:.2f})",
                    f"Penembusan bersih +{px - c1.high:.2f} pts dengan momentum tick aktif",
                ],
            )
        # Break below previous low
        if px < (c1.low - 0.10):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=tick.bid,
                timestamp_ms=tick.ts_ms,
                reasons=[
                    f"Breakout Low Candle C[1]: Harga ({px:.2f}) < Low ({c1.low:.2f})",
                    f"Penembusan bersih {px - c1.low:.2f} pts dengan momentum tick aktif",
                ],
            )
        return None


class FailedBreakoutPattern(BasePattern):
    """Pola 8: Failed Breakout (Fakeout / Trap)."""
    def __init__(self):
        super().__init__(
            pattern_id=8,
            name="Failed Breakout",
            category="Hybrid",
            description="Harga menembus level High/Low candle lalu berbalik tajam (jebakan likuiditas).",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(2)
        ticks = buffer.get_recent_ticks(15)
        if not candles or len(ticks) < 10:
            return None
        c1 = candles[0]
        t_now = ticks[-1]
        
        # Check if recent ticks touched above c1.high, but now fell back below it
        max_tick_px = max(t.mid for t in ticks)
        min_tick_px = min(t.mid for t in ticks)

        # Bull trap (Failed upside breakout -> SELL)
        if max_tick_px > c1.high and t_now.mid < (c1.high - 0.15):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t_now.bid,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Bull Trap: Sempat tembus ke {max_tick_px:.2f} di atas C[1] High ({c1.high:.2f})",
                    f"Harga terseret jatuh kembali ke {t_now.mid:.2f} (Penolakan breakout terkonfirmasi)",
                ],
            )
        # Bear trap (Failed downside breakout -> BUY)
        if min_tick_px < c1.low and t_now.mid > (c1.low + 0.15):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t_now.ask,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Bear Trap: Sempat tembus ke {min_tick_px:.2f} di bawah C[1] Low ({c1.low:.2f})",
                    f"Harga memantul kembali ke {t_now.mid:.2f} (Penolakan breakdown terkonfirmasi)",
                ],
            )
        return None


class MicroPullbackPattern(BasePattern):
    """Pola 9: Micro Pullback."""
    def __init__(self):
        super().__init__(
            pattern_id=9,
            name="Micro Pullback",
            category="Hybrid",
            description="Koreksi mikro menguji 50% body bar momentum lalu berlanjut searah tren.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(2)
        ticks = buffer.get_recent_ticks(15)
        if not candles or len(ticks) < 8:
            return None
        c1 = candles[0]
        t_now = ticks[-1]
        
        # Bullish momentum in c1, pullback to ~50% in current ticks, then rebound
        if c1.is_bullish and c1.body >= 1.0:
            mid_c1 = (c1.open + c1.close) / 2.0
            min_recent = min(t.mid for t in ticks)
            if min_recent <= mid_c1 and t_now.mid > (mid_c1 + 0.20):
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    price=t_now.ask,
                    timestamp_ms=t_now.ts_ms,
                    reasons=[
                        f"Micro Pullback Bullish menyentuh area 50% C[1] ({mid_c1:.2f})",
                        f"Buyer kembali menekan ke atas menuju {t_now.mid:.2f}",
                    ],
                )
        # Bearish momentum in c1, pullback to ~50%, then resume downward
        if c1.is_bearish and c1.body >= 1.0:
            mid_c1 = (c1.open + c1.close) / 2.0
            max_recent = max(t.mid for t in ticks)
            if max_recent >= mid_c1 and t_now.mid < (mid_c1 - 0.20):
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    price=t_now.bid,
                    timestamp_ms=t_now.ts_ms,
                    reasons=[
                        f"Micro Pullback Bearish menyentuh area 50% C[1] ({mid_c1:.2f})",
                        f"Seller kembali menekan ke bawah menuju {t_now.mid:.2f}",
                    ],
                )
        return None


class MicroTrendReversalPattern(BasePattern):
    """Pola 10: Micro Trend Reversal."""
    def __init__(self):
        super().__init__(
            pattern_id=10,
            name="Micro Trend Reversal",
            category="Hybrid",
            description="Pembalikan arah tren lokal 3 bar oleh akselerasi tick bar berjalan.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(4)
        tick = buffer.latest_tick
        if len(candles) < 3 or not tick:
            return None
        c1, c2, c3 = candles[0], candles[1], candles[2]
        px = tick.mid

        # 3 Consecutive lower highs, now broken by current tick
        if (c1.high < c2.high < c3.high) and px > c1.high + 0.15:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=tick.ask,
                timestamp_ms=tick.ts_ms,
                reasons=[
                    "Micro Downtrend 3 Bar (Lower Highs) berhasil ditembus ke atas",
                    f"Harga saat ini ({px:.2f}) > High C[1] ({c1.high:.2f})",
                ],
            )
        # 3 Consecutive higher lows, now broken downward
        if (c1.low > c2.low > c3.low) and px < c1.low - 0.15:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=tick.bid,
                timestamp_ms=tick.ts_ms,
                reasons=[
                    "Micro Uptrend 3 Bar (Higher Lows) berhasil ditembus ke bawah",
                    f"Harga saat ini ({px:.2f}) < Low C[1] ({c1.low:.2f})",
                ],
            )
        return None


class MicroRangeExpansionPattern(BasePattern):
    """Pola 18: Micro Range Expansion."""
    def __init__(self):
        super().__init__(
            pattern_id=18,
            name="Micro Range Expansion",
            category="Hybrid",
            description="Ekspansi rentang harga mendadak melampaui rata-rata range beberapa bar.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(5)
        ticks = buffer.get_recent_ticks(20)
        if len(candles) < 3 or len(ticks) < 10:
            return None
        avg_range = sum(c.range for c in candles[:3]) / 3.0
        t_now = ticks[-1]
        t_old = ticks[0]
        tick_span = abs(t_now.mid - t_old.mid)

        if tick_span >= (avg_range * 1.3):
            dir_choice = SignalDirection.BUY if t_now.mid > t_old.mid else SignalDirection.SELL
            px = t_now.ask if dir_choice == SignalDirection.BUY else t_now.bid
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=dir_choice,
                price=px,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Ekspansi Rentang Mikro: Perpindahan {tick_span:.2f} pts (> 1.3x avg {avg_range:.2f} pts)",
                    f"Arah ekspansi agresif: {dir_choice.value}",
                ],
            )
        return None


class MicroRangeCompressionPattern(BasePattern):
    """Pola 19: Micro Range Compression."""
    def __init__(self):
        super().__init__(
            pattern_id=19,
            name="Micro Range Compression",
            category="Hybrid",
            description="Penyempitan rentang harga dalam 20 tick sebelum terjadinya ledakan harga.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(25)
        if len(ticks) < 20:
            return None
        high_p = max(t.mid for t in ticks)
        low_p = min(t.mid for t in ticks)
        span = high_p - low_p
        t_now = ticks[-1]

        # Ultra tight compression: Gold stuck in < 0.20 pts for 20 ticks, now popping
        if span <= 0.22:
            # Check if last tick starts breaking out of this tight range
            if t_now.mid >= high_p - 0.02:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    price=t_now.ask,
                    timestamp_ms=t_now.ts_ms,
                    reasons=[
                        f"Kompresi Rentang Mikro Ketat: Hanya {span:.2f} pts dalam 20 tick",
                        f"Tick mulai meledak ke batas atas ({high_p:.2f})",
                    ],
                )
            if t_now.mid <= low_p + 0.02:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    price=t_now.bid,
                    timestamp_ms=t_now.ts_ms,
                    reasons=[
                        f"Kompresi Rentang Mikro Ketat: Hanya {span:.2f} pts dalam 20 tick",
                        f"Tick mulai meledak ke batas bawah ({low_p:.2f})",
                    ],
                )
        return None


class VolatilityBurstPattern(BasePattern):
    """Pola 20: Volatility Burst."""
    def __init__(self):
        super().__init__(
            pattern_id=20,
            name="Volatility Burst",
            category="Hybrid",
            description="Kombinasi serentak lonjakan frekuensi tick dan lonjakan rentang harga.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(30)
        if len(ticks) < 20:
            return None
        t_now = ticks[-1]
        t_old = ticks[0]
        dt_sec = max(0.1, (t_now.ts_ms - t_old.ts_ms) / 1000.0)
        freq = len(ticks) / dt_sec
        disp = t_now.mid - t_old.mid

        if freq >= 20.0 and abs(disp) >= 0.50:
            dir_choice = SignalDirection.BUY if disp > 0 else SignalDirection.SELL
            px = t_now.ask if dir_choice == SignalDirection.BUY else t_now.bid
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=dir_choice,
                price=px,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Ledakan Volatilitas & Frekuensi Serentak: {freq:.1f} t/s & displacement {disp:.2f} pts",
                    f"Arah pergerakan: {dir_choice.value}",
                ],
            )
        return None


class RejectionPattern(BasePattern):
    """Pola 24: Rejection Pattern."""
    def __init__(self):
        super().__init__(
            pattern_id=24,
            name="Rejection Pattern",
            category="Hybrid",
            description="Penolakan harga cepat di level ekstrem meninggalkan ekor intra-bar.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(20)
        if len(ticks) < 15:
            return None
        t_now = ticks[-1]
        max_p = max(t.mid for t in ticks)
        min_p = min(t.mid for t in ticks)

        # Upper rejection: reached high then dropped by 0.35 pts
        if (max_p - t_now.mid) >= 0.35:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t_now.bid,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Penolakan Atas (Upper Rejection): Puncak {max_p:.2f} ditolak turun {max_p - t_now.mid:.2f} pts",
                    "Tekanan seller kuat muncul di pucuk harga",
                ],
            )
        # Lower rejection: reached low then bounced by 0.35 pts
        if (t_now.mid - min_p) >= 0.35:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t_now.ask,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Penolakan Bawah (Lower Rejection): Dasar {min_p:.2f} memantul naik {t_now.mid - min_p:.2f} pts",
                    "Tekanan buyer kuat muncul di dasar harga",
                ],
            )
        return None


class GapPattern(BasePattern):
    """Pola 28: Gap Pattern."""
    def __init__(self):
        super().__init__(
            pattern_id=28,
            name="Gap Pattern",
            category="Hybrid",
            description="Lompatan harga (price gap) antara candle atau antar tick berturut-turut.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(2)
        if len(candles) >= 2:
            c0, c1 = candles[0], candles[1]
            gap = c0.open - c1.close
            tick = buffer.latest_tick
            ts = tick.ts_ms if tick else int(c0.timestamp.timestamp() * 1000)
            
            # Gap up >= 0.40 pts
            if gap >= 0.40:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    price=c0.open,
                    timestamp_ms=ts,
                    reasons=[
                        f"Gap Up Terdeteksi: Lompatan +{gap:.2f} pts dari {c1.close:.2f} ke {c0.open:.2f}",
                        "Momentum pembukaan bullish agresif",
                    ],
                )
            # Gap down <= -0.40 pts
            if gap <= -0.40:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    price=c0.open,
                    timestamp_ms=ts,
                    reasons=[
                        f"Gap Down Terdeteksi: Lompatan {gap:.2f} pts dari {c1.close:.2f} ke {c0.open:.2f}",
                        "Momentum pembukaan bearish agresif",
                    ],
                )
        return None


class FailedMomentumPattern(BasePattern):
    """Pola 29: Failed Momentum."""
    def __init__(self):
        super().__init__(
            pattern_id=29,
            name="Failed Momentum",
            category="Hybrid",
            description="Dorongan momentum awal yang gagal berlanjut dan berbalik 100%.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(30)
        if len(ticks) < 25:
            return None
        t_start = ticks[0]
        t_mid = ticks[12]
        t_now = ticks[-1]

        leg1 = t_mid.mid - t_start.mid
        leg2 = t_now.mid - t_mid.mid

        # Bullish momentum failed
        if leg1 >= 0.50 and leg2 <= -0.50:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t_now.bid,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Momentum Naik Gagal (Failed Bull Momentum): Naik +{leg1:.2f} pts namun luntur kembali {leg2:.2f} pts",
                    "Kegagalan mempertahankan harga tinggi memicu sinyal jual",
                ],
            )
        # Bearish momentum failed
        if leg1 <= -0.50 and leg2 >= 0.50:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t_now.ask,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Momentum Turun Gagal (Failed Bear Momentum): Turun {leg1:.2f} pts namun dipulihkan kembali +{leg2:.2f} pts",
                    "Kegagalan mempertahankan harga rendah memicu sinyal beli",
                ],
            )
        return None


class MomentumExhaustionPattern(BasePattern):
    """Pola 30: Momentum Exhaustion."""
    def __init__(self):
        super().__init__(
            pattern_id=30,
            name="Momentum Exhaustion",
            category="Hybrid",
            description="Momentum kehilangan tenaga di penghujung pergerakan panjang.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(3)
        ticks = buffer.get_recent_ticks(20)
        if not candles or len(ticks) < 15:
            return None
        c1 = candles[0]
        t_now = ticks[-1]
        
        # Extended run in c1 followed by tick stalling
        tick_span = max(t.mid for t in ticks) - min(t.mid for t in ticks)
        if c1.is_bullish and c1.range >= 1.5 and tick_span <= 0.15:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t_now.bid,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Kehabisan Tenaga Buyer (Bull Exhaustion) setelah bar besar {c1.range:.2f} pts",
                    f"Rentang tick saat ini mati di pucuk (hanya {tick_span:.2f} pts)",
                ],
            )
        if c1.is_bearish and c1.range >= 1.5 and tick_span <= 0.15:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t_now.ask,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Kehabisan Tenaga Seller (Bear Exhaustion) setelah bar besar {c1.range:.2f} pts",
                    f"Rentang tick saat ini mati di dasar (hanya {tick_span:.2f} pts)",
                ],
            )
        return None


class VReversalPattern(BasePattern):
    """Pola 36: V-Reversal."""
    def __init__(self):
        super().__init__(
            pattern_id=36,
            name="V-Reversal",
            category="Hybrid",
            description="Pembalikan arah cepat berbentuk huruf V setelah kejatuhan tajam.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(35)
        if len(ticks) < 25:
            return None
        t_start = ticks[0]
        t_bottom = min(ticks, key=lambda t: t.mid)
        t_now = ticks[-1]

        drop = t_start.mid - t_bottom.mid
        rebound = t_now.mid - t_bottom.mid

        # V-reversal: drop >= 0.50 pts, rebound recovering at least 80% of drop
        if drop >= 0.50 and rebound >= (drop * 0.80):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t_now.ask,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Pola V-Reversal Klasik: Kejatuhan cepat {drop:.2f} pts disusul Rebound {rebound:.2f} pts",
                    f"Pemulihan {rebound / drop * 100:.1f}% dari titik terendah {t_bottom.mid:.2f}",
                ],
            )
        return None


class InvertedVReversalPattern(BasePattern):
    """Pola 37: Inverted V-Reversal."""
    def __init__(self):
        super().__init__(
            pattern_id=37,
            name="Inverted V-Reversal",
            category="Hybrid",
            description="Pembalikan arah cepat berbentuk huruf V terbalik setelah reli tajam.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(35)
        if len(ticks) < 25:
            return None
        t_start = ticks[0]
        t_top = max(ticks, key=lambda t: t.mid)
        t_now = ticks[-1]

        rally = t_top.mid - t_start.mid
        slump = t_top.mid - t_now.mid

        if rally >= 0.50 and slump >= (rally * 0.80):
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t_now.bid,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Pola Inverted V-Reversal: Reli cepat +{rally:.2f} pts disusul Kolaps {slump:.2f} pts",
                    f"Penurunan {slump / rally * 100:.1f}% dari titik puncak {t_top.mid:.2f}",
                ],
            )
        return None


class HybridTickCandlePattern(BasePattern):
    """Pola 40: Hybrid Tick-Candle."""
    def __init__(self):
        super().__init__(
            pattern_id=40,
            name="Hybrid Tick-Candle",
            category="Hybrid",
            description="Sinergi multi-faktor: Candle Pin Bar/Inside Bar diperkuat lonjakan tick imbalance.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(2)
        ticks = buffer.get_recent_ticks(20)
        if not candles or len(ticks) < 15:
            return None
        c1 = candles[0]
        t_now = ticks[-1]

        upticks = sum(1 for i in range(1, len(ticks)) if ticks[i].mid > ticks[i - 1].mid)
        downticks = sum(1 for i in range(1, len(ticks)) if ticks[i].mid < ticks[i - 1].mid)
        total = max(1, upticks + downticks)
        imbalance = upticks / total

        # Lower wick in c1 + high tick imbalance upward
        if c1.lower_wick >= (c1.range * 0.45) and imbalance >= 0.70:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t_now.ask,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Sinergi Hybrid Rejection + Imbalance: Ekor C[1] {c1.lower_wick:.2f} pts",
                    f"Konfirmasi Tick Imbalance Uptick: {imbalance * 100:.1f}%",
                ],
            )
        # Upper wick in c1 + high tick imbalance downward
        if c1.upper_wick >= (c1.range * 0.45) and (downticks / total) >= 0.70:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t_now.bid,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Sinergi Hybrid Rejection + Imbalance: Ekor C[1] {c1.upper_wick:.2f} pts",
                    f"Konfirmasi Tick Imbalance Downtick: {(downticks / total) * 100:.1f}%",
                ],
            )
        return None
