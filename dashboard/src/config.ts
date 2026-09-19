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
