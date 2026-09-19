# BTC Signal Dashboard

Dashboard statis untuk melihat sinyal dari bot (`../run_bot.py`). Membaca
`state.json` langsung dari GitHub lewat raw URL, jadi **tidak butuh API server**.

**Stack:** Vite · React 19 · TypeScript · Tailwind CSS v4 · pnpm

## Menjalankan lokal

Butuh Node ≥ 22 dan pnpm (`corepack enable` akan memasang versi yang tepat
sesuai field `packageManager` di `package.json`).

```bash
cd dashboard
pnpm install
pnpm dev          # http://localhost:5173
```

Sumber data hanya diatur lewat variabel `VITE_STATE_URL` (tidak ada pengaturan
URL di UI). Tanpa variabel ini dashboard menunjuk ke URL placeholder. Buat
`dashboard/.env.local`:

```
VITE_STATE_URL=https://raw.githubusercontent.com/<user>/<repo>/main/state.json
```

Untuk tes dengan file lokal, boleh pakai path relatif: `VITE_STATE_URL=./state.json`
lalu taruh `state.json` di `dashboard/public/`.

| Script | Fungsi |
|---|---|
| `pnpm dev` | dev server dengan hot reload |
| `pnpm typecheck` | type-check saja (`tsc --noEmit`) |
| `pnpm build` | type-check + build produksi ke `dist/` |
| `pnpm preview` | serve hasil build untuk dicek |

## Deploy (Cloudflare Pages)

Dashboard di-deploy ke **Cloudflare Pages** saja. Tidak ada workflow GitHub
Actions untuk dashboard (deploy ke GitHub Pages sudah dihapus).

**Opsi 1: hubungkan repo GitHub ke Pages.** Pengaturan build:

| Setting | Nilai |
|---|---|
| Root directory | `dashboard` |
| Build command | `pnpm build` |
| Build output directory | `dist` |
| Build watch paths | `dashboard/*` |

Environment variables (Settings → Environment variables):

```
NODE_VERSION=22
VITE_STATE_URL=https://raw.githubusercontent.com/harvey-moeid/byga/main/state.json
```

`VITE_STATE_URL` dibaca saat **build**, jadi harus sudah terisi sebelum build
pertama. Kalau kosong, dashboard menunjuk ke URL placeholder dan datanya kosong.

**Opsi 2: direct upload.** Isi `dashboard/.env.local` (lihat di atas), lalu:

```bash
cd dashboard
pnpm build
npx wrangler pages deploy dist
```

> Bot meng-commit `state.json` tiap 5 menit dengan pesan `[skip ci]`. Dashboard
> mengambil data saat runtime, bukan saat build, jadi commit itu tidak perlu
> memicu build. Isi **Build watch paths** (`dashboard/*`) supaya perubahan di
> luar folder dashboard tidak memicu build ulang di Cloudflare.

Repo harus **public** agar `raw.githubusercontent.com` bisa dibaca tanpa autentikasi.

## Struktur

```
src/
├── main.tsx              entry point
├── App.tsx               susunan halaman; menghubungkan hooks dan komponen
├── config.ts             konstanta (interval refresh, URL state.json dari VITE_STATE_URL)
├── types.ts              tipe data state.json (cerminan engine/scoring.py & state_store.py)
├── hooks/
│   └── useStateJson.ts   polling + status koneksi
├── lib/
│   ├── format.ts         format angka & waktu
│   └── stats.ts          hitung sinyal aktif, riwayat, win rate (fungsi murni)
└── components/           StatCard, StatusIndicator, StatusBadge,
                          ActiveSignalsTable, HistoryTable
```

## Keputusan desain

- **`base: './'` di `vite.config.ts`.** Path relatif membuat build jalan di
  root domain maupun subpath tanpa hardcode nama repo.
- **Data lama tidak dibuang saat fetch gagal.** Hanya indikator koneksi yang
  berubah merah. Lebih berguna daripada layar kosong saat koneksi putus sesaat.
- **Cache-buster `?t=` + `cache: 'no-store'`.** `raw.githubusercontent.com`
  meng-cache respons beberapa menit; tanpa ini dashboard bisa menampilkan data basi.
- **Logika turunan di `lib/stats.ts`, bukan di komponen.** Fungsi murni, mudah dites,
  tidak tercampur urusan tampilan.
- **Tidak ada `innerHTML`.** React meng-escape semua nilai, jadi isi `state.json`
  (mis. nama pattern) tidak bisa menyisipkan HTML/script. Versi HTML lama
  merakit tabel dengan template string tanpa escape.
- **Tailwind lewat plugin Vite**, bukan CDN. CSS di-generate saat build
  (~12 kB) dan tidak ada skrip pihak ketiga yang dimuat saat runtime.
- **`StatusBadge` bertipe `Record<SignalStatus, ...>`.** Kalau `SignalStatus`
  ditambah status baru, TypeScript memaksa kita memberi warna untuknya.

## Kalau bot menambah/mengubah field

Sumber kebenaran skema ada di Python (`engine/scoring.py`, `state_store.py`).
Sesuaikan `src/types.ts`, lalu `pnpm typecheck` akan menunjukkan komponen
mana yang ikut terpengaruh.
