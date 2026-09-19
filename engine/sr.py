"""Support/Resistance zone calculation. Port 1:1 dari
packages/engine/src/patterns/sr.ts
"""
from typing import List, Optional
from .swing import find_swing_points


def _cluster_prices(prices: List[float], tolerance: float) -> List[dict]:
    """Cluster prices yang berdekatan dalam tolerance."""
    if not prices:
        return []

    clusters: List[dict] = []
    sorted_prices = sorted(prices)

    current_cluster = {
        "price": sorted_prices[0],
        "touches": 1,
        "strength": 1.0,
        "zones": [{"high": sorted_prices[0], "low": sorted_prices[0]}],
    }

    for price in sorted_prices[1:]:
        avg_price = current_cluster["price"]
        diff_percent = abs(price - avg_price) / avg_price if avg_price else 0

        if diff_percent <= tolerance:
            current_cluster["touches"] += 1
            current_cluster["zones"].append({"high": price, "low": price})
            current_cluster["price"] = sum(z["high"] for z in current_cluster["zones"]) / len(current_cluster["zones"])
            current_cluster["strength"] = current_cluster["touches"] * (1 / len(current_cluster["zones"]))
        else:
            clusters.append(current_cluster)
            current_cluster = {
                "price": price,
                "touches": 1,
                "strength": 1.0,
                "zones": [{"high": price, "low": price}],
            }

    clusters.append(current_cluster)

    return [c for c in clusters if c["touches"] >= 2]  # Only keep zones with 2+ touches


def calculate_sr_zones(candles: List[dict], tolerance: float = 0.001) -> List[dict]:
    """Cluster swing points menjadi S/R zones (tolerance 0.1% default)."""
    swing_highs, swing_lows = find_swing_points(candles, 2)

    resistance_clusters = _cluster_prices([s["price"] for s in swing_highs], tolerance)
    support_clusters = _cluster_prices([s["price"] for s in swing_lows], tolerance)

    zones = [
        {"price": c["price"], "touches": c["touches"], "strength": c["strength"]}
        for c in resistance_clusters + support_clusters
    ]

    return sorted(zones, key=lambda z: z["strength"], reverse=True)


def is_near_sr_zone(price: float, zones: List[dict], tolerance: float = 0.002) -> Optional[dict]:
    for zone in zones:
        diff_percent = abs(price - zone["price"]) / zone["price"]
        if diff_percent <= tolerance:
            return zone
    return None


def get_proximity_score(price: float, zones: List[dict]) -> int:
    """Score: 15 jika sangat dekat (< 0.1%), turun linear sampai 0 di 1%."""
    if not zones:
        return 0

    min_distance = min(abs(price - z["price"]) / price for z in zones)

    if min_distance < 0.001:
        return 15
    if min_distance > 0.01:
        return 0

    import math
    return math.floor(15 * (1 - min_distance / 0.01))
