"""IRGA overlay: pure scoring/classification logic for the optional signal
sourced from the `bygatc` BTC forecasting project. No I/O here -- fetching
the live snapshot lives in `irga_client.py`, reading a historical series
for backtesting lives in `irga_history.py`.

IMPORTANT CONTEXT (from bygatc's own docs -- model/serve/predict.py and
docs/TRADE_FLOW.md #3 and #8):

  p_up            Probability of BTC finishing higher over IRGA's H=19h
                   forecast window. Walk-forward validated log-loss is
                   0.6941, against 0.6931 for a coin flip -- i.e. NO proven
                   directional skill at this horizon. bygatc's own dashboard
                   deliberately pins this field to a neutral 50/50 everywhere
                   it feeds a trade decision (`to_legacy()` in that repo),
                   specifically so it never drives one on its own.
  p_vol_amplify   Probability that realized volatility over the window
                   exceeds trailing realized vol. This one IS validated
                   (2.79% QLIKE improvement vs a Log-HAR baseline, p=0.043)
                   and is what bygatc's own futures-desk logic
                   (`buildFuturesPlan`) uses -- for risk sizing, never
                   direction.

Per explicit request, this bot uses BOTH: p_up contributes a small, capped
number of points to the total score (so a strong pattern signal can still
win on its own when IRGA disagrees or is unavailable, and IRGA alone --
with everything else at zero -- can never reach the watchlist floor).
p_vol_amplify only ever removes points / reduces size, never adds conviction.
A signal that leans heavily on the IRGA-direction bonus to clear the
threshold is weaker evidence than one built mostly from patterns/volume/
trend/S-R, since that bonus is grounded in a component with no demonstrated
edge -- keep that in mind when reading `irgaPUp` on a notification.
"""
from typing import TypedDict

VOL_TIER_ELEVATED = 0.55
VOL_TIER_HIGH = 0.70

# Max points p_up can add to score_candle()'s total (out of 100). Additive
# only, and the final total is clamped to 100 -- see scoring.py.
DIRECTION_MAX_POINTS = 15.0
# |p_up - 0.5| at or above this is treated as "full-strength" tilt.
DIRECTION_SATURATION = 0.15

# Points subtracted from the total when the vol regime is "high". A soft
# filter, not a hard block -- mirrors bygatc's own "reduce size / avoid new
# entries if possible" framing for that tier rather than an absolute veto.
HIGH_VOL_SCORE_PENALTY = 10.0


class IrgaSnapshot(TypedDict):
    p_up: float
    p_vol_amplify: float
    age_hours: float
    model: str


def classify_vol_tier(p_vol_amplify: float) -> str:
    """calm / elevated / high -- same thresholds bygatc uses for its own
    Discord volatility-regime alerts (lib/futuresSignal.ts)."""
    if p_vol_amplify >= VOL_TIER_HIGH:
        return "high"
    if p_vol_amplify >= VOL_TIER_ELEVATED:
        return "elevated"
    return "calm"


def direction_score(p_up: float, signal_type: str) -> float:
    """0..DIRECTION_MAX_POINTS. Zero (never negative) when IRGA disagrees
    with the pattern-based direction or reads as neutral -- disagreement
    withholds bonus points rather than penalizing the pattern signal, since
    p_up alone has no proven edge either way."""
    tilt = p_up - 0.5
    aligned = (signal_type == "LONG" and tilt > 0) or (signal_type == "SHORT" and tilt < 0)
    if not aligned:
        return 0.0
    strength = min(abs(tilt) / DIRECTION_SATURATION, 1.0)
    return round(DIRECTION_MAX_POINTS * strength, 2)


def vol_score_penalty(p_vol_amplify: float) -> float:
    """0 or HIGH_VOL_SCORE_PENALTY, subtracted from the total when the
    vol-expansion regime is 'high'."""
    return HIGH_VOL_SCORE_PENALTY if classify_vol_tier(p_vol_amplify) == "high" else 0.0


def vol_size_multiplier(p_vol_amplify: float) -> float:
    """Position-size multiplier, 1.0 = full size. Same heuristic bygatc's
    own buildFuturesPlan() uses (1 - p_vol_amplify * 0.6), floored at 0.3 so
    this factor alone never zeroes size out. Informational only -- this bot
    doesn't place orders, so it's surfaced on the signal/notification for
    the trader to apply manually."""
    return round(max(0.3, 1.0 - p_vol_amplify * 0.6), 2)
