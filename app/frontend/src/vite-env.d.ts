/// <reference types="vite/client" />

/** Shape of the runtime configuration injected by /config.js (see index.html). */
interface AppRuntimeConfig {
  /** Optional absolute API origin. Empty string = same origin (recommended). */
  apiBaseUrl?: string;
}

interface Window {
  __APP_CONFIG__?: AppRuntimeConfig;
}
