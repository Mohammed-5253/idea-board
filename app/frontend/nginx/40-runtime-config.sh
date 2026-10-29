#!/bin/sh
# =============================================================================
# FILE: app/frontend/nginx/40-runtime-config.sh
#       (copied to /docker-entrypoint.d/; the official NGINX entrypoint runs every
#        executable script there, in name order, BEFORE starting nginx)
# WHAT: Writes /tmp/runtime-config/config.js from environment variables.
# WHY:  Runtime (not build-time) configuration – the SAME image digest runs on local,
#       AWS and GCP; only env vars differ (learning doc 11 §5).
# INPUT: API_BASE_URL – optional absolute origin; empty = same origin (recommended).
# SECURITY NOTE: the value is embedded in JavaScript, so it is VALIDATED against a strict
#   character allowlist first. IF someone sets API_BASE_URL='"};alert(1);//' THEN the
#   container refuses to start instead of serving injected script.
# =============================================================================
set -eu

OUT_DIR=/tmp/runtime-config
API_BASE_URL="${API_BASE_URL:-}"

case "$API_BASE_URL" in
  "" ) ;;
  http://*|https://* )
    # Allow only URL-safe characters (no quotes, spaces, semicolons, angle brackets).
    if printf '%s' "$API_BASE_URL" | grep -Eq '[^A-Za-z0-9._~:/?#@!$&()*+,=%-]'; then
      echo "40-runtime-config: API_BASE_URL contains forbidden characters" >&2; exit 1
    fi ;;
  * ) echo "40-runtime-config: API_BASE_URL must start with http:// or https://" >&2; exit 1 ;;
esac

mkdir -p "$OUT_DIR"
printf 'window.__APP_CONFIG__ = { apiBaseUrl: "%s" };\n' "$API_BASE_URL" > "$OUT_DIR/config.js"
echo "40-runtime-config: wrote $OUT_DIR/config.js (apiBaseUrl='${API_BASE_URL}')"
