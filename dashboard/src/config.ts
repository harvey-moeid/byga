/** Key localStorage untuk URL state.json yang dipilih user di panel pengaturan. */
export const STORAGE_KEY = 'btc-signal-dashboard-url';

/** Interval polling. Bot menulis state.json tiap 5 menit, jadi 60 detik sudah lebih dari cukup. */
export const REFRESH_MS = 60_000;

/** Jumlah baris riwayat yang ditampilkan. */
export const HISTORY_LIMIT = 20;

/**
 * URL default state.json.
 *
 * Urutan prioritas (lihat useSourceUrl):
 *   1. URL yang disimpan user di localStorage (override manual)
 *   2. VITE_STATE_URL -- di-inject saat build oleh workflow deploy, sehingga
 *      dashboard yang sudah ter-deploy langsung menunjuk ke repo-nya sendiri
 *      tanpa perlu setting manual USER/REPO.
 *   3. Placeholder -- hanya muncul saat dev lokal tanpa .env.
 */
export const DEFAULT_STATE_URL =
  import.meta.env.VITE_STATE_URL ??
  'https://raw.githubusercontent.com/USER/REPO/main/state.json';
