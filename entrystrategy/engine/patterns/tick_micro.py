"""Microstructure & M5 Candle Strategy Patterns (Pola 11-17, 22, 23).
Supports both direct M5 candle evaluation from MT5 and legacy tick streams.
"""
from typing import Optional, List
from entrystrategy.engine.base import BasePattern
from entrystrategy.core.models import EntrySignal, SignalDirection, PatternRole, TickData
from entrystrategy.core.buffer import MarketBuffer


class TickMomentumPattern(BasePattern):
    """Pola 11: Momentum / Price Shift Pattern.
    Akumulasi perpindahan harga mikro / momentum bar M5 kuat.
    """
    def __init__(self):
        super().__init__(
            pattern_id=11,
            name="Momentum Displacement",
            category="Candle",
            description="Dorongan kuat harga dari akumulasi pergeseran harga M5 atau jendela mikro.",
            role=PatternRole.ENTRY,
            phenomenon="Akumulasi perpindahan harga terarah melampaui rentang rata-rata",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(25)
        if len(ticks) >= 15:
            t_now = ticks[-1]
            t_old = ticks[0]
            shift = t_now.mid - t_old.mid
            dt_sec = max(0.1, (t_now.ts_ms - t_old.ts_ms) / 1000.0)

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

        # M5 Candle-based evaluation (Primary MT5 mode)
        candles = buffer.get_recent_candles(3)
        if len(candles) >= 2:
            c0, c1 = candles[0], candles[1]
            shift = c0.close - c1.open
            if shift >= 1.0 and c0.is_bullish:
                ref_px = round(c1.open, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(min(c0.low, c1.low), 2)
                event_id = f"m5_mom_buy_{int(c0.timestamp.timestamp())}_{trig_px}"
                if not self._is_event_deduplicated(event_id):
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
                        timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                        reasons=[
                            f"Momentum Candle M5 Bullish: Perpindahan +{shift:.2f} pts melampaui bar sebelumnya",
                            f"Harga bergerak kuat dari {ref_px:.2f} -> {trig_px:.2f}",
                        ],
                        metrics={"shift": round(shift, 2)},
                    )
            if shift <= -1.0 and c0.is_bearish:
                ref_px = round(c1.open, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(max(c0.high, c1.high), 2)
                event_id = f"m5_mom_sell_{int(c0.timestamp.timestamp())}_{trig_px}"
                if not self._is_event_deduplicated(event_id):
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
                        timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                        reasons=[
                            f"Momentum Candle M5 Bearish: Perpindahan {shift:.2f} pts melampaui bar sebelumnya",
                            f"Harga jatuh kuat dari {ref_px:.2f} -> {trig_px:.2f}",
                        ],
                        metrics={"shift": round(shift, 2)},
                    )
        return None


class TickReversalPattern(BasePattern):
    """Pola 12: Reversal Pattern.
    Pembalikan arah cepat (V-shape) setelah dorongan tajam.
    """
    def __init__(self):
        super().__init__(
            pattern_id=12,
            name="V-Reversal Flow",
            category="Candle",
            description="Pembalikan arah secara tiba-tiba setelah penurunan atau kenaikan tajam.",
            role=PatternRole.ENTRY,
            phenomenon="Pembalikan arah tajam (V-reversal) setelah dorongan impuls",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(30)
        if len(ticks) >= 20:
            mid_idx = len(ticks) // 2
            t_first = ticks[0]
            t_mid = ticks[mid_idx]
            t_now = ticks[-1]

            leg1 = t_mid.mid - t_first.mid
            leg2 = t_now.mid - t_mid.mid

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
                        "Pembalikan Cepat (V-Shape Reversal)",
                        f"Drop awal: {leg1:.2f} pts disusul Rebound instan: +{leg2:.2f} pts",
                    ],
                    metrics={"leg1": round(leg1, 2), "leg2": round(leg2, 2)},
                )
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
                        "Pembalikan Cepat (Inverted V-Shape Reversal)",
                        f"Rally awal: +{leg1:.2f} pts disusul Drop instan: {leg2:.2f} pts",
                    ],
                    metrics={"leg1": round(leg1, 2), "leg2": round(leg2, 2)},
                )

        # M5 Candle-based evaluation
        candles = buffer.get_recent_candles(3)
        if len(candles) >= 2:
            c0, c1 = candles[0], candles[1]
            if c1.is_bearish and c0.is_bullish and c1.body >= 0.80 and c0.close >= (c1.open - 0.25 * c1.body):
                ref_px = round(c1.low, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(min(c0.low, c1.low) - 0.15, 2)
                event_id = f"m5_rev_buy_{int(c0.timestamp.timestamp())}_{trig_px}"
                if not self._is_event_deduplicated(event_id):
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
                        timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                        reasons=[
                            f"V-Reversal M5: Bar penurunan {c1.body:.2f} pts langsung dibalas pantulan bar naik {c0.body:.2f} pts",
                            f"Penutupan {trig_px:.2f} merebut kembali mayoritas range drop",
                        ],
                    )
            if c1.is_bullish and c0.is_bearish and c1.body >= 0.80 and c0.close <= (c1.open + 0.25 * c1.body):
                ref_px = round(c1.high, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(max(c0.high, c1.high) + 0.15, 2)
                event_id = f"m5_rev_sell_{int(c0.timestamp.timestamp())}_{trig_px}"
                if not self._is_event_deduplicated(event_id):
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
                        timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                        reasons=[
                            f"Inverted V-Reversal M5: Bar reli {c1.body:.2f} pts langsung dibalas penurunan tajam {c0.body:.2f} pts",
                            f"Penutupan {trig_px:.2f} merebut kembali mayoritas range rally",
                        ],
                    )
        return None


class TickImbalancePattern(BasePattern):
    """Pola 13: Volume & Quote Imbalance.
    Dominasi arah transaksi / pergerakan kuotasi harga.
    """
    def __init__(self):
        super().__init__(
            pattern_id=13,
            name="Volume Imbalance",
            category="Candle",
            description="Dominasi volume buyer vs seller (> 70%) dalam rangkaian candle M5.",
            role=PatternRole.CONFIRMATION,
            phenomenon="Dominasi arah volume transaksi / kuotasi harga",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(21)
        if len(ticks) >= 20:
            upticks = sum(1 for i in range(1, len(ticks)) if ticks[i].mid - ticks[i - 1].mid > 0.001)
            downticks = sum(1 for i in range(1, len(ticks)) if ticks[i].mid - ticks[i - 1].mid < -0.001)
            total_active = upticks + downticks
            if total_active >= 12:
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

        # M5 Candle-based evaluation
        candles = buffer.get_recent_candles(4)
        if len(candles) >= 3:
            c_sample = candles[:3]
            v_bull = sum((c.tick_volume or 1.0) for c in c_sample if c.is_bullish)
            v_bear = sum((c.tick_volume or 1.0) for c in c_sample if c.is_bearish)
            v_tot = v_bull + v_bear
            c0 = c_sample[0]
            if v_tot > 0:
                if (v_bull / v_tot) >= 0.70 and c0.is_bullish:
                    ref_px = round(min(c.low for c in c_sample), 2)
                    trig_px = round(c0.close, 2)
                    event_id = f"m5_imb_buy_{int(c0.timestamp.timestamp())}"
                    if not self._is_event_deduplicated(event_id):
                        return EntrySignal(
                            pattern_id=self.pattern_id,
                            family_name=self.name,
                            direction=SignalDirection.BUY,
                            reference_price=ref_px,
                            trigger_price=trig_px,
                            invalidation_price=ref_px,
                            pattern_role=self.role,
                            phenomenon=self.phenomenon,
                            event_id=event_id,
                            price=trig_px,
                            timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                            reasons=[
                                f"Dominasi Volume Bullish M5: {v_bull / v_tot * 100:.1f}% dalam 3 bar M5 terakhir",
                                "Volume transaksi didominasi oleh pergerakan kenaikan",
                            ],
                        )
                elif (v_bear / v_tot) >= 0.70 and c0.is_bearish:
                    ref_px = round(max(c.high for c in c_sample), 2)
                    trig_px = round(c0.close, 2)
                    event_id = f"m5_imb_sell_{int(c0.timestamp.timestamp())}"
                    if not self._is_event_deduplicated(event_id):
                        return EntrySignal(
                            pattern_id=self.pattern_id,
                            family_name=self.name,
                            direction=SignalDirection.SELL,
                            reference_price=ref_px,
                            trigger_price=trig_px,
                            invalidation_price=ref_px,
                            pattern_role=self.role,
                            phenomenon=self.phenomenon,
                            event_id=event_id,
                            price=trig_px,
                            timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                            reasons=[
                                f"Dominasi Volume Bearish M5: {v_bear / v_tot * 100:.1f}% dalam 3 bar M5 terakhir",
                                "Volume transaksi didominasi oleh pergerakan penurunan",
                            ],
                        )
        return None


class TickBurstPattern(BasePattern):
    """Pola 14: Volume Burst Pattern.
    Lonjakan frekuensi transaksi / volume candle M5 bersamaan pergerakan arah jelas.
    """
    def __init__(self):
        super().__init__(
            pattern_id=14,
            name="Volume Burst",
            category="Candle",
            description="Lonjakan volume candle M5 abnormal (> 1.7x rata-rata) dengan dorongan body searah.",
            role=PatternRole.ENTRY,
            phenomenon="Ledakan volume transaksi bersamaan perpindahan harga searah",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(25)
        if len(ticks) >= 18:
            t_now = ticks[-1]
            t_old = ticks[0]
            dt_ms = max(50, t_now.ts_ms - t_old.ts_ms)
            frequency = (len(ticks) / dt_ms) * 1000.0

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

        # M5 Candle-based evaluation
        candles = buffer.get_recent_candles(6)
        if len(candles) >= 5:
            c0 = candles[0]
            prior = candles[1:5]
            avg_v = sum((c.tick_volume or 1.0) for c in prior) / len(prior)
            if avg_v > 0 and (c0.tick_volume or 1.0) >= 1.7 * avg_v and c0.body >= 0.50:
                if c0.is_bullish:
                    event_id = f"m5_vburst_buy_{int(c0.timestamp.timestamp())}"
                    if not self._is_event_deduplicated(event_id):
                        return EntrySignal(
                            pattern_id=self.pattern_id,
                            family_name=self.name,
                            direction=SignalDirection.BUY,
                            reference_price=round(c0.open, 2),
                            trigger_price=round(c0.close, 2),
                            invalidation_price=round(c0.low, 2),
                            pattern_role=self.role,
                            phenomenon=self.phenomenon,
                            event_id=event_id,
                            price=round(c0.close, 2),
                            timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                            reasons=[
                                f"Ledakan Volume M5: {c0.tick_volume:.0f} vs rata-rata {avg_v:.0f} (Ratio {c0.tick_volume/avg_v:.1f}x)",
                                f"Bar ekspansi bullish dengan penutupan kuat di {c0.close:.2f}",
                            ],
                        )
                elif c0.is_bearish:
                    event_id = f"m5_vburst_sell_{int(c0.timestamp.timestamp())}"
                    if not self._is_event_deduplicated(event_id):
                        return EntrySignal(
                            pattern_id=self.pattern_id,
                            family_name=self.name,
                            direction=SignalDirection.SELL,
                            reference_price=round(c0.open, 2),
                            trigger_price=round(c0.close, 2),
                            invalidation_price=round(c0.high, 2),
                            pattern_role=self.role,
                            phenomenon=self.phenomenon,
                            event_id=event_id,
                            price=round(c0.close, 2),
                            timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                            reasons=[
                                f"Ledakan Volume M5: {c0.tick_volume:.0f} vs rata-rata {avg_v:.0f} (Ratio {c0.tick_volume/avg_v:.1f}x)",
                                f"Bar ekspansi bearish dengan penutupan lemah di {c0.close:.2f}",
                            ],
                        )
        return None


class TickExhaustionPattern(BasePattern):
    """Pola 15: Volume Exhaustion.
    Perhentian pergeseran harga pada volume tinggi setelah impuls, disusul tanda pembalikan.
    """
    def __init__(self):
        super().__init__(
            pattern_id=15,
            name="Volume Exhaustion",
            category="Candle",
            description="Perhentian pergeseran harga pada volume tinggi setelah impuls kuat, mengindikasikan absorption.",
            role=PatternRole.SETUP_TRIGGER,
            phenomenon="Pemberhentian perpindahan harga pada volume tinggi disusul reaksi awal pembalikan",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(30)
        if len(ticks) >= 25:
            t_now = ticks[-1]
            t_prev = ticks[-2]
            first_part = ticks[:15]
            last_part = ticks[15:]
            shift_first = first_part[-1].mid - first_part[0].mid
            shift_last = abs(last_part[-1].mid - last_part[0].mid)
            dt_stall_ms = max(50, last_part[-1].ts_ms - last_part[0].ts_ms)
            freq_stall = (len(last_part) / dt_stall_ms) * 1000.0

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

        # M5 Candle-based evaluation
        candles = buffer.get_recent_candles(5)
        if len(candles) >= 3:
            c0, c1 = candles[0], candles[1]
            prior = candles[1:4]
            avg_v = sum((c.tick_volume or 1.0) for c in prior) / len(prior)
            if (c0.tick_volume or 1.0) >= 1.4 * avg_v:
                if c1.is_bullish and (c0.upper_wick >= 0.45 * c0.range or c0.body <= 0.35 * c0.range):
                    event_id = f"m5_exh_sell_{int(c0.timestamp.timestamp())}"
                    if not self._is_event_deduplicated(event_id):
                        return EntrySignal(
                            pattern_id=self.pattern_id,
                            family_name=self.name,
                            direction=SignalDirection.SELL,
                            reference_price=round(c0.high, 2),
                            trigger_price=round(c0.close, 2),
                            invalidation_price=round(c0.high + 0.15, 2),
                            pattern_role=self.role,
                            phenomenon=self.phenomenon,
                            event_id=event_id,
                            price=round(c0.close, 2),
                            timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                            reasons=[
                                f"Volume Exhaustion M5 (Puncak): Volume tinggi ({c0.tick_volume:.0f}) namun pergerakan tertahan",
                                f"Penolakan atas atau body menyusut di puncak {c0.high:.2f}",
                            ],
                        )
                if c1.is_bearish and (c0.lower_wick >= 0.45 * c0.range or c0.body <= 0.35 * c0.range):
                    event_id = f"m5_exh_buy_{int(c0.timestamp.timestamp())}"
                    if not self._is_event_deduplicated(event_id):
                        return EntrySignal(
                            pattern_id=self.pattern_id,
                            family_name=self.name,
                            direction=SignalDirection.BUY,
                            reference_price=round(c0.low, 2),
                            trigger_price=round(c0.close, 2),
                            invalidation_price=round(c0.low - 0.15, 2),
                            pattern_role=self.role,
                            phenomenon=self.phenomenon,
                            event_id=event_id,
                            price=round(c0.close, 2),
                            timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                            reasons=[
                                f"Volume Exhaustion M5 (Dasar): Volume tinggi ({c0.tick_volume:.0f}) namun pergerakan tertahan",
                                f"Penolakan bawah atau body menyusut di dasar {c0.low:.2f}",
                            ],
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
            category="Candle",
            description="Kecepatan perpindahan harga per satuan bar M5 (delta P / delta t).",
            role=PatternRole.ENTRY,
            phenomenon="Kecepatan perpindahan harga ekspansif per satuan waktu",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(20)
        if len(ticks) >= 12:
            t_now = ticks[-1]
            t_old = ticks[0]
            dt_sec = max(0.1, (t_now.ts_ms - t_old.ts_ms) / 1000.0)
            velocity = (t_now.mid - t_old.mid) / dt_sec

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

        # M5 Candle-based evaluation
        candles = buffer.get_recent_candles(5)
        if len(candles) >= 4:
            c0 = candles[0]
            prior = candles[1:4]
            avg_r = sum(c.range for c in prior) / len(prior)
            if avg_r > 0 and c0.range >= 1.8 * avg_r and c0.body >= 0.60 * c0.range:
                if c0.is_bullish:
                    event_id = f"m5_vel_buy_{int(c0.timestamp.timestamp())}"
                    if not self._is_event_deduplicated(event_id):
                        return EntrySignal(
                            pattern_id=self.pattern_id,
                            family_name=self.name,
                            direction=SignalDirection.BUY,
                            reference_price=round(c0.open, 2),
                            trigger_price=round(c0.close, 2),
                            invalidation_price=round(c0.low, 2),
                            pattern_role=self.role,
                            phenomenon=self.phenomenon,
                            event_id=event_id,
                            price=round(c0.close, 2),
                            timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                            reasons=[
                                f"Kecepatan Ekspansi M5 Tinggi: Range {c0.range:.2f} pts (> 1.8x rata-rata {avg_r:.2f} pts)",
                                f"Dominasi body bullish {c0.body:.2f} pts",
                            ],
                        )
                elif c0.is_bearish:
                    event_id = f"m5_vel_sell_{int(c0.timestamp.timestamp())}"
                    if not self._is_event_deduplicated(event_id):
                        return EntrySignal(
                            pattern_id=self.pattern_id,
                            family_name=self.name,
                            direction=SignalDirection.SELL,
                            reference_price=round(c0.open, 2),
                            trigger_price=round(c0.close, 2),
                            invalidation_price=round(c0.high, 2),
                            pattern_role=self.role,
                            phenomenon=self.phenomenon,
                            event_id=event_id,
                            price=round(c0.close, 2),
                            timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                            reasons=[
                                f"Kecepatan Ekspansi M5 Tinggi: Range {c0.range:.2f} pts (> 1.8x rata-rata {avg_r:.2f} pts)",
                                f"Dominasi body bearish {c0.body:.2f} pts",
                            ],
                        )
        return None


class PriceAccelerationPattern(BasePattern):
    """Pola 17: Price Acceleration.
    Percepatan perubahan kecepatan harga (turunan kedua d2P/dt2) atau akselerasi body M5.
    """
    def __init__(self):
        super().__init__(
            pattern_id=17,
            name="Price Acceleration",
            category="Candle",
            description="Percepatan perubahan kecepatan pergerakan harga atau ekspansi bar bertingkat.",
            role=PatternRole.ENTRY,
            phenomenon="Percepatan laju kecepatan perpindahan harga (d2P/dt2)",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(24)
        if len(ticks) >= 18:
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

        # M5 Candle-based evaluation
        candles = buffer.get_recent_candles(4)
        if len(candles) >= 3:
            c0, c1 = candles[0], candles[1]
            if c0.is_bullish and c1.is_bullish and c0.body > 1.25 * c1.body and c1.body >= 0.30:
                event_id = f"m5_acc_buy_{int(c0.timestamp.timestamp())}"
                if not self._is_event_deduplicated(event_id):
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.BUY,
                        reference_price=round(c1.open, 2),
                        trigger_price=round(c0.close, 2),
                        invalidation_price=round(c1.low, 2),
                        pattern_role=self.role,
                        phenomenon=self.phenomenon,
                        event_id=event_id,
                        price=round(c0.close, 2),
                        timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                        reasons=[
                            f"Akselerasi M5 Bullish: Body bar membesar progresif ({c1.body:.2f} -> {c0.body:.2f} pts)",
                            "Laju kenaikan harga semakin kencang",
                        ],
                    )
            elif c0.is_bearish and c1.is_bearish and c0.body > 1.25 * c1.body and c1.body >= 0.30:
                event_id = f"m5_acc_sell_{int(c0.timestamp.timestamp())}"
                if not self._is_event_deduplicated(event_id):
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.SELL,
                        reference_price=round(c1.open, 2),
                        trigger_price=round(c0.close, 2),
                        invalidation_price=round(c1.high, 2),
                        pattern_role=self.role,
                        phenomenon=self.phenomenon,
                        event_id=event_id,
                        price=round(c0.close, 2),
                        timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                        reasons=[
                            f"Akselerasi M5 Bearish: Body bar membesar progresif ({c1.body:.2f} -> {c0.body:.2f} pts)",
                            "Laju penurunan harga semakin kencang",
                        ],
                    )
        return None


class ConsecutivePriceMovementPattern(BasePattern):
    """Pola 22: Consecutive Price Movement.
    Sekuens pergerakan searah berturut-turut tanpa interupsi.
    """
    def __init__(self):
        super().__init__(
            pattern_id=22,
            name="Consecutive Movement",
            category="Candle",
            description="Sekuens run length pergerakan searah berturut-turut pada bar M5.",
            role=PatternRole.ENTRY,
            phenomenon="Rangkaian sekuens pergerakan harga searah tanpa interupsi",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(12)
        if len(ticks) >= 7:
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

        # M5 Candle-based evaluation
        candles = buffer.get_recent_candles(4)
        if len(candles) >= 3:
            c0, c1, c2 = candles[0], candles[1], candles[2]
            if all(c.is_bullish for c in (c0, c1, c2)) and c0.close > c1.close > c2.close and c0.high > c1.high > c2.high:
                event_id = f"m5_consec_buy_{int(c0.timestamp.timestamp())}"
                if not self._is_event_deduplicated(event_id):
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.BUY,
                        reference_price=round(c2.open, 2),
                        trigger_price=round(c0.close, 2),
                        invalidation_price=round(c2.low, 2),
                        pattern_role=self.role,
                        phenomenon=self.phenomenon,
                        event_id=event_id,
                        price=round(c0.close, 2),
                        timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                        reasons=[
                            "3 Candle M5 Berturut-turut Bullish dengan Higher Highs & Closes",
                            f"Pergerakan konsisten naik dari {c2.open:.2f} -> {c0.close:.2f}",
                        ],
                    )
            elif all(c.is_bearish for c in (c0, c1, c2)) and c0.close < c1.close < c2.close and c0.low < c1.low < c2.low:
                event_id = f"m5_consec_sell_{int(c0.timestamp.timestamp())}"
                if not self._is_event_deduplicated(event_id):
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=SignalDirection.SELL,
                        reference_price=round(c2.open, 2),
                        trigger_price=round(c0.close, 2),
                        invalidation_price=round(c2.high, 2),
                        pattern_role=self.role,
                        phenomenon=self.phenomenon,
                        event_id=event_id,
                        price=round(c0.close, 2),
                        timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                        reasons=[
                            "3 Candle M5 Berturut-turut Bearish dengan Lower Lows & Closes",
                            f"Pergerakan konsisten turun dari {c2.open:.2f} -> {c0.close:.2f}",
                        ],
                    )
        return None


class AlternatingTickPattern(BasePattern):
    """Pola 23: Alternating Pattern.
    Patahnya osilasi bolak-balik oleh terobosan searah pada M5 atau jendela mikro.
    """
    def __init__(self):
        super().__init__(
            pattern_id=23,
            name="Alternating Breakout",
            category="Candle",
            description="Patahnya osilasi harga bolak-balik (ping-pong) memicu sinyal arah terobosan.",
            role=PatternRole.SETUP_TRIGGER,
            phenomenon="Patahnya osilasi bolak-balik mikro/M5 oleh terobosan searah",
            cooldown_ms=2500,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(12)
        if len(ticks) >= 8:
            diffs = [ticks[i].mid - ticks[i - 1].mid for i in range(1, len(ticks))]
            signs = [1 if d > 0.001 else (-1 if d < -0.001 else 0) for d in diffs]
            if len(signs) >= 6:
                was_alternating = (signs[-3] * signs[-4] == -1) and (signs[-4] * signs[-5] == -1)
                alt_ticks = ticks[:-2]
                high_alt = max(t.mid for t in alt_ticks)
                low_alt = min(t.mid for t in alt_ticks)
                span_alt = high_alt - low_alt
                t_now = ticks[-1]

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

        # M5 Candle-based evaluation
        candles = buffer.get_recent_candles(5)
        if len(candles) >= 4:
            c0, c1, c2, c3 = candles[0], candles[1], candles[2], candles[3]
            was_alternating = (c3.is_bullish != c2.is_bullish) and (c2.is_bullish != c1.is_bullish)
            if was_alternating:
                range_high = max(c1.high, c2.high, c3.high)
                range_low = min(c1.low, c2.low, c3.low)
                if c0.is_bullish and c0.close > range_high:
                    event_id = f"m5_alt_buy_{int(c0.timestamp.timestamp())}"
                    if not self._is_event_deduplicated(event_id):
                        return EntrySignal(
                            pattern_id=self.pattern_id,
                            family_name=self.name,
                            direction=SignalDirection.BUY,
                            reference_price=round(range_high, 2),
                            trigger_price=round(c0.close, 2),
                            invalidation_price=round(range_low, 2),
                            pattern_role=self.role,
                            phenomenon=self.phenomenon,
                            event_id=event_id,
                            price=round(c0.close, 2),
                            timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                            reasons=[
                                f"Breakout M5 dari Fase Alternating: Candle menembus batas atas {range_high:.2f}",
                                "Pola bolak-balik terpecahkan ke arah kenaikan",
                            ],
                        )
                elif c0.is_bearish and c0.close < range_low:
                    event_id = f"m5_alt_sell_{int(c0.timestamp.timestamp())}"
                    if not self._is_event_deduplicated(event_id):
                        return EntrySignal(
                            pattern_id=self.pattern_id,
                            family_name=self.name,
                            direction=SignalDirection.SELL,
                            reference_price=round(range_low, 2),
                            trigger_price=round(c0.close, 2),
                            invalidation_price=round(range_high, 2),
                            pattern_role=self.role,
                            phenomenon=self.phenomenon,
                            event_id=event_id,
                            price=round(c0.close, 2),
                            timestamp_ms=int(c0.timestamp.timestamp() * 1000),
                            reasons=[
                                f"Breakout M5 dari Fase Alternating: Candle menembus batas bawah {range_low:.2f}",
                                "Pola bolak-balik terpecahkan ke arah penurunan",
                            ],
                        )
        return None
