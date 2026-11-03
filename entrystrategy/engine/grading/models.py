"""Data models and value types for Strategy Tier Grading Engine."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple


class GradeTier(str, Enum):
    """Grading Tiers matching technical quality brackets."""
    SSS = "SSS"  # 95.00 - 100.00
    SS = "SS"    # 90.00 - 94.99
    S = "S"      # 85.00 - 89.99
    A = "A"      # 75.00 - 84.99
    B = "B"      # 65.00 - 74.99
    C = "C"      # 50.00 - 64.99
    D = "D"      # 0.00  - 49.99

    @classmethod
    def from_score(cls, score: float) -> "GradeTier":
        """Maps a raw total score to its corresponding Tier."""
        clamped = max(0.0, min(100.0, score))
        if clamped >= 95.0:
            return cls.SSS
        elif clamped >= 90.0:
            return cls.SS
        elif clamped >= 85.0:
            return cls.S
        elif clamped >= 75.0:
            return cls.A
        elif clamped >= 65.0:
            return cls.B
        elif clamped >= 50.0:
            return cls.C
        else:
            return cls.D


class DataStatus(str, Enum):
    """Classification of data source transparency and availability."""
    OBSERVED = "OBSERVED"        # Dihitung langsung dari data candle/tick nyata
    ESTIMATED = "ESTIMATED"      # Dihitung melalui proxy / dekomposisi intra-bar
    UNAVAILABLE = "UNAVAILABLE"  # Data tidak tersedia (misal MTF context tanpa bar closed)
    INSUFFICIENT = "INSUFFICIENT" # Data tersedia tapi sampel di bawah ambang minimal


class DataSufficiencyStatus(str, Enum):
    """Overall data sufficiency status for the grading assessment."""
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class GradingComponent(str, Enum):
    """The five foundational components evaluated for every entry signal."""
    PATTERN_QUALITY = "pattern_quality"
    MARKET_STRUCTURE = "market_structure"
    LOCATION_QUALITY = "location_quality"
    CANDLE_CONFIRMATION = "candle_confirmation"
    EXECUTION_QUALITY = "execution_quality"


@dataclass
class GradingWeights:
    """Configurable weights for the 5 grading components (default sum = 1.0)."""
    pattern_quality: float = 0.30
    market_structure: float = 0.20
    location_quality: float = 0.20
    candle_confirmation: float = 0.15
    execution_quality: float = 0.15

    def __post_init__(self):
        total = (
            self.pattern_quality
            + self.market_structure
            + self.location_quality
            + self.candle_confirmation
            + self.execution_quality
        )
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"GradingWeights components must sum to 1.0, got {total:.4f}")

    def to_dict(self) -> Dict[str, float]:
        return {
            "pattern_quality": self.pattern_quality,
            "market_structure": self.market_structure,
            "location_quality": self.location_quality,
            "candle_confirmation": self.candle_confirmation,
            "execution_quality": self.execution_quality,
        }


@dataclass
class ComponentBreakdown:
    """Component scores (0.0 to 100.0) produced by the evaluation layer."""
    pattern_quality: float = 0.0
    market_structure: float = 0.0
    location_quality: float = 0.0
    candle_confirmation: float = 0.0
    execution_quality: float = 0.0
    statuses: Dict[str, str] = field(default_factory=dict)
    effective_weights: Dict[str, float] = field(default_factory=dict)
    available_components: int = 5

    def __post_init__(self):
        self.pattern_quality = round(max(0.0, min(100.0, float(self.pattern_quality))), 2)
        self.market_structure = round(max(0.0, min(100.0, float(self.market_structure))), 2)
        self.location_quality = round(max(0.0, min(100.0, float(self.location_quality))), 2)
        self.candle_confirmation = round(max(0.0, min(100.0, float(self.candle_confirmation))), 2)
        self.execution_quality = round(max(0.0, min(100.0, float(self.execution_quality))), 2)

        # Default statuses to OBSERVED if not provided
        if not self.statuses:
            self.statuses = {
                "pattern_quality": DataStatus.OBSERVED.value,
                "market_structure": DataStatus.OBSERVED.value,
                "location_quality": DataStatus.OBSERVED.value,
                "candle_confirmation": DataStatus.OBSERVED.value,
                "execution_quality": DataStatus.OBSERVED.value,
            }

    def calculate_normalized_score(
        self, weights: GradingWeights
    ) -> Tuple[float, float, Dict[str, float], bool]:
        """Calculates normalized total score over available components without artificial bias.

        Returns:
            normalized_score: Weighted average of available components (0-100)
            effective_weight_sum: Sum of weights of available components
            effective_weights: Normalized weight dict for transparency
            is_insufficient: True if critical data is missing or available weight < 0.40
        """
        weights_dict = weights.to_dict()
        scores_dict = self.to_dict()

        available_weights: Dict[str, float] = {}
        effective_sum = 0.0

        for comp, status in self.statuses.items():
            if status not in (DataStatus.UNAVAILABLE.value, DataStatus.INSUFFICIENT.value):
                w = weights_dict.get(comp, 0.0)
                available_weights[comp] = w
                effective_sum += w

        # Insufficient check: less than 40% of component weight available,
        # or Pattern Quality is missing
        is_insufficient = (
            effective_sum < 0.40
            or self.statuses.get("pattern_quality") in (DataStatus.UNAVAILABLE.value, DataStatus.INSUFFICIENT.value)
        )

        if effective_sum <= 0.0:
            return 0.0, 0.0, {k: 0.0 for k in weights_dict}, True

        effective_weights: Dict[str, float] = {}
        weighted_sum = 0.0
        for comp, w in weights_dict.items():
            if comp in available_weights:
                eff_w = round(w / effective_sum, 4)
                effective_weights[comp] = eff_w
                weighted_sum += scores_dict[comp] * eff_w
            else:
                effective_weights[comp] = 0.0

        self.effective_weights = effective_weights
        self.available_components = len(available_weights)

        normalized_score = round(max(0.0, min(100.0, weighted_sum)), 2)
        return normalized_score, effective_sum, effective_weights, is_insufficient

    def calculate_total_score(self, weights: GradingWeights) -> float:
        """Calculates normalized total score (backward-compatible method)."""
        score, _, eff_weights, _ = self.calculate_normalized_score(weights)
        self.effective_weights = eff_weights
        return score

    def to_dict(self) -> Dict[str, float]:
        return {
            "pattern_quality": self.pattern_quality,
            "market_structure": self.market_structure,
            "location_quality": self.location_quality,
            "candle_confirmation": self.candle_confirmation,
            "execution_quality": self.execution_quality,
        }


class EvidenceCluster(str, Enum):
    """Clusters used to prevent double-counting correlated market phenomena."""
    MOMENTUM_DISPLACEMENT = "MOMENTUM_DISPLACEMENT"
    STRUCTURAL_BREAK = "STRUCTURAL_BREAK"
    REJECTION_WICK = "REJECTION_WICK"
    LOCATION_CONFLUENCE = "LOCATION_CONFLUENCE"
    MTF_ALIGNMENT = "MTF_ALIGNMENT"


@dataclass
class EvidenceItem:
    """Individual unit of evidence gathered during grading."""
    cluster: EvidenceCluster
    description: str
    score: float  # 0 to 100
    weight: float = 1.0
    is_contradiction: bool = False
    penalty: float = 0.0


@dataclass
class GradingResult:
    """Final output of the Strategy Tier Grading Engine for an EntrySignal."""
    tier: GradeTier
    score: float
    confidence: float
    timeframe: str
    version: str
    breakdown: ComponentBreakdown
    reasons: List[str] = field(default_factory=list)
    penalties: List[str] = field(default_factory=list)
    capped_reason: Optional[str] = None
    data_sufficiency: str = "SUFFICIENT"
    effective_weights: Dict[str, float] = field(default_factory=dict)
    validation_status: str = "NOT VALIDATED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grade": self.tier.value,
            "grade_score": round(self.score, 2),
            "grade_confidence": round(self.confidence, 2),
            "grade_timeframe": self.timeframe,
            "grade_version": self.version,
            "grade_breakdown": self.breakdown.to_dict(),
            "grade_reasons": self.reasons,
            "grade_penalties": self.penalties,
            "capped_reason": self.capped_reason,
            "data_sufficiency": self.data_sufficiency,
            "effective_weights": self.effective_weights,
            "validation_status": self.validation_status,
        }
