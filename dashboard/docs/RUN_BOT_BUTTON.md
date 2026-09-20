# Tombol "Jalankan Bot"

Tombol di halaman Beranda dashboard untuk menjalankan workflow `trading-bot.yml`
sekarang juga, tanpa menunggu cron 5 menit. Tombol **terkunci selama bot
berjalan** (baik run dari cron maupun dari tombol ini).

## Cara kerja

```
Browser --GET/POST--> /api/bot (Cloudflare Pages Function) --API--> GitHub Actions
                       token GH_DISPATCH_TOKEN hanya ada di sini
```

- `functions/api/bot.ts` -- Pages Function. `GET` mengembalikan status
  (sedang berjalan atau tidak), `POST` memicu `workflow_dispatch`.
- `src/hooks/useBotRun.ts` -- polling status dan aksi tombol.
- `src/lib/botRun.ts` -- aturan murni: teks UI dan kapan tombol terkunci.
- `src/components/BotRunButton.tsx` -- kartu + tombol di Beranda.

Kenapa lewat function: memicu workflow butuh token dengan izin Actions write,
dan isi bundle JS dashboard bisa dibaca siapa pun. Token disimpan sebagai secret
Cloudflare dan tidak pernah dikirim ke browser.

## Kapan tombol terkunci

| Kondisi | Tampilan | Tombol |
|---|---|---|
| Ada run antre/berjalan (cron atau manual, perangkat mana pun) | "Bot sedang berjalan" | terkunci |
| Baru ditekan, run belum muncul di GitHub (maks 60 detik) | "Memulai run..." | terkunci |
| Secret belum diisi | "Belum dikonfigurasi" | terkunci |
| Endpoint tidak terjangkau (mis. `pnpm dev`) | "Tidak tersedia" | terkunci |
| Selain itu | "Siap dijalankan" + info run terakhir | aktif |

Status diambil dari server, bukan ditebak di browser, jadi run dari cron atau
dari perangkat lain ikut mengunci tombol. Polling tiap 20 detik saat idle, 5
detik saat bot berjalan, dan berhenti saat tab tidak terlihat.

## Setup (sekali saja)

1. **Buat token GitHub** (fine-grained personal access token):
   GitHub > Settings > Developer settings > Personal access tokens >
   Fine-grained tokens > Generate new token.
   - Repository access: **Only select repositories** > `byga`
   - Permissions > Repository permissions > **Actions: Read and write**
     (Metadata: Read-only ikut otomatis). Jangan beri izin lain.
   - Expiration: pilih yang wajar dan catat tanggalnya. Saat token kedaluwarsa
     tombol akan menampilkan "Tidak tersedia".
2. **Simpan sebagai secret di Cloudflare Pages**:
   Workers & Pages > project dashboard > Settings > Variables and Secrets >
   Add > Type **Secret**, Name `GH_DISPATCH_TOKEN`, Value token tadi.
3. **Deploy ulang** (push ke `main` atau Retry deployment). Secret baru hanya
   berlaku untuk deployment berikutnya.

Variabel opsional (Plaintext) kalau nama repo/workflow/branch berbeda:

| Nama | Default |
|---|---|
| `GH_REPO` | `harvey-moeid/byga` |
| `GH_WORKFLOW` | `trading-bot.yml` |
| `GH_REF` | `main` |

Frontend juga bisa diarahkan ke endpoint lain lewat `VITE_BOT_API_URL` saat
build (default `/api/bot`).

## Keamanan

Endpoint `/api/bot` sengaja tanpa login. Perlindungannya ada di sisi server:

- `POST` hanya diterima dari origin yang sama dengan dashboard (403 selain itu).
- `POST` ditolak (409) selama masih ada run antre/berjalan.
- Cooldown 30 detik sejak run terakhir dibuat (429).
- Token hanya berizin Actions di satu repo, dan tidak pernah muncul di respons.
  Detail error GitHub tidak diteruskan ke browser.

Dampak terburuk jika endpoint disalahgunakan: bot jalan lebih sering dari 5
menit. `run_bot.py` idempotent (memakai `fetch_cursor` di `state.json`), jadi
tidak ada sinyal ganda. Perlu diketahui izin Actions write juga mencakup
membatalkan/menjalankan ulang workflow di repo itu.

Kalau ingin dikunci penuh, letakkan project Pages di belakang **Cloudflare
Access** (Zero Trust). Tidak perlu mengubah kode.

## Mencoba secara lokal

`pnpm dev` (Vite) tidak menjalankan Pages Function, jadi tombol menampilkan
"Tidak tersedia". Untuk mencoba function sungguhan:

```bash
cd dashboard
echo "GH_DISPATCH_TOKEN=<token>" > .dev.vars   # sudah di-.gitignore, jangan di-commit
pnpm build
npx wrangler pages dev dist
```

Lalu buka alamat yang dicetak wrangler. Tombol akan memicu run sungguhan di
GitHub.

## Kontrak API

`GET /api/bot` -> 200
```json
{ "configured": true, "running": false,
  "lastRun": { "status": "completed", "conclusion": "success",
               "createdAt": "2026-09-20T10:00:00Z", "event": "schedule", "url": "..." } }
```
`configured: false` jika secret belum diisi.

`POST /api/bot`

| Status | Arti |
|---|---|
| 202 `{ok:true}` | Workflow dipicu. Run muncul di GitHub beberapa detik kemudian |
| 403 | Origin bukan dashboard ini |
| 409 `{running:true}` | Masih ada run antre/berjalan |
| 429 `{retryAfter}` | Cooldown, coba lagi setelah sekian detik |
| 502 `{status}` | GitHub menolak (mis. 401 token salah/kedaluwarsa, 404 repo/workflow salah) |
| 503 | Secret belum diisi |

## Catatan

- Setelah run selesai, `state.json` di-commit oleh bot dan dashboard
  mengambilnya lewat polling normal (60 detik), jadi data baru bisa tampil
  sedikit setelah tombol aktif lagi.
- Tombol memicu `workflow_dispatch`, yang sudah ada di `trading-bot.yml`.
  Jangan dihapus dari workflow.
