"""Signal engine: pattern detection, volume analysis, S/R, scoring.

Port 1:1 dari packages/engine (TypeScript/Cloudflare Workers) ke Python
murni tanpa dependency I/O -- dipakai baik oleh run_bot.py (live, via
GitHub Actions) maupun backtest.py.
"""
from .scoring import score_candle, calculate_atr
from .patterns import determine_trend
from .irga import IrgaSnapshot, classify_vol_tier

__all__ = [
    "score_candle",
    "calculate_atr",
    "determine_trend",
    "IrgaSnapshot",
    "classify_vol_tier",
]
