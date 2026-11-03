"""Thresholds, minimum tier gating rules, and timeframe calibration for XAUUSD."""
from typing import Dict, Any, List, Optional
from entrystrategy.core.models import Candle


# Tier Score Boundaries
TIER_THRESHOLDS = {
    "SSS": 95.0,
    "SS": 90.0,
    "S": 85.0,
    "A": 75.0,
    "B": 65.0,
    "C": 50.0,
    "D": 0.0,
}

# Strict Tier Gating Rules (Prerequisites that prevent tier inflation)
TIER_GATING = {
    "SSS": {
        "min_score": 95.0,
        "min_pattern_quality": 90.0,
        "min_market_structure": 90.0,
        "min_candle_confirmation": 85.0,
        "min_execution_quality": 80.0,
        "min_confidence": 0.85,
        "allow_critical_contradiction": False,
    },
    "SS": {
        "min_score": 90.0,
        "min_component_floor": 65.0,
        "min_confidence": 0.70,
        "allow_critical_contradiction": False,
    },
    "S": {
        "min_score": 85.0,
        "min_component_floor": 50.0,
        "min_confidence": 0.60,
        "allow_critical_contradiction": False,
    },
}

# Timeframe Calibration Parameters for XAUUSD (Gold)
TIMEFRAME_PROFILES: Dict[str, Dict[str, Any]] = {
    "M1": {
        "default_atr": 1.2,
        "min_displacement_ratio": 1.4,
        "max_acceptable_spread": 0.35,
        "retest_depth_shallow": 0.382,
        "retest_depth_deep": 0.618,
        "min_required_closed_bars": 10,
    },
    "M5": {
        "default_atr": 2.5,
        "min_displacement_ratio": 1.3,
        "max_acceptable_spread": 0.45,
        "retest_depth_shallow": 0.382,
        "retest_depth_deep": 0.618,
        "min_required_closed_bars": 10,
    },
    "M15": {
        "default_atr": 4.5,
        "min_displacement_ratio": 1.25,
        "max_acceptable_spread": 0.60,
        "retest_depth_shallow": 0.382,
        "retest_depth_deep": 0.618,
        "min_required_closed_bars": 8,
    },
}


def get_timeframe_profile(timeframe: str) -> Dict[str, Any]:
    """Retrieves calibration profile for active timeframe with safe fallback."""
    tf_clean = (timeframe or "M5").upper()
    return TIMEFRAME_PROFILES.get(tf_clean, TIMEFRAME_PROFILES["M5"])


def calculate_atr(candles: List[Candle], period: int = 14) -> float:
    """Calculates True Range average across available closed candles."""
    if not candles:
        return 1.5
    
    n = min(len(candles), period)
    if n <= 1:
        return candles[0].range if candles else 1.5

    tr_sum = 0.0
    for i in range(n):
        c_curr = candles[i]
        if i + 1 < len(candles):
            c_prev = candles[i + 1]
            tr = max(
                c_curr.range,
                abs(c_curr.high - c_prev.close),
                abs(c_curr.low - c_prev.close),
            )
        else:
            tr = c_curr.range
        tr_sum += tr

    return round(tr_sum / n, 2)
