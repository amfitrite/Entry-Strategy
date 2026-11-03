"""Candle-only price-action strategies for M1 and M5.

All predicates consume completed OHLC candles only. Tick data is deliberately
excluded from strategy evaluation; the live quote stream may still be used by
the execution-price estimator elsewhere in the application.
"""
from typing import List, Optional, Tuple

from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.core.models import (
    Candle,
    EntrySignal,
    PatternRole,
    SignalDirection,
)
from entrystrategy.engine.base import BasePattern


def _make_signal(
    pattern: BasePattern,
    buffer: MarketBuffer,
    candle: Candle,
    direction: SignalDirection,
    reference: float,
    trigger: float,
    invalidation: float,
    reasons: List[str],
    metrics: Optional[dict] = None,
    role: Optional[PatternRole] = None,
) -> EntrySignal:
    """Create a stable candle-event signal with explicit invalidation."""
    return EntrySignal(
        pattern_id=pattern.pattern_id,
        family_name=pattern.name,
        direction=direction,
        reference_price=round(reference, 2),
        trigger_price=round(trigger, 2),
        invalidation_price=round(invalidation, 2),
        pattern_role=role or pattern.role,
        phenomenon=pattern.phenomenon,
        event_id=f"candle:{pattern.pattern_id}:{candle.timestamp.isoformat()}:{direction.value}",
        timestamp_ms=buffer.current_time_ms,
        reasons=reasons,
        metrics=metrics or {},
    )


def _average_range(candles: List[Candle]) -> float:
    return sum(c.range for c in candles) / len(candles) if candles else 0.0


def _recent_pivots(candles: List[Candle], left: int = 2, right: int = 2):
    """Return confirmed swing highs/lows as (price, candle-index), newest first.

    Candle index 0 is the newest completed candle. A pivot is only eligible
    after both its newer and older neighboring candles have closed.
    """
    swing_highs: List[Tuple[float, int]] = []
    swing_lows: List[Tuple[float, int]] = []
    for i in range(left, len(candles) - right):
        current = candles[i]
        neighbors = candles[i - left:i] + candles[i + 1:i + right + 1]
        if len(neighbors) != left + right:
            continue
        if all(current.high > item.high for item in neighbors):
            swing_highs.append((current.high, i))
        if all(current.low < item.low for item in neighbors):
            swing_lows.append((current.low, i))
    return swing_highs, swing_lows


class ChangeOfCharacterPattern(BasePattern):
    """11: CHoCH — a confirmed break against the immediately prior swing trend."""

    def __init__(self):
        super().__init__(
            pattern_id=11,
            name="CHoCH (Change of Character)",
            category="Structure",
            description="Close candle menembus protected swing berlawanan dengan struktur HH/HL atau LH/LL sebelumnya.",
            role=PatternRole.ENTRY,
            phenomenon="Perubahan karakter struktur setelah tren lokal kehilangan swing yang dilindungi",
            cooldown_ms=5000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(16)
        if len(candles) < 9:
            return None
        highs, lows = _recent_pivots(candles)
        if len(highs) < 2 or len(lows) < 2:
            return None

        c0 = candles[0]
        avg = _average_range(candles[1:8])
        break_buffer = max(0.05, avg * 0.04)
        downtrend = highs[0][0] < highs[1][0] and lows[0][0] < lows[1][0]
        uptrend = highs[0][0] > highs[1][0] and lows[0][0] > lows[1][0]

        if downtrend and c0.is_bullish and c0.body >= avg * 0.30 and c0.close > highs[0][0] + break_buffer:
            return _make_signal(
                self, buffer, c0, SignalDirection.BUY, highs[0][0], c0.close, c0.low,
                [
                    f"Struktur sebelumnya LH/LL; protected lower-high {highs[0][0]:.2f} ditembus oleh close bullish",
                    f"Body candle {c0.body:.2f} memenuhi displacement minimum {avg * 0.30:.2f}",
                ],
                {"broken_swing_high": round(highs[0][0], 2), "prior_trend": "BEARISH", "break_buffer": round(break_buffer, 2)},
            )
        if uptrend and c0.is_bearish and c0.body >= avg * 0.30 and c0.close < lows[0][0] - break_buffer:
            return _make_signal(
                self, buffer, c0, SignalDirection.SELL, lows[0][0], c0.close, c0.high,
                [
                    f"Struktur sebelumnya HH/HL; protected higher-low {lows[0][0]:.2f} ditembus oleh close bearish",
                    f"Body candle {c0.body:.2f} memenuhi displacement minimum {avg * 0.30:.2f}",
                ],
                {"broken_swing_low": round(lows[0][0], 2), "prior_trend": "BULLISH", "break_buffer": round(break_buffer, 2)},
            )
        return None


class BreakOfStructurePattern(BasePattern):
    """12: BOS — continuation break in the direction of confirmed swing structure."""

    def __init__(self):
        super().__init__(
            pattern_id=12,
            name="BOS (Break of Structure)",
            category="Structure",
            description="Close candle menembus swing high/low searah tren HH/HL atau LH/LL yang sudah terbentuk.",
            role=PatternRole.ENTRY,
            phenomenon="Kelanjutan struktur tren melalui penutupan candle melewati swing terkonfirmasi",
            cooldown_ms=5000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(16)
        if len(candles) < 9:
            return None
        highs, lows = _recent_pivots(candles)
        if len(highs) < 2 or len(lows) < 2:
            return None
        c0 = candles[0]
        avg = _average_range(candles[1:8])
        threshold = max(0.05, avg * 0.04)
        uptrend = highs[0][0] > highs[1][0] and lows[0][0] > lows[1][0]
        downtrend = highs[0][0] < highs[1][0] and lows[0][0] < lows[1][0]

        if uptrend and c0.is_bullish and c0.close > highs[0][0] + threshold:
            return _make_signal(
                self, buffer, c0, SignalDirection.BUY, highs[0][0], c0.close, lows[0][0],
                [f"Struktur HH/HL berlanjut: close {c0.close:.2f} melewati swing high {highs[0][0]:.2f}"],
                {"swing_high": round(highs[0][0], 2), "swing_low": round(lows[0][0], 2), "structure": "HH_HL"},
            )
        if downtrend and c0.is_bearish and c0.close < lows[0][0] - threshold:
            return _make_signal(
                self, buffer, c0, SignalDirection.SELL, lows[0][0], c0.close, highs[0][0],
                [f"Struktur LH/LL berlanjut: close {c0.close:.2f} melewati swing low {lows[0][0]:.2f}"],
                {"swing_low": round(lows[0][0], 2), "swing_high": round(highs[0][0], 2), "structure": "LH_LL"},
            )
        return None


class CandleDisplacementPattern(BasePattern):
    """13: large directional candle with body/range and local-range breakout."""

    def __init__(self):
        super().__init__(
            pattern_id=13,
            name="Candle Displacement",
            category="Price Action",
            description="Candle impulsif dengan body dominan dan close melewati ekstrem tiga candle sebelumnya.",
            role=PatternRole.ENTRY,
            phenomenon="Displacement OHLC: ekspansi range, body dominan, dan close di luar range lokal",
            cooldown_ms=4000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(7)
        if len(candles) < 5:
            return None
        c0 = candles[0]
        avg = _average_range(candles[1:6])
        if avg <= 0 or c0.range < 1.45 * avg or c0.body < 0.65 * c0.range:
            return None
        prior_high = max(c.high for c in candles[1:4])
        prior_low = min(c.low for c in candles[1:4])
        close_position = (c0.close - c0.low) / c0.range

        if c0.is_bullish and c0.close > prior_high and close_position >= 0.80:
            return _make_signal(
                self, buffer, c0, SignalDirection.BUY, prior_high, c0.close, c0.low,
                [f"Range {c0.range:.2f} > 1.45x rata-rata {avg:.2f}", f"Body {c0.body:.2f} ({c0.body / c0.range:.0%} range) dan close menembus high lokal {prior_high:.2f}"],
                {"range_ratio": round(c0.range / avg, 2), "body_ratio": round(c0.body / c0.range, 2), "broken_high": round(prior_high, 2)},
            )
        if c0.is_bearish and c0.close < prior_low and close_position <= 0.20:
            return _make_signal(
                self, buffer, c0, SignalDirection.SELL, prior_low, c0.close, c0.high,
                [f"Range {c0.range:.2f} > 1.45x rata-rata {avg:.2f}", f"Body {c0.body:.2f} ({c0.body / c0.range:.0%} range) dan close menembus low lokal {prior_low:.2f}"],
                {"range_ratio": round(c0.range / avg, 2), "body_ratio": round(c0.body / c0.range, 2), "broken_low": round(prior_low, 2)},
            )
        return None


class BreakoutRetestPattern(BasePattern):
    """14: closed breakout followed by a candle retest that holds the broken level."""

    def __init__(self):
        super().__init__(
            pattern_id=14,
            name="Breakout Retest",
            category="Price Action",
            description="Candle breakout ditutup di luar range, lalu candle berikutnya retest level dan close kembali searah breakout.",
            role=PatternRole.ENTRY,
            phenomenon="Perubahan resistance menjadi support atau support menjadi resistance yang tervalidasi retest",
            cooldown_ms=5000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(9)
        if len(candles) < 8:
            return None
        retest, breakout = candles[0], candles[1]
        base = candles[2:8]
        level_high = max(c.high for c in base)
        level_low = min(c.low for c in base)
        avg = _average_range(base)
        threshold = max(0.05, avg * 0.04)
        tolerance = max(0.10, avg * 0.18)

        if (
            breakout.is_bullish and breakout.close > level_high + threshold
            and retest.is_bullish and retest.low <= level_high + tolerance
            and retest.close > level_high
        ):
            return _make_signal(
                self, buffer, retest, SignalDirection.BUY, level_high, retest.close, min(retest.low, level_high - tolerance),
                [f"Breakout candle menutup di atas range {level_high:.2f}", f"Retest menyentuh area level (toleransi {tolerance:.2f}) lalu close kembali di atasnya"],
                {"breakout_close": round(breakout.close, 2), "retest_low": round(retest.low, 2), "retest_level": round(level_high, 2)},
            )
        if (
            breakout.is_bearish and breakout.close < level_low - threshold
            and retest.is_bearish and retest.high >= level_low - tolerance
            and retest.close < level_low
        ):
            return _make_signal(
                self, buffer, retest, SignalDirection.SELL, level_low, retest.close, max(retest.high, level_low + tolerance),
                [f"Breakdown candle menutup di bawah range {level_low:.2f}", f"Retest menyentuh area level (toleransi {tolerance:.2f}) lalu close kembali di bawahnya"],
                {"breakout_close": round(breakout.close, 2), "retest_high": round(retest.high, 2), "retest_level": round(level_low, 2)},
            )
        return None


class FairValueGapPattern(BasePattern):
    """15: three-candle fair-value-gap formation with a displacement middle candle."""

    def __init__(self):
        super().__init__(
            pattern_id=15,
            name="Fair Value Gap (FVG)",
            category="Price Action",
            description="Gap tiga candle antara wick candle pertama dan ketiga, dikonfirmasi candle tengah yang impulsif.",
            role=PatternRole.ENTRY,
            phenomenon="Inefisiensi harga tiga candle (bullish atau bearish FVG) terbentuk setelah displacement",
            cooldown_ms=5000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(5)
        if len(candles) < 3:
            return None
        c0, c1, c2 = candles[0], candles[1], candles[2]
        avg = _average_range(candles[1:5]) if len(candles) >= 5 else _average_range(candles)
        min_gap = max(0.05, avg * 0.04)
        displacement = c1.body >= max(0.20, c1.range * 0.55) and c1.range >= avg * 0.90 if avg else False

        bull_gap = c0.low - c2.high
        if displacement and c1.is_bullish and c0.is_bullish and bull_gap >= min_gap:
            midpoint = (c2.high + c0.low) / 2.0
            return _make_signal(
                self, buffer, c0, SignalDirection.BUY, midpoint, c0.close, c2.high,
                [f"Bullish FVG terbentuk: candle pertama high {c2.high:.2f} < candle ketiga low {c0.low:.2f}", f"Gap {bull_gap:.2f} pts dengan displacement candle tengah"],
                {"fvg_low": round(c2.high, 2), "fvg_high": round(c0.low, 2), "fvg_size": round(bull_gap, 2), "displacement_body": round(c1.body, 2)},
            )

        bear_gap = c2.low - c0.high
        if displacement and c1.is_bearish and c0.is_bearish and bear_gap >= min_gap:
            midpoint = (c0.high + c2.low) / 2.0
            return _make_signal(
                self, buffer, c0, SignalDirection.SELL, midpoint, c0.close, c2.low,
                [f"Bearish FVG terbentuk: candle pertama low {c2.low:.2f} > candle ketiga high {c0.high:.2f}", f"Gap {bear_gap:.2f} pts dengan displacement candle tengah"],
                {"fvg_low": round(c0.high, 2), "fvg_high": round(c2.low, 2), "fvg_size": round(bear_gap, 2), "displacement_body": round(c1.body, 2)},
            )
        return None


class FairValueGapRetestPattern(BasePattern):
    """16: retest and rejection of a previously formed three-candle FVG."""

    def __init__(self):
        super().__init__(
            pattern_id=16,
            name="FVG Retest",
            category="Price Action",
            description="Harga kembali menguji zona FVG yang masih valid lalu candle menutup menjauh dari zona.",
            role=PatternRole.ENTRY,
            phenomenon="Mitigasi sebagian zona FVG dan rejection close untuk kelanjutan arah displacement",
            cooldown_ms=5000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(6)
        if len(candles) < 5:
            return None
        retest, post, third, middle, first = candles[:5]
        avg = _average_range(candles[1:6])
        tolerance = max(0.05, avg * 0.04)

        bull_gap_low, bull_gap_high = first.high, third.low
        if (
            middle.is_bullish and third.is_bullish and bull_gap_high - bull_gap_low >= tolerance
            and post.low > bull_gap_low
            and retest.is_bullish
            and retest.low <= bull_gap_high
            and retest.high >= bull_gap_low
            and retest.close > (bull_gap_low + bull_gap_high) / 2.0
        ):
            return _make_signal(
                self, buffer, retest, SignalDirection.BUY, (bull_gap_low + bull_gap_high) / 2.0,
                retest.close, bull_gap_low,
                [f"Retest masuk ke bullish FVG {bull_gap_low:.2f}–{bull_gap_high:.2f}", "Candle rejection bullish menutup di atas midpoint FVG; batas bawah gap belum ditembus candle sebelumnya"],
                {"fvg_low": round(bull_gap_low, 2), "fvg_high": round(bull_gap_high, 2), "retest_low": round(retest.low, 2)},
            )

        bear_gap_low, bear_gap_high = third.high, first.low
        if (
            middle.is_bearish and third.is_bearish and bear_gap_high - bear_gap_low >= tolerance
            and post.high < bear_gap_high
            and retest.is_bearish
            and retest.high >= bear_gap_low
            and retest.low <= bear_gap_high
            and retest.close < (bear_gap_low + bear_gap_high) / 2.0
        ):
            return _make_signal(
                self, buffer, retest, SignalDirection.SELL, (bear_gap_low + bear_gap_high) / 2.0,
                retest.close, bear_gap_high,
                [f"Retest masuk ke bearish FVG {bear_gap_low:.2f}–{bear_gap_high:.2f}", "Candle rejection bearish menutup di bawah midpoint FVG; batas atas gap belum ditembus candle sebelumnya"],
                {"fvg_low": round(bear_gap_low, 2), "fvg_high": round(bear_gap_high, 2), "retest_high": round(retest.high, 2)},
            )
        return None


class OrderBlockRetestPattern(BasePattern):
    """17: last opposing candle before displacement + structural break, then retest."""

    def __init__(self):
        super().__init__(
            pattern_id=17,
            name="Order Block Retest",
            category="Price Action",
            description="Retest candle berlawanan terakhir sebelum displacement yang mematahkan range lokal.",
            role=PatternRole.ENTRY,
            phenomenon="Mitigasi order-block berbasis candle terakhir berlawanan sebelum displacement dan break lokal",
            cooldown_ms=5000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(9)
        if len(candles) < 8:
            return None
        retest, impulse, block = candles[0], candles[1], candles[2]
        context = candles[3:8]
        avg = _average_range(context)
        threshold = max(0.05, avg * 0.05)
        prior_high = max(c.high for c in context)
        prior_low = min(c.low for c in context)

        if (
            block.is_bearish and impulse.is_bullish
            and impulse.body >= max(0.25, avg * 1.20)
            and impulse.close > prior_high + threshold
            and retest.is_bullish and retest.low <= block.open
            and retest.high >= block.low and retest.close > block.open
        ):
            return _make_signal(
                self, buffer, retest, SignalDirection.BUY, block.open, retest.close, block.low,
                [f"Demand order block = candle bearish terakhir ({block.low:.2f}–{block.open:.2f})", f"Displacement bullish menutup di atas high konteks {prior_high:.2f}; retest ditolak naik"],
                {"ob_low": round(block.low, 2), "ob_high": round(block.open, 2), "impulse_body": round(impulse.body, 2), "prior_high": round(prior_high, 2)},
            )
        if (
            block.is_bullish and impulse.is_bearish
            and impulse.body >= max(0.25, avg * 1.20)
            and impulse.close < prior_low - threshold
            and retest.is_bearish and retest.high >= block.open
            and retest.low <= block.high and retest.close < block.open
        ):
            return _make_signal(
                self, buffer, retest, SignalDirection.SELL, block.open, retest.close, block.high,
                [f"Supply order block = candle bullish terakhir ({block.open:.2f}–{block.high:.2f})", f"Displacement bearish menutup di bawah low konteks {prior_low:.2f}; retest ditolak turun"],
                {"ob_low": round(block.open, 2), "ob_high": round(block.high, 2), "impulse_body": round(impulse.body, 2), "prior_low": round(prior_low, 2)},
            )
        return None


class TrendPullbackPattern(BasePattern):
    """22: pullback entry in an established short-term HH/HL or LH/LL sequence."""

    def __init__(self):
        super().__init__(
            pattern_id=22,
            name="Trend Pullback",
            category="Price Action",
            description="Pullback pada struktur tren lokal, diikuti close konfirmasi yang menembus candle koreksi.",
            role=PatternRole.ENTRY,
            phenomenon="Retracement tren dan continuation setelah candle koreksi gagal membalikkan struktur",
            cooldown_ms=4000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(6)
        if len(candles) < 5:
            return None
        trigger, pullback, recent, middle, oldest = candles[:5]
        impulse_low = min(oldest.low, middle.low, recent.low)
        impulse_high = max(oldest.high, middle.high, recent.high)
        impulse_range = impulse_high - impulse_low
        if impulse_range <= 0:
            return None

        bullish_structure = (
            oldest.high < middle.high < recent.high
            and oldest.low < middle.low < recent.low
        )
        bullish_retrace = (impulse_high - pullback.low) / impulse_range
        if (
            bullish_structure and pullback.is_bearish and trigger.is_bullish
            and 0.25 <= bullish_retrace <= 0.75
            and trigger.close > pullback.high
        ):
            return _make_signal(
                self, buffer, trigger, SignalDirection.BUY, pullback.low, trigger.close, pullback.low,
                [f"Struktur HH/HL bertahan pada tiga candle impuls", f"Pullback retrace {bullish_retrace:.0%} dari leg; candle bullish menutup di atas high koreksi"],
                {"retracement_ratio": round(bullish_retrace, 3), "impulse_low": round(impulse_low, 2), "impulse_high": round(impulse_high, 2)},
            )

        bearish_structure = (
            oldest.high > middle.high > recent.high
            and oldest.low > middle.low > recent.low
        )
        bearish_retrace = (pullback.high - impulse_low) / impulse_range
        if (
            bearish_structure and pullback.is_bullish and trigger.is_bearish
            and 0.25 <= bearish_retrace <= 0.75
            and trigger.close < pullback.low
        ):
            return _make_signal(
                self, buffer, trigger, SignalDirection.SELL, pullback.high, trigger.close, pullback.high,
                [f"Struktur LH/LL bertahan pada tiga candle impuls", f"Pullback retrace {bearish_retrace:.0%} dari leg; candle bearish menutup di bawah low koreksi"],
                {"retracement_ratio": round(bearish_retrace, 3), "impulse_low": round(impulse_low, 2), "impulse_high": round(impulse_high, 2)},
            )
        return None


class DonchianBreakoutPattern(BasePattern):
    """23: closed-candle breakout of the previous 10-bar Donchian range."""

    def __init__(self):
        super().__init__(
            pattern_id=23,
            name="Donchian Range Breakout",
            category="Price Action",
            description="Close candle keluar dari high/low tertinggi-terendah 10 candle sebelumnya dengan body konfirmasi.",
            role=PatternRole.ENTRY,
            phenomenon="Breakout penutupan dari batas range multi-candle, bukan sekadar penetrasi intrabar",
            cooldown_ms=5000,
        )

    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        candles = buffer.get_recent_candles(11)
        if len(candles) < 9:
            return None
        c0 = candles[0]
        lookback = candles[1:]
        upper = max(c.high for c in lookback)
        lower = min(c.low for c in lookback)
        avg = _average_range(lookback)
        threshold = max(0.05, avg * 0.05)
        body_ratio = c0.body / c0.range

        if c0.is_bullish and c0.close > upper + threshold and body_ratio >= 0.50:
            return _make_signal(
                self, buffer, c0, SignalDirection.BUY, upper, c0.close, c0.low,
                [f"Close bullish {c0.close:.2f} menembus Donchian high {upper:.2f}", f"Body candle {body_ratio:.0%} dari range menghindari breakout berbasis wick saja"],
                {"donchian_high": round(upper, 2), "body_ratio": round(body_ratio, 3), "lookback_bars": len(lookback)},
            )
        if c0.is_bearish and c0.close < lower - threshold and body_ratio >= 0.50:
            return _make_signal(
                self, buffer, c0, SignalDirection.SELL, lower, c0.close, c0.high,
                [f"Close bearish {c0.close:.2f} menembus Donchian low {lower:.2f}", f"Body candle {body_ratio:.0%} dari range menghindari breakdown berbasis wick saja"],
                {"donchian_low": round(lower, 2), "body_ratio": round(body_ratio, 3), "lookback_bars": len(lookback)},
            )
        return None
