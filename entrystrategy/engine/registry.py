"""Registry managing 40 candle-based M1/M5 entry strategy families."""
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
            p.ChangeOfCharacterPattern(),
            p.BreakOfStructurePattern(),
            p.CandleDisplacementPattern(),
            p.BreakoutRetestPattern(),
            p.FairValueGapPattern(),
            p.FairValueGapRetestPattern(),
            p.OrderBlockRetestPattern(),
            p.MicroRangeExpansionPattern(),
            p.MicroRangeCompressionPattern(),
            p.VolatilityBurstPattern(),
            # 21 - 30
            p.VolatilityContractionPattern(),
            p.TrendPullbackPattern(),
            p.DonchianBreakoutPattern(),
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
            p.CandleRejectionConfluencePattern(),
        ]
        for inst in instances:
            self._patterns[inst.pattern_id] = inst

    def get_pattern(self, pattern_id: int) -> Optional[BasePattern]:
        return self._patterns.get(pattern_id)

    def get_all_patterns(self) -> List[BasePattern]:
        return [self._patterns[pid] for pid in sorted(self._patterns.keys())]

    def evaluate_all(self, buffer: MarketBuffer, enable_ticks: bool = False) -> List[EntrySignal]:
        """Evaluates all 40 candle-based patterns against the active M1/M5 timeframe."""
        fired_signals: List[EntrySignal] = []
        now_ms = buffer.current_time_ms
        for pid in sorted(self._patterns.keys()):
            pattern = self._patterns[pid]
            signal = pattern.check(buffer)
            if signal:
                # 1. P0 Fix: Ensure timestamp_ms represents detection time, preventing instant expiry
                if signal.timestamp_ms < (now_ms - 10_000):
                    signal.timestamp_ms = now_ms

                # Adapt max_age_sec to timeframe if using candle mode
                if not buffer.enable_ticks:
                    if buffer.active_timeframe == "M15":
                        signal.max_age_sec = 900.0  # 15 minutes for M15 bar
                    elif buffer.active_timeframe == "M5":
                        signal.max_age_sec = 300.0  # 5 minutes for M5 bar
                    elif buffer.active_timeframe == "M1":
                        signal.max_age_sec = 60.0   # 1 minute for M1 bar

                # 2. P0 Fix: Ensure execution_price accounts for Bid/Ask spread
                signal.execution_price = buffer.get_execution_price(signal.direction, signal.trigger_price)

                fired_signals.append(signal)
        return fired_signals

    def get_matrix_status(self) -> List[Dict]:
        """Returns snapshot of current status for all 40 patterns for UI rendering."""
        return [self._patterns[pid].get_info() for pid in sorted(self._patterns.keys())]
