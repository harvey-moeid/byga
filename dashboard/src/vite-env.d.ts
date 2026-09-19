/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL raw state.json. Diisi oleh workflow deploy (lihat .github/workflows/dashboard.yml). */
  readonly VITE_STATE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
