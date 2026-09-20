/**
 * Cloudflare Pages Function -- rute /api/bot
 *
 * Jembatan antara dashboard (statis, publik) dan GitHub Actions:
 *   GET  /api/bot  -> apakah workflow bot sedang berjalan
 *   POST /api/bot  -> jalankan workflow bot sekarang (workflow_dispatch)
 *
 * Keputusan desain:
 * - Kenapa lewat function, bukan langsung dari browser: memanggil API dispatch
 *   butuh token dengan izin Actions write, dan isi bundle JS dashboard terbaca
 *   siapa pun. Token hanya hidup sebagai secret Pages (GH_DISPATCH_TOKEN) dan
 *   tidak pernah dikirim ke browser.
 * - Endpoint ini sengaja TANPA login, jadi pengamannya ada di sisi server:
 *   (1) POST hanya diterima dari origin yang sama dengan dashboard,
 *   (2) POST ditolak selama ada run yang belum selesai (409) -- ini juga
 *       yang membuat tombol di UI tidak bisa ditekan saat bot berjalan,
 *   (3) cooldown COOLDOWN_SECONDS sejak run terakhir dibuat (429).
 *   Kalau endpoint disalahgunakan, dampak terburuknya bot jalan lebih sering:
 *   run_bot.py idempotent (pakai fetch_cursor), jadi tidak ada sinyal ganda.
 *   Untuk kunci yang lebih ketat, taruh project Pages di belakang Cloudflare
 *   Access (lihat docs/RUN_BOT_BUTTON.md).
 * - Detail error dari GitHub tidak diteruskan ke browser, hanya kode status.
 */

interface Env {
  /** Secret. Fine-grained PAT untuk repo bot dengan izin Actions: read & write. */
  GH_DISPATCH_TOKEN?: string;
  /** Opsional. Default 'harvey-moeid/byga'. */
  GH_REPO?: string;
  /** Opsional. Nama file workflow. Default 'trading-bot.yml'. */
  GH_WORKFLOW?: string;
  /** Opsional. Branch yang dijalankan. Default 'main'. */
  GH_REF?: string;
}

interface Context {
  request: Request;
  env: Env;
}

interface WorkflowRun {
  status: string | null;
  conclusion: string | null;
  created_at: string;
  html_url: string;
  event: string;
}

const DEFAULTS = { repo: 'harvey-moeid/byga', workflow: 'trading-bot.yml', ref: 'main' };
const COOLDOWN_SECONDS = 30;
/** Bot berjalan dengan concurrency 1 (maks 1 running + 1 pending), 10 run terakhir lebih dari cukup. */
const RUNS_LOOKBACK = 10;

class GitHubError extends Error {
  status: number;
  constructor(status: number) {
    super(`GitHub API ${status}`);
    this.status = status;
  }
}

function settings(env: Env) {
  return {
    repo: env.GH_REPO || DEFAULTS.repo,
    workflow: env.GH_WORKFLOW || DEFAULTS.workflow,
    ref: env.GH_REF || DEFAULTS.ref,
  };
}

function reply(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    // no-store: status harus selalu segar, jangan sampai di-cache CDN/browser.
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...headers },
  });
}

async function github(env: Env, path: string, method: 'GET' | 'POST' = 'GET', body?: unknown): Promise<Response> {
  const headers: Record<string, string> = {
    Accept: 'application/vnd.github+json',
    Authorization: `Bearer ${env.GH_DISPATCH_TOKEN}`,
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'byga-dashboard', // GitHub API menolak request tanpa User-Agent
  };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  return fetch(`https://api.github.com${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function listRuns(env: Env): Promise<WorkflowRun[]> {
  const { repo, workflow } = settings(env);
  const res = await github(env, `/repos/${repo}/actions/workflows/${encodeURIComponent(workflow)}/runs?per_page=${RUNS_LOOKBACK}`);
  if (!res.ok) throw new GitHubError(res.status);
  const data = (await res.json()) as { workflow_runs?: WorkflowRun[] };
  return data.workflow_runs ?? [];
}

function summarize(runs: WorkflowRun[]) {
  // Belum 'completed' berarti masih antre / berjalan (queued, in_progress, waiting, ...).
  // Berlaku untuk run dari cron maupun manual -- keduanya sama-sama mengunci tombol.
  const running = runs.some((r) => r.status !== 'completed');
  const latest = runs[0];
  return {
    running,
    lastRun: latest
      ? { status: latest.status, conclusion: latest.conclusion, createdAt: latest.created_at, event: latest.event, url: latest.html_url }
      : null,
  };
}

function upstreamFailure(err: unknown): Response {
  const status = err instanceof GitHubError ? err.status : 0;
  return reply({ ok: false, error: 'github_error', status }, 502);
}

export const onRequestGet = async ({ env }: Context): Promise<Response> => {
  // 200 + configured:false (bukan error) supaya UI bisa menampilkan petunjuk setup dengan tenang.
  if (!env.GH_DISPATCH_TOKEN) return reply({ configured: false, running: false, lastRun: null });
  try {
    return reply({ configured: true, ...summarize(await listRuns(env)) });
  } catch (err) {
    return upstreamFailure(err);
  }
};

export const onRequestPost = async ({ request, env }: Context): Promise<Response> => {
  if (!env.GH_DISPATCH_TOKEN) return reply({ ok: false, error: 'not_configured' }, 503);

  // Browser selalu mengirim Origin pada POST. Menolak origin lain menahan situs
  // pihak ketiga memicu bot lewat browser pengunjung.
  if (request.headers.get('Origin') !== new URL(request.url).origin) {
    return reply({ ok: false, error: 'forbidden_origin' }, 403);
  }

  try {
    const runs = await listRuns(env);

    if (summarize(runs).running) return reply({ ok: false, error: 'already_running', running: true }, 409);

    const latest = runs[0];
    if (latest) {
      const ageSeconds = (Date.now() - Date.parse(latest.created_at)) / 1000;
      if (ageSeconds < COOLDOWN_SECONDS) {
        const retryAfter = Math.ceil(COOLDOWN_SECONDS - ageSeconds);
        return reply({ ok: false, error: 'cooldown', retryAfter }, 429, { 'Retry-After': String(retryAfter) });
      }
    }

    const { repo, workflow, ref } = settings(env);
    const res = await github(env, `/repos/${repo}/actions/workflows/${encodeURIComponent(workflow)}/dispatches`, 'POST', { ref });
    if (res.status !== 204) throw new GitHubError(res.status); // sukses = 204 No Content
    return reply({ ok: true }, 202);
  } catch (err) {
    return upstreamFailure(err);
  }
};

/** Method lain (PUT, DELETE, ...) tidak dipakai. */
export const onRequest = async (): Promise<Response> =>
  reply({ ok: false, error: 'method_not_allowed' }, 405, { Allow: 'GET, POST' });
