#!/usr/bin/env python3
"""Standalone backtest runner. Port dari packages/backtest/src (index.ts,
simulate.ts, report.ts, okxHistory.ts).

Usage:
    python backtest.py [days] [--irga-history PATH]   # days default 90

--irga-history PATH  Opsional. Aktifkan overlay IRGA (lihat
    engine/irga.py) selama backtest, dibaca dari file JSON point-in-time
    yang kamu siapkan sendiri -- lihat irga_history.py untuk format &
    kenapa live API tidak bisa dipakai untuk ini (tidak ada endpoint
    historis, hanya /latest). Tanpa flag ini backtest berjalan identik
    dengan sebelum overlay ada.

Fetch candle historis 5m & 15m BTC-USDT-SWAP dari OKX, jalankan lewat
scoring logic PERSIS SAMA dengan yang dipakai run_bot.py (import dari
package `engine` yang sama -- bukan reimplementasi terpisah), simulasikan
outcome TP/SL, lalu tulis laporan JSON. Sinyal tidak punya batas waktu
(expired) maupun ambang pembatalan (invalidated) -- sama seperti
check_signal() di run_bot.py.
"""
import json
import os
import sys
from datetime import datetime, timezone

from engine import score_candle, determine_trend
import irga_history
import okx_client

WINDOW = 100
SCORE_SEND_THRESHOLD = 70
SCORE_WATCHLIST_THRESHOLD = 50


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def generate_signals(primary_candles, timeframe, m15_candles, irga_hist=None):
    """Walk-forward: skor tiap candle persis seperti live engine akan
    melakukannya (window trailing 100 candle, cek alignment M15).

    `irga_hist`: list snapshot terurut dari irga_history.load_irga_history(),
    atau None untuk backtest tanpa overlay IRGA. Snapshot dipilih via
    snapshot_at_or_before(current_candle["closeTime"]) -- tidak pernah
    memakai snapshot dari masa depan candle yang sedang dinilai."""
    out = []
    m15_pointer = -1

    for i in range(WINDOW - 1, len(primary_candles)):
        window = primary_candles[i - WINDOW + 1: i + 1]
        current_index = len(window) - 1
        current_candle = window[current_index]

        if timeframe == "15m":
            m15_trend = determine_trend(window)
        else:
            while (
                m15_pointer + 1 < len(m15_candles)
                and m15_candles[m15_pointer + 1]["closeTime"] <= current_candle["closeTime"]
            ):
                m15_pointer += 1
            m15_window_end = m15_pointer + 1
            m15_window_start = max(0, m15_window_end - WINDOW)
            m15_window = m15_candles[m15_window_start:m15_window_end]
            m15_trend = determine_trend(m15_window) if m15_window else "neutral"

        irga_snapshot = (
            irga_history.snapshot_at_or_before(irga_hist, current_candle["closeTime"])
            if irga_hist
            else None
        )

        scored = score_candle(window, current_index, timeframe, m15_trend, irga=irga_snapshot)
        if not scored or scored["score"] < SCORE_WATCHLIST_THRESHOLD:
            continue

        signal = {
            **scored,
            "timeframe": timeframe,
            "candleOpenTime": current_candle["openTime"],
            "createdAt": _iso(current_candle["closeTime"]),
            "status": "active" if scored["score"] >= SCORE_SEND_THRESHOLD else "watchlist",
        }
        out.append({"index": i, "signal": signal})

    return out


def simulate_outcome(candles, signal_index, signal):
    """Scan forward candle-by-candle, prioritas: SL -> TP2 -> TP1 (identik
    dengan check_signal() di run_bot.py, tapi dicek per high/low candle
    historis, bukan poll harga tiap 5 menit).

    Keputusan desain: tidak ada lagi cabang expired (batas 1 jam) maupun
    invalidated (harga menembus 0.5% di luar entry zone). Live bot memantau
    sinyal tanpa batas waktu sampai kena TP/SL, jadi backtest harus
    mengukur hal yang sama -- kalau tidak, win rate backtest tidak bisa
    dibandingkan dengan hasil live.

    Kalau dalam seluruh data historis harga tidak pernah menyentuh SL/TP,
    sinyal dikembalikan sebagai 'active' (masih terbuka di akhir window)
    dan tidak ikut dihitung di win rate maupun cumulative R.

    Kalau SL dan TP tersentuh dalam candle yang sama, SL dimenangkan
    (asumsi konservatif -- urutan intra-candle tidak diketahui)."""
    for i in range(signal_index + 1, len(candles)):
        candle = candles[i]
        high = float(candle["high"])
        low = float(candle["low"])

        if signal["type"] == "LONG":
            if low <= signal["stopLoss"]:
                return {"status": "sl_hit", "closedPrice": signal["stopLoss"], "closedAt": _iso(candle["closeTime"])}
            if high >= signal["tp2"]:
                return {"status": "tp2_hit", "closedPrice": signal["tp2"], "closedAt": _iso(candle["closeTime"])}
            if high >= signal["tp1"]:
                return {"status": "tp1_hit", "closedPrice": signal["tp1"], "closedAt": _iso(candle["closeTime"])}
        else:
            if high >= signal["stopLoss"]:
                return {"status": "sl_hit", "closedPrice": signal["stopLoss"], "closedAt": _iso(candle["closeTime"])}
            if low <= signal["tp2"]:
                return {"status": "tp2_hit", "closedPrice": signal["tp2"], "closedAt": _iso(candle["closeTime"])}
            if low <= signal["tp1"]:
                return {"status": "tp1_hit", "closedPrice": signal["tp1"], "closedAt": _iso(candle["closeTime"])}

    last = candles[-1]
    return {"status": "active", "closedPrice": float(last["close"]), "closedAt": _iso(last["closeTime"])}


def run_backtest(primary_candles, timeframe, m15_candles, irga_hist=None):
    candidates = generate_signals(primary_candles, timeframe, m15_candles, irga_hist=irga_hist)
    results = []
    for c in candidates:
        signal, index = c["signal"], c["index"]
        if signal["status"] != "active":
            results.append(signal)  # watchlist: dicatat, tidak pernah ditrack
            continue
        outcome = simulate_outcome(primary_candles, index, signal)
        results.append({**signal, **outcome})
    return results


def build_win_rate_report(signals):
    def is_win(s):
        return s["status"] in ("tp1_hit", "tp2_hit")

    def is_loss(s):
        return s["status"] == "sl_hit"

    def win_rate(w, l):
        return round((w / (w + l)) * 100, 2) if (w + l) > 0 else None

    actionable = [s for s in signals if s["status"] != "watchlist"]
    overall = {"total": 0, "wins": 0, "losses": 0}
    by_pattern = {}
    by_hour = {}

    for s in actionable:
        overall["total"] += 1
        win, loss = is_win(s), is_loss(s)
        if win:
            overall["wins"] += 1
        if loss:
            overall["losses"] += 1

        for pattern in s["patterns"]:
            b = by_pattern.setdefault(pattern, {"total": 0, "wins": 0, "losses": 0})
            b["total"] += 1
            if win:
                b["wins"] += 1
            if loss:
                b["losses"] += 1

        hour = datetime.fromisoformat(s["createdAt"]).hour
        b = by_hour.setdefault(hour, {"total": 0, "wins": 0, "losses": 0})
        b["total"] += 1
        if win:
            b["wins"] += 1
        if loss:
            b["losses"] += 1

    return {
        "overall": {**overall, "winRate": win_rate(overall["wins"], overall["losses"])},
        "perPattern": {k: {**v, "winRate": win_rate(v["wins"], v["losses"])} for k, v in by_pattern.items()},
        "perHourUTC": {
            str(k): {**v, "winRate": win_rate(v["wins"], v["losses"])}
            for k, v in sorted(by_hour.items())
        },
    }


def build_performance_report(signals):
    closed = [s for s in signals if s["status"] not in ("watchlist", "active") and s.get("closedPrice") is not None]

    cumulative_r = 0.0
    monthly = {}

    for s in closed:
        entry_ref = s["entryZoneStart"] if s["type"] == "LONG" else s["entryZoneEnd"]
        risk = (entry_ref - s["stopLoss"]) if s["type"] == "LONG" else (s["stopLoss"] - entry_ref)
        if not risk or risk <= 0:
            continue

        move = (s["closedPrice"] - entry_ref) if s["type"] == "LONG" else (entry_ref - s["closedPrice"])
        r = round(move / risk, 3)
        cumulative_r = round(cumulative_r + r, 3)

        month_key = s["closedAt"][:7]
        b = monthly.setdefault(month_key, {"trades": 0, "wins": 0, "losses": 0, "netR": 0})
        b["trades"] += 1
        if r > 0:
            b["wins"] += 1
        if r < 0:
            b["losses"] += 1
        b["netR"] = round(b["netR"] + r, 3)

    return {"finalCumulativeR": cumulative_r, "monthly": monthly}


def _parse_args(argv):
    days = 90
    irga_history_path = None
    positional_consumed = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--irga-history":
            if i + 1 >= len(argv):
                print("--irga-history butuh PATH, contoh: --irga-history irga_hist.json")
                sys.exit(1)
            irga_history_path = argv[i + 1]
            i += 2
            continue
        if not positional_consumed:
            days = int(arg)
            positional_consumed = True
        i += 1
    return days, irga_history_path


def main():
    days, irga_history_path = _parse_args(sys.argv[1:])
    print(f"\nBTC Signal System -- Backtest ({days} hari)\n")

    irga_hist = None
    if irga_history_path:
        irga_hist = irga_history.load_irga_history(irga_history_path)
        print(f"IRGA overlay ENABLED: {len(irga_hist)} snapshot dari {irga_history_path}")
    else:
        print("IRGA overlay OFF (jalankan dengan --irga-history PATH untuk mengaktifkan)")

    print("Fetching historical candles from OKX...")
    print("5m:")
    candles_5m = okx_client.fetch_historical_candles("5m", days)
    print(f"  -> {len(candles_5m)} candles")

    print("15m:")
    candles_15m = okx_client.fetch_historical_candles("15m", days)
    print(f"  -> {len(candles_15m)} candles")

    if len(candles_5m) < 100 or len(candles_15m) < 100:
        print("\nData historis tidak cukup (butuh >=100 candle/timeframe). Batal.")
        sys.exit(1)

    print("\nRunning walk-forward simulation...")
    signals_5m = run_backtest(candles_5m, "5m", candles_15m, irga_hist=irga_hist)
    signals_15m = run_backtest(candles_15m, "15m", candles_15m, irga_hist=irga_hist)
    all_signals = signals_5m + signals_15m

    actionable = [s for s in all_signals if s["status"] != "watchlist"]
    watchlist = [s for s in all_signals if s["status"] == "watchlist"]
    still_active = [s for s in actionable if s["status"] == "active"]

    win_rate_report = build_win_rate_report(all_signals)
    performance_report = build_performance_report(all_signals)

    print("\n=== Summary ===")
    print(f"Actionable signals (score >= 70): {len(actionable)}")
    print(f"Watchlist entries (score 50-69):  {len(watchlist)}")
    print(f"Still open at end of window:      {len(still_active)}")
    overall = win_rate_report["overall"]
    print(f"Win rate (TP1/TP2 vs SL): {overall['winRate']}% ({overall['wins']}W / {overall['losses']}L)")
    print(f"Final cumulative R (1% risk/trade): {performance_report['finalCumulativeR']}")

    output_dir = os.path.join(os.path.dirname(__file__), "backtest_output")
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    output_path = os.path.join(output_dir, f"backtest-{ts}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "params": {"days": days, "generatedAt": datetime.now(timezone.utc).isoformat()},
                "summary": {
                    "actionableSignals": len(actionable),
                    "watchlistEntries": len(watchlist),
                    "stillOpen": len(still_active),
                },
                "winRate": win_rate_report,
                "performance": performance_report,
                "signals": all_signals,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nFull report written to {output_path}\n")


if __name__ == "__main__":
    main()
