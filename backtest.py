#!/usr/bin/env python3
"""Standalone backtest runner. Port dari packages/backtest/src (index.ts,
simulate.ts, report.ts, okxHistory.ts).

Usage:
    python backtest.py [days] [--irga-history PATH] [--fee-bps N] [--slippage-bps N] [--split-ratio R]

--irga-history PATH  Opsional. Aktifkan overlay IRGA (lihat
    engine/irga.py) selama backtest, dibaca dari file JSON point-in-time
    yang kamu siapkan sendiri -- lihat irga_history.py untuk format &
    kenapa live API tidak bisa dipakai untuk ini (tidak ada endpoint
    historis, hanya /latest). Tanpa flag ini backtest berjalan identik
    dengan sebelum overlay ada.

--fee-bps N          Opsional, default 5 (0.05%, taker fee OKX futures per
    sisi). Diterapkan 2x per trade (entry + exit).

--slippage-bps N     Opsional, default 2 (0.02% per sisi, estimasi kasar
    untuk BTC-USDT-SWAP -- market cukup likuid tapi entry/exit market-order
    di 5m timeframe realistis meleset beberapa bps dari harga yang dipakai
    scoring). Diterapkan 2x per trade sama seperti fee.

    Kenapa ini penting: `cumulativeR` versi lama (dan `computeStats` di
    dashboard) menghitung R murni dari selisih harga tanpa biaya sama
    sekali. Untuk strategi scalping di 5m, fee+slippage round-trip bisa
    memakan porsi signifikan dari edge teoritis -- laporan sekarang
    menampilkan grossR (versi lama, tanpa biaya) BERDAMPINGAN dengan netR
    (dikurangi estimasi biaya), supaya jelas berapa dari "profit" itu yang
    riil vs yang bakal hilang kena fee/slippage saat live.

--split-ratio R       Opsional, default 0.5. Selain laporan agregat penuh,
    backtest juga membagi periode jadi dua segmen berurutan (rasio R:1-R)
    dan melaporkan performa tiap segmen terpisah. ROI/win-rate yang cuma
    bagus di satu segmen tapi jelek di segmen lain adalah tanda kuat
    overfitting terhadap satu rezim pasar, bukan edge yang robust -- catatan:
    ini BUKAN walk-forward parameter tuning (scoring.py tidak punya
    parameter yang di-fit dari data), melainkan pengecekan konsistensi
    performa antar periode waktu.

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

# Estimasi biaya round-trip, dalam basis poin (1 bps = 0.01%), SATU SISI.
# Diterapkan 2x per trade (entry + exit) di apply_costs(). Ini estimasi kasar
# untuk order market di BTC-USDT-SWAP OKX -- kalau kamu tahu fee tier akun
# atau slippage riil yang berbeda, override lewat --fee-bps/--slippage-bps.
DEFAULT_FEE_BPS = 5.0        # 0.05% taker fee (tier dasar OKX futures)
DEFAULT_SLIPPAGE_BPS = 2.0   # 0.02% estimasi slippage market-order


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


def apply_costs(gross_r: float, entry_ref: float, closed_price: float, risk: float, fee_bps: float, slippage_bps: float):
    """Estimasi biaya round-trip (fee + slippage, masing-masing dikenakan di
    ENTRY dan EXIT) dan kembalikan (net_r, cost_r).

    Asumsi: fee & slippage dihitung sebagai persentase dari harga entry dan
    harga exit (bukan dari risk), lalu dikonversi ke satuan R dengan dibagi
    `risk` (jarak entry->SL, definisi 1R yang sama dipakai di seluruh kode
    ini -- lihat computeStats() di dashboard/src/lib/stats.ts).

    Ini estimasi, bukan simulasi order-book -- untuk BTC-USDT-SWAP yang
    likuid, slippage riil untuk ukuran posisi kecil-menengah biasanya lebih
    kecil dari estimasi ini, tapi bisa lebih besar saat volatilitas tinggi
    (persis saat sinyal RVOL/pattern breakout paling sering terpicu --
    artinya estimasi flat ini kemungkinan MENGUNDERESTIMATE biaya riil pada
    kondisi market yang justru paling sering memicu sinyal).
    """
    rate = (fee_bps + slippage_bps) / 10_000.0
    cost_price = abs(entry_ref) * rate + abs(closed_price) * rate
    cost_r = cost_price / risk if risk else 0.0
    net_r = round(gross_r - cost_r, 3)
    return net_r, round(cost_r, 3)


def build_performance_report(signals, fee_bps: float = DEFAULT_FEE_BPS, slippage_bps: float = DEFAULT_SLIPPAGE_BPS):
    """Hitung cumulative R dua versi:

    - grossR: selisih harga murni / risk, TANPA biaya (sama seperti
      computeStats() di dashboard -- ini angka yang ditampilkan Discord/UI).
    - netR: grossR dikurangi estimasi fee+slippage (lihat apply_costs()).

    Juga menghitung `falseWins`: trade yang statusnya tp1_hit/tp2_hit
    ("win" dari sisi harga) tapi netR <= 0 setelah biaya -- indikator
    seberapa besar porsi "kemenangan" yang sebenarnya rugi net-of-cost.
    Kalau angka ini besar relatif ke total wins, win rate yang ditampilkan
    dashboard menyesatkan soal profitabilitas riil.
    """
    closed = [s for s in signals if s["status"] not in ("watchlist", "active") and s.get("closedPrice") is not None]

    cumulative_gross_r = 0.0
    cumulative_net_r = 0.0
    false_wins = 0
    monthly = {}

    for s in closed:
        entry_ref = s["entryZoneStart"] if s["type"] == "LONG" else s["entryZoneEnd"]
        risk = (entry_ref - s["stopLoss"]) if s["type"] == "LONG" else (s["stopLoss"] - entry_ref)
        if not risk or risk <= 0:
            continue

        move = (s["closedPrice"] - entry_ref) if s["type"] == "LONG" else (entry_ref - s["closedPrice"])
        gross_r = round(move / risk, 3)
        net_r, cost_r = apply_costs(gross_r, entry_ref, s["closedPrice"], risk, fee_bps, slippage_bps)

        if s["status"] in ("tp1_hit", "tp2_hit") and net_r <= 0:
            false_wins += 1

        cumulative_gross_r = round(cumulative_gross_r + gross_r, 3)
        cumulative_net_r = round(cumulative_net_r + net_r, 3)

        month_key = s["closedAt"][:7]
        b = monthly.setdefault(month_key, {"trades": 0, "wins": 0, "losses": 0, "grossR": 0, "netR": 0})
        b["trades"] += 1
        if gross_r > 0:
            b["wins"] += 1
        if gross_r < 0:
            b["losses"] += 1
        b["grossR"] = round(b["grossR"] + gross_r, 3)
        b["netR"] = round(b["netR"] + net_r, 3)

    return {
        "costAssumptions": {"feeBps": fee_bps, "slippageBps": slippage_bps, "note": "per sisi, diterapkan di entry & exit"},
        "finalCumulativeGrossR": cumulative_gross_r,
        "finalCumulativeNetR": cumulative_net_r,
        "falseWins": false_wins,
        "closedTrades": len(closed),
        "monthly": monthly,
    }


def split_by_time(signals, ratio: float = 0.5):
    """Bagi `signals` jadi dua segmen berurutan berdasarkan createdAt,
    bukan berdasarkan index list (list bisa berisi campuran 5m+15m yang
    tidak terurut waktu). `ratio` = proporsi durasi waktu untuk segmen
    pertama (bukan proporsi jumlah sinyal -- supaya pembagian representasi
    waktu kalender, bukan sekadar jumlah trade).

    Catatan penting (lihat juga docstring modul): ini BUKAN walk-forward
    parameter optimization, karena scoring.py tidak punya parameter yang
    di-fit dari data historis. Ini murni pengecekan "apakah performa
    konsisten across periode", untuk mendeteksi hasil yang cuma bagus
    karena kebetulan cocok dengan satu rezim pasar (mis. bull run kencang)
    di dalam window backtest.
    """
    if not signals:
        return [], []
    timestamps = [datetime.fromisoformat(s["createdAt"]) for s in signals]
    t_min, t_max = min(timestamps), max(timestamps)
    cutoff = t_min + (t_max - t_min) * ratio
    first, second = [], []
    for s, t in zip(signals, timestamps):
        (first if t <= cutoff else second).append(s)
    return first, second


def _parse_args(argv):
    days = 90
    irga_history_path = None
    fee_bps = DEFAULT_FEE_BPS
    slippage_bps = DEFAULT_SLIPPAGE_BPS
    split_ratio = 0.5
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
        if arg == "--fee-bps":
            if i + 1 >= len(argv):
                print("--fee-bps butuh angka, contoh: --fee-bps 5")
                sys.exit(1)
            fee_bps = float(argv[i + 1])
            i += 2
            continue
        if arg == "--slippage-bps":
            if i + 1 >= len(argv):
                print("--slippage-bps butuh angka, contoh: --slippage-bps 2")
                sys.exit(1)
            slippage_bps = float(argv[i + 1])
            i += 2
            continue
        if arg == "--split-ratio":
            if i + 1 >= len(argv):
                print("--split-ratio butuh angka 0-1, contoh: --split-ratio 0.5")
                sys.exit(1)
            split_ratio = float(argv[i + 1])
            i += 2
            continue
        if not positional_consumed:
            days = int(arg)
            positional_consumed = True
        i += 1
    return days, irga_history_path, fee_bps, slippage_bps, split_ratio


def _print_performance(label, perf):
    print(f"  [{label}] closed trades: {perf['closedTrades']}, false wins (TP hit tapi netR<=0): {perf['falseWins']}")
    print(f"  [{label}] grossR: {perf['finalCumulativeGrossR']}  |  netR (setelah fee+slippage): {perf['finalCumulativeNetR']}")


def main():
    days, irga_history_path, fee_bps, slippage_bps, split_ratio = _parse_args(sys.argv[1:])
    print(f"\nBTC Signal System -- Backtest ({days} hari)\n")
    print(f"Cost assumptions: {fee_bps} bps fee + {slippage_bps} bps slippage per sisi (override via --fee-bps/--slippage-bps)\n")

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
    performance_report = build_performance_report(all_signals, fee_bps=fee_bps, slippage_bps=slippage_bps)

    first_half, second_half = split_by_time(actionable, ratio=split_ratio)
    perf_first = build_performance_report(first_half, fee_bps=fee_bps, slippage_bps=slippage_bps)
    perf_second = build_performance_report(second_half, fee_bps=fee_bps, slippage_bps=slippage_bps)

    print("\n=== Summary ===")
    print(f"Actionable signals (score >= 70): {len(actionable)}")
    print(f"Watchlist entries (score 50-69):  {len(watchlist)}")
    print(f"Still open at end of window:      {len(still_active)}")
    overall = win_rate_report["overall"]
    print(f"Win rate (TP1/TP2 vs SL): {overall['winRate']}% ({overall['wins']}W / {overall['losses']}L)")
    print(f"Final cumulative grossR (tanpa biaya, = angka lama):  {performance_report['finalCumulativeGrossR']}")
    print(f"Final cumulative netR   (setelah fee+slippage):       {performance_report['finalCumulativeNetR']}")
    if performance_report["closedTrades"]:
        false_win_pct = round(performance_report["falseWins"] / performance_report["closedTrades"] * 100, 1)
        print(f"False wins (TP hit tapi rugi net-of-cost): {performance_report['falseWins']} / {performance_report['closedTrades']} closed ({false_win_pct}%)")

    print(f"\n=== Konsistensi antar periode (split ratio {split_ratio}, BUKAN parameter tuning) ===")
    _print_performance("Periode 1 (lebih awal)", perf_first)
    _print_performance("Periode 2 (lebih akhir)", perf_second)
    if perf_first["finalCumulativeNetR"] > 0 and perf_second["finalCumulativeNetR"] <= 0 or \
       perf_first["finalCumulativeNetR"] <= 0 and perf_second["finalCumulativeNetR"] > 0:
        print("  PERINGATAN: hasil netR berlawanan tanda antar periode -- indikasi kuat hasil agregat tidak robust / bergantung rezim pasar tertentu.")

    output_dir = os.path.join(os.path.dirname(__file__), "backtest_output")
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    output_path = os.path.join(output_dir, f"backtest-{ts}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "params": {
                    "days": days,
                    "generatedAt": datetime.now(timezone.utc).isoformat(),
                    "feeBps": fee_bps,
                    "slippageBps": slippage_bps,
                    "splitRatio": split_ratio,
                },
                "summary": {
                    "actionableSignals": len(actionable),
                    "watchlistEntries": len(watchlist),
                    "stillOpen": len(still_active),
                },
                "winRate": win_rate_report,
                "performance": performance_report,
                "periodConsistency": {"period1": perf_first, "period2": perf_second},
                "signals": all_signals,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nFull report written to {output_path}\n")


if __name__ == "__main__":
    main()
