"""Live fetch of the IRGA snapshot published by the `bygatc` BTC dashboard
Worker (GET /api/irga/latest). This is an optional overlay: any failure
(missing config, network error, timeout, malformed/stale payload) returns
None so the bot keeps running on the price-action strategy alone -- see
engine/irga.py for why p_up is treated as a small, capped bonus rather
than a hard requirement.

Config (env vars):
  IRGA_API_URL         Full URL of the Worker's /api/irga/latest
                         endpoint, e.g.
                         https://btc-dashboard-worker-production.<sub>.workers.dev/api/irga/latest
                         If unset, IRGA is skipped entirely -- the bot
                         behaves exactly like it did before this feature.
  IRGA_MAX_AGE_HOURS   A snapshot older than this (from the payload's
                         `ageHrs`, or derived from `anchor_utc` if that's
                         missing) is treated as stale and ignored. Default 3
                         -- bygatc's own GitHub Actions pushes a fresh one
                         every 30 min, so anything older means that pipeline
                         is down and the number can't be trusted.
"""
import os
from datetime import datetime, timezone
from typing import Optional

import requests

def _env(name: str) -> str:
    # An unset GitHub Actions secret resolves to "" rather than leaving the
    # env var absent, so treat blank the same as missing everywhere here.
    return (os.environ.get(name) or "").strip()


IRGA_API_URL = _env("IRGA_API_URL") or None
IRGA_TIMEOUT_SECONDS = 10
try:
    IRGA_MAX_AGE_HOURS = float(_env("IRGA_MAX_AGE_HOURS") or "3")
except ValueError:
    IRGA_MAX_AGE_HOURS = 3.0


def _age_hours(payload: dict) -> Optional[float]:
    age_hrs = payload.get("ageHrs")
    if isinstance(age_hrs, (int, float)):
        return float(age_hrs)

    anchor_utc = payload.get("anchor_utc")
    if not anchor_utc:
        return None
    try:
        anchor_dt = datetime.fromisoformat(str(anchor_utc).replace("Z", "+00:00"))
        if anchor_dt.tzinfo is None:
            anchor_dt = anchor_dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - anchor_dt).total_seconds() / 3600
    except (ValueError, TypeError):
        return None


def get_irga_snapshot() -> Optional[dict]:
    """Fetch + normalize the latest IRGA payload. Never raises -- returns
    None if IRGA_API_URL is unset, the request fails, the payload is
    missing the fields we need, or the snapshot is stale."""
    if not IRGA_API_URL:
        return None

    try:
        resp = requests.get(IRGA_API_URL, timeout=IRGA_TIMEOUT_SECONDS)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        print(f"IRGA fetch failed, continuing without it: {exc}")
        return None

    p_up = payload.get("p_up")
    p_vol_amplify = payload.get("p_vol_amplify")
    if not isinstance(p_up, (int, float)) or not isinstance(p_vol_amplify, (int, float)):
        print("IRGA payload missing p_up/p_vol_amplify, continuing without it")
        return None

    age = _age_hours(payload)
    if age is not None and age > IRGA_MAX_AGE_HOURS:
        print(f"IRGA snapshot stale ({age:.1f}h old), continuing without it")
        return None

    return {
        "p_up": float(p_up),
        "p_vol_amplify": float(p_vol_amplify),
        "age_hours": age if age is not None else 0.0,
        "model": str(payload.get("model", "unknown")),
    }
