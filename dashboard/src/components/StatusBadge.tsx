import type { SignalStatus } from '../types';

// Record<SignalStatus, ...> membuat TypeScript memaksa kita menambah warna
// kalau bot suatu hari mengeluarkan status baru.
const STYLES: Record<SignalStatus, string> = {
  active: 'bg-blue-500/20 text-blue-300',
  watchlist: 'bg-slate-500/20 text-slate-300',
  tp1_hit: 'bg-emerald-500/20 text-emerald-300',
  tp2_hit: 'bg-emerald-500/20 text-emerald-300',
  sl_hit: 'bg-red-500/20 text-red-300',
};

// state.json bisa berisi status yang belum dikenal (mis. bot lebih baru dari dashboard).
const FALLBACK = 'bg-slate-500/20 text-slate-300';

export default function StatusBadge({ status }: { status: SignalStatus }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STYLES[status] ?? FALLBACK}`}>
      {status}
    </span>
  );
}
