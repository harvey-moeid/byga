import { useEffect, useState } from 'react';
import type { BotState } from '../types';

export type ConnectionStatus =
  | { kind: 'loading' }
  | { kind: 'ok' }
  | { kind: 'error'; message: string };

/**
 * Polling state.json tiap `intervalMs`.
 *
 * Keputusan penting:
 * - Kalau fetch gagal, data terakhir yang sukses TIDAK dihapus -- yang berubah
 *   hanya status koneksi. Lebih berguna melihat data lama + indikator merah
 *   daripada layar kosong karena koneksi putus sesaat.
 * - Cache-buster `?t=` + `cache: 'no-store'` supaya tidak dapat versi lama dari
 *   CDN/browser (raw.githubusercontent.com meng-cache respons beberapa menit).
 * - AbortController: saat URL diganti atau komponen unmount, request lama
 *   dibatalkan sehingga respons basi tidak menimpa data baru.
 */
export function useStateJson(url: string, intervalMs: number) {
  const [data, setData] = useState<BotState | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>({ kind: 'loading' });

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      try {
        // Base = halaman saat ini, sehingga URL relatif (mis. "./state.json" saat
        // dev/preview lokal) juga valid. Melempar error kalau URL rusak.
        const target = new URL(url, window.location.href);
        target.searchParams.set('t', String(Date.now()));

        const res = await fetch(target, { cache: 'no-store', signal: controller.signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        setData((await res.json()) as BotState);
        setStatus({ kind: 'ok' });
      } catch (err) {
        if (controller.signal.aborted) return; // dibatalkan oleh cleanup, bukan error sungguhan
        setStatus({
          kind: 'error',
          message: err instanceof Error ? err.message : String(err),
        });
      }
    }

    setStatus({ kind: 'loading' });
    void load();
    const timer = setInterval(() => void load(), intervalMs);

    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [url, intervalMs]);

  return { data, status };
}
