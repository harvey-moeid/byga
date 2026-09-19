/**
 * Bentuk data di state.json.
 * Sumber kebenarannya ada di Python: `engine/scoring.py` (field sinyal) dan
 * `state_store.py` (struktur state). Kalau field di sana berubah, sesuaikan di sini.
 */

export type SignalType = 'LONG' | 'SHORT';

export type SignalStatus =
  | 'active'
  | 'watchlist'
  | 'tp1_hit'
  | 'tp2_hit'
  | 'sl_hit'
  | 'expired'
  | 'invalidated';

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

export interface BotState {
  signals?: Signal[];
  last_price?: number | null;
  /** ISO 8601 waktu run bot terakhir; null sebelum bot pernah jalan. */
  last_run_at?: string | null;
}
