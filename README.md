# BTC Signal Bot (Python + GitHub Actions)

Port lengkap dari `trading-main` (monorepo Cloudflare Workers: fetcher, engine,
tracker, api, frontend, backtest) menjadi Python murni yang jalan lewat
**GitHub Actions cron**, tanpa Cloudflare Workers/D1/KV/Queues sama sekali.

## Cara kerja

Satu script (`run_bot.py`) dijalankan tiap 5 menit oleh
`.github/workflows/trading-bot.yml`, menggabungkan 3 worker asli jadi satu
proses:

1. **Fetch** candle 5m & 15m BTC-USDT-SWAP dari OKX (public API, tanpa API key).
2. **Engine**: skor tiap candle closed yang belum pernah diproses — pattern
   price action (engulfing, pinbar, inside bar, BOS, CHoCH), volume (RVOL,
   spike), S/R proximity, alignment trend M15. Score â‰¥70 = sinyal aktif +
   notifikasi Discord baru; score 50-69 = watchlist (dicatat, tanpa notif).
3. **Tracker**: cek semua sinyal aktif terhadap mark price terkini —
   TP1/TP2/SL/expired (1 jam)/invalidated — kirim alert Discord saat kena.
4. Semua state (sinyal, cursor candle terakhir yang diproses) disimpan di
   **`state.json`**, di-commit balik ke repo oleh workflow setiap kali berubah.

Logika pattern/scoring ada di folder `engine/` — modul murni tanpa I/O, persis
seperti desain asli (`packages/engine`), supaya bisa dipakai identik oleh
`run_bot.py` (live) maupun `backtest.py` (historis).

## Kenapa OKX, bukan Binance/Bybit?

Kode aslinya sudah lebih dulu pindah dari Binance ke OKX untuk sumber candle
publiknya (lihat komentar di kode: *"our current source (OKX public
candles)..."*). Ini konsisten dengan pengalaman umum: endpoint futures
publik Binance (`fapi.binance.com`) kerap menolak request dari IP Indonesia
("service unavailable from a restricted location"), sedangkan endpoint
publik OKX tidak punya pembatasan itu. Bybit juga merupakan pilihan yang
valid (kini malah sudah punya entitas berizin di Indonesia via akuisisi NOBI,
per Juli 2026) — jika suatu saat ingin pindah, cukup ganti isi
`okx_client.py` dengan pemetaan endpoint yang setara.

Catatan: karena runner GitHub Actions berjalan di server Microsoft (bukan di
Indonesia), pembatasan akses dari ISP Indonesia sebenarnya tidak relevan
untuk *bot*-nya sendiri — yang relevan adalah geo-restriction dari sisi
exchange (Binance futures), bukan dari sisi Kominfo (yang setahu ini baru
memblokir akun media sosial exchange asing, bukan endpoint API publiknya).

## Setup

1. **Buat repo GitHub baru** (public, supaya `state.json` bisa dibaca dashboard
   lewat raw URL tanpa autentikasi), lalu push isi folder ini.

2. **Set GitHub Secrets** (Settings → Secrets and variables → Actions):
   - `DISCORD_WEBHOOK_URL` — webhook untuk notifikasi sinyal baru
   - `DISCORD_ALERT_WEBHOOK` — webhook untuk alert TP/SL/expired
   - `IRGA_API_URL` — opsional, lihat bagian [Strategy overlay: IRGA](#strategy-overlay-irga-opsional). Kosongkan/skip kalau tidak dipakai.

3. **Aktifkan permission workflow untuk push**: Settings → Actions → General
   → Workflow permissions → pilih **"Read and write permissions"** (supaya
   `GITHUB_TOKEN` bisa commit `state.json` balik ke repo).

4. **Perhatikan backfill di run pertama**: karena `fetch_cursor` mulai dari 0,
   run pertama akan memproses ~100 candle historis per timeframe (â‰ˆ8 jam
   data 5m + â‰ˆ25 jam data 15m) sebagai "baru", yang bisa menghasilkan beberapa
   sinyal sekaligus. Kalau tidak mau kena spam Discord di run pertama,
   kosongkan dulu isi secret webhook, biarkan satu run jalan (cursor akan
   maju), baru isi secret webhook-nya setelah itu.

5. Commit sudah menyertakan workflow cron `*/5 * * * *` — begitu di-push ke
   `main` dan Actions diaktifkan, bot langsung jalan otomatis.

## Strategy overlay: IRGA (opsional)

Selain scoring price-action (`engine/scoring.py`), bot ini bisa menggabungkan
sinyal dari model **IRGA** (proyek forecasting BTC terpisah, `bygatc`) —
diaktifkan opsional, hanya kalau kamu men-deploy Worker `bygatc` itu sendiri
dan mengisi `IRGA_API_URL`. Kalau kosong, bot berjalan identik seperti
sebelum overlay ini ada.

**Kenapa dua komponen dipakai secara berbeda** — ini bukan pilihan
sembarangan, tapi mengikuti persis apa yang didokumentasikan di
`docs/TRADE_FLOW.md` milik `bygatc` sendiri:

| Komponen IRGA | Status validasi | Dipakai untuk di bot ini |
|---|---|---|
| `p_up` (arah) | **Tidak tervalidasi** — log-loss walk-forward 0.6941, nyaris sama dengan lempar koin (0.6931). `bygatc` sendiri memin field ini ke 50/50 di semua tempat yang mempengaruhi keputusan trade, persis karena alasan ini. | Bonus **tambahan** ke score, maksimal 15 poin dari 100, dan **hanya menambah, tidak pernah mengurangi** — kalau IRGA tidak setuju dengan arah pattern, bonusnya 0, bukan minus. Skor akhir tetap di-clamp ke 100, jadi IRGA sendirian (tanpa pattern/volume/trend/S-R) tidak akan pernah cukup untuk lolos floor watchlist (50). |
| `p_vol_amplify` (ekspansi volatilitas) | **Tervalidasi** — beda 2.79% QLIKE vs baseline Log-HAR (p=0.043). Ini yang dipakai `buildFuturesPlan()` di `bygatc` untuk risk sizing. | Filter + risk-sizing: tier `high` (≥70%) memotong 10 poin dari score (soft filter, bukan blocker mutlak); semua tier menghasilkan `sizeMultiplier` (0.3–1.0) yang ditampilkan di notifikasi Discord untuk kamu terapkan manual ke position size — bot ini tidak eksekusi order, jadi tidak ada sizing otomatis. |

Field `irgaPUp`, `irgaVolTier`, `sizeMultiplier` ikut disimpan di tiap
signal (`state.json`) dan ditampilkan di embed Discord ("IRGA p(up) --
info only, weak edge" dilabeli eksplisit apa adanya, sama seperti label
`upside_is_informative: false` di payload aslinya).

**Setup:**
1. Deploy `bygatc` (lihat README repo itu) sampai `GET /api/irga/latest`
   bisa diakses publik.
2. Tambahkan GitHub Secret di repo bot ini:
   - `IRGA_API_URL` — contoh: `https://btc-dashboard-worker-production.<sub>.workers.dev/api/irga/latest`
   - `IRGA_MAX_AGE_HOURS` — opsional, default 3 jam. Snapshot lebih tua dari ini diabaikan (pipeline `bygatc` push tiap 30 menit).

**Backtest dengan IRGA:** live API `bygatc` cuma punya endpoint `/latest`
(bukan histori), jadi untuk backtest kamu perlu siapkan sendiri file JSON
point-in-time (`{"hour_ts": ..., "p_up": ..., "p_vol_amplify": ...}` per
baris, lihat docstring `irga_history.py`) — misalnya dengan menjalankan
`model/serve/predict.py` milik `bygatc` dalam loop atas anchor historis.
Tanpa file ini, `backtest.py` jalan tanpa overlay IRGA persis seperti
sebelumnya:

```bash
python backtest.py 90 --irga-history irga_hist.json
```

## Dashboard (opsional)

`dashboard/` adalah dashboard statis (Vite + React + TypeScript + Tailwind, pakai
pnpm) yang membaca `state.json` langsung dari GitHub lewat raw URL — jadi
**tidak perlu API server terpisah** sama sekali (beda dari `packages/api` di
versi Cloudflare aslinya).

Cara deploy (otomatis via `.github/workflows/dashboard.yml`):
1. Di repo GitHub: Settings → Pages → **Source: GitHub Actions**.
2. Push perubahan di `dashboard/` ke `main` — workflow akan build & deploy, dan
   otomatis mengarahkan dashboard ke `state.json` di repo yang sama.
3. Selesai — dashboard auto-refresh tiap 60 detik.

Development lokal, struktur kode, dan keputusan desain: lihat
[`dashboard/README.md`](dashboard/README.md).

## Backtest

```bash
pip install -r requirements.txt
python backtest.py 90   # backtest 90 hari terakhir
```

Memakai **fungsi scoring yang sama persis** dengan `run_bot.py` (sama-sama
import dari `engine/`), jadi hasil backtest benar-benar mencerminkan logika
yang live, bukan reimplementasi terpisah yang bisa drift. Laporan JSON
(win rate per pattern, per jam UTC, cumulative R) ditulis ke
`backtest_output/`.

## Menjalankan manual / debug lokal

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK_URL=...      # opsional, kalau kosong notifikasi di-skip
export DISCORD_ALERT_WEBHOOK=...    # opsional
export IRGA_API_URL=...           # opsional, lihat bagian Strategy overlay: IRGA
python run_bot.py
```

## Perbedaan dari versi Cloudflare asli

| Aspek | Cloudflare (asli) | Python + GitHub Actions (ini) |
|---|---|---|
| Compute | 3 Workers terpisah (fetcher/engine/tracker) | 1 script (`run_bot.py`) per run |
| Antrian | Cloudflare Queues | tidak perlu (diproses langsung, sinkron) |
| Database | D1 (`signals`, `fetch_cursor`, `error_logs`) | `state.json`, di-commit ke repo |
| Cache harga | KV (TTL 5 menit) | tidak perlu — cukup 1x fetch per run |
| Dashboard | `packages/api` (Hono, baca D1) + `packages/frontend` (React) | Vite + React (statis, deploy ke Pages) baca `state.json` langsung |
| Backtest | Node.js/TypeScript, impor `engine/src` | Python, impor `engine/` (modul sama) |

Satu trade-off yang perlu disadari: `state.json` yang di-commit tiap 5 menit
berarti riwayat commit repo akan tumbuh cepat (~288 commit/hari kalau ada
perubahan). Ukuran array sinyal & error log sudah dibatasi otomatis di
`state_store.py` (`MAX_SIGNALS_KEPT`, `MAX_ERROR_LOGS`) supaya file JSON-nya
sendiri tidak membengkak, tapi histori git commit-nya tetap bertambah terus.
Kalau ini mengganggu, opsi ke depan: pindah state ke branch terpisah
(orphan branch) atau ganti ke GitHub Gist.
