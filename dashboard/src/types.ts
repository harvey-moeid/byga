/**
 * Bentuk data di state.json.
 * Sumber kebenarannya ada di Python: `engine/scoring.py` (field sinyal) dan
 * `state_store.py` (struktur state). Kalau field di sana berubah, sesuaikan di sini.
 */

export type SignalType = 'LONG' | 'SHORT';

/**
 * Sinyal sekarang selalu dipantau sampai kena hasil nyata -- tidak ada lagi
 * 'expired' atau 'invalidated'. Data lama di state.json bisa saja masih
 * berisi status itu (dibuat sebelum perubahan ini); StatusBadge menangani
 * status tak dikenal lewat fallback-nya sendiri, jadi aman ditampilkan.
 */
export type SignalStatus =
  | 'active'
  | 'watchlist'
  | 'tp1_hit'
  | 'tp2_hit'
  | 'sl_hit';

export interface Signal {
  id: number;
  timeframe: string;
  type: SignalType;
  score: number;
  status: SignalStatus;
  patterns?: string[];
  entryZoneStart: number;
  entryZoneEnd: number;
  stopLoss: number;
  tp1: number;
  tp2: number;
  /** ISO 8601, di-set saat sinyal dibuat. */
  createdAt: string;
  /** Hanya ada setelah sinyal ditutup. */
  closedPrice?: number | null;
  closedAt?: string;
}

/** Candle OHLC ringkas (lihat state_store.set_recent_candles), untuk chart candlestick. */
export interface Candle {
  /** openTime candle, epoch ms. */
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
}

export interface BotState {
  signals?: Signal[];
  last_price?: number | null;
  /** ISO 8601 waktu run bot terakhir; null sebelum bot pernah jalan. */
  last_run_at?: string | null;
  /** Snapshot candle terakhir per timeframe (saat ini hanya '15m'). */
  candles?: Record<string, Candle[]>;
}
