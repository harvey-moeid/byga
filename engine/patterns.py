"""Pattern detection: Engulfing, Pin Bar, Inside Bar, BOS, CHoCH.
Port 1:1 dari packages/engine/src/patterns/index.ts
"""
from typing import List, Optional, TypedDict
from .swing import get_recent_swings


class PatternResult(TypedDict):
    detected: bool
    type: str
    confidence: float


def _none(pattern_type: str) -> PatternResult:
    return {"detected": False, "type": pattern_type, "confidence": 0}


def detect_engulfing(candles: List[dict], current_index: int) -> PatternResult:
    """Bullish/Bearish Engulfing: body candle[i] > body candle[i-1], warna
    berlawanan, body ratio > 1.5x."""
    if current_index < 1 or current_index >= len(candles):
        return _none("engulfing")

    current = candles[current_index]
    previous = candles[current_index - 1]

    current_open = float(current["open"])
    current_close = float(current["close"])
    previous_open = float(previous["open"])
    previous_close = float(previous["close"])

    current_body = abs(current_close - current_open)
    previous_body = abs(previous_close - previous_open)

    is_bullish = current_close > current_open
    is_previous_bearish = previous_close < previous_open
    is_bullish_engulfing = (
        is_bullish and is_previous_bearish
        and current_open <= previous_close and current_close >= previous_open
        and current_body > previous_body * 1.5
    )

    is_bearish = current_close < current_open
    is_previous_bullish = previous_close > previous_open
    is_bearish_engulfing = (
        is_bearish and is_previous_bullish
        and current_open >= previous_close and current_close <= previous_open
        and current_body > previous_body * 1.5
    )

    if is_bullish_engulfing or is_bearish_engulfing:
        return {
            "detected": True,
            "type": "bullish_engulfing" if is_bullish_engulfing else "bearish_engulfing",
            "confidence": min(100.0, (current_body / previous_body) * 50) if previous_body else 0,
        }

    return _none("engulfing")


def detect_pin_bar(candles: List[dict], current_index: int) -> PatternResult:
    """Pin Bar / Rejection Wick: wick > 2x body, wick dominan satu arah,
    close di 70% range."""
    if current_index < 0 or current_index >= len(candles):
        return _none("pinbar")

    candle = candles[current_index]
    open_ = float(candle["open"])
    high = float(candle["high"])
    low = float(candle["low"])
    close = float(candle["close"])

    body = abs(close - open_)
    range_ = high - low
    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low

    if range_ == 0:
        return _none("pinbar")

    is_bullish_pin = lower_wick > body * 2 and close > open_ and close > low + range_ * 0.7
    is_bearish_pin = upper_wick > body * 2 and close < open_ and close < high - range_ * 0.7

    if is_bullish_pin or is_bearish_pin:
        dominant_wick = max(upper_wick, lower_wick)
        return {
            "detected": True,
            "type": "bullish_pinbar" if is_bullish_pin else "bearish_pinbar",
            "confidence": min(100.0, (dominant_wick / body) * 30) if body else 0,
        }

    return _none("pinbar")


def detect_inside_bar(candles: List[dict], current_index: int) -> PatternResult:
    """Inside Bar (konsolidasi): High[i] < High[i-1] && Low[i] > Low[i-1]."""
    if current_index < 1 or current_index >= len(candles):
        return _none("insidebar")

    current = candles[current_index]
    previous = candles[current_index - 1]

    current_high = float(current["high"])
    current_low = float(current["low"])
    previous_high = float(previous["high"])
    previous_low = float(previous["low"])

    is_inside = current_high < previous_high and current_low > previous_low

    if is_inside:
        prev_range = previous_high - previous_low
        inside_ratio = (current_high - current_low) / prev_range if prev_range else 0
        return {
            "detected": True,
            "type": "inside_bar",
            "confidence": min(100.0, (1 - inside_ratio) * 100),
        }

    return _none("insidebar")


def detect_bos(candles: List[dict], current_index: int) -> PatternResult:
    """Break of Structure: Close menembus swing high/low 5 candle terakhir
    dengan momentum."""
    if current_index < 6 or current_index >= len(candles):
        return _none("bos")

    recent_candles = candles[: current_index + 1]
    swings = get_recent_swings(recent_candles, 2, 5)
    highs, lows = swings["highs"], swings["lows"]

    if not highs or not lows:
        return _none("bos")

    current_close = float(candles[current_index]["close"])
    max_swing_high = max(highs)
    min_swing_low = min(lows)

    bullish_bos = current_close > max_swing_high
    bearish_bos = current_close < min_swing_low

    if bullish_bos or bearish_bos:
        breakthrough = (
            (current_close - max_swing_high) / max_swing_high * 100
            if bullish_bos
            else (min_swing_low - current_close) / min_swing_low * 100
        )

        return {
            "detected": True,
            "type": "bullish_bos" if bullish_bos else "bearish_bos",
            "confidence": min(100.0, breakthrough * 1000),
        }

    return _none("bos")


def detect_choch(candles: List[dict], current_index: int) -> PatternResult:
    """Change of Character (Reversal Alert): setelah downtrend, candle
    bullish close di atas previous swing high (dan sebaliknya)."""
    if current_index < 10 or current_index >= len(candles):
        return _none("choch")

    prev_candles = candles[current_index - 10: current_index - 5]
    prev_lows = [float(c["low"]) for c in prev_candles]
    prev_highs = [float(c["high"]) for c in prev_candles]

    is_downtrend = prev_lows[-1] < prev_lows[0]
    is_uptrend = prev_highs[-1] > prev_highs[0]

    current_close = float(candles[current_index]["close"])
    swings = get_recent_swings(candles[: current_index + 1], 2, 3)
    highs, lows = swings["highs"], swings["lows"]

    if is_downtrend and highs:
        last_swing_high = highs[-1]
        if current_close > last_swing_high:
            return {"detected": True, "type": "bullish_choch", "confidence": 70}

    if is_uptrend and lows:
        last_swing_low = lows[-1]
        if current_close < last_swing_low:
            return {"detected": True, "type": "bearish_choch", "confidence": 70}

    return _none("choch")


# Re-export supaya `from engine.patterns import determine_trend` tetap jalan
# (mengikuti `export { determineTrend } from './trend'` di index.ts asli)
from .trend import determine_trend  # noqa: E402,F401
