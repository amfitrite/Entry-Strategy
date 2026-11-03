"""Hybrid Tick-Candle Entry Patterns (Pola 7-10, 18-20, 24, 28-30, 36-37, 40)."""
from typing import Optional, List
from entrystrategy.engine.base import BasePattern
from entrystrategy.core.models import EntrySignal, SignalDirection, PatternRole, Candle, TickData
from entrystrategy.core.buffer import MarketBuffer


class BreakoutPattern(BasePattern):
    """Pola 7: Breakout (Candle Range Breakout).
    Penembusan High atau Low candle sebelumnya oleh harga saat ini.
    """
    def __init__(self):
        super().__init__(
            pattern_id=7,
            name="Breakout",
            category="Hybrid",
            description="Penembusan High atau Low candle sebelumnya dengan konfirmasi laju tick.",
            role=PatternRole.ENTRY,
            phenomenon="Penembusan batas High/Low candle sebelumnya oleh harga saat ini",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(2)
        tick = buffer.latest_tick
        if not candles:
            return None
        c1 = candles[0]  # Previous closed candle

        if tick:
            px = tick.mid
            # Break above previous high
            if px > (c1.high + 0.10):
                ref_px = round(c1.high, 2)
                trig_px = round(tick.ask, 2)
                inval_px = round(c1.low, 2)
                event_id = f"breakout_buy_{tick.ts_ms}_{int(c1.timestamp.timestamp())}"
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
                        f"Breakout High Candle C[1]: Harga ({px:.2f}) > High ({ref_px:.2f})",
                        f"Penembusan bersih +{px - c1.high:.2f} pts dengan momentum tick aktif",
                    ],
                    metrics={"breakout_pts": round(px - c1.high, 2)},
                )
            # Break below previous low
            if px < (c1.low - 0.10):
                ref_px = round(c1.low, 2)
                trig_px = round(tick.bid, 2)
                inval_px = round(c1.high, 2)
                event_id = f"breakout_sell_{tick.ts_ms}_{int(c1.timestamp.timestamp())}"
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
                        f"Breakout Low Candle C[1]: Harga ({px:.2f}) < Low ({ref_px:.2f})",
                        f"Penembusan bersih {px - c1.low:.2f} pts dengan momentum tick aktif",
                    ],
                    metrics={"breakout_pts": round(px - c1.low, 2)},
                )

        # M5 / M1 Candle-based evaluation
        if len(candles) >= 2:
            c0, c1 = candles[0], candles[1]
            if c0.is_bullish and c0.close > (c1.high + 0.15) and c0.body >= 0.40:
                ref_px = round(c1.high, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(c1.low, 2)
                event_id = f"m5_breakout_buy_{int(c0.timestamp.timestamp())}"
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
                        timestamp_ms=buffer.current_time_ms,
                        reasons=[
                            f"Breakout High Candle C[1] M5: Penutupan ({trig_px:.2f}) > High ({ref_px:.2f})",
                            f"Penembusan bar bullish +{c0.close - c1.high:.2f} pts terkonfirmasi",
                        ],
                        metrics={"breakout_pts": round(c0.close - c1.high, 2)},
                    )
            if c0.is_bearish and c0.close < (c1.low - 0.15) and c0.body >= 0.40:
                ref_px = round(c1.low, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(c1.high, 2)
                event_id = f"m5_breakout_sell_{int(c0.timestamp.timestamp())}"
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
                        timestamp_ms=buffer.current_time_ms,
                        reasons=[
                            f"Breakout Low Candle C[1] M5: Penutupan ({trig_px:.2f}) < Low ({ref_px:.2f})",
                            f"Penembusan bar bearish {c0.close - c1.low:.2f} pts terkonfirmasi",
                        ],
                        metrics={"breakout_pts": round(c0.close - c1.low, 2)},
                    )
        return None


class FailedBreakoutPattern(BasePattern):
    """Pola 8: Failed Breakout (Liquidity Sweep & Reclaim).
    Penembusan palsu disusul penolakan tajam dan reclaim kembali ke dalam range.
    """
    def __init__(self):
        super().__init__(
            pattern_id=8,
            name="Failed Breakout",
            category="Hybrid",
            description="Harga menyapu level High/Low candle lalu berbalik tajam dan reclaim (jebakan likuiditas).",
            role=PatternRole.ENTRY,
            phenomenon="Penembusan palsu (bull/bear trap) disusul sweep dan reclaim kembali ke dalam range",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(2)
        ticks = buffer.get_recent_ticks(15)
        if not candles:
            return None
        c1 = candles[0]

        if len(ticks) >= 10:
            t_now = ticks[-1]
            max_tick_px = max(t.mid for t in ticks)
            min_tick_px = min(t.mid for t in ticks)

            # Bull trap (Failed upside breakout -> SELL)
            if max_tick_px > c1.high and t_now.mid < (c1.high - 0.15):
                ref_px = round(c1.high, 2)
                trig_px = round(t_now.bid, 2)
                inval_px = round(max_tick_px + 0.15, 2)
                event_id = f"failed_breakout_sell_{t_now.ts_ms}_{int(c1.timestamp.timestamp())}"
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
                        timestamp_ms=t_now.ts_ms,
                        reasons=[
                            f"Bull Trap: Sempat menembus ke {max_tick_px:.2f} di atas C[1] High ({ref_px:.2f})",
                            f"Harga terseret jatuh kembali ke {t_now.mid:.2f} (Penolakan breakout terkonfirmasi)",
                        ],
                        metrics={"pierce_high": round(max_tick_px, 2), "ref_high": ref_px},
                    )
            # Bear trap (Failed downside breakout -> BUY)
            if min_tick_px < c1.low and t_now.mid > (c1.low + 0.15):
                ref_px = round(c1.low, 2)
                trig_px = round(t_now.ask, 2)
                inval_px = round(min_tick_px - 0.15, 2)
                event_id = f"failed_breakout_buy_{t_now.ts_ms}_{int(c1.timestamp.timestamp())}"
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
                        timestamp_ms=t_now.ts_ms,
                        reasons=[
                            f"Bear Trap: Sempat menembus ke {min_tick_px:.2f} di bawah C[1] Low ({ref_px:.2f})",
                            f"Harga memantul kembali ke {t_now.mid:.2f} (Penolakan breakdown terkonfirmasi)",
                        ],
                        metrics={"pierce_low": round(min_tick_px, 2), "ref_low": ref_px},
                    )

        # M5 / M1 Candle-based Liquidity Sweep + Reclaim
        if len(candles) >= 2:
            c0, c1 = candles[0], candles[1]
            # Bullish Reclaim (Bear Trap): c0 sweeps below c1.low, closes back above c1.low
            if c0.low < (c1.low - 0.15) and c0.close >= (c1.low + 0.15) and c0.is_bullish:
                ref_px = round(c1.low, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(c0.low - 0.15, 2)
                event_id = f"m5_sweep_reclaim_buy_{int(c0.timestamp.timestamp())}"
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
                        timestamp_ms=buffer.current_time_ms,
                        reasons=[
                            f"Liquidity Sweep Bawah: Ekor C[0] ({c0.low:.2f}) menyapu likuiditas di bawah Swing Low C[1] ({ref_px:.2f})",
                            f"Reclaim Terkonfirmasi: Penutupan C[0] ({trig_px:.2f}) kembali ke atas level dengan candle bullish",
                        ],
                        metrics={"sweep_level": ref_px, "sweep_low": round(c0.low, 2)},
                    )
            # Bearish Reclaim (Bull Trap): c0 sweeps above c1.high, closes back below c1.high
            if c0.high > (c1.high + 0.15) and c0.close <= (c1.high - 0.15) and c0.is_bearish:
                ref_px = round(c1.high, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(c0.high + 0.15, 2)
                event_id = f"m5_sweep_reclaim_sell_{int(c0.timestamp.timestamp())}"
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
                        timestamp_ms=buffer.current_time_ms,
                        reasons=[
                            f"Liquidity Sweep Atas: Ekor C[0] ({c0.high:.2f}) menyapu likuiditas di atas Swing High C[1] ({ref_px:.2f})",
                            f"Reclaim Terkonfirmasi: Penutupan C[0] ({trig_px:.2f}) kembali ke bawah level dengan candle bearish",
                        ],
                        metrics={"sweep_level": ref_px, "sweep_high": round(c0.high, 2)},
                    )
        return None


class MicroPullbackPattern(BasePattern):
    """Pola 9: Micro Pullback.
    Koreksi mikro menguji 50% body bar impuls lalu berlanjut searah tren.
    """
    def __init__(self):
        super().__init__(
            pattern_id=9,
            name="Micro Pullback",
            category="Hybrid",
            description="Koreksi mikro menguji 50% body bar momentum lalu berlanjut searah tren.",
            role=PatternRole.CONFIRMATION,
            phenomenon="Koreksi mikro menguji area 50% body candle impuls disusul kelanjutan tren",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(2)
        ticks = buffer.get_recent_ticks(15)
        if not candles:
            return None
        c1 = candles[0]

        if len(ticks) >= 8:
            t_now = ticks[-1]
            # Bullish momentum in c1, pullback to ~50% in current ticks, then rebound
            if c1.is_bullish and c1.body >= 1.0:
                mid_c1 = (c1.open + c1.close) / 2.0
                min_recent = min(t.mid for t in ticks)
                if min_recent <= mid_c1 and t_now.mid > (mid_c1 + 0.20):
                    ref_px = round(mid_c1, 2)
                    trig_px = round(t_now.ask, 2)
                    inval_px = round(c1.low, 2)
                    event_id = f"micro_pullback_buy_{t_now.ts_ms}_{int(c1.timestamp.timestamp())}"
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
                            timestamp_ms=t_now.ts_ms,
                            reasons=[
                                f"Micro Pullback Bullish menyentuh area 50% C[1] ({ref_px:.2f})",
                                f"Harga kembali menekan ke atas menuju {round(t_now.mid, 2):.2f}",
                            ],
                            metrics={"mid_c1": ref_px, "pullback_low": round(min_recent, 2)},
                        )
            # Bearish momentum in c1, pullback to ~50%, then resume downward
            if c1.is_bearish and c1.body >= 1.0:
                mid_c1 = (c1.open + c1.close) / 2.0
                max_recent = max(t.mid for t in ticks)
                if max_recent >= mid_c1 and t_now.mid < (mid_c1 - 0.20):
                    ref_px = round(mid_c1, 2)
                    trig_px = round(t_now.bid, 2)
                    inval_px = round(c1.high, 2)
                    event_id = f"micro_pullback_sell_{t_now.ts_ms}_{int(c1.timestamp.timestamp())}"
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
                            timestamp_ms=t_now.ts_ms,
                            reasons=[
                                f"Micro Pullback Bearish menyentuh area 50% C[1] ({ref_px:.2f})",
                                f"Harga kembali menekan ke bawah menuju {round(t_now.mid, 2):.2f}",
                            ],
                            metrics={"mid_c1": ref_px, "pullback_high": round(max_recent, 2)},
                        )

        # M5 / M1 Candle-based evaluation
        if len(candles) >= 2:
            c0, c1 = candles[0], candles[1]
            if c1.is_bullish and c1.body >= 1.0:
                mid_c1 = (c1.open + c1.close) / 2.0
                if c0.low <= mid_c1 and c0.close > (mid_c1 + 0.20) and c0.is_bullish:
                    ref_px = round(mid_c1, 2)
                    trig_px = round(c0.close, 2)
                    inval_px = round(c1.low, 2)
                    event_id = f"m5_pullback_buy_{int(c0.timestamp.timestamp())}"
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
                            timestamp_ms=buffer.current_time_ms,
                            reasons=[
                                f"Micro Pullback M5: Ekor menguji area 50% body impuls C[1] ({ref_px:.2f})",
                                f"Harga memantul naik ditutup di {trig_px:.2f} melanjutkan tren bullish",
                            ],
                            metrics={"mid_c1": ref_px, "c0_low": round(c0.low, 2)},
                        )
            if c1.is_bearish and c1.body >= 1.0:
                mid_c1 = (c1.open + c1.close) / 2.0
                if c0.high >= mid_c1 and c0.close < (mid_c1 - 0.20) and c0.is_bearish:
                    ref_px = round(mid_c1, 2)
                    trig_px = round(c0.close, 2)
                    inval_px = round(c1.high, 2)
                    event_id = f"m5_pullback_sell_{int(c0.timestamp.timestamp())}"
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
                            timestamp_ms=buffer.current_time_ms,
                            reasons=[
                                f"Micro Pullback M5: Ekor menguji area 50% body impuls C[1] ({ref_px:.2f})",
                                f"Harga tertekan turun ditutup di {trig_px:.2f} melanjutkan tren bearish",
                            ],
                            metrics={"mid_c1": ref_px, "c0_high": round(c0.high, 2)},
                        )
        return None


class MicroTrendReversalPattern(BasePattern):
    """Pola 10: Micro Trend Reversal.
    Pembalikan struktur tren mikro setelah terbentuknya pivot berlawanan dan penembusan level kunci.
    """
    def __init__(self):
        super().__init__(
            pattern_id=10,
            name="Micro Trend Reversal",
            category="Hybrid",
            description="Pembalikan arah tren lokal 3 bar oleh terbentuknya pivot baru dan penembusan level.",
            role=PatternRole.STRUCTURE,
            phenomenon="Pembalikan struktur tren mikro setelah terbentuknya pivot berlawanan dan penembusan level kunci",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(4)
        tick = buffer.latest_tick
        if len(candles) < 3:
            return None
        c1, c2, c3 = candles[0], candles[1], candles[2]

        if tick:
            px = tick.mid
            # Micro Downtrend (3 lower highs), higher low formed (c1.low > c2.low), now tick breaks above c1.high
            if (c1.high < c2.high < c3.high) and (c1.low > c2.low) and px > (c1.high + 0.15):
                ref_px = round(c1.high, 2)
                trig_px = round(tick.ask, 2)
                inval_px = round(c1.low, 2)
                event_id = f"micro_trend_buy_{tick.ts_ms}_{int(c1.timestamp.timestamp())}"
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
                        timestamp_ms=tick.ts_ms,
                        reasons=[
                            f"Micro Trend Reversal Bullish: Lower highs (C3->C2->C1) diimbangi higher low",
                            f"Harga saat ini ({px:.2f}) menembus swing high C[1] ({ref_px:.2f})",
                        ],
                        metrics={"broken_high": ref_px, "higher_low": round(c1.low, 2)},
                    )

            # Micro Uptrend (3 higher lows), lower high formed (c1.high < c2.high), now tick breaks below c1.low
            if (c1.low > c2.low > c3.low) and (c1.high < c2.high) and px < (c1.low - 0.15):
                ref_px = round(c1.low, 2)
                trig_px = round(tick.bid, 2)
                inval_px = round(c1.high, 2)
                event_id = f"micro_trend_sell_{tick.ts_ms}_{int(c1.timestamp.timestamp())}"
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
                        timestamp_ms=tick.ts_ms,
                        reasons=[
                            f"Micro Trend Reversal Bearish: Higher lows (C3->C2->C1) diimbangi lower high",
                            f"Harga saat ini ({px:.2f}) menembus swing low C[1] ({ref_px:.2f})",
                        ],
                        metrics={"broken_low": ref_px, "lower_high": round(c1.high, 2)},
                    )

        # M5 / M1 Candle-based evaluation
        if len(candles) >= 4:
            c0, c1, c2, c3 = candles[0], candles[1], candles[2], candles[3]
            # Bullish Pivot Reversal
            if (c1.high < c2.high < c3.high) and (c1.low > c2.low) and c0.close > (c1.high + 0.15) and c0.is_bullish:
                ref_px = round(c1.high, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(c1.low, 2)
                event_id = f"m5_micro_trend_buy_{int(c0.timestamp.timestamp())}"
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
                        timestamp_ms=buffer.current_time_ms,
                        reasons=[
                            f"Micro Trend Reversal Bullish M5: Lower highs diimbangi Higher Low di C[1]",
                            f"Candle C[0] ({trig_px:.2f}) menembus swing high C[1] ({ref_px:.2f})",
                        ],
                        metrics={"broken_high": ref_px, "higher_low": round(c1.low, 2)},
                    )
            # Bearish Pivot Reversal
            if (c1.low > c2.low > c3.low) and (c1.high < c2.high) and c0.close < (c1.low - 0.15) and c0.is_bearish:
                ref_px = round(c1.low, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(c1.high, 2)
                event_id = f"m5_micro_trend_sell_{int(c0.timestamp.timestamp())}"
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
                        timestamp_ms=buffer.current_time_ms,
                        reasons=[
                            f"Micro Trend Reversal Bearish M5: Higher lows diimbangi Lower High di C[1]",
                            f"Candle C[0] ({trig_px:.2f}) menembus swing low C[1] ({ref_px:.2f})",
                        ],
                        metrics={"broken_low": ref_px, "lower_high": round(c1.high, 2)},
                    )
        return None


class MicroRangeExpansionPattern(BasePattern):
    """Pola 18: Micro Range Expansion.
    Ekspansi rentang harga mendadak melampaui rata-rata range beberapa bar.
    """
    def __init__(self):
        super().__init__(
            pattern_id=18,
            name="Micro Range Expansion",
            category="Hybrid",
            description="Ekspansi rentang harga mendadak melampaui rata-rata range beberapa bar.",
            role=PatternRole.ENTRY,
            phenomenon="Ekspansi rentang harga mendadak melampaui rata-rata range bar historis",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(5)
        ticks = buffer.get_recent_ticks(20)
        if len(candles) < 3:
            return None
        avg_range = sum(c.range for c in candles[:3]) / 3.0

        if len(ticks) >= 10:
            t_now = ticks[-1]
            t_old = ticks[0]
            tick_span = abs(t_now.mid - t_old.mid)

            if tick_span >= (avg_range * 1.3):
                dir_choice = SignalDirection.BUY if t_now.mid > t_old.mid else SignalDirection.SELL
                ref_px = round(t_old.mid, 2)
                trig_px = round(t_now.ask if dir_choice == SignalDirection.BUY else t_now.bid, 2)
                inval_px = ref_px
                event_id = f"range_exp_{dir_choice.value}_{t_now.ts_ms}_{round(t_now.mid, 2)}"
                if not self._is_event_deduplicated(event_id):
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=dir_choice,
                        reference_price=ref_px,
                        trigger_price=trig_px,
                        invalidation_price=inval_px,
                        pattern_role=self.role,
                        phenomenon=self.phenomenon,
                        event_id=event_id,
                        price=trig_px,
                        timestamp_ms=t_now.ts_ms,
                        reasons=[
                            f"Ekspansi Rentang Mikro: Perpindahan {tick_span:.2f} pts (> 1.3x avg {avg_range:.2f} pts)",
                            f"Arah ekspansi agresif: {dir_choice.value}",
                        ],
                        metrics={"tick_span": round(tick_span, 2), "avg_bar_range": round(avg_range, 2)},
                    )

        # M5 / M1 Candle-based evaluation
        if len(candles) >= 4:
            c0 = candles[0]
            prior = candles[1:4]
            avg_r = sum(c.range for c in prior) / len(prior)
            if avg_r > 0 and c0.range >= (1.4 * avg_r) and c0.body >= (0.60 * c0.range):
                if c0.is_bullish:
                    ref_px = round(c0.open, 2)
                    trig_px = round(c0.close, 2)
                    inval_px = round(c0.low, 2)
                    event_id = f"m5_range_exp_buy_{int(c0.timestamp.timestamp())}"
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
                            timestamp_ms=buffer.current_time_ms,
                            reasons=[
                                f"Ekspansi Rentang Bar M5: Rentang {c0.range:.2f} pts (> 1.4x avg {avg_r:.2f} pts)",
                                f"Dorongan bullish solid dari {ref_px:.2f} menuju {trig_px:.2f}",
                            ],
                            metrics={"range": round(c0.range, 2), "avg_range": round(avg_r, 2)},
                        )
                elif c0.is_bearish:
                    ref_px = round(c0.open, 2)
                    trig_px = round(c0.close, 2)
                    inval_px = round(c0.high, 2)
                    event_id = f"m5_range_exp_sell_{int(c0.timestamp.timestamp())}"
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
                            timestamp_ms=buffer.current_time_ms,
                            reasons=[
                                f"Ekspansi Rentang Bar M5: Rentang {c0.range:.2f} pts (> 1.4x avg {avg_r:.2f} pts)",
                                f"Dorongan bearish solid dari {ref_px:.2f} menuju {trig_px:.2f}",
                            ],
                            metrics={"range": round(c0.range, 2), "avg_range": round(avg_r, 2)},
                        )
        return None


class MicroRangeCompressionPattern(BasePattern):
    """Pola 19: Micro Range Compression.
    Penyempitan volatilitas mikro/M5 (kompresi) yang ditembus oleh terobosan searah.
    """
    def __init__(self):
        super().__init__(
            pattern_id=19,
            name="Micro Range Compression",
            category="Hybrid",
            description="Penyempitan rentang harga historis sebelum terjadinya terobosan arah.",
            role=PatternRole.SETUP_TRIGGER,
            phenomenon="Penyempitan volatilitas mikro (kompresi) yang ditembus oleh tick terobosan",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(25)
        if len(ticks) >= 20:
            hist_ticks = ticks[:-1]
            high_hist = max(t.mid for t in hist_ticks)
            low_hist = min(t.mid for t in hist_ticks)
            span_hist = high_hist - low_hist
            t_now = ticks[-1]

            if span_hist <= 0.22:
                if t_now.mid > (high_hist + 0.03):
                    ref_px = round(high_hist, 2)
                    trig_px = round(t_now.ask, 2)
                    inval_px = round(low_hist, 2)
                    event_id = f"range_comp_buy_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                            timestamp_ms=t_now.ts_ms,
                            reasons=[
                                f"Kompresi Rentang Mikro Ketat: Hanya {span_hist:.2f} pts dalam {len(hist_ticks)} tick historis",
                                f"Tick pemicu ({round(t_now.mid, 2):.2f}) meledak menembus batas atas ({ref_px:.2f})",
                            ],
                            metrics={"span_hist": round(span_hist, 2), "breakout_level": ref_px},
                        )
                if t_now.mid < (low_hist - 0.03):
                    ref_px = round(low_hist, 2)
                    trig_px = round(t_now.bid, 2)
                    inval_px = round(high_hist, 2)
                    event_id = f"range_comp_sell_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                            timestamp_ms=t_now.ts_ms,
                            reasons=[
                                f"Kompresi Rentang Mikro Ketat: Hanya {span_hist:.2f} pts dalam {len(hist_ticks)} tick historis",
                                f"Tick pemicu ({round(t_now.mid, 2):.2f}) meledak menembus batas bawah ({ref_px:.2f})",
                            ],
                            metrics={"span_hist": round(span_hist, 2), "breakout_level": ref_px},
                        )

        # M5 / M1 Candle-based evaluation
        candles = buffer.get_recent_candles(5)
        if len(candles) >= 4:
            c0 = candles[0]
            c1, c2, c3 = candles[1], candles[2], candles[3]
            comp_high = max(c1.high, c2.high, c3.high)
            comp_low = min(c1.low, c2.low, c3.low)
            span_comp = comp_high - comp_low

            if span_comp <= 0.60:
                if c0.is_bullish and c0.close > (comp_high + 0.15):
                    ref_px = round(comp_high, 2)
                    trig_px = round(c0.close, 2)
                    inval_px = round(comp_low, 2)
                    event_id = f"m5_range_comp_buy_{int(c0.timestamp.timestamp())}"
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
                            timestamp_ms=buffer.current_time_ms,
                            reasons=[
                                f"Kompresi Bar M5 3 Bar: Rentang konsolidasi ketat {span_comp:.2f} pts",
                                f"Terobosan Bullish C[0] ({trig_px:.2f}) menembus batas kompresi ({ref_px:.2f})",
                            ],
                            metrics={"span_comp": round(span_comp, 2), "breakout_level": ref_px},
                        )
                if c0.is_bearish and c0.close < (comp_low - 0.15):
                    ref_px = round(comp_low, 2)
                    trig_px = round(c0.close, 2)
                    inval_px = round(comp_high, 2)
                    event_id = f"m5_range_comp_sell_{int(c0.timestamp.timestamp())}"
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
                            timestamp_ms=buffer.current_time_ms,
                            reasons=[
                                f"Kompresi Bar M5 3 Bar: Rentang konsolidasi ketat {span_comp:.2f} pts",
                                f"Terobosan Bearish C[0] ({trig_px:.2f}) menembus batas kompresi ({ref_px:.2f})",
                            ],
                            metrics={"span_comp": round(span_comp, 2), "breakout_level": ref_px},
                        )
        return None


class VolatilityBurstPattern(BasePattern):
    """Pola 20: Volatility Burst.
    Kombinasi serentak lonjakan frekuensi tick dan pergeseran rentang harga.
    """
    def __init__(self):
        super().__init__(
            pattern_id=20,
            name="Volatility Burst",
            category="Hybrid",
            description="Kombinasi serentak lonjakan frekuensi tick dan lonjakan rentang harga.",
            role=PatternRole.ENTRY,
            phenomenon="Kombinasi serentak lonjakan frekuensi kedatangan tick dan perpindahan rentang harga",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(30)
        if len(ticks) >= 20:
            t_now = ticks[-1]
            t_old = ticks[0]
            dt_sec = max(0.1, (t_now.ts_ms - t_old.ts_ms) / 1000.0)
            freq = len(ticks) / dt_sec
            disp = t_now.mid - t_old.mid

            if freq >= 20.0 and abs(disp) >= 0.50:
                dir_choice = SignalDirection.BUY if disp > 0 else SignalDirection.SELL
                ref_px = round(t_old.mid, 2)
                trig_px = round(t_now.ask if dir_choice == SignalDirection.BUY else t_now.bid, 2)
                inval_px = ref_px
                event_id = f"vol_burst_{dir_choice.value}_{t_now.ts_ms}_{round(t_now.mid, 2)}"
                if not self._is_event_deduplicated(event_id):
                    return EntrySignal(
                        pattern_id=self.pattern_id,
                        family_name=self.name,
                        direction=dir_choice,
                        reference_price=ref_px,
                        trigger_price=trig_px,
                        invalidation_price=inval_px,
                        pattern_role=self.role,
                        phenomenon=self.phenomenon,
                        event_id=event_id,
                        price=trig_px,
                        timestamp_ms=t_now.ts_ms,
                        reasons=[
                            f"Ledakan Volatilitas & Frekuensi Serentak: {freq:.1f} t/s & displacement {disp:.2f} pts",
                            f"Arah pergerakan: {dir_choice.value}",
                        ],
                        metrics={"freq_tps": round(freq, 1), "displacement": round(disp, 2)},
                    )

        # M5 / M1 Candle-based evaluation
        candles = buffer.get_recent_candles(5)
        if len(candles) >= 4:
            c0 = candles[0]
            prior = candles[1:4]
            avg_r = sum(c.range for c in prior) / len(prior)
            avg_v = sum((c.tick_volume or 1.0) for c in prior) / len(prior)
            if avg_r > 0 and c0.range >= (1.5 * avg_r) and (c0.tick_volume or 1.0) >= (1.5 * avg_v):
                if c0.is_bullish:
                    ref_px = round(c0.open, 2)
                    trig_px = round(c0.close, 2)
                    inval_px = round(c0.low, 2)
                    event_id = f"m5_vol_burst_buy_{int(c0.timestamp.timestamp())}"
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
                            timestamp_ms=buffer.current_time_ms,
                            reasons=[
                                f"Ledakan Volatilitas M5 Bullish: Range {c0.range:.2f} pts (> 1.5x avg {avg_r:.2f} pts)",
                                f"Volume {c0.tick_volume:.0f} (> 1.5x avg {avg_v:.0f}) mengonfirmasi dorongan kuat",
                            ],
                            metrics={"range": round(c0.range, 2), "volume": c0.tick_volume},
                        )
                elif c0.is_bearish:
                    ref_px = round(c0.open, 2)
                    trig_px = round(c0.close, 2)
                    inval_px = round(c0.high, 2)
                    event_id = f"m5_vol_burst_sell_{int(c0.timestamp.timestamp())}"
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
                            timestamp_ms=buffer.current_time_ms,
                            reasons=[
                                f"Ledakan Volatilitas M5 Bearish: Range {c0.range:.2f} pts (> 1.5x avg {avg_r:.2f} pts)",
                                f"Volume {c0.tick_volume:.0f} (> 1.5x avg {avg_v:.0f}) mengonfirmasi dorongan kuat",
                            ],
                            metrics={"range": round(c0.range, 2), "volume": c0.tick_volume},
                        )
        return None


class RejectionPattern(BasePattern):
    """Pola 24: Rejection Pattern.
    Penolakan harga cepat di level ekstrem meninggalkan ekor intra-bar.
    """
    def __init__(self):
        super().__init__(
            pattern_id=24,
            name="Rejection Pattern",
            category="Hybrid",
            description="Penolakan harga cepat di level ekstrem meninggalkan ekor intra-bar.",
            role=PatternRole.ENTRY,
            phenomenon="Penolakan harga cepat di level ekstrem meninggalkan ekor intra-bar",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(20)
        if len(ticks) >= 15:
            t_now = ticks[-1]
            min_idx = min(range(len(ticks)), key=lambda i: ticks[i].mid)
            max_idx = max(range(len(ticks)), key=lambda i: ticks[i].mid)
            min_p = ticks[min_idx].mid
            max_p = ticks[max_idx].mid

            # Upper rejection: reached high AFTER low, then dropped by >= 0.35 pts
            if max_idx > min_idx and (max_p - t_now.mid) >= 0.35:
                ref_px = round(max_p, 2)
                trig_px = round(t_now.bid, 2)
                inval_px = round(max_p + 0.15, 2)
                event_id = f"rejection_sell_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                        f"Penolakan Atas (Upper Rejection): Puncak {ref_px:.2f} ditolak turun {max_p - t_now.mid:.2f} pts",
                        "Tekanan penolakan kuat muncul di pucuk harga",
                    ],
                    metrics={"rejection_pts": round(max_p - t_now.mid, 2), "extreme": ref_px},
                )

            # Lower rejection: reached low AFTER high, then bounced by >= 0.35 pts
            if min_idx > max_idx and (t_now.mid - min_p) >= 0.35:
                ref_px = round(min_p, 2)
                trig_px = round(t_now.ask, 2)
                inval_px = round(min_p - 0.15, 2)
                event_id = f"rejection_buy_{t_now.ts_ms}_{round(t_now.mid, 2)}"
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
                        f"Penolakan Bawah (Lower Rejection): Dasar {ref_px:.2f} memantul naik {t_now.mid - min_p:.2f} pts",
                        "Tekanan pantulan kuat muncul di dasar harga",
                    ],
                    metrics={"rejection_pts": round(t_now.mid - min_p, 2), "extreme": ref_px},
                )

        # M5 Candle-based evaluation
        candles = buffer.get_recent_candles(2)
        if candles:
            c0 = candles[0]
            if c0.lower_wick >= 0.50 * c0.range and c0.range >= 0.60:
                ref_px = round(c0.low, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(c0.low - 0.15, 2)
                event_id = f"m5_rejection_buy_{int(c0.timestamp.timestamp())}"
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
                        timestamp_ms=buffer.current_time_ms,
                        reasons=[
                            f"Penolakan Bawah M5 (Lower Rejection): Ekor bawah {c0.lower_wick:.2f} pts (> 50% range)",
                            "Tekanan pantulan kuat muncul di dasar candle M5",
                        ],
                    )
            if c0.upper_wick >= 0.50 * c0.range and c0.range >= 0.60:
                ref_px = round(c0.high, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(c0.high + 0.15, 2)
                event_id = f"m5_rejection_sell_{int(c0.timestamp.timestamp())}"
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
                        timestamp_ms=buffer.current_time_ms,
                        reasons=[
                            f"Penolakan Atas M5 (Upper Rejection): Ekor atas {c0.upper_wick:.2f} pts (> 50% range)",
                            "Tekanan penolakan kuat muncul di pucuk candle M5",
                        ],
                    )
        return None


class GapPattern(BasePattern):
    """Pola 28: Gap Pattern.
    Lompatan harga (price gap) antara candle berturut-turut tanpa jeda sesi.
    Audit fix: Memeriksa kontinuitas intraday (selisih waktu <= 180s) agar tidak salah deteksi akhir sesi.
    """
    def __init__(self):
        super().__init__(
            pattern_id=28,
            name="Gap Pattern",
            category="Hybrid",
            description="Lompatan harga intraday antara candle berturut-turut.",
            role=PatternRole.ENTRY,
            phenomenon="Lompatan harga intraday (price gap) antara candle berturut-turut tanpa jeda sesi",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(2)
        if len(candles) >= 2:
            c0, c1 = candles[0], candles[1]
            time_diff = abs((c0.timestamp - c1.timestamp).total_seconds())
            max_allowed = 600 if buffer.active_timeframe == "M5" else 180
            if time_diff > max_allowed:
                return None

            gap = c0.open - c1.close
            tick = buffer.latest_tick
            ts = tick.ts_ms if tick else buffer.current_time_ms
            
            # Gap up >= 0.40 pts
            if gap >= 0.40:
                ref_px = round(c1.close, 2)
                trig_px = round(tick.ask if tick else c0.open, 2)
                inval_px = ref_px
                event_id = f"gap_buy_{int(c0.timestamp.timestamp())}_{trig_px}"
                if self._is_candle_deduplicated(c0.timestamp, SignalDirection.BUY) or self._is_event_deduplicated(event_id):
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
                    timestamp_ms=ts,
                    reasons=[
                        f"Gap Up Intraday Terdeteksi: Lompatan +{gap:.2f} pts dari {ref_px:.2f} ke {trig_px:.2f}",
                        "Momentum pembukaan candle melompat agresif",
                    ],
                    metrics={"gap_pts": round(gap, 2)},
                )
            # Gap down <= -0.40 pts
            if gap <= -0.40:
                ref_px = round(c1.close, 2)
                trig_px = round(tick.bid if tick else c0.open, 2)
                inval_px = ref_px
                event_id = f"gap_sell_{int(c0.timestamp.timestamp())}_{trig_px}"
                if self._is_candle_deduplicated(c0.timestamp, SignalDirection.SELL) or self._is_event_deduplicated(event_id):
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
                    timestamp_ms=ts,
                    reasons=[
                        f"Gap Down Intraday Terdeteksi: Lompatan {gap:.2f} pts dari {ref_px:.2f} ke {trig_px:.2f}",
                        "Momentum pembukaan candle merosot tajam",
                    ],
                    metrics={"gap_pts": round(gap, 2)},
                )
        return None


class FailedMomentumPattern(BasePattern):
    """Pola 29: Failed Momentum.
    Dorongan momentum awal yang gagal berlanjut dan berbalik 100%.
    """
    def __init__(self):
        super().__init__(
            pattern_id=29,
            name="Failed Momentum",
            category="Hybrid",
            description="Dorongan momentum awal yang gagal berlanjut dan berbalik 100%.",
            role=PatternRole.ENTRY,
            phenomenon="Impuls momentum awal yang gagal mempertahankan arah dan berbalik 100%",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(30)
        if len(ticks) >= 25:
            t_start = ticks[0]
            t_mid = ticks[12]
            t_now = ticks[-1]

            leg1 = t_mid.mid - t_start.mid
            leg2 = t_now.mid - t_mid.mid

            # Bullish momentum failed
            if leg1 >= 0.50 and leg2 <= -0.50:
                ref_px = round(t_mid.mid, 2)
                trig_px = round(t_now.bid, 2)
                inval_px = round(t_mid.mid + 0.15, 2)
                event_id = f"failed_mom_sell_{t_now.ts_ms}_{ref_px}"
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
                        timestamp_ms=t_now.ts_ms,
                        reasons=[
                            f"Momentum Naik Gagal: Dorongan +{leg1:.2f} pts luntur total {leg2:.2f} pts",
                            f"Puncak di {ref_px:.2f} gagal dipertahankan, harga kembali ke {round(t_now.mid, 2):.2f}",
                        ],
                        metrics={"leg1": round(leg1, 2), "leg2": round(leg2, 2)},
                    )
            # Bearish momentum failed
            if leg1 <= -0.50 and leg2 >= 0.50:
                ref_px = round(t_mid.mid, 2)
                trig_px = round(t_now.ask, 2)
                inval_px = round(t_mid.mid - 0.15, 2)
                event_id = f"failed_mom_buy_{t_now.ts_ms}_{ref_px}"
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
                        timestamp_ms=t_now.ts_ms,
                        reasons=[
                            f"Momentum Turun Gagal: Dorongan {leg1:.2f} pts dipulihkan total +{leg2:.2f} pts",
                            f"Dasar di {ref_px:.2f} gagal dipertahankan, harga kembali ke {round(t_now.mid, 2):.2f}",
                        ],
                        metrics={"leg1": round(leg1, 2), "leg2": round(leg2, 2)},
                    )

        # M5 / M1 Candle-based evaluation
        candles = buffer.get_recent_candles(2)
        if len(candles) >= 2:
            c0, c1 = candles[0], candles[1]
            if c1.is_bullish and c1.body >= 1.0 and c0.is_bearish and c0.close <= (c1.open + 0.15):
                ref_px = round(c1.high, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(c1.high + 0.15, 2)
                event_id = f"m5_failed_mom_sell_{int(c0.timestamp.timestamp())}"
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
                        timestamp_ms=buffer.current_time_ms,
                        reasons=[
                            f"Momentum Naik M5 Gagal Total: Bar bullish {c1.body:.2f} pts di-reversal 100% oleh bar bearish {c0.body:.2f} pts",
                            f"Penutupan {trig_px:.2f} menembus kembali di bawah open C[1] ({c1.open:.2f})",
                        ],
                        metrics={"c1_body": round(c1.body, 2), "c0_body": round(c0.body, 2)},
                    )
            if c1.is_bearish and c1.body >= 1.0 and c0.is_bullish and c0.close >= (c1.open - 0.15):
                ref_px = round(c1.low, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(c1.low - 0.15, 2)
                event_id = f"m5_failed_mom_buy_{int(c0.timestamp.timestamp())}"
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
                        timestamp_ms=buffer.current_time_ms,
                        reasons=[
                            f"Momentum Turun M5 Gagal Total: Bar bearish {c1.body:.2f} pts di-reversal 100% oleh bar bullish {c0.body:.2f} pts",
                            f"Penutupan {trig_px:.2f} menembus kembali di atas open C[1] ({c1.open:.2f})",
                        ],
                        metrics={"c1_body": round(c1.body, 2), "c0_body": round(c0.body, 2)},
                    )
        return None


class MomentumExhaustionPattern(BasePattern):
    """Pola 30: Momentum Exhaustion.
    Momentum kehilangan tenaga di penghujung pergerakan panjang disusul konfirmasi penolakan.
    """
    def __init__(self):
        super().__init__(
            pattern_id=30,
            name="Momentum Exhaustion",
            category="Hybrid",
            description="Momentum kehilangan tenaga di penghujung bar besar disusul tanda pembalikan.",
            role=PatternRole.SETUP_TRIGGER,
            phenomenon="Kehilangan momentum dorongan besar disusul konfirmasi penolakan arah balik",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(3)
        ticks = buffer.get_recent_ticks(20)
        if not candles:
            return None
        c1 = candles[0]

        if len(ticks) >= 15:
            t_now = ticks[-1]
            stall_ticks = ticks[:-1]
            tick_span = max(t.mid for t in stall_ticks) - min(t.mid for t in stall_ticks)
            # Extended run in c1 followed by tick stalling and then reversal tick break
            if c1.is_bullish and c1.range >= 1.5 and tick_span <= 0.20 and t_now.mid < (c1.high - 0.20):
                ref_px = round(c1.high, 2)
                trig_px = round(t_now.bid, 2)
                inval_px = round(c1.high + 0.15, 2)
                event_id = f"mom_exh_sell_{t_now.ts_ms}_{ref_px}"
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
                        timestamp_ms=t_now.ts_ms,
                        reasons=[
                            f"Kehabisan Tenaga Buyer (Bull Exhaustion) setelah bar besar {c1.range:.2f} pts",
                            f"Rentang tick macet di pucuk ({tick_span:.2f} pts) dan mulai terdorong turun di bawah {ref_px:.2f}",
                        ],
                        metrics={"candle_range": round(c1.range, 2), "tick_span": round(tick_span, 2)},
                    )
            if c1.is_bearish and c1.range >= 1.5 and tick_span <= 0.20 and t_now.mid > (c1.low + 0.20):
                ref_px = round(c1.low, 2)
                trig_px = round(t_now.ask, 2)
                inval_px = round(c1.low - 0.15, 2)
                event_id = f"mom_exh_buy_{t_now.ts_ms}_{ref_px}"
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
                        timestamp_ms=t_now.ts_ms,
                        reasons=[
                            f"Kehabisan Tenaga Seller (Bear Exhaustion) setelah bar besar {c1.range:.2f} pts",
                            f"Rentang tick macet di dasar ({tick_span:.2f} pts) dan mulai terdorong naik di atas {ref_px:.2f}",
                        ],
                        metrics={"candle_range": round(c1.range, 2), "tick_span": round(tick_span, 2)},
                    )

        # M5 / M1 Candle-based evaluation
        if len(candles) >= 2:
            c0 = candles[0]
            c1 = candles[1]
            if c1.is_bullish and c1.range >= 1.5 and c0.close < (c1.high - 0.20):
                if c0.body <= (0.35 * c1.body) or c0.upper_wick >= (0.40 * c0.range):
                    ref_px = round(c1.high, 2)
                    trig_px = round(c0.close, 2)
                    inval_px = round(max(c0.high, c1.high) + 0.15, 2)
                    event_id = f"m5_mom_exh_sell_{int(c0.timestamp.timestamp())}"
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
                            timestamp_ms=buffer.current_time_ms,
                            reasons=[
                                f"Kehabisan Tenaga Buyer (Bull Exhaustion) M5: Reli besar {c1.range:.2f} pts gagal berlanjut",
                                f"Bar C[0] terhenti (body kecil/ekor atas panjang) dan terdorong turun ke {trig_px:.2f}",
                            ],
                            metrics={"c1_range": round(c1.range, 2), "c0_body": round(c0.body, 2)},
                        )
            if c1.is_bearish and c1.range >= 1.5 and c0.close > (c1.low + 0.20):
                if c0.body <= (0.35 * c1.body) or c0.lower_wick >= (0.40 * c0.range):
                    ref_px = round(c1.low, 2)
                    trig_px = round(c0.close, 2)
                    inval_px = round(min(c0.low, c1.low) - 0.15, 2)
                    event_id = f"m5_mom_exh_buy_{int(c0.timestamp.timestamp())}"
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
                            timestamp_ms=buffer.current_time_ms,
                            reasons=[
                                f"Kehabisan Tenaga Seller (Bear Exhaustion) M5: Penurunan besar {c1.range:.2f} pts gagal berlanjut",
                                f"Bar C[0] terhenti (body kecil/ekor bawah panjang) dan terdorong naik ke {trig_px:.2f}",
                            ],
                            metrics={"c1_range": round(c1.range, 2), "c0_body": round(c0.body, 2)},
                        )
        return None


class VReversalPattern(BasePattern):
    """Pola 36: V-Reversal.
    Pembalikan arah tajam berbentuk V setelah penurunan cepat.
    """
    def __init__(self):
        super().__init__(
            pattern_id=36,
            name="V-Reversal",
            category="Hybrid",
            description="Pembalikan arah cepat berbentuk huruf V setelah kejatuhan tajam.",
            role=PatternRole.ENTRY,
            phenomenon="Pembalikan arah tajam berbentuk V setelah penurunan cepat",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(35)
        if len(ticks) >= 25:
            t_start = ticks[0]
            t_bottom = min(ticks, key=lambda t: t.mid)
            t_now = ticks[-1]

            drop = t_start.mid - t_bottom.mid
            rebound = t_now.mid - t_bottom.mid

            # V-reversal: drop >= 0.50 pts, rebound recovering at least 80% of drop
            if drop >= 0.50 and rebound >= (drop * 0.80):
                ref_px = round(t_bottom.mid, 2)
                trig_px = round(t_now.ask, 2)
                inval_px = round(t_bottom.mid - 0.20, 2)
                event_id = f"v_rev_{t_now.ts_ms}_{ref_px}"
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
                        f"Pola V-Reversal: Kejatuhan cepat {drop:.2f} pts disusul Rebound {rebound:.2f} pts",
                        f"Pemulihan {rebound / drop * 100:.1f}% dari titik terendah {ref_px:.2f}",
                    ],
                    metrics={"drop": round(drop, 2), "rebound": round(rebound, 2)},
                )

        # M5 Candle-based evaluation
        candles = buffer.get_recent_candles(3)
        if len(candles) >= 2:
            c0, c1 = candles[0], candles[1]
            if c1.is_bearish and c0.is_bullish and c1.body >= 0.80 and c0.close >= (c1.open - 0.20 * c1.body):
                ref_px = round(c1.low, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(min(c0.low, c1.low) - 0.15, 2)
                event_id = f"m5_v_rev_{int(c0.timestamp.timestamp())}"
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
                        timestamp_ms=buffer.current_time_ms,
                        reasons=[
                            f"V-Reversal M5: Bar penurunan {c1.body:.2f} pts langsung dibalas rebound kuat {c0.body:.2f} pts",
                            f"Pemulihan harga merebut kembali level {trig_px:.2f}",
                        ],
                    )
        return None


class InvertedVReversalPattern(BasePattern):
    """Pola 37: Inverted V-Reversal.
    Pembalikan arah tajam berbentuk V terbalik setelah reli cepat.
    """
    def __init__(self):
        super().__init__(
            pattern_id=37,
            name="Inverted V-Reversal",
            category="Hybrid",
            description="Pembalikan arah cepat berbentuk huruf V terbalik setelah reli tajam.",
            role=PatternRole.ENTRY,
            phenomenon="Pembalikan arah tajam berbentuk V terbalik setelah reli cepat",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        ticks = buffer.get_recent_ticks(35)
        if len(ticks) >= 25:
            t_start = ticks[0]
            t_top = max(ticks, key=lambda t: t.mid)
            t_now = ticks[-1]

            rally = t_top.mid - t_start.mid
            slump = t_top.mid - t_now.mid

            if rally >= 0.50 and slump >= (rally * 0.80):
                ref_px = round(t_top.mid, 2)
                trig_px = round(t_now.bid, 2)
                inval_px = round(t_top.mid + 0.20, 2)
                event_id = f"inv_v_rev_{t_now.ts_ms}_{ref_px}"
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
                        f"Pola Inverted V-Reversal: Reli cepat +{rally:.2f} pts disusul Kolaps {slump:.2f} pts",
                        f"Penurunan {slump / rally * 100:.1f}% dari titik puncak {ref_px:.2f}",
                    ],
                    metrics={"rally": round(rally, 2), "slump": round(slump, 2)},
                )

        # M5 Candle-based evaluation
        candles = buffer.get_recent_candles(3)
        if len(candles) >= 2:
            c0, c1 = candles[0], candles[1]
            if c1.is_bullish and c0.is_bearish and c1.body >= 0.80 and c0.close <= (c1.open + 0.20 * c1.body):
                ref_px = round(c1.high, 2)
                trig_px = round(c0.close, 2)
                inval_px = round(max(c0.high, c1.high) + 0.15, 2)
                event_id = f"m5_inv_v_rev_{int(c0.timestamp.timestamp())}"
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
                        timestamp_ms=buffer.current_time_ms,
                        reasons=[
                            f"Inverted V-Reversal M5: Bar reli {c1.body:.2f} pts langsung dibalas kejatuhan kuat {c0.body:.2f} pts",
                            f"Penurunan harga menembus kembali level {trig_px:.2f}",
                        ],
                    )
        return None


class CandleRejectionConfluencePattern(BasePattern):
    """40: Candle-only rejection + follow-through confluence."""

    def __init__(self):
        super().__init__(
            pattern_id=40,
            name="Candle Rejection Confluence",
            category="Candle",
            description="Pin-bar rejection pada candle sebelumnya yang dikonfirmasi close candle berikutnya searah pantulan.",
            role=PatternRole.ENTRY,
            phenomenon="Rejection wick pada level ekstrem dan candle follow-through pada timeframe yang sama",
            cooldown_ms=4000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(3)
        if len(candles) < 2:
            return None
        c0, c1 = candles[0], candles[1]

        if c1.lower_wick >= c1.range * 0.45 and c0.is_bullish and c0.close > c1.close:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.BUY,
                reference_price=round(c1.low, 2),
                trigger_price=round(c0.close, 2),
                invalidation_price=round(c1.low - 0.15, 2),
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=f"candle_rejection_buy_{int(c0.timestamp.timestamp())}",
                price=round(c0.close, 2),
                timestamp_ms=buffer.current_time_ms,
                reasons=[
                    f"Lower rejection wick {c1.lower_wick:.2f} pts pada candle sebelumnya",
                    f"Follow-through bullish close {c0.close:.2f} di atas close rejection {c1.close:.2f}",
                ],
                metrics={"rejection_wick": round(c1.lower_wick, 2), "rejection_low": round(c1.low, 2)},
            )
        if c1.upper_wick >= c1.range * 0.45 and c0.is_bearish and c0.close < c1.close:
            return EntrySignal(
                pattern_id=self.pattern_id,
                family_name=self.name,
                direction=SignalDirection.SELL,
                reference_price=round(c1.high, 2),
                trigger_price=round(c0.close, 2),
                invalidation_price=round(c1.high + 0.15, 2),
                pattern_role=self.role,
                phenomenon=self.phenomenon,
                event_id=f"candle_rejection_sell_{int(c0.timestamp.timestamp())}",
                price=round(c0.close, 2),
                timestamp_ms=buffer.current_time_ms,
                reasons=[
                    f"Upper rejection wick {c1.upper_wick:.2f} pts pada candle sebelumnya",
                    f"Follow-through bearish close {c0.close:.2f} di bawah close rejection {c1.close:.2f}",
                ],
                metrics={"rejection_wick": round(c1.upper_wick, 2), "rejection_high": round(c1.high, 2)},
            )
        return None
