"""Swing High/Low detection - dasar untuk BOS, CHoCH, S/R.
Port 1:1 dari packages/engine/src/patterns/swing.ts
"""
from typing import List, TypedDict


class SwingPoint(TypedDict):
    index: int
    price: float
    type: str  # 'high' | 'low'


def find_swing_points(candles: List[dict], lookback: int = 2):
    """Swing high di index i: high[i] adalah tertinggi dibanding `lookback`
    candle di kiri dan kanannya (fractal method)."""
    swing_highs: List[SwingPoint] = []
    swing_lows: List[SwingPoint] = []

    for i in range(lookback, len(candles) - lookback):
        window = candles[i - lookback: i + lookback + 1]
        window_high = [float(c["high"]) for c in window]
        window_low = [float(c["low"]) for c in window]

        current_high = float(candles[i]["high"])
        current_low = float(candles[i]["low"])

        if current_high == max(window_high):
            swing_highs.append({"index": i, "price": current_high, "type": "high"})

        if current_low == min(window_low):
            swing_lows.append({"index": i, "price": current_low, "type": "low"})

    return swing_highs, swing_lows


def get_recent_swings(candles: List[dict], lookback: int = 2, last_n: int = 5):
    """Get recent swing high/low for BOS/CHoCH detection."""
    swing_highs, swing_lows = find_swing_points(candles, lookback)

    recent_highs = [s["price"] for s in swing_highs[-last_n:]]
    recent_lows = [s["price"] for s in swing_lows[-last_n:]]

    return {"highs": recent_highs, "lows": recent_lows}
