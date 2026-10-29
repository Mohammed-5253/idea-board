/**
 * Runtime configuration accessor.
 *
 * WHY a function (not a constant)?  Tests can change `window.__APP_CONFIG__` between cases,
 * and the value is read when a request is made – never frozen at import time.
 * IF /config.js failed to load THEN we fall back to same-origin, which is correct for
 * every approved deployment (local proxy, Envoy Gateway on both clouds).
 */
export function apiBaseUrl(): string {
  const configured = window.__APP_CONFIG__?.apiBaseUrl ?? "";
  // Strip a trailing slash so `${base}/api/ideas` never becomes `//api/ideas`.
  return configured.replace(/\/+$/, "");
}
