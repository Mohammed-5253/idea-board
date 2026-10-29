/*
 * FILE: app/frontend/public/config.js
 * WHAT: DEFAULT runtime configuration, used by `npm run dev` and as the fallback in the image.
 * WHY:  In containers this file is REGENERATED at startup from environment variables
 *       (Phase 4 entrypoint), e.g. API_BASE_URL. An empty apiBaseUrl means "same origin":
 *       the app calls relative URLs like /api/ideas – the recommended setup everywhere.
 * IF the API is ever hosted on a different origin THEN set apiBaseUrl (and enable CORS on
 *    the backend – which is NOT approved/needed today).
 */
window.__APP_CONFIG__ = { apiBaseUrl: "" };
