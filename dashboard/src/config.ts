/** Interval polling. Bot menulis state.json tiap 5 menit, jadi 60 detik sudah lebih dari cukup. */
export const REFRESH_MS = 60_000;

/** Jumlah baris riwayat yang ditampilkan. */
export const HISTORY_LIMIT = 20;

/**
 * URL state.json.
 *
 * Diambil dari VITE_STATE_URL yang di-set saat build (environment variable di
 * Cloudflare Pages, atau dashboard/.env.local saat dev lokal). Tidak ada
 * pengaturan URL di UI; untuk mengganti sumber data, ubah variabel itu lalu
 * build ulang. Placeholder hanya muncul saat dev lokal tanpa .env.
 */
export const STATE_URL =
  import.meta.env.VITE_STATE_URL ??
  'https://raw.githubusercontent.com/USER/REPO/main/state.json';

/**
 * Endpoint Pages Function untuk status & menjalankan bot (lihat
 * functions/api/bot.ts dan docs/RUN_BOT_BUTTON.md). Default '/api/bot' berlaku
 * karena dashboard dilayani dari root domain Cloudflare Pages.
 */
export const BOT_API_URL: string = import.meta.env.VITE_BOT_API_URL ?? '/api/bot';

/** Polling status bot saat idle -- pelan, cukup untuk mendeteksi run cron. */
export const BOT_POLL_IDLE_MS = 20_000;

/** Polling saat bot berjalan atau baru diminta jalan -- cepat, supaya tombol segera aktif lagi. */
export const BOT_POLL_ACTIVE_MS = 5_000;

/** Batas menunggu run baru muncul di GitHub setelah tombol ditekan (kunci "starting"). */
export const BOT_START_TIMEOUT_MS = 60_000;
