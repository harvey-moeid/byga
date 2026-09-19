"""Volume analysis: RVOL, Volume Spike, CVD Divergence, Taker Buy Ratio.
Port 1:1 dari packages/engine/src/volume/index.ts
"""
from typing import List, Optional, TypedDict


class VolumeAnalysis(TypedDict):
    rvol: float
    volumeSpike: bool
    cvdDivergence: Optional[str]
    takerBuyRatio: float
    confidence: float


def calculate_rvol(candles: List[dict], current_index: int, period: int = 20) -> float:
    """RVOL = volume[i] / avg_volume[20]"""
    if current_index < period or current_index >= len(candles):
        return 1.0

    current_volume = float(candles[current_index]["volume"])
    past_candles = candles[current_index - period: current_index]
    avg_volume = sum(float(c["volume"]) for c in past_candles) / period

    return current_volume / avg_volume if avg_volume > 0 else 1.0


def detect_volume_spike(candles: List[dict], current_index: int, threshold: float = 2.0) -> bool:
    """Volume candle[i] > 2x rata-rata 20 candle terakhir."""
    rvol = calculate_rvol(candles, current_index, 20)
    return rvol > threshold


def analyze_volume(candles: List[dict], current_index: int) -> VolumeAnalysis:
    """Full volume analysis.

    OKX's public candles endpoint (sumber data kita) tidak menyediakan
    taker buy/sell volume split seperti Binance. CVD divergence & taker-ratio
    bonus dimatikan di sini alih-alih diisi data placeholder, yang justru
    akan membiaskan semua sinyal ke satu arah.
    """
    rvol = calculate_rvol(candles, current_index)
    volume_spike = detect_volume_spike(candles, current_index)

    cvd_divergence = None
    taker_buy_ratio = 0.5

    confidence = 0.0
    if rvol > 2.5:
        confidence += 40  # Extreme volume
    elif rvol > 1.5:
        confidence += 25  # Significant volume
    elif rvol > 1.0:
        confidence += 10  # Above average

    if volume_spike:
        confidence += 20

    return {
        "rvol": rvol,
        "volumeSpike": volume_spike,
        "cvdDivergence": cvd_divergence,
        "takerBuyRatio": taker_buy_ratio,
        "confidence": min(100.0, confidence),
    }
