"""Pure Tick Microstructure Entry Patterns (Pola 11-17, 22, 23)."""
from typing import Optional, List
from entrystrategy.engine.base import BasePattern
from entrystrategy.core.models import EntrySignal, SignalDirection, PatternRole, TickData
from entrystrategy.core.buffer import MarketBuffer


class TickMomentumPattern(BasePattern):
    """Pola 11: Tick Momentum.
    Akumulasi perpindahan harga mikro dalam jendela tick singkat.
    """
    def __init__(self):
        super().__init__(
            pattern_id=11,
            name="Tick Momentum",
            category="Tick",
            description="Dorongan kuat harga dari akumulasi pergeseran tick dalam jendela mikro.",
            role=PatternRole.ENTRY,
            phenomenon="Akumulasi perpindahan harga mikro dalam jendela tick singkat",
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

        # Shift threshold: >= 0.50 points within <= 2.5s
        if shift >= 0.50 and dt_sec <= 2.5:
            ref_px = round(t_old.mid, 2)
            trig_px = round(t_now.ask, 2)
            inval_px = round(t_old.mid - 0.20, 2)
            event_id = f"tick_mom_buy_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                    f"Lonjakan Tick Naik: +{shift:.2f} pts dalam {dt_sec:.2f} detik ({len(ticks)} ticks)",
                    f"Harga bergerak dari {ref_px:.2f} -> {round(t_now.mid, 2):.2f}",
                ],
                metrics={"shift": round(shift, 2), "dt_sec": round(dt_sec, 2)},
            )
        if shift <= -0.50 and dt_sec <= 2.5:
            ref_px = round(t_old.mid, 2)
            trig_px = round(t_now.bid, 2)
            inval_px = round(t_old.mid + 0.20, 2)
            event_id = f"tick_mom_sell_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                    f"Lonjakan Tick Turun: {shift:.2f} pts dalam {dt_sec:.2f} detik ({len(ticks)} ticks)",
                    f"Harga jatuh dari {ref_px:.2f} -> {round(t_now.mid, 2):.2f}",
                ],
                metrics={"shift": round(shift, 2), "dt_sec": round(dt_sec, 2)},
            )
        return None


class TickReversalPattern(BasePattern):
    """Pola 12: Tick Reversal.
    Pembalikan arah mikro (V-shape) setelah dorongan tajam.
    """
    def __init__(self):
        super().__init__(
            pattern_id=12,
            name="Tick Reversal",
            category="Tick",
            description="Pembalikan arah tick secara tiba-tiba setelah penurunan atau kenaikan cepat.",
            role=PatternRole.ENTRY,
            phenomenon="Pembalikan arah mikro (V-reversal) setelah dorongan cepat",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(30)
        if len(ticks) < 20:
            return None
        mid_idx = len(ticks) // 2
        t_first = ticks[0]
        t_mid = ticks[mid_idx]
        t_now = ticks[-1]

        leg1 = t_mid.mid - t_first.mid
        leg2 = t_now.mid - t_mid.mid

        # Sharp down leg followed by sharp up reversal
        if leg1 <= -0.40 and leg2 >= 0.35:
            ref_px = round(t_mid.mid, 2)
            trig_px = round(t_now.ask, 2)
            inval_px = round(t_mid.mid - 0.20, 2)
            event_id = f"tick_rev_buy_{t_mid.ts_ms}_{t_now.ts_ms}"
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
                    "Pembalikan Tick Cepat (V-Shape Tick Reversal)",
                    f"Drop awal: {leg1:.2f} pts disusul Rebound instan: +{leg2:.2f} pts",
                ],
                metrics={"leg1": round(leg1, 2), "leg2": round(leg2, 2)},
            )
        # Sharp up leg followed by sharp down reversal
        if leg1 >= 0.40 and leg2 <= -0.35:
            ref_px = round(t_mid.mid, 2)
            trig_px = round(t_now.bid, 2)
            inval_px = round(t_mid.mid + 0.20, 2)
            event_id = f"tick_rev_sell_{t_mid.ts_ms}_{t_now.ts_ms}"
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
                    "Pembalikan Tick Cepat (Inverted V-Shape Tick Reversal)",
                    f"Rally awal: +{leg1:.2f} pts disusul Drop instan: {leg2:.2f} pts",
                ],
                metrics={"leg1": round(leg1, 2), "leg2": round(leg2, 2)},
            )
        return None


class TickImbalancePattern(BasePattern):
    """Pola 13: Tick Imbalance (Quote Direction Dominance).
    Dominasi arah perubahan quote tick (uptick/downtick) dalam sampel tick mikro.
    Catatan: Mengukur dominasi pergeseran harga kuotasi, bukan data agresor transaksi orderflow.
    """
    def __init__(self):
        super().__init__(
            pattern_id=13,
            name="Tick Imbalance",
            category="Tick",
            description="Dominasi arah perubahan quote (uptick/downtick > 75%) dalam sampel 20 tick.",
            role=PatternRole.CONFIRMATION,
            phenomenon="Dominasi arah perubahan quote tick mikro",
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
        ratio_down = downticks / total_active
        t_now = ticks[-1]
        t_start = ticks[0]

        if ratio_up >= 0.75:
            ref_px = round(t_start.mid, 2)
            trig_px = round(t_now.ask, 2)
            inval_px = round(min(t.mid for t in ticks), 2)
            event_id = f"tick_imb_buy_{t_now.ts_ms}_{upticks}_{downticks}"
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
                    f"Dominasi Perubahan Quote Uptick: {ratio_up * 100:.1f}% ({upticks} naik vs {downticks} turun)",
                    "Pergeseran kuotasi harga didominasi arah kenaikan",
                ],
                metrics={"imbalance_ratio": round(ratio_up, 2)},
            )
        if ratio_down >= 0.75:
            ref_px = round(t_start.mid, 2)
            trig_px = round(t_now.bid, 2)
            inval_px = round(max(t.mid for t in ticks), 2)
            event_id = f"tick_imb_sell_{t_now.ts_ms}_{upticks}_{downticks}"
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
                    f"Dominasi Perubahan Quote Downtick: {ratio_down * 100:.1f}% ({downticks} turun vs {upticks} naik)",
                    "Pergeseran kuotasi harga didominasi arah penurunan",
                ],
                metrics={"imbalance_ratio": round(ratio_down, 2)},
            )
        return None


class TickBurstPattern(BasePattern):
    """Pola 14: Tick Burst.
    Lonjakan frekuensi transaksi tick bersamaan dengan perpindahan harga searah.
    """
    def __init__(self):
        super().__init__(
            pattern_id=14,
            name="Tick Burst",
            category="Tick",
            description="Lonjakan frekuensi transaksi tick dalam rentang waktu sub-detik dengan arah pergeseran jelas.",
            role=PatternRole.ENTRY,
            phenomenon="Lonjakan frekuensi kedatangan tick bersamaan perpindahan harga searah",
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

        # Burst threshold: >= 20 ticks/sec with directional displacement >= 0.30
        if frequency >= 20.0:
            price_shift = t_now.mid - t_old.mid
            if price_shift >= 0.30:
                ref_px = round(t_old.mid, 2)
                trig_px = round(t_now.ask, 2)
                inval_px = round(t_old.mid, 2)
                event_id = f"tick_burst_buy_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                        f"Ledakan Frekuensi Tick: {frequency:.1f} ticks/detik ({len(ticks)} ticks dalam {dt_ms} ms)",
                        f"Arah pergeseran harga: +{price_shift:.2f} pts ke atas",
                    ],
                    metrics={"freq_tps": round(frequency, 1), "price_shift": round(price_shift, 2)},
                )
            elif price_shift <= -0.30:
                ref_px = round(t_old.mid, 2)
                trig_px = round(t_now.bid, 2)
                inval_px = round(t_old.mid, 2)
                event_id = f"tick_burst_sell_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                        f"Ledakan Frekuensi Tick: {frequency:.1f} ticks/detik ({len(ticks)} ticks dalam {dt_ms} ms)",
                        f"Arah pergeseran harga: {price_shift:.2f} pts ke bawah",
                    ],
                    metrics={"freq_tps": round(frequency, 1), "price_shift": round(price_shift, 2)},
                )
        return None


class TickExhaustionPattern(BasePattern):
    """Pola 15: Tick Exhaustion.
    Mengukur lonjakan frekuensi tick namun harga terhenti (stalling / delta P menyusut),
    diikuti oleh tick pembalikan mikro.
    """
    def __init__(self):
        super().__init__(
            pattern_id=15,
            name="Tick Exhaustion",
            category="Tick",
            description="Perhentian pergeseran harga pada frekuensi tick tinggi setelah impuls kuat, disusul tick pembalikan.",
            role=PatternRole.SETUP_TRIGGER,
            phenomenon="Pemberhentian perpindahan harga pada frekuensi tick tinggi disusul reaksi awal pembalikan",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(30)
        if len(ticks) < 25:
            return None
        t_now = ticks[-1]
        t_prev = ticks[-2]
        
        # Analyze first part (impulse) vs last part (stall/absorption)
        first_part = ticks[:15]
        last_part = ticks[15:]
        
        shift_first = first_part[-1].mid - first_part[0].mid
        shift_last = abs(last_part[-1].mid - last_part[0].mid)
        
        # Frequency of stall phase: ticks per sec
        dt_stall_ms = max(50, last_part[-1].ts_ms - last_part[0].ts_ms)
        freq_stall = (len(last_part) / dt_stall_ms) * 1000.0

        # Fast move up followed by tight stall and tick turning down
        if shift_first >= 0.40 and shift_last <= 0.08 and freq_stall >= 5.0 and t_now.mid < t_prev.mid:
            extreme_p = round(max(t.mid for t in ticks), 2)
            trig_px = round(t_now.bid, 2)
            inval_px = round(extreme_p + 0.15, 2)
            event_id = f"tick_exh_sell_{t_now.ts_ms}_{round(t_now.mid, 2)}"
            if self._is_event_deduplicated(event_id):
                return None
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                reference_price=extreme_p,
                trigger_price=trig_px,
                invalidation_price=inval_px,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=event_id,
                price=trig_px,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Exhaustion Buyer: Dorongan naik +{shift_first:.2f} pts terhenti di {extreme_p:.2f}",
                    f"Aktivitas {freq_stall:.1f} tick/detik namun pergerakan hanya {shift_last:.2f} pts, disusul tick reversal",
                ],
                metrics={"shift_impulse": round(shift_first, 2), "shift_stall": round(shift_last, 2), "freq_stall": round(freq_stall, 1)},
            )

        # Fast move down followed by tight stall and tick turning up
        if shift_first <= -0.40 and shift_last <= 0.08 and freq_stall >= 5.0 and t_now.mid > t_prev.mid:
            extreme_p = round(min(t.mid for t in ticks), 2)
            trig_px = round(t_now.ask, 2)
            inval_px = round(extreme_p - 0.15, 2)
            event_id = f"tick_exh_buy_{t_now.ts_ms}_{round(t_now.mid, 2)}"
            if self._is_event_deduplicated(event_id):
                return None
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                reference_price=extreme_p,
                trigger_price=trig_px,
                invalidation_price=inval_px,
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=event_id,
                price=trig_px,
                timestamp_ms=t_now.ts_ms,
                reasons=[
                    f"Exhaustion Seller: Dorongan turun {shift_first:.2f} pts terhenti di {extreme_p:.2f}",
                    f"Aktivitas {freq_stall:.1f} tick/detik namun pergerakan hanya {shift_last:.2f} pts, disusul tick reversal",
                ],
                metrics={"shift_impulse": round(shift_first, 2), "shift_stall": round(shift_last, 2), "freq_stall": round(freq_stall, 1)},
            )
        return None


class PriceVelocityPattern(BasePattern):
    """Pola 16: Price Velocity.
    Kecepatan perpindahan harga per satuan waktu (delta P / delta t).
    """
    def __init__(self):
        super().__init__(
            pattern_id=16,
            name="Price Velocity",
            category="Tick",
            description="Kecepatan perpindahan harga per satuan waktu (delta P / delta t).",
            role=PatternRole.ENTRY,
            phenomenon="Kecepatan perpindahan harga mikro per satuan waktu",
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
            ref_px = round(t_old.mid, 2)
            trig_px = round(t_now.ask, 2)
            inval_px = round(t_old.mid - 0.20, 2)
            event_id = f"price_vel_buy_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                    f"Kecepatan Harga Positif Tinggi: +{velocity:.2f} pts/detik",
                    f"Perpindahan {t_now.mid - t_old.mid:.2f} pts dalam {dt_sec:.2f}s",
                ],
                metrics={"velocity": round(velocity, 2)},
            )
        if velocity <= -0.40:
            ref_px = round(t_old.mid, 2)
            trig_px = round(t_now.bid, 2)
            inval_px = round(t_old.mid + 0.20, 2)
            event_id = f"price_vel_sell_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                    f"Kecepatan Harga Negatif Tinggi: {velocity:.2f} pts/detik",
                    f"Perpindahan {t_now.mid - t_old.mid:.2f} pts dalam {dt_sec:.2f}s",
                ],
                metrics={"velocity": round(velocity, 2)},
            )
        return None


class PriceAccelerationPattern(BasePattern):
    """Pola 17: Price Acceleration.
    Percepatan perubahan kecepatan harga (turunan kedua d2P/dt2).
    """
    def __init__(self):
        super().__init__(
            pattern_id=17,
            name="Price Acceleration",
            category="Tick",
            description="Percepatan perubahan kecepatan harga mikro (turunan kedua d2P/dt2).",
            role=PatternRole.ENTRY,
            phenomenon="Percepatan laju kecepatan perpindahan harga (d2P/dt2)",
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
            ref_px = round(t2.mid, 2)
            trig_px = round(t3.ask, 2)
            inval_px = round(t1.mid, 2)
            event_id = f"price_acc_buy_{t3.ts_ms}_{round(t3.mid, 2)}"
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
                timestamp_ms=t3.ts_ms,
                reasons=[
                    f"Akselerasi Harga Bullish: +{accel:.2f} pts/s²",
                    f"Velocity melompat dari {v1:.2f} -> {v2:.2f} pts/s",
                ],
                metrics={"accel": round(accel, 2), "v1": round(v1, 2), "v2": round(v2, 2)},
            )
        if accel <= -0.35 and v2 < 0:
            ref_px = round(t2.mid, 2)
            trig_px = round(t3.bid, 2)
            inval_px = round(t1.mid, 2)
            event_id = f"price_acc_sell_{t3.ts_ms}_{round(t3.mid, 2)}"
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
                timestamp_ms=t3.ts_ms,
                reasons=[
                    f"Akselerasi Harga Bearish: {accel:.2f} pts/s²",
                    f"Velocity meluncur turun dari {v1:.2f} -> {v2:.2f} pts/s",
                ],
                metrics={"accel": round(accel, 2), "v1": round(v1, 2), "v2": round(v2, 2)},
            )
        return None


class ConsecutivePriceMovementPattern(BasePattern):
    """Pola 22: Consecutive Price Movement.
    Sekuens run length beberapa tick bergerak searah tanpa interupsi.
    """
    def __init__(self):
        super().__init__(
            pattern_id=22,
            name="Consecutive Price Movement",
            category="Tick",
            description="Sekuens run length 6 tick bergerak searah tanpa interupsi.",
            role=PatternRole.ENTRY,
            phenomenon="Rangkaian sekuens pergerakan tick searah tanpa interupsi",
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
        t_base = ticks[-7]

        if is_all_up:
            ref_px = round(t_base.mid, 2)
            trig_px = round(t_now.ask, 2)
            inval_px = ref_px
            event_id = f"consec_tick_buy_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                    "6 Tick Berturut-turut Naik Murni Tanpa Interupsi",
                    f"Akumulasi dorongan: +{t_now.mid - t_base.mid:.2f} pts dari {ref_px:.2f}",
                ],
                metrics={"streak": 6, "gain": round(t_now.mid - t_base.mid, 2)},
            )
        if is_all_down:
            ref_px = round(t_base.mid, 2)
            trig_px = round(t_now.bid, 2)
            inval_px = ref_px
            event_id = f"consec_tick_sell_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                    "6 Tick Berturut-turut Turun Murni Tanpa Interupsi",
                    f"Akumulasi dorongan: {t_now.mid - t_base.mid:.2f} pts dari {ref_px:.2f}",
                ],
                metrics={"streak": 6, "gain": round(t_now.mid - t_base.mid, 2)},
            )
        return None


class AlternatingTickPattern(BasePattern):
    """Pola 23: Alternating Tick Pattern.
    Patahnya osilasi bolak-balik (ping-pong mikro) oleh terobosan searah 2 tick berturut-turut.
    """
    def __init__(self):
        super().__init__(
            pattern_id=23,
            name="Alternating Tick Pattern",
            category="Tick",
            description="Patahnya osilasi tick bolak-balik (ping-pong) memicu sinyal arah terobosan.",
            role=PatternRole.SETUP_TRIGGER,
            phenomenon="Patahnya osilasi bolak-balik mikro oleh terobosan searah",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(12)
        if len(ticks) < 8:
            return None
        
        diffs = [ticks[i].mid - ticks[i - 1].mid for i in range(1, len(ticks))]
        signs = [1 if d > 0.001 else (-1 if d < -0.001 else 0) for d in diffs]
        
        if len(signs) >= 6:
            # Alternating in earlier 3 transitions: e.g. signs[-3] != signs[-4] and signs[-4] != signs[-5]
            was_alternating = (signs[-3] * signs[-4] == -1) and (signs[-4] * signs[-5] == -1)
            
            # Historical alternating band from ticks[:-2]
            alt_ticks = ticks[:-2]
            high_alt = max(t.mid for t in alt_ticks)
            low_alt = min(t.mid for t in alt_ticks)
            span_alt = high_alt - low_alt
            
            t_now = ticks[-1]
            
            # Tight ping-pong band (<= 0.25 pts) followed by 2 consecutive breakout ticks
            if was_alternating and span_alt <= 0.25:
                if signs[-1] == 1 and signs[-2] == 1 and t_now.mid > high_alt:
                    ref_px = round(high_alt, 2)
                    trig_px = round(t_now.ask, 2)
                    inval_px = round(low_alt, 2)
                    event_id = f"alt_tick_buy_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                            f"Patahnya Siklus Ping-Pong Tick (Band: {span_alt:.2f} pts)",
                            f"Dua uptick beruntun menembus batas atas ping-pong ({ref_px:.2f}) ke {round(t_now.mid, 2):.2f}",
                        ],
                        metrics={"span_alt": round(span_alt, 2), "breakout_level": ref_px},
                    )
                if signs[-1] == -1 and signs[-2] == -1 and t_now.mid < low_alt:
                    ref_px = round(low_alt, 2)
                    trig_px = round(t_now.bid, 2)
                    inval_px = round(high_alt, 2)
                    event_id = f"alt_tick_sell_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                            f"Patahnya Siklus Ping-Pong Tick (Band: {span_alt:.2f} pts)",
                            f"Dua downtick beruntun menembus batas bawah ping-pong ({ref_px:.2f}) ke {round(t_now.mid, 2):.2f}",
                        ],
                        metrics={"span_alt": round(span_alt, 2), "breakout_level": ref_px},
                    )
        return None
