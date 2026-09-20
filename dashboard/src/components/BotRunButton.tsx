import { useBotRun } from '../hooks/useBotRun';
import { describeBot, describeConclusion } from '../lib/botRun';
import { fmtTime } from '../lib/format';

/**
 * Kartu status bot + tombol "Jalankan Sekarang".
 * Semua aturan teks dan kapan tombol terkunci ada di lib/botRun.ts (describeBot).
 * Memakai kelas .setting-card yang sudah ada supaya tampilannya konsisten.
 */
export default function BotRunButton() {
  const { availability, running, starting, lastRun, error, trigger } = useBotRun();

  const ui = describeBot({
    availability,
    running,
    starting,
    error,
    lastRunText: lastRun
      ? `${fmtTime(lastRun.createdAt)} (${describeConclusion(lastRun.conclusion)}, ${lastRun.event === 'schedule' ? 'otomatis' : 'manual'})`
      : null,
  });

  return (
    <div className="setting-card">
      <div className="min-w-0 flex-1" aria-live="polite">
        <small>Bot</small>
        <strong>{ui.title}</strong>
        {ui.detail && <p className={ui.isError ? 'negative' : undefined}>{ui.detail}</p>}
      </div>
      <button
        type="button"
        onClick={() => void trigger()}
        disabled={ui.disabled}
        aria-busy={running || starting}
        className="shrink-0 rounded-lg bg-[#00d99a] px-3 py-2.5 text-xs font-extrabold text-[#00261c] disabled:cursor-not-allowed disabled:opacity-40"
      >
        {ui.label}
      </button>
    </div>
  );
}
