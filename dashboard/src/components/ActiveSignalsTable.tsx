import type { Signal } from '../types';
import { fmt, fmtTime } from '../lib/format';

export default function ActiveSignalsTable({ signals }: { signals: Signal[] }) {
  if (!signals.length) return <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-900/50 p-6 text-center text-sm text-slate-500">Tidak ada sinyal aktif saat ini.</div>;
  return <>
    <div className="space-y-3 md:hidden">
      {signals.map((s) => <article key={s.id} className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
        <div className="flex items-start justify-between gap-3">
          <div><div className="text-xs text-slate-500">{s.timeframe} · {fmtTime(s.createdAt)}</div><div className={`mt-1 text-lg font-bold ${s.type === 'LONG' ? 'text-emerald-400' : 'text-red-400'}`}>{s.type}</div></div>
          <div className="rounded-lg bg-slate-800 px-3 py-1.5 text-center"><div className="text-[10px] uppercase text-slate-500">Score</div><div className="font-bold">{s.score}</div></div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 text-xs"><Metric label="Entry" value={`${fmt(s.entryZoneStart)} - ${fmt(s.entryZoneEnd)}`} /><Metric label="Stop Loss" value={fmt(s.stopLoss)} danger /><Metric label="TP 1" value={fmt(s.tp1)} good /><Metric label="TP 2" value={fmt(s.tp2)} good /></div>
        {!!s.patterns?.length && <div className="mt-4 border-t border-slate-800 pt-3 text-xs text-slate-400">Pattern: {s.patterns.join(', ')}</div>}
      </article>)}
    </div>
    <div className="hidden overflow-x-auto rounded-2xl border border-slate-800 bg-slate-900/80 md:block"><table className="w-full text-sm"><thead className="text-left text-xs uppercase text-slate-500"><tr>{['TF','Tipe','Score','Entry','SL','TP1','TP2','Pattern','Dibuat'].map(c => <th key={c} className="p-3">{c}</th>)}</tr></thead><tbody>{signals.map(s => <tr key={s.id} className="border-t border-slate-800"><td className="p-3">{s.timeframe}</td><td className={`p-3 font-medium ${s.type === 'LONG' ? 'text-emerald-400' : 'text-red-400'}`}>{s.type}</td><td className="p-3">{s.score}</td><td className="p-3 font-mono">{fmt(s.entryZoneStart)} - {fmt(s.entryZoneEnd)}</td><td className="p-3 font-mono">{fmt(s.stopLoss)}</td><td className="p-3 font-mono">{fmt(s.tp1)}</td><td className="p-3 font-mono">{fmt(s.tp2)}</td><td className="p-3 text-slate-400">{(s.patterns ?? []).join(', ')}</td><td className="p-3 text-slate-400">{fmtTime(s.createdAt)}</td></tr>)}</tbody></table></div>
  </>;
}
function Metric({ label, value, danger = false, good = false }: { label: string; value: string; danger?: boolean; good?: boolean }) { return <div className="rounded-xl bg-slate-950/70 p-3"><div className="text-[10px] uppercase text-slate-500">{label}</div><div className={`mt-1 break-words font-mono text-xs ${danger ? 'text-red-300' : good ? 'text-emerald-300' : 'text-slate-200'}`}>{value}</div></div>; }
