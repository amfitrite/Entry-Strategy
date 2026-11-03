"""Candle-only hybrid and price-action entry families for M1/M5."""
from typing import Optional, List
from entrystrategy.engine.base import BasePattern
from entrystrategy.core.models import EntrySignal, SignalDirection, PatternRole, Candle
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
            description="Penutupan candle menembus High atau Low candle sebelumnya.",
            role=PatternRole.ENTRY,
            phenomenon="Penembusan batas High/Low candle sebelumnya oleh harga saat ini",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(2)
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
        # Evaluate only completed OHLC candles for the active timeframe.
        candles = buffer.get_recent_candles(2)
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
        # Evaluate only completed OHLC candles for the active timeframe.
        candles = buffer.get_recent_candles(2)
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
        # Evaluate only completed OHLC candles for the active timeframe.
        candles = buffer.get_recent_candles(4)
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
        # Evaluate only completed OHLC candles for the active timeframe.
        candles = buffer.get_recent_candles(5)
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
            phenomenon="Kompresi range beberapa candle yang diikuti close candle keluar dari batas range",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        # Evaluate only completed OHLC candles for the active timeframe.
        candles = buffer.get_recent_candles(5)
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
    """Pola 20: OHLC Volatility Expansion.
    Candle range expands sharply versus prior bars and closes near its directional extreme.
    """
    def __init__(self):
        super().__init__(
            pattern_id=20,
            name="Volatility Burst",
            category="Hybrid",
            description="Ekspansi range candle disertai body dominan dan close dekat ekstrem arah.",
            role=PatternRole.ENTRY,
            phenomenon="Ekspansi volatilitas terukur melalui OHLC candle dibandingkan range sebelumnya",
            cooldown_ms=3000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(5)
        if len(candles) < 4:
            return None
        c0 = candles[0]
        prior = candles[1:4]
        avg_r = sum(c.range for c in prior) / len(prior)
        if avg_r <= 0 or c0.range < 1.5 * avg_r or c0.body < 0.65 * c0.range:
            return None

        body_ratio = c0.body / c0.range
        close_position = (c0.close - c0.low) / c0.range
        if c0.is_bullish and close_position >= 0.80:
            ref_px = round(c0.open, 2)
            trig_px = round(c0.close, 2)
            inval_px = round(c0.low, 2)
            event_id = f"ohlc_volatility_burst_buy_{int(c0.timestamp.timestamp())}"
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
                        f"Range candle {c0.range:.2f} pts >= 1.5x rata-rata {avg_r:.2f} pts",
                        f"Body dominan {body_ratio:.0%}; close berada di 20% teratas range candle",
                    ],
                    metrics={"range": round(c0.range, 2), "avg_range": round(avg_r, 2), "body_ratio": round(body_ratio, 3), "close_position": round(close_position, 3)},
                )
        if c0.is_bearish and close_position <= 0.20:
            ref_px = round(c0.open, 2)
            trig_px = round(c0.close, 2)
            inval_px = round(c0.high, 2)
            event_id = f"ohlc_volatility_burst_sell_{int(c0.timestamp.timestamp())}"
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
                        f"Range candle {c0.range:.2f} pts >= 1.5x rata-rata {avg_r:.2f} pts",
                        f"Body dominan {body_ratio:.0%}; close berada di 20% terbawah range candle",
                    ],
                    metrics={"range": round(c0.range, 2), "avg_range": round(avg_r, 2), "body_ratio": round(body_ratio, 3), "close_position": round(close_position, 3)},
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
        # Evaluate only completed OHLC candles for the active timeframe.
        candles = buffer.get_recent_candles(2)
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
            ts = buffer.current_time_ms
            
            # Gap up >= 0.40 pts
            if gap >= 0.40:
                ref_px = round(c1.close, 2)
                trig_px = round(c0.open, 2)
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
                trig_px = round(c0.open, 2)
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
        # Evaluate only completed OHLC candles for the active timeframe.
        candles = buffer.get_recent_candles(2)
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
        # Evaluate only completed OHLC candles for the active timeframe.
        candles = buffer.get_recent_candles(3)
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
        # Evaluate only completed OHLC candles for the active timeframe.
        candles = buffer.get_recent_candles(3)
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
        # Evaluate only completed OHLC candles for the active timeframe.
        candles = buffer.get_recent_candles(3)
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
