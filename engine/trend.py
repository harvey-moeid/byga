"""Market-structure trend classification: higher-highs + higher-lows = up,
lower-highs + lower-lows = down, anything else = neutral.
Port 1:1 dari packages/engine/src/patterns/trend.ts
"""
from typing import List
from .swing import find_swing_points


def determine_trend(candles: List[dict], lookback: int = 2) -> str:
    swing_highs, swing_lows = find_swing_points(candles, lookback)

    # Need at least two of each to compare "higher/lower than the previous
    # one" -- with fewer, there's no structure to classify yet.
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "neutral"

    prev_high, last_high = swing_highs[-2]["price"], swing_highs[-1]["price"]
    prev_low, last_low = swing_lows[-2]["price"], swing_lows[-1]["price"]

    if last_high > prev_high and last_low > prev_low:
        return "up"
    if last_high < prev_high and last_low < prev_low:
        return "down"
    return "neutral"
