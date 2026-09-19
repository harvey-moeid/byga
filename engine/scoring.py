"""Pure signal-scoring logic. Port 1:1 dari packages/engine/src/scoring.ts.

Tidak melakukan I/O apa pun (tidak fetch, tidak baca state) supaya bisa
dipakai identik oleh run_bot.py (live) maupun backtest.py.
"""
from typing import List, Optional, TypedDict

from .patterns import (
    detect_engulfing,
    detect_pin_bar,
    detect_inside_bar,
    detect_bos,
    detect_choch,
)
from .volume import analyze_volume
from .sr import calculate_sr_zones, get_proximity_score
from .irga import (
    IrgaSnapshot,
    classify_vol_tier,
    direction_score,
    vol_score_penalty,
    vol_size_multiplier,
)


class ScoredCandidate(TypedDict):
    type: str
    patterns: List[str]
    score: int
    rvol: float
    takerBuyRatio: float
    entryZoneStart: float
    entryZoneEnd: float
    stopLoss: float
    tp1: float
    tp2: float
    # IRGA overlay (see engine/irga.py). None/1.0 when no snapshot was
    # supplied -- these are always present so callers don't need to branch.
    irgaPUp: Optional[float]
    irgaVolTier: Optional[str]
    sizeMultiplier: float


def calculate_atr(candles: List[dict], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0

    true_ranges = []
    for i in range(1, len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        prev_close = float(candles[i - 1]["close"])

        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    recent_tr = true_ranges[-period:]
    return sum(recent_tr) / period


def score_candle(
    candles: List[dict],
    current_index: int,
    timeframe: str,
    m15_trend: str,
    irga: Optional[IrgaSnapshot] = None,
) -> Optional[ScoredCandidate]:
    """Score the candle at `current_index` within `candles` (fixed-size
    trailing window, 100 candles in produksi). `m15_trend` disuplai oleh
    caller (bukan di-fetch di sini) -- live bot mengambilnya dari candle
    15m yang baru difetch, backtest dari series historis M15 yang di-join
    berdasarkan timestamp.

    `irga`: snapshot opsional dari engine/irga.py's IrgaSnapshot
    (live: irga_client.get_irga_snapshot(); backtest:
    irga_history.snapshot_at_or_before()). Sepenuhnya opsional -- None
    berarti scoring persis sama seperti sebelum overlay ini ada.

    Return None jika total score di bawah watchlist floor (50).
    """
    current_candle = candles[current_index]

    # 1. Pattern Detection (max 35 points)
    patterns: List[str] = []
    pattern_score = 0.0

    engulfing = detect_engulfing(candles, current_index)
    if engulfing["detected"]:
        patterns.append(engulfing["type"])
        pattern_score += engulfing["confidence"] * 0.35

    pinbar = detect_pin_bar(candles, current_index)
    if pinbar["detected"]:
        patterns.append(pinbar["type"])
        pattern_score += pinbar["confidence"] * 0.35

    inside_bar = detect_inside_bar(candles, current_index)
    if inside_bar["detected"]:
        patterns.append(inside_bar["type"])
        pattern_score += inside_bar["confidence"] * 0.2

    bos = detect_bos(candles, current_index)
    if bos["detected"]:
        patterns.append(bos["type"])
        pattern_score += bos["confidence"] * 0.3

    choch = detect_choch(candles, current_index)
    if choch["detected"]:
        patterns.append(choch["type"])
        pattern_score += choch["confidence"] * 0.25

    pattern_score = min(35.0, pattern_score)

    # Tentukan arah sinyal berdasarkan pattern yang terdeteksi.
    bullish_patterns = sum(1 for p in patterns if "bullish" in p)
    bearish_patterns = sum(1 for p in patterns if "bearish" in p)
    signal_type = "LONG" if bullish_patterns > bearish_patterns else "SHORT"

    # 2. Volume Analysis (max 30 points)
    volume_analysis = analyze_volume(candles, current_index)
    volume_score = min(30.0, volume_analysis["confidence"] * 0.3)

    # 3. M15 Trend Alignment (max 20 points)
    # Sinyal 5m dicek terhadap trend M15 (full credit jika align, 0 jika
    # berlawanan, partial jika M15 belum punya struktur jelas). Sinyal 15m
    # tidak punya higher timeframe untuk konfirmasi -- strukturnya sendiri
    # sudah jadi konfirmasi -- full credit.
    if timeframe == "15m":
        trend_alignment_score = 20
    elif m15_trend == "neutral":
        trend_alignment_score = 10
    elif (signal_type == "LONG" and m15_trend == "up") or (signal_type == "SHORT" and m15_trend == "down"):
        trend_alignment_score = 20
    else:
        trend_alignment_score = 0

    # 4. S/R Proximity (max 15 points)
    sr_zones = calculate_sr_zones(candles)
    current_price = float(current_candle["close"])
    proximity_score = get_proximity_score(current_price, sr_zones)

    base_score = pattern_score + volume_score + trend_alignment_score + proximity_score

    # 5. IRGA overlay (optional -- see engine/irga.py for why p_up only
    # ever adds a small, capped bonus and p_vol_amplify only ever subtracts).
    irga_fields: dict = {"irgaPUp": None, "irgaVolTier": None, "sizeMultiplier": 1.0}
    irga_delta = 0.0
    if irga is not None:
        irga_delta = direction_score(irga["p_up"], signal_type) - vol_score_penalty(
            irga["p_vol_amplify"]
        )
        irga_fields = {
            "irgaPUp": round(irga["p_up"], 4),
            "irgaVolTier": classify_vol_tier(irga["p_vol_amplify"]),
            "sizeMultiplier": vol_size_multiplier(irga["p_vol_amplify"]),
        }

    # Clamped to [0, 100] so IRGA can nudge a borderline candidate across
    # the watchlist/active thresholds but can never inflate the score past
    # what the "/100" label everywhere (Discord embeds, backtest reports)
    # implies, and pattern/volume/trend/S-R still dominate the outcome.
    total_score = max(0, min(100, round(base_score + irga_delta)))
    if total_score < 50:
        return None

    atr = calculate_atr(candles, 14)
    close_price = float(current_candle["close"])

    return {
        "type": signal_type,
        "patterns": patterns,
        "score": total_score,
        "rvol": volume_analysis["rvol"],
        "takerBuyRatio": volume_analysis["takerBuyRatio"],
        "entryZoneStart": close_price * 0.9995 if signal_type == "LONG" else close_price * 1.0005,
        "entryZoneEnd": close_price * 1.0005 if signal_type == "LONG" else close_price * 0.9995,
        "stopLoss": close_price - atr * 1.5 if signal_type == "LONG" else close_price + atr * 1.5,
        "tp1": close_price + atr * 2 if signal_type == "LONG" else close_price - atr * 2,
        "tp2": close_price + atr * 4 if signal_type == "LONG" else close_price - atr * 4,
        **irga_fields,
    }
