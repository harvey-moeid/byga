import type { Signal } from '../types';

export interface Stats {
  active: Signal[];
  /** Breakdown arah sinyal aktif -- dipakai alih-alih hardcode 'LONG'. */
  activeLong: number;
  activeShort: number;
  /** Sinyal yang sudah selesai (kena TP1/TP2/SL), terbaru dulu. */
  closed: Signal[];
  wins: number;
  losses: number;
  /** Contoh: "66.7% (2W/1L)", atau "-" kalau belum ada sinyal selesai. */
  winRateLabel: string;
  /** R-multiple kumulatif dari semua sinyal closed (risk = jarak entry->SL = 1R). */
  cumulativeR: number;
  /** Contoh: "+4.20R" atau "-1.50R". */
  cumulativeRLabel: string;
}

/**
 * Hasil trade yang sah. Sengaja whitelist, bukan "semua status selain
 * active/watchlist": sinyal lama di state.json bisa masih berstatus
 * 'expired' / 'invalidated' (dibuat sebelum bot berhenti memakai status itu),
 * dan status tak dikenal lain di masa depan, dan keduanya bukan hasil trade
 * yang sebenarnya -- jangan sampai ikut mengotori total closed, riwayat,
 * maupun cumulative R.
 */
const RESOLVED_STATUSES: ReadonlyArray<string> = ['tp1_hit', 'tp2_hit', 'sl_hit'];

/**
 * Semua turunan data dihitung di sini sebagai fungsi murni (tanpa React),
 * supaya gampang dites dan tidak tercampur dengan urusan tampilan.
 *
 * Win rate hanya menghitung TP vs SL.
 *
 * cumulativeR memakai rumus yang sama persis dengan build_performance_report()
 * di backtest.py -- risk = jarak entry ke SL (1R), PnL dinyatakan dalam
 * kelipatan R, bukan persen modal (bot ini tidak tahu ukuran posisi asli
 * trader), supaya angkanya tidak menyiratkan profit uang riil yang palsu.
 */
export function computeStats(signals: Signal[]): Stats {
  const active = signals.filter((s) => s.status === 'active');
  const activeLong = active.filter((s) => s.type === 'LONG').length;
  const activeShort = active.filter((s) => s.type === 'SHORT').length;

  const closed = signals
    .filter((s) => RESOLVED_STATUSES.includes(s.status))
    .sort(
      (a, b) =>
        new Date(b.closedAt ?? 0).getTime() - new Date(a.closedAt ?? 0).getTime(),
    );

  const wins = closed.filter((s) => s.status === 'tp1_hit' || s.status === 'tp2_hit').length;
  const losses = closed.filter((s) => s.status === 'sl_hit').length;
  const decided = wins + losses;

  const winRateLabel =
    decided > 0
      ? `${((wins / decided) * 100).toFixed(1)}% (${wins}W/${losses}L)`
      : '-';

  let cumulativeR = 0;
  for (const s of closed) {
    if (s.closedPrice == null) continue;
    const entryRef = s.type === 'LONG' ? s.entryZoneStart : s.entryZoneEnd;
    const risk = s.type === 'LONG' ? entryRef - s.stopLoss : s.stopLoss - entryRef;
    if (!risk || risk <= 0) continue;
    const move = s.type === 'LONG' ? s.closedPrice - entryRef : entryRef - s.closedPrice;
    cumulativeR += move / risk;
  }
  cumulativeR = Math.round(cumulativeR * 100) / 100;
  const cumulativeRLabel = `${cumulativeR >= 0 ? '+' : ''}${cumulativeR.toFixed(2)}R`;

  return { active, activeLong, activeShort, closed, wins, losses, winRateLabel, cumulativeR, cumulativeRLabel };
}
