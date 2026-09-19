interface Props { label: string; value: string | number; small?: boolean; accent?: boolean; }
export default function StatCard({ label, value, small = false, accent = false }: Props) {
  return (
    <div className="min-w-0 rounded-2xl border border-slate-800/80 bg-slate-900/80 p-3.5 shadow-lg shadow-black/10 sm:p-4">
      <div className="truncate text-[10px] font-semibold uppercase tracking-wider text-slate-500 sm:text-xs">{label}</div>
      <div className={`mt-2 truncate ${small ? 'text-xs font-medium sm:text-sm' : 'text-xl font-bold sm:text-2xl'} ${accent ? 'text-emerald-300' : 'text-slate-100'}`}>{value}</div>
    </div>
  );
}
