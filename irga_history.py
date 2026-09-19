"""Load a historical series of IRGA snapshots for backtesting.

bygatc doesn't ship point-in-time historical *predictions* -- only the raw
price/realized-vol series used as the model's *input* features
(data/irga_history.parquet in that repo has hour_ts/OHLCV/rv5.../ but no
p_up or p_vol_amplify column; those are only ever computed live by
model/serve/predict.py and pushed to the Worker). To backtest this bot with
IRGA included, generate your own point-in-time series -- e.g. run
predict.py in a loop over historical anchors in the bygatc repo and dump
each forecast's {hour_ts, p_up, p_vol_amplify} -- then pass that file to
backtest.py via --irga-history. Without it, backtest.py runs exactly as
before (IRGA overlay simply isn't applied).

File format: JSON array, order doesn't matter, each element:
  {"hour_ts": 1754640000, "p_up": 0.53, "p_vol_amplify": 0.41}
`hour_ts` is unix seconds and must be a real forecast anchor time -- using a
snapshot to score a candle that closed *before* that anchor would be
look-ahead bias, so snapshot_at_or_before() only ever looks backward.
"""
import bisect
import json
from typing import List, Optional


def load_irga_history(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        rows = json.load(f)
    rows = [r for r in rows if isinstance(r.get("hour_ts"), (int, float))]
    rows.sort(key=lambda r: r["hour_ts"])
    return rows


def snapshot_at_or_before(history: List[dict], ts_ms: int) -> Optional[dict]:
    """Most recent IRGA snapshot published at or before `ts_ms` (a
    candle's close time, in milliseconds) -- never a future one."""
    if not history:
        return None
    ts_seconds = ts_ms / 1000
    keys = [r["hour_ts"] for r in history]
    idx = bisect.bisect_right(keys, ts_seconds) - 1
    if idx < 0:
        return None
    row = history[idx]
    return {
        "p_up": float(row["p_up"]),
        "p_vol_amplify": float(row["p_vol_amplify"]),
        "age_hours": (ts_seconds - row["hour_ts"]) / 3600,
        "model": str(row.get("model", "unknown")),
    }
