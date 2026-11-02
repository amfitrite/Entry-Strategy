"""Pure Tick Microstructure Entry Patterns (Pola 11-17, 22, 23)."""
from typing import Optional, List
from entrystrategy.engine.base import BasePattern
from entrystrategy.core.models import EntrySignal, SignalDirection, TickData
from entrystrategy.core.buffer import MarketBuffer


class TickMomentumPattern(BasePattern):
    """Pola 11: Tick Momentum."""
    def __init__(self):
        super().__init__(
            pattern_id=11,
            name="Tick Momentum",
            category="Tick",
            description="Dorongan kuat harga dari akumulasi pergeseran tick dalam jendela mikro.",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(25)
        if len(ticks) < 15:
            return None
        t_now = ticks[-1]
        t_old = ticks[0]
        shift = t_now.mid - t_old.mid
        dt_sec = max(0.1, (t_now.ts_ms - t_old.ts_ms) / 1000.0)

        # Shift threshold: 0.60 points on Gold within ~1-2 sec
        if shift >= 0.50 and dt_sec <= 2.5:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t_now.ask,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Lonjakan Tick Naik: +{shift:.2f} pts dalam {dt_sec:.2f} detik ({len(ticks)} ticks)",
                    f"Harga bergerak dari {t_old.mid:.2f} -> {t_now.mid:.2f}",
                ],
                metrics={"shift": round(shift, 2), "dt_sec": round(dt_sec, 2)},
            )
        if shift <= -0.50 and dt_sec <= 2.5:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t_now.bid,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Lonjakan Tick Turun: {shift:.2f} pts dalam {dt_sec:.2f} detik ({len(ticks)} ticks)",
                    f"Harga jatuh dari {t_old.mid:.2f} -> {t_now.mid:.2f}",
                ],
                metrics={"shift": round(shift, 2), "dt_sec": round(dt_sec, 2)},
            )
        return None


class TickReversalPattern(BasePattern):
    """Pola 12: Tick Reversal."""
    def __init__(self):
        super().__init__(
            pattern_id=12,
            name="Tick Reversal",
            category="Tick",
            description="Pembalikan arah tick secara tiba-tiba setelah penurunan atau kenaikan cepat.",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(30)
        if len(ticks) < 20:
            return None
        # First half vs second half
        mid_idx = len(ticks) // 2
        t_first = ticks[0]
        t_mid = ticks[mid_idx]
        t_now = ticks[-1]

        leg1 = t_mid.mid - t_first.mid
        leg2 = t_now.mid - t_mid.mid

        # Sharp down leg followed by sharp up reversal
        if leg1 <= -0.40 and leg2 >= 0.35:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t_now.ask,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Pembalikan Tick Cepat (V-Shape Tick Reversal)",
                    f"Drop awal: {leg1:.2f} pts disusul Rebound instan: +{leg2:.2f} pts",
                ],
            )
        # Sharp up leg followed by sharp down reversal
        if leg1 >= 0.40 and leg2 <= -0.35:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t_now.bid,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Pembalikan Tick Cepat (Inverted V-Shape Tick Reversal)",
                    f"Rally awal: +{leg1:.2f} pts disusul Drop instan: {leg2:.2f} pts",
                ],
            )
        return None


class TickImbalancePattern(BasePattern):
    """Pola 13: Tick Imbalance."""
    def __init__(self):
        super().__init__(
            pattern_id=13,
            name="Tick Imbalance",
            category="Tick",
            description="Dominasi agresif uptick atau downtick (> 75%) dalam sampel 20 tick.",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(21)
        if len(ticks) < 20:
            return None
        upticks = 0
        downticks = 0
        for i in range(1, len(ticks)):
            diff = ticks[i].mid - ticks[i - 1].mid
            if diff > 0.001:
                upticks += 1
            elif diff < -0.001:
                downticks += 1

        total_active = upticks + downticks
        if total_active < 12:
            return None
        ratio_up = upticks / total_active
        t_now = ticks[-1]

        if ratio_up >= 0.75:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t_now.ask,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Dominasi Uptick Ekstrem: {ratio_up * 100:.1f}% ({upticks} naik vs {downticks} turun)",
                    f"Tekanan beli agresif terkonfirmasi pada micro-orderflow",
                ],
                metrics={"imbalance_ratio": round(ratio_up, 2)},
            )
        if (downticks / total_active) >= 0.75:
            ratio_down = downticks / total_active
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t_now.bid,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Dominasi Downtick Ekstrem: {ratio_down * 100:.1f}% ({downticks} turun vs {upticks} naik)",
                    f"Tekanan jual agresif terkonfirmasi pada micro-orderflow",
                ],
                metrics={"imbalance_ratio": round(ratio_down, 2)},
            )
        return None


class TickBurstPattern(BasePattern):
    """Pola 14: Tick Burst."""
    def __init__(self):
        super().__init__(
            pattern_id=14,
            name="Tick Burst",
            category="Tick",
            description="Lonjakan frekuensi transaksi tick dalam rentang waktu sub-detik.",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(25)
        if len(ticks) < 18:
            return None
        t_now = ticks[-1]
        t_old = ticks[0]
        dt_ms = max(50, t_now.ts_ms - t_old.ts_ms)
        frequency = (len(ticks) / dt_ms) * 1000.0  # ticks per second

        # Burst threshold: >= 25 ticks/sec with directional displacement
        if frequency >= 25.0:
            price_shift = t_now.mid - t_old.mid
            if price_shift >= 0.30:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    price=t_now.ask,
                    timestamp_ms=t_now.ts_ms,
                    reasons=[
                        f"Ledakan Frekuensi Tick: {frequency:.1f} ticks/detik ({len(ticks)} ticks dalam {dt_ms} ms)",
                        f"Arah pergeseran harga: +{price_shift:.2f} pts ke atas",
                    ],
                    metrics={"freq_tps": round(frequency, 1)},
                )
            elif price_shift <= -0.30:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    price=t_now.bid,
                    timestamp_ms=t_now.ts_ms,
                    reasons=[
                        f"Ledakan Frekuensi Tick: {frequency:.1f} ticks/detik ({len(ticks)} ticks dalam {dt_ms} ms)",
                        f"Arah pergeseran harga: {price_shift:.2f} pts ke bawah",
                    ],
                    metrics={"freq_tps": round(frequency, 1)},
                )
        return None


class TickExhaustionPattern(BasePattern):
    """Pola 15: Tick Exhaustion."""
    def __init__(self):
        super().__init__(
            pattern_id=15,
            name="Tick Exhaustion",
            category="Tick",
            description="Penyerapan likuiditas: frekuensi tick tinggi namun pergerakan harga terhenti.",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(30)
        if len(ticks) < 25:
            return None
        t_now = ticks[-1]
        
        # Analyze first 15 ticks vs last 10 ticks
        first_part = ticks[:15]
        last_part = ticks[15:]
        
        shift_first = first_part[-1].mid - first_part[0].mid
        shift_last = abs(last_part[-1].mid - last_part[0].mid)
        
        # Fast move followed by flat absorption (< 0.10 pts in last 10 ticks)
        if shift_first >= 0.50 and shift_last <= 0.08:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t_now.bid,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Exhaustion Buyer: Rally +{shift_first:.2f} pts macet total di pucuk",
                    f"Pergerakan 10 tick terakhir menyusut ke {shift_last:.2f} pts (Order Absorption)",
                ],
            )
        if shift_first <= -0.50 and shift_last <= 0.08:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t_now.ask,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Exhaustion Seller: Drop {shift_first:.2f} pts macet total di dasar",
                    f"Pergerakan 10 tick terakhir menyusut ke {shift_last:.2f} pts (Order Absorption)",
                ],
            )
        return None


class PriceVelocityPattern(BasePattern):
    """Pola 16: Price Velocity."""
    def __init__(self):
        super().__init__(
            pattern_id=16,
            name="Price Velocity",
            category="Tick",
            description="Kecepatan perpindahan harga per satuan waktu (delta P / delta t).",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(20)
        if len(ticks) < 12:
            return None
        t_now = ticks[-1]
        t_old = ticks[0]
        dt_sec = max(0.1, (t_now.ts_ms - t_old.ts_ms) / 1000.0)
        velocity = (t_now.mid - t_old.mid) / dt_sec  # points per second

        if velocity >= 0.40:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t_now.ask,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Kecepatan Harga Positif Tinggi: +{velocity:.2f} pts/detik",
                    f"Perpindahan {t_now.mid - t_old.mid:.2f} pts dalam {dt_sec:.2f}s",
                ],
                metrics={"velocity": round(velocity, 2)},
            )
        if velocity <= -0.40:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t_now.bid,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Kecepatan Harga Negatif Tinggi: {velocity:.2f} pts/detik",
                    f"Perpindahan {t_now.mid - t_old.mid:.2f} pts dalam {dt_sec:.2f}s",
                ],
                metrics={"velocity": round(velocity, 2)},
            )
        return None


class PriceAccelerationPattern(BasePattern):
    """Pola 17: Price Acceleration."""
    def __init__(self):
        super().__init__(
            pattern_id=17,
            name="Price Acceleration",
            category="Tick",
            description="Percepatan perubahan kecepatan harga (turunan kedua d2P/dt2).",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(24)
        if len(ticks) < 18:
            return None
        t1, t2, t3 = ticks[0], ticks[len(ticks) // 2], ticks[-1]
        dt1 = max(0.1, (t2.ts_ms - t1.ts_ms) / 1000.0)
        dt2 = max(0.1, (t3.ts_ms - t2.ts_ms) / 1000.0)
        
        v1 = (t2.mid - t1.mid) / dt1
        v2 = (t3.mid - t2.mid) / dt2
        accel = (v2 - v1) / dt2

        if accel >= 0.35 and v2 > 0:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t3.ask,
                timestamp_ms=t3.ts_ms,
                reasons=[
                    f"Akselerasi Harga Bullish: +{accel:.2f} pts/s²",
                    f"Velocity melompat dari {v1:.2f} -> {v2:.2f} pts/s",
                ],
                metrics={"accel": round(accel, 2)},
            )
        if accel <= -0.35 and v2 < 0:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t3.bid,
                timestamp_ms=t3.ts_ms,
                reasons=[
                    f"Akselerasi Harga Bearish: {accel:.2f} pts/s²",
                    f"Velocity meluncur turun dari {v1:.2f} -> {v2:.2f} pts/s",
                ],
                metrics={"accel": round(accel, 2)},
            )
        return None


class ConsecutivePriceMovementPattern(BasePattern):
    """Pola 22: Consecutive Price Movement."""
    def __init__(self):
        super().__init__(
            pattern_id=22,
            name="Consecutive Price Movement",
            category="Tick",
            description="Sekuens run length beberapa tick bergerak searah tanpa interupsi.",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(12)
        if len(ticks) < 7:
            return None
        
        # Check consecutive upticks in last 6 ticks
        is_all_up = all(ticks[i].mid > ticks[i - 1].mid for i in range(len(ticks) - 6, len(ticks)))
        is_all_down = all(ticks[i].mid < ticks[i - 1].mid for i in range(len(ticks) - 6, len(ticks)))
        t_now = ticks[-1]

        if is_all_up:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                price=t_now.ask,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    "6 Tick Berturut-turut Naik Murni Tanpa Interupsi",
                    f"Akumulasi dorongan: +{t_now.mid - ticks[-7].mid:.2f} pts",
                ],
            )
        if is_all_down:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                price=t_now.bid,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    "6 Tick Berturut-turut Turun Murni Tanpa Interupsi",
                    f"Akumulasi dorongan: {t_now.mid - ticks[-7].mid:.2f} pts",
                ],
            )
        return None


class AlternatingTickPattern(BasePattern):
    """Pola 23: Alternating Tick Pattern."""
    def __init__(self):
        super().__init__(
            pattern_id=23,
            name="Alternating Tick Pattern",
            category="Tick",
            description="Patahnya osilasi tick bolak-balik (ping-pong) memicu sinyal arah terobosan.",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(10)
        if len(ticks) < 8:
            return None
        
        # Check if first 4-5 ticks were strictly alternating (+, -, +, -)
        diffs = [ticks[i].mid - ticks[i - 1].mid for i in range(1, len(ticks))]
        signs = [1 if d > 0.001 else (-1 if d < -0.001 else 0) for d in diffs]
        
        if len(signs) >= 6:
            # Alternating in earlier ticks:
            was_alternating = (signs[-4] * signs[-5] == -1) and (signs[-5] * signs[-6] == -1)
            # Breakout in last 2 ticks in same direction:
            t_now = ticks[-1]
            if was_alternating and signs[-1] == 1 and signs[-2] == 1:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.BUY,
                    price=t_now.ask,
                    timestamp_ms=t_now.ts_ms,
                    reasons=[
                        "Patahnya Siklus Ping-Pong Tick (Alternating Breakout)",
                        "Dua dorongan Uptick beruntun memecah konsolidasi mikro ke atas",
                    ],
                )
            if was_alternating and signs[-1] == -1 and signs[-2] == -1:
                return EntrySignal(
                    pattern_id=self.pattern_id,
                    family_name=self.name,
                    direction=SignalDirection.SELL,
                    price=t_now.bid,
                    timestamp_ms=t_now.ts_ms,
                    reasons=[
                        "Patahnya Siklus Ping-Pong Tick (Alternating Breakout)",
                        "Dua dorongan Downtick beruntun memecah konsolidasi mikro ke bawah",
                    ],
                )
        return None
