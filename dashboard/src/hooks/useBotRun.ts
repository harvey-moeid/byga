import { useCallback, useEffect, useRef, useState } from 'react';
import { BOT_API_URL, BOT_POLL_ACTIVE_MS, BOT_POLL_IDLE_MS, BOT_START_TIMEOUT_MS } from '../config';
import { hasRunAppeared } from '../lib/botRun';
import type { BotAvailability, BotLastRun, BotStatusResponse } from '../lib/botRun';

/**
 * Status + aksi "jalankan bot" lewat Pages Function /api/bot.
 *
 * Keputusan penting:
 * - Status diambil dari server (bukan ditebak di klien), jadi tombol juga
 *   terkunci saat run berasal dari cron atau dari perangkat lain.
 * - Setelah POST berhasil, tombol tetap terkunci (`starting`) sampai run baru
 *   terlihat di GitHub, karena API baru menampilkannya beberapa detik kemudian.
 *   Batas tunggu BOT_START_TIMEOUT_MS mencegah tombol terkunci selamanya kalau
 *   run tidak pernah muncul.
 * - Polling lambat saat idle, cepat saat menunggu/berjalan, dan berhenti saat
 *   tab tidak terlihat (hemat kuota API GitHub).
 */
export function useBotRun() {
  const [availability, setAvailability] = useState<BotAvailability>('loading');
  const [running, setRunning] = useState(false);
  const [starting, setStarting] = useState(false);
  const [lastRun, setLastRun] = useState<BotLastRun | null>(null);
  // Dua sumber pesan dipisah: gagal memuat status (hilang sendiri saat pulih)
  // dan gagal/ditolak saat menekan tombol (hilang sendiri setelah cooldown).
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  // Waktu (ms) tombol ditekan; null = tidak sedang menunggu run muncul.
  const triggeredAt = useRef<number | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await fetch(BOT_API_URL, { cache: 'no-store', signal });
      // Di dev lokal rute ini tidak ada dan server mengembalikan index.html.
      const isJson = (res.headers.get('content-type') ?? '').includes('application/json');
      if (!res.ok || !isJson) throw new Error(`HTTP ${res.status}`);

      const data = (await res.json()) as BotStatusResponse;
      if (!data.configured) {
        setAvailability('not_configured');
        return;
      }
      setAvailability('ready');
      setLoadError(null);
      setRunning(data.running);
      setLastRun(data.lastRun);

      const t = triggeredAt.current;
      if (t !== null && (hasRunAppeared(data, t) || Date.now() - t > BOT_START_TIMEOUT_MS)) {
        triggeredAt.current = null;
        setStarting(false);
      }
    } catch (err) {
      if (signal?.aborted) return;
      setAvailability('unreachable');
      setLoadError(err instanceof Error ? `Gagal memuat status bot (${err.message}).` : null);
    }
  }, []);

  const pollMs = running || starting ? BOT_POLL_ACTIVE_MS : BOT_POLL_IDLE_MS;

  useEffect(() => {
    const controller = new AbortController();
    const tick = () => {
      if (!document.hidden) void refresh(controller.signal);
    };
    tick();
    const timer = setInterval(tick, pollMs);
    document.addEventListener('visibilitychange', tick);
    return () => {
      controller.abort();
      clearInterval(timer);
      document.removeEventListener('visibilitychange', tick);
    };
  }, [refresh, pollMs]);

  const trigger = useCallback(async () => {
    // Penjaga sinkron: state React baru berubah setelah render, jadi dua klik
    // beruntun bisa lolos dari `disabled`. Ref ini langsung berlaku.
    if (triggeredAt.current !== null) return;
    setActionError(null);
    triggeredAt.current = Date.now();
    setStarting(true);

    const stopWaiting = () => {
      triggeredAt.current = null;
      setStarting(false);
    };

    try {
      const res = await fetch(BOT_API_URL, { method: 'POST' });
      if (res.status === 202) return; // polling cepat (starting) akan menangkap run barunya

      stopWaiting();
      const body = (await res.json().catch(() => ({}))) as { retryAfter?: number };
      if (res.status === 409) {
        setRunning(true); // sudah ada run lain (mis. cron); tombol terkunci lewat `running`
      } else if (res.status === 429) {
        const wait = body.retryAfter ?? 30;
        setActionError(`Tunggu ${wait} detik sebelum menjalankan lagi.`);
        setTimeout(() => setActionError(null), wait * 1000); // pesan basi setelah cooldown lewat
      } else if (res.status === 503) {
        setAvailability('not_configured');
      } else {
        setActionError(`Gagal menjalankan bot (HTTP ${res.status}).`);
      }
    } catch {
      stopWaiting();
      setActionError('Tidak dapat menghubungi server.');
    }
  }, []);

  const error = availability === 'unreachable' ? loadError : actionError;
  return { availability, running, starting, lastRun, error, trigger };
}
