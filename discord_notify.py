"""Kirim embed Discord. Port dari sendDiscordNotification (engine/index.ts)
dan sendAlert (tracker/index.ts)."""
import os
from datetime import datetime, timezone

import requests

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")       # sinyal baru
DISCORD_ALERT_WEBHOOK = os.environ.get("DISCORD_ALERT_WEBHOOK")   # TP/SL/expired


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"


def send_new_signal_notification(signal: dict) -> None:
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not configured, skip notification")
        return

    fields = [
        {"name": "Score", "value": f"{signal['score']}/100", "inline": True},
        {"name": "Entry Zone", "value": f"{signal['entryZoneStart']:.2f} - {signal['entryZoneEnd']:.2f}", "inline": True},
        {"name": "Stop Loss", "value": f"{signal['stopLoss']:.2f}", "inline": True},
        {"name": "TP1", "value": f"{signal['tp1']:.2f}", "inline": True},
        {"name": "TP2", "value": f"{signal['tp2']:.2f}", "inline": True},
        {"name": "Patterns", "value": ", ".join(signal["patterns"]) or "-", "inline": False},
    ]

    # IRGA overlay, only shown when a snapshot was actually used for this
    # signal (see engine/irga.py). p_up is explicitly labeled "info only"
    # here for the same reason bygatc labels it that way in its own alerts --
    # its walk-forward directional skill is close to a coin flip, it only
    # ever nudged this score by a small, capped amount.
    if signal.get("irgaVolTier"):
        fields.append({
            "name": "IRGA Vol Regime",
            "value": f"{signal['irgaVolTier'].upper()} (size x{signal['sizeMultiplier']})",
            "inline": True,
        })
    if signal.get("irgaPUp") is not None:
        fields.append({
            "name": "IRGA p(up) -- info only, weak edge",
            "value": f"{signal['irgaPUp'] * 100:.1f}%",
            "inline": True,
        })

    embed = {
        "title": f"{signal['type']} Signal - BTCUSDT {signal['timeframe']}",
        "color": 0x00FF00 if signal["type"] == "LONG" else 0xFF0000,
        "fields": fields,
        "timestamp": _now_iso(),
        "footer": {"text": "BTC Signal System v1.1 (Python/GitHub Actions)"},
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=15)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to send Discord signal notification: {exc}")


def send_alert(signal: dict, alert_type: str, price: float) -> None:
    if not DISCORD_ALERT_WEBHOOK:
        print("DISCORD_ALERT_WEBHOOK not configured, skip alert")
        return

    if signal["type"] == "LONG":
        pnl = (price - signal["entryZoneStart"]) / signal["entryZoneStart"] * 100
    else:
        pnl = (signal["entryZoneEnd"] - price) / signal["entryZoneEnd"] * 100

    if "TP" in alert_type:
        color = 0x00FF00
    elif alert_type == "Expired":
        color = 0xFFA500
    else:
        color = 0xFF0000

    embed = {
        "title": f"{alert_type} - {signal['type']} {signal['timeframe']}",
        "description": f"Signal #{signal['id']} triggered",
        "color": color,
        "fields": [
            {"name": "Symbol", "value": "BTC/USDT", "inline": True},
            {"name": "Type", "value": signal["type"], "inline": True},
            {"name": "Entry Zone", "value": f"${signal['entryZoneStart']:.2f} - ${signal['entryZoneEnd']:.2f}", "inline": True},
            {"name": "Stop Loss", "value": f"${signal['stopLoss']:.2f}", "inline": True},
            {"name": "Current Price", "value": f"${price:.2f}", "inline": True},
            {"name": "TP1", "value": f"${signal['tp1']:.2f}", "inline": True},
            {"name": "TP2", "value": f"${signal['tp2']:.2f}", "inline": True},
            {"name": "Score", "value": f"{signal['score']}/100", "inline": True},
            {"name": "PnL", "value": f"{pnl:.2f}%", "inline": True},
            {"name": "Patterns", "value": ", ".join(signal.get("patterns") or []) or "N/A", "inline": False},
        ],
        "timestamp": _now_iso(),
        "footer": {"text": "BTC Signal System v1.1 (Python/GitHub Actions)"},
    }

    try:
        resp = requests.post(DISCORD_ALERT_WEBHOOK, json={"embeds": [embed]}, timeout=15)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to send Discord alert: {exc}")
