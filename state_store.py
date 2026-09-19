"""State persistence untuk GitHub Actions runner yang tidak persisten.

Menggantikan D1 (tabel signals, fetch_cursor, error_logs) dan KV (cache)
dari trading-main dengan satu file JSON yang di-commit balik ke repo oleh
workflow setelah setiap run. Cukup untuk skala 1 symbol / 2 timeframe pada
cadence 5 menit -- tidak butuh database sungguhan.
"""
import json
import os
from typing import List, Optional

STATE_PATH = os.environ.get("STATE_PATH", "state.json")

DEFAULT_STATE = {
    "fetch_cursor": {"5m": 0, "15m": 0},
    "next_signal_id": 1,
    "signals": [],        # semua signal (active/watchlist/tp*/sl/expired/invalidated)
    "error_logs": [],     # beberapa error terakhir, untuk debugging (bukan pengganti log CI)
    "last_price": None,   # mark price terakhir, untuk ditampilkan di dashboard
    "last_run_at": None,  # timestamp run terakhir (ISO), untuk ditampilkan di dashboard
}

MAX_ERROR_LOGS = 50
MAX_SIGNALS_KEPT = 2000  # cegah state.json tumbuh tanpa batas


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return json.loads(json.dumps(DEFAULT_STATE))  # deep copy
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        state = json.load(f)
    # Isi field yang mungkin belum ada (migrasi state lama)
    for key, default in DEFAULT_STATE.items():
        state.setdefault(key, default)
    return state


def save_state(state: dict) -> None:
    # Batasi ukuran array supaya state.json tidak membengkak selamanya.
    if len(state["signals"]) > MAX_SIGNALS_KEPT:
        state["signals"] = state["signals"][-MAX_SIGNALS_KEPT:]
    if len(state["error_logs"]) > MAX_ERROR_LOGS:
        state["error_logs"] = state["error_logs"][-MAX_ERROR_LOGS:]

    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")


def log_error(state: dict, worker_name: str, message: str) -> None:
    import time
    state["error_logs"].append({
        "worker": worker_name,
        "message": message,
        "timestamp": int(time.time() * 1000),
    })


def get_active_signals(state: dict) -> List[dict]:
    return [s for s in state["signals"] if s["status"] == "active"]


def add_signal(state: dict, signal: dict) -> dict:
    signal = dict(signal)
    signal["id"] = state["next_signal_id"]
    state["next_signal_id"] += 1
    state["signals"].append(signal)
    return signal


def update_signal_status(state: dict, signal_id: int, status: str, closed_price: Optional[float], closed_at: str) -> None:
    for s in state["signals"]:
        if s["id"] == signal_id:
            s["status"] = status
            s["closedPrice"] = closed_price
            s["closedAt"] = closed_at
            return
