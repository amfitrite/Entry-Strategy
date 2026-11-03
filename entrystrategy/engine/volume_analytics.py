"""Volume and Order Flow Mathematical Analytics Engine for XAUUSD.

Provides standardized calculations for:
1. Relative Volume (RVOL) and Volume Z-Score Anomaly.
2. Estimated Delta and Cumulative Volume Delta (CVD) via Price-Decomposition Proxy.
3. Rolling Volume Profile (POC, VAH, VAL, HVN, LVN) with Discrete Price Binning.
4. Micro Footprint Price-Level Imbalance & Absorption Detection.

DATA SOURCE INTEGRITY:
- Dukascopy Swiss ECN supplies observed tick volume and bid-side OHLC prices.
- All delta and footprint metrics are explicitly tagged as [ESTIMATED_DELTA_PROXY]
  or [PROXY_PRICE_LEVEL_FOOTPRINT] because true aggressor-flagged trade tape
  is not distributed by OTC spot gold feeds.
"""
import math
from typing import List, Dict, Any, Optional, Tuple
from entrystrategy.core.models import Candle


def calculate_rvol_and_zscore(
    candles: List[Candle],
    lookback: int = 20
) -> Dict[str, float]:
    """Calculates RVOL (Relative Volume) and Volume Z-Score against historical baseline.

    Args:
        candles: List of closed candles (index 0 is newest completed bar).
        lookback: Number of prior bars to compute baseline (excluding index 0).

    Returns:
        Dict with volume, baseline_mean, baseline_std, rvol, z_score.
    """
    if not candles:
        return {"current_vol": 0.0, "baseline_mean": 1.0, "baseline_std": 0.0, "rvol": 1.0, "z_score": 0.0}

    current_vol = float(candles[0].tick_volume or candles[0].real_volume or 1.0)
    baseline_candles = candles[1:1 + lookback]

    if not baseline_candles:
        return {"current_vol": current_vol, "baseline_mean": current_vol, "baseline_std": 0.0, "rvol": 1.0, "z_score": 0.0}

    vols = [float(c.tick_volume or c.real_volume or 1.0) for c in baseline_candles]
    mean_v = sum(vols) / len(vols)
    variance = sum((v - mean_v) ** 2 for v in vols) / len(vols)
    std_v = math.sqrt(variance)

    rvol = current_vol / max(mean_v, 0.001)
    z_score = (current_vol - mean_v) / max(std_v, 0.001) if std_v > 0.0001 else 0.0

    return {
        "current_vol": round(current_vol, 2),
        "baseline_mean": round(mean_v, 2),
        "baseline_std": round(std_v, 2),
        "rvol": round(rvol, 3),
        "z_score": round(z_score, 2),
    }


def estimate_candle_delta(candle: Candle) -> Dict[str, float]:
    """Estimates intra-bar buy/sell volume and net delta from candle geometry.

    Methodology (Lee-Ready / Intra-Bar Price Decomposition Proxy):
    - When price closes near high, buying volume was predominant.
    - When price closes near low, selling volume was predominant.
    - Normalized positioning: pos = (Close - Low) / (High - Low)
    - Buy Volume = Total Volume * pos
    - Sell Volume = Total Volume * (1 - pos)
    - Net Delta = Buy Volume - Sell Volume = Total Volume * (2 * pos - 1)

    TAG: [ESTIMATED_DELTA_PROXY]
    """
    vol = float(candle.tick_volume or candle.real_volume or 1.0)
    rng = max(candle.high - candle.low, 0.01)
    pos = max(0.0, min(1.0, (candle.close - candle.low) / rng))

    buy_vol = vol * pos
    sell_vol = vol * (1.0 - pos)
    delta = buy_vol - sell_vol
    delta_ratio = delta / max(vol, 0.001)

    return {
        "total_vol": round(vol, 2),
        "est_buy_vol": round(buy_vol, 2),
        "est_sell_vol": round(sell_vol, 2),
        "est_delta": round(delta, 2),
        "delta_ratio": round(delta_ratio, 3),
    }


def calculate_cvd_series(candles: List[Candle], count: int = 20) -> List[float]:
    """Calculates Cumulative Volume Delta (CVD) series for recent candles.

    Args:
        candles: Candles with index 0 being newest completed bar.
        count: Number of bars to include in CVD accumulation.

    Returns:
        List of CVD values in chronological order (oldest to newest).
    """
    n = min(len(candles), count)
    if n == 0:
        return []

    # Reverse to chronological order (oldest to newest)
    ordered = [candles[i] for i in range(n - 1, -1, -1)]
    cvd_series: List[float] = []
    running_cvd = 0.0

    for c in ordered:
        d_info = estimate_candle_delta(c)
        running_cvd += d_info["est_delta"]
        cvd_series.append(round(running_cvd, 2))

    return cvd_series


def calculate_volume_profile(
    candles: List[Candle],
    lookback: int = 24,
    bin_size: float = 0.25,
    value_area_pct: float = 0.70
) -> Dict[str, Any]:
    """Builds a discrete rolling Volume Profile across recent candles.

    Args:
        candles: Candles with index 0 being newest completed bar.
        lookback: Number of recent candles to profile.
        bin_size: Discrete price step in points (XAUUSD default: 0.25 pts).
        value_area_pct: Fraction of volume defining Value Area (default: 70%).

    Returns:
        Dict containing poc_price, vah_price, val_price, hvn_nodes, lvn_nodes,
        total_profile_volume, and bins dict.
    """
    n = min(len(candles), lookback)
    if n == 0:
        return {
            "poc_price": 0.0,
            "vah_price": 0.0,
            "val_price": 0.0,
            "hvn_nodes": [],
            "lvn_nodes": [],
            "total_profile_volume": 0.0,
            "bins": {},
        }

    subset = candles[:n]
    overall_low = min(c.low for c in subset)
    overall_high = max(c.high for c in subset)

    if overall_high <= overall_low:
        overall_high = overall_low + bin_size

    # Establish discrete bins
    num_bins = max(1, int(math.ceil((overall_high - overall_low) / bin_size)) + 1)
    bins: Dict[float, float] = {}
    for i in range(num_bins):
        bp = round(overall_low + (i * bin_size), 2)
        bins[bp] = 0.0

    total_vol = 0.0
    for c in subset:
        c_vol = float(c.tick_volume or c.real_volume or 1.0)
        c_rng = max(c.high - c.low, bin_size * 0.5)
        # Allocate candle volume across intersecting price bins
        start_bin_idx = max(0, int(math.floor((c.low - overall_low) / bin_size)))
        end_bin_idx = min(num_bins - 1, int(math.floor((c.high - overall_low) / bin_size)))
        bins_covered = max(1, end_bin_idx - start_bin_idx + 1)
        vol_per_bin = c_vol / bins_covered

        for idx in range(start_bin_idx, end_bin_idx + 1):
            bp = round(overall_low + (idx * bin_size), 2)
            bins[bp] = bins.get(bp, 0.0) + vol_per_bin
            total_vol += vol_per_bin

    # 1. Point of Control (POC)
    sorted_bins = sorted(bins.items(), key=lambda x: x[0])
    poc_price, poc_vol = max(sorted_bins, key=lambda x: x[1])

    # 2. Value Area High (VAH) & Value Area Low (VAL) - 70% distribution around POC
    target_va_vol = total_vol * value_area_pct
    poc_idx = [i for i, (p, _) in enumerate(sorted_bins) if p == poc_price][0]

    va_indices = {poc_idx}
    current_va_vol = poc_vol
    left_idx = poc_idx - 1
    right_idx = poc_idx + 1

    while current_va_vol < target_va_vol and (left_idx >= 0 or right_idx < len(sorted_bins)):
        left_vol = sorted_bins[left_idx][1] if left_idx >= 0 else -1.0
        right_vol = sorted_bins[right_idx][1] if right_idx < len(sorted_bins) else -1.0

        if right_vol >= left_vol and right_idx < len(sorted_bins):
            va_indices.add(right_idx)
            current_va_vol += right_vol
            right_idx += 1
        elif left_idx >= 0:
            va_indices.add(left_idx)
            current_va_vol += left_vol
            left_idx -= 1
        else:
            break

    val_price = sorted_bins[min(va_indices)][0]
    vah_price = sorted_bins[max(va_indices)][0]

    # 3. High Volume Nodes (HVN) & Low Volume Nodes (LVN) detection
    hvn_nodes: List[float] = []
    lvn_nodes: List[float] = []

    mean_bin_vol = total_vol / max(len(sorted_bins), 1)

    for i in range(1, len(sorted_bins) - 1):
        prev_v = sorted_bins[i - 1][1]
        curr_p, curr_v = sorted_bins[i]
        next_v = sorted_bins[i + 1][1]

        # Local Peak & volume above 1.25x average -> HVN
        if curr_v > prev_v and curr_v > next_v and curr_v >= 1.25 * mean_bin_vol:
            hvn_nodes.append(curr_p)
        # Local Valley & volume below 0.65x average -> LVN
        elif curr_v < prev_v and curr_v < next_v and curr_v <= 0.65 * mean_bin_vol:
            lvn_nodes.append(curr_p)

    return {
        "poc_price": round(poc_price, 2),
        "vah_price": round(vah_price, 2),
        "val_price": round(val_price, 2),
        "poc": round(poc_price, 2),
        "vah": round(vah_price, 2),
        "val": round(val_price, 2),
        "hvn_nodes": [round(p, 2) for p in hvn_nodes],
        "lvn_nodes": [round(p, 2) for p in lvn_nodes],
        "total_profile_volume": round(total_vol, 2),
        "total_volume": round(total_vol, 2),
        "bins": {k: round(v, 2) for k, v in bins.items()},
    }


def calculate_footprint_imbalance(
    candle: Candle,
    bin_size: float = 0.25,
    imbalance_ratio: float = 3.0
) -> Dict[str, Any]:
    """Estimates footprint price-level imbalance across candle height.

    Distributes candle volume into price increments (0.25 pts for XAUUSD) and
    evaluates buying vs selling aggression proxy.

    TAG: [PROXY_PRICE_LEVEL_FOOTPRINT]
    """
    vol = float(candle.tick_volume or candle.real_volume or 1.0)
    rng = max(candle.high - candle.low, bin_size)
    num_bins = max(1, int(math.ceil(rng / bin_size)))

    buy_imbalance_count = 0
    sell_imbalance_count = 0
    stacked_buy_levels: List[float] = []
    stacked_sell_levels: List[float] = []

    current_stacked_buy = 0
    current_stacked_sell = 0
    max_stacked_buy = 0
    max_stacked_sell = 0

    # Distribute volume gradient based on close location
    close_pos = max(0.0, min(1.0, (candle.close - candle.low) / rng))

    for b in range(num_bins):
        lvl_price = round(candle.low + (b * bin_size), 2)
        # Level momentum bias
        lvl_pos = (b + 0.5) / num_bins
        # Weight buy vs sell volume based on price gradient
        buy_weight = close_pos * (0.5 + 0.5 * lvl_pos)
        sell_weight = (1.0 - close_pos) * (1.0 - 0.5 * lvl_pos)
        sum_w = max(buy_weight + sell_weight, 0.001)

        lvl_buy = (buy_weight / sum_w) * (vol / num_bins)
        lvl_sell = (sell_weight / sum_w) * (vol / num_bins)

        # Diagonal imbalance test
        if lvl_buy >= imbalance_ratio * max(lvl_sell, 0.1):
            buy_imbalance_count += 1
            current_stacked_buy += 1
            current_stacked_sell = 0
            if current_stacked_buy >= 3:
                stacked_buy_levels.append(lvl_price)
            if current_stacked_buy > max_stacked_buy:
                max_stacked_buy = current_stacked_buy
        elif lvl_sell >= imbalance_ratio * max(lvl_buy, 0.1):
            sell_imbalance_count += 1
            current_stacked_sell += 1
            current_stacked_buy = 0
            if current_stacked_sell >= 3:
                stacked_sell_levels.append(lvl_price)
            if current_stacked_sell > max_stacked_sell:
                max_stacked_sell = current_stacked_sell
        else:
            current_stacked_buy = 0
            current_stacked_sell = 0

    return {
        "total_levels": num_bins,
        "imbalance_ratio_threshold": imbalance_ratio,
        "buy_imbalance_count": buy_imbalance_count,
        "sell_imbalance_count": sell_imbalance_count,
        "max_stacked_buy": max_stacked_buy,
        "max_stacked_sell": max_stacked_sell,
        "has_stacked_buy": max_stacked_buy >= 3,
        "has_stacked_sell": max_stacked_sell >= 3,
        "stacked_buy_levels": stacked_buy_levels,
        "stacked_sell_levels": stacked_sell_levels,
        "stacked_buy_imbalances": stacked_buy_levels,
        "stacked_sell_imbalances": stacked_sell_levels,
    }
