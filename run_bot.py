#!/usr/bin/env python3
"""Entry point yang dijalankan cron GitHub Actions tiap 5 menit.

Menggabungkan 3 worker Cloudflare asli (fetcher, engine, tracker) jadi satu
proses sinkron:
  1. Fetch candle 5m & 15m terbaru dari OKX.
  2. Untuk tiap candle yang belum pernah diproses (dicek via fetch_cursor di
     state.json): jalankan engine scoring -> simpan sinyal baru (active jika
     score>=70, watchlist jika score 50-69) -> kirim notifikasi Discord untuk
     sinyal baru.
  3. Untuk semua sinyal 'active': cek harga terkini vs TP1/TP2/SL/expired
     (1 jam)/invalidated -> update status -> kirim alert Discord jika kena.
  4. Tulis balik state.json (di-commit oleh workflow jika berubah).

State (pengganti D1+KV+Queue Cloudflare) disimpan di satu file JSON lokal,
lihat state_store.py.
"""
import sys
from datetime import datetime, timezone

import discord_notify
import irga_client
import okx_client
from engine import score_candle, determine_trend
from state_store import (
    load_state,
    save_state,
    log_error,
    get_active_signals,
    add_signal,
    update_signal_status,
    set_recent_candles,
)

SCORE_SEND_THRESHOLD = 70
SCORE_WATCHLIST_THRESHOLD = 50
EXPIRY_HOURS = 1
TIMEFRAMES = ["5m", "15m"]
WINDOW = 100


def process_new_candles(
    state: dict,
    timeframe: str,
    candles: list,
    m15_trend: str,
    irga: dict | None = None,
) -> None:
    """Skor tiap candle closed yang openTime-nya lebih baru dari fetch_cursor
    (idempotent -- menggantikan cek `candle_open_time` di D1 & filterUnprocessed
    di fetcher asli). `irga` opsional (lihat engine/irga.py + irga_client.py)
    -- dipakai apa adanya untuk semua candle baru dalam satu run (snapshot-nya
    tidak berubah dalam window 5 menit ini)."""
    cursor = state["fetch_cursor"].get(timeframe, 0)
    new_indices = [i for i, c in enumerate(candles) if c["openTime"] > cursor]

    if not new_indices:
        return

    for i in new_indices:
        window = candles[: i + 1]
        current_index = len(window) - 1
        candle = window[current_index]

        trend_for_this = determine_trend(window) if timeframe == "15m" else m15_trend

        try:
            scored = score_candle(window, current_index, timeframe, trend_for_this, irga=irga)
        except Exception as exc:  # noqa: BLE001
            log_error(state, "engine", f"score_candle failed for {timeframe}@{candle['openTime']}: {exc}")
            continue

        if not scored:
            continue

        signal = {
            "timeframe": timeframe,
            **scored,
            "status": "active" if scored["score"] >= SCORE_SEND_THRESHOLD else "watchlist",
            "candleOpenTime": candle["openTime"],
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }

        saved = add_signal(state, signal)

        if signal["status"] == "active":
            discord_notify.send_new_signal_notification(saved)
            print(f"Signal generated: {saved['type']} {timeframe} score={saved['score']}")
        else:
            print(f"Watchlist entry: {timeframe} score={saved['score']}")

    # Advance cursor ke candle terbaru yang baru saja diproses.
    state["fetch_cursor"][timeframe] = candles[new_indices[-1]]["openTime"]


def check_signal(signal: dict, current_price: float) -> str:
    """Return salah satu dari: tp_hit | sl_hit | expired | invalidated | active.
    Urutan pengecekan: expired -> SL -> invalidated -> TP2 -> TP1 (TP2 dicek
    lebih dulu karena harga bisa melompati TP1 langsung ke TP2 dalam satu
    interval 5 menit; kalau TP1 dicek duluan, TP2 tidak akan pernah tercapai
    -- sama seperti simulate_outcome() di backtest.py)."""
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    hours_since_signal = (now_ms - signal["candleOpenTime"]) / (1000 * 60 * 60)

    if hours_since_signal >= EXPIRY_HOURS:
        return "expired"

    if signal["type"] == "LONG":
        if current_price <= signal["stopLoss"]:
            return "sl_hit"
        if current_price <= signal["entryZoneStart"] * 0.995:
            return "invalidated"
        if current_price >= signal["tp2"]:
            return "tp2_hit"
        if current_price >= signal["tp1"]:
            return "tp1_hit"
    else:
        if current_price >= signal["stopLoss"]:
            return "sl_hit"
        if current_price >= signal["entryZoneEnd"] * 1.005:
            return "invalidated"
        if current_price <= signal["tp2"]:
            return "tp2_hit"
        if current_price <= signal["tp1"]:
            return "tp1_hit"

    return "active"


ALERT_LABELS = {
    "sl_hit": "SL Hit",
    "tp1_hit": "TP1 Hit",
    "tp2_hit": "TP2 Hit",
    "expired": "Expired",
}


def track_active_signals(state: dict, current_price: float) -> None:
    active_signals = get_active_signals(state)
    if not active_signals:
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    tp_hits = sl_hits = expired = invalidated = 0

    for signal in active_signals:
        try:
            result = check_signal(signal, current_price)
        except Exception as exc:  # noqa: BLE001
            log_error(state, "tracker", f"check_signal failed for #{signal['id']}: {exc}")
            continue

        if result == "active":
            continue

        status = "tp1_hit" if result == "tp1_hit" else (
            "tp2_hit" if result == "tp2_hit" else result
        )
        update_signal_status(state, signal["id"], status, current_price, now_iso)

        if result in ("sl_hit", "tp1_hit", "tp2_hit", "expired"):
            discord_notify.send_alert(signal, ALERT_LABELS[result if result in ALERT_LABELS else "sl_hit"], current_price)

        if result in ("tp1_hit", "tp2_hit"):
            tp_hits += 1
        elif result == "sl_hit":
            sl_hits += 1
        elif result == "expired":
            expired += 1
        elif result == "invalidated":
            invalidated += 1

    print(
        f"Tracker: price={current_price} tp_hits={tp_hits} sl_hits={sl_hits} "
        f"expired={expired} invalidated={invalidated} still_active={len(active_signals) - tp_hits - sl_hits - expired - invalidated}"
    )


def main() -> int:
    state = load_state()

    # 1) Fetch candle terbaru untuk kedua timeframe.
    candles_by_tf = {}
    for tf in TIMEFRAMES:
        try:
            candles_by_tf[tf] = okx_client.fetch_candles(tf, WINDOW)
        except Exception as exc:  # noqa: BLE001
            log_error(state, "fetcher", f"fetch_candles({tf}) failed: {exc}")
            print(f"ERROR fetching {tf} candles: {exc}", file=sys.stderr)
            candles_by_tf[tf] = []

    # 1a) Simpan snapshot candle 15m (untuk chart candlestick di dashboard).
    # Kalau fetch gagal (list kosong), biarkan snapshot lama di state apa adanya.
    if candles_by_tf.get("15m"):
        set_recent_candles(state, "15m", candles_by_tf["15m"])

    # 1b) Snapshot IRGA opsional -- sekali per run, dipakai untuk semua
    # candle baru di run ini. Gagal/absen -> None, bot lanjut tanpa overlay.
    try:
        irga_snapshot = irga_client.get_irga_snapshot()
    except Exception as exc:  # noqa: BLE001
        log_error(state, "irga", f"get_irga_snapshot failed: {exc}")
        irga_snapshot = None

    # 2) Generate sinyal untuk candle yang belum diproses.
    m15_trend = "neutral"
    if candles_by_tf.get("15m"):
        m15_trend = determine_trend(candles_by_tf["15m"])
        process_new_candles(state, "15m", candles_by_tf["15m"], m15_trend, irga=irga_snapshot)
    if candles_by_tf.get("5m"):
        process_new_candles(state, "5m", candles_by_tf["5m"], m15_trend, irga=irga_snapshot)

    # 3) Cek TP/SL/expired untuk semua sinyal aktif.
    try:
        price_data = okx_client.fetch_mark_price_with_retry()
        state["last_price"] = price_data["markPrice"]
        track_active_signals(state, price_data["markPrice"])
    except Exception as exc:  # noqa: BLE001
        log_error(state, "tracker", f"fetch_mark_price failed: {exc}")
        print(f"ERROR fetching mark price, skip tracking this run: {exc}", file=sys.stderr)

    state["last_run_at"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
