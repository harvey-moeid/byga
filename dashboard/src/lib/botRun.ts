/**
 * Logika murni untuk tombol "Jalankan Bot" (tanpa React, supaya mudah dites).
 * Kontrak API-nya ada di functions/api/bot.ts.
 */

export interface BotLastRun {
  status: string | null;
  conclusion: string | null;
  /** ISO 8601, kapan run dibuat. */
  createdAt: string;
  /** 'schedule' (cron) atau 'workflow_dispatch' (manual). */
  event: string;
  url: string;
}

/** Balasan GET /api/bot. */
export interface BotStatusResponse {
  configured: boolean;
  running: boolean;
  lastRun: BotLastRun | null;
}

export type BotAvailability = 'loading' | 'ready' | 'not_configured' | 'unreachable';

/**
 * Toleransi selisih jam antara browser dan GitHub saat membandingkan waktu
 * tombol ditekan dengan created_at run.
 */
const CLOCK_SKEW_MS = 10_000;

/**
 * Sesudah POST berhasil, run baru muncul di API GitHub beberapa detik kemudian.
 * Selama itu tombol tetap terkunci ("starting"). Fungsi ini menjawab: apakah
 * run yang kita minta sudah terlihat (sedang jalan, atau bahkan sudah selesai)
 * sehingga kunci boleh diserahkan ke status `running` dari server?
 */
export function hasRunAppeared(status: BotStatusResponse, triggeredAt: number): boolean {
  if (status.running) return true;
  return status.lastRun !== null && Date.parse(status.lastRun.createdAt) >= triggeredAt - CLOCK_SKEW_MS;
}

export interface BotUiInput {
  availability: BotAvailability;
  running: boolean;
  starting: boolean;
  error: string | null;
  /** Ringkasan run terakhir yang sudah diformat, atau null. */
  lastRunText: string | null;
}

export interface BotUi {
  title: string;
  detail: string;
  label: string;
  /** Tombol tidak bisa ditekan. Aturan utamanya: terkunci selama bot berjalan. */
  disabled: boolean;
  isError: boolean;
}

export function describeConclusion(conclusion: string | null): string {
  switch (conclusion) {
    case 'success':
      return 'berhasil';
    case 'failure':
    case 'timed_out':
      return 'gagal';
    case 'cancelled':
      return 'dibatalkan';
    default:
      return conclusion ?? 'belum selesai';
  }
}

export function describeBot(s: BotUiInput): BotUi {
  if (s.availability === 'loading') {
    return { title: 'Memeriksa status bot...', detail: '', label: 'Jalankan', disabled: true, isError: false };
  }
  if (s.availability === 'not_configured') {
    return {
      title: 'Belum dikonfigurasi',
      detail: 'Isi secret GH_DISPATCH_TOKEN di Cloudflare Pages (lihat dashboard/docs/RUN_BOT_BUTTON.md).',
      label: 'Jalankan',
      disabled: true,
      isError: false,
    };
  }
  if (s.availability === 'unreachable') {
    return {
      title: 'Tidak tersedia',
      detail: s.error ?? 'Endpoint /api/bot tidak dapat dihubungi (mode lokal tidak menjalankan Pages Function).',
      label: 'Jalankan',
      disabled: true,
      isError: true,
    };
  }
  if (s.running) {
    return {
      title: 'Bot sedang berjalan',
      detail: 'Tombol aktif lagi setelah run selesai.',
      label: 'Berjalan...',
      disabled: true,
      isError: false,
    };
  }
  if (s.starting) {
    return { title: 'Memulai run...', detail: 'Menunggu GitHub Actions menerima permintaan.', label: 'Memulai...', disabled: true, isError: false };
  }
  return {
    title: 'Siap dijalankan',
    detail: s.error ?? (s.lastRunText ? `Run terakhir: ${s.lastRunText}` : 'Belum ada riwayat run.'),
    label: 'Jalankan Sekarang',
    disabled: false,
    isError: s.error !== null,
  };
}
