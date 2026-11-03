"""Historical Validation Framework for Strategy Tier Grading.

Provides out-of-sample statistical performance attribution for:
    strategy_id + timeframe + tier
Measuring:
- Signal count
- Win rate (%)
- Average R-multiple (risk-adjusted return)
- Expectancy (E = (WinRate * AvgWinR) - (LossRate * AvgLossR))
- Maximum Adverse Excursion (MAE in points/ATR)
- Maximum Favorable Excursion (MFE in points/ATR)
- Tier distribution

All unvalidated tiers carry the explicit label: NOT VALIDATED.
"""
from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class TierPerformanceMetrics:
    strategy_id: int
    timeframe: str
    tier: str
    signal_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    avg_r: float = 0.0
    expectancy: float = 0.0
    max_adverse_excursion: float = 0.0
    max_favorable_excursion: float = 0.0
    validation_status: str = "NOT VALIDATED"
    is_out_of_sample: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "timeframe": self.timeframe,
            "tier": self.tier,
            "signal_count": self.signal_count,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate": round(self.win_rate, 2),
            "avg_r": round(self.avg_r, 2),
            "expectancy": round(self.expectancy, 2),
            "max_adverse_excursion": round(self.max_adverse_excursion, 2),
            "max_favorable_excursion": round(self.max_favorable_excursion, 2),
            "validation_status": self.validation_status,
            "is_out_of_sample": self.is_out_of_sample,
        }


class HistoricalTierValidator:
    """Evaluates historical performance metrics per strategy + timeframe + tier."""

    def __init__(self, is_out_of_sample: bool = True):
        self.is_out_of_sample = is_out_of_sample

    def evaluate_signals(
        self,
        strategy_id: int,
        timeframe: str,
        tier: str,
        signals_with_outcomes: List[Dict[str, Any]],
    ) -> TierPerformanceMetrics:
        """Calculates performance metrics for a specific strategy + timeframe + tier bucket.

        Args:
            strategy_id: Strategy ID (1 - 56)
            timeframe: M1, M5, or M15
            tier: SSS, SS, S, A, B, C, D
            signals_with_outcomes: List of dicts with keys:
                - 'r_multiple': float (e.g. +2.0, -1.0)
                - 'is_win': bool
                - 'mae': float (max adverse price movement)
                - 'mfe': float (max favorable price movement)
        """
        n = len(signals_with_outcomes)
        if n == 0:
            return TierPerformanceMetrics(
                strategy_id=strategy_id,
                timeframe=timeframe,
                tier=tier,
                validation_status="NOT VALIDATED",
                is_out_of_sample=self.is_out_of_sample,
            )

        wins = sum(1 for s in signals_with_outcomes if s.get("is_win", False))
        losses = n - wins
        win_rate = (wins / n) * 100.0

        r_values = [s.get("r_multiple", 0.0) for s in signals_with_outcomes]
        avg_r = sum(r_values) / n if n > 0 else 0.0

        win_r = [r for r in r_values if r > 0]
        loss_r = [abs(r) for r in r_values if r <= 0]
        avg_win = (sum(win_r) / len(win_r)) if win_r else 0.0
        avg_loss = (sum(loss_r) / len(loss_r)) if loss_r else 1.0

        # Expectancy formula: (WinRate * AvgWin) - (LossRate * AvgLoss)
        p_win = wins / n
        p_loss = losses / n
        expectancy = (p_win * avg_win) - (p_loss * avg_loss)

        maes = [s.get("mae", 0.0) for s in signals_with_outcomes]
        mfes = [s.get("mfe", 0.0) for s in signals_with_outcomes]
        avg_mae = sum(maes) / n if n > 0 else 0.0
        avg_mfe = sum(mfes) / n if n > 0 else 0.0

        status = "VALIDATED" if (n >= 30 and self.is_out_of_sample) else "NOT VALIDATED (INSUFFICIENT_SAMPLE)"

        return TierPerformanceMetrics(
            strategy_id=strategy_id,
            timeframe=timeframe,
            tier=tier,
            signal_count=n,
            win_count=wins,
            loss_count=losses,
            win_rate=round(win_rate, 2),
            avg_r=round(avg_r, 2),
            expectancy=round(expectancy, 2),
            max_adverse_excursion=round(avg_mae, 2),
            max_favorable_excursion=round(avg_mfe, 2),
            validation_status=status,
            is_out_of_sample=self.is_out_of_sample,
        )
