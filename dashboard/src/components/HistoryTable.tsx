import type { Signal } from '../types';
import { fmt, fmtTime } from '../lib/format';
import StatusBadge from './StatusBadge';
export default function HistoryTable({ signals }: { signals: Signal[] }) {
  if (!signals.length) return <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-900/50 p-6 text-center text-sm text-slate-500">Belum ada riwayat.</div>;
  return <div className="overflow-x-auto rounded-2xl border border-slate-800 bg-slate-900/80"><table className="w-full text-sm"><thead className="text-left text-xs uppercase text-slate-500"><tr>{['TF','Tipe','Score','Status','Closed Price','Ditutup'].map(c => <th key={c} className="p-3">{c}</th>)}</tr></thead><tbody>{signals.map(s => <tr key={s.id} className="border-t border-slate-800"><td className="p-3">{s.timeframe}</td><td className={`p-3 font-medium ${s.type === 'LONG' ? 'text-emerald-400' : 'text-red-400'}`}>{s.type}</td><td className="p-3">{s.score}</td><td className="p-3"><StatusBadge status={s.status} /></td><td className="p-3 font-mono">{fmt(s.closedPrice)}</td><td className="p-3 text-slate-400">{fmtTime(s.closedAt)}</td></tr>)}</tbody></table></div>;
}
