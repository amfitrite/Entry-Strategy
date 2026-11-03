"""Registry managing all 40 Strategy Families."""
from typing import Dict, List, Optional
from entrystrategy.engine.base import BasePattern
from entrystrategy.core.models import EntrySignal
from entrystrategy.core.buffer import MarketBuffer
import entrystrategy.engine.patterns as p


class PatternRegistry:
    def __init__(self):
        self._patterns: Dict[int, BasePattern] = {}
        self._register_all_40_families()

    def _register_all_40_families(self):
        instances = [
            # 1 - 10
            p.CandlestickReversalPattern(),
            p.CandlestickContinuationPattern(),
            p.MultiCandleReversalPattern(),
            p.InsideBarBreakoutPattern(),
            p.OutsideBarBreakoutPattern(),
            p.MomentumPattern(),
            p.BreakoutPattern(),
            p.FailedBreakoutPattern(),
            p.MicroPullbackPattern(),
            p.MicroTrendReversalPattern(),
            # 11 - 20
            p.TickMomentumPattern(),
            p.TickReversalPattern(),
            p.TickImbalancePattern(),
            p.TickBurstPattern(),
            p.TickExhaustionPattern(),
            p.PriceVelocityPattern(),
            p.PriceAccelerationPattern(),
            p.MicroRangeExpansionPattern(),
            p.MicroRangeCompressionPattern(),
            p.VolatilityBurstPattern(),
            # 21 - 30
            p.VolatilityContractionPattern(),
            p.ConsecutivePriceMovementPattern(),
            p.AlternatingTickPattern(),
            p.RejectionPattern(),
            p.WickPattern(),
            p.BodyExpansionPattern(),
            p.BodyContractionPattern(),
            p.GapPattern(),
            p.FailedMomentumPattern(),
            p.MomentumExhaustionPattern(),
            # 31 - 40
            p.MicroDoubleTopPattern(),
            p.MicroDoubleBottomPattern(),
            p.MicroSwingBreakPattern(),
            p.MicroSwingFailurePattern(),
            p.ThreePushPattern(),
            p.VReversalPattern(),
            p.InvertedVReversalPattern(),
            p.StaircasePattern(),
            p.CandleSequencePattern(),
            p.HybridTickCandlePattern(),
        ]
        for inst in instances:
            self._patterns[inst.pattern_id] = inst

    def get_pattern(self, pattern_id: int) -> Optional[BasePattern]:
        return self._patterns.get(pattern_id)

    def get_all_patterns(self) -> List[BasePattern]:
        return [self._patterns[pid] for pid in sorted(self._patterns.keys())]

    def evaluate_all(self, buffer: MarketBuffer, enable_ticks: bool = False) -> List[EntrySignal]:
        """Evaluates all 40 patterns against current market buffer state using M5 candles."""
        fired_signals: List[EntrySignal] = []
        for pid in sorted(self._patterns.keys()):
            pattern = self._patterns[pid]
            signal = pattern.check(buffer)
            if signal:
                # Adapt max_age_sec to timeframe if using candle mode
                if not buffer.enable_ticks:
                    if buffer.active_timeframe == "M5":
                        signal.max_age_sec = 300.0  # 5 minutes for M5 bar
                    elif buffer.active_timeframe == "M1":
                        signal.max_age_sec = 60.0   # 1 minute for M1 bar
                fired_signals.append(signal)
        return fired_signals

    def get_matrix_status(self) -> List[Dict]:
        """Returns snapshot of current status for all 40 patterns for UI rendering."""
        return [self._patterns[pid].get_info() for pid in sorted(self._patterns.keys())]
