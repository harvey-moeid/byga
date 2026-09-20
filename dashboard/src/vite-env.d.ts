/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL raw state.json. Diisi oleh workflow deploy (lihat .github/workflows/dashboard.yml). */
  readonly VITE_STATE_URL?: string;
  /** Opsional. Endpoint tombol Jalankan Bot. Default '/api/bot' (Pages Function). */
  readonly VITE_BOT_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
