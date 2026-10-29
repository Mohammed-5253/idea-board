# syntax=docker/dockerfile:1
# =============================================================================
# FILE: app/frontend/Dockerfile
# WHAT: Production image for the React SPA: static files served by unprivileged NGINX.
# SPEC: Part 2 – "Create a Dockerfile for your React frontend."
# HOW:  docker build -t idea-board-frontend ./app/frontend
#
# DESIGN (two stages, ADR-011/014):
#   build    node:24 LTS (Alpine) → `npm ci` (exact lockfile) → `npm run build`
#            (type-check + Vite bundle into dist/)
#   runtime  nginx-unprivileged 1.30 stable (Alpine) → only dist/ + config template.
#            No Node.js, no node_modules, no source in the final image (~tens of MB).
# RUNTIME CONFIG: env vars → /config.js and the NGINX config at START (not build), so the
#   SAME digest is promoted to every environment and cloud.
# SECURITY NOTE: digest-pinned bases; runs as UID 101 on port 8080 (no root, no
#   privileged port); security headers in nginx/default.conf.template.
# LEARN: docs/learning/12-containers-docker.md
# =============================================================================

ARG NODE_IMAGE=node:24.22.1-alpine@sha256:06d7adf3e0ef61a13f1d28682726366f97a15aa1888c934d3ecec86c33918b53
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.30.6-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03

# ---------------------------------------------------------------------------
# Stage 1: build the static bundle
# ---------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS build
WORKDIR /app
# Dependencies first (cached layer): changes to src/ don't trigger a reinstall.
# `npm ci` installs EXACTLY package-lock.json and fails if it is out of sync.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY . .
# `build` = `tsc --noEmit && vite build`: a type error fails the image build.
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: serve with NGINX (non-root)
# ---------------------------------------------------------------------------
FROM ${NGINX_IMAGE} AS runtime

LABEL org.opencontainers.image.title="idea-board-frontend" \
      org.opencontainers.image.description="Idea Board React SPA served by NGINX" \
      org.opencontainers.image.source="https://github.com/<owner>/idea-board" \
      org.opencontainers.image.licenses="UNLICENSED"

# Defaults for docker-compose. Kubernetes overlays override them via env.
# NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1 → the official entrypoint exports NGINX_LOCAL_RESOLVERS
# (nameservers from /etc/resolv.conf) for the `resolver` directive in our template.
ENV BACKEND_UPSTREAM=http://backend:8000 \
    API_BASE_URL="" \
    NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1

# SECURITY (found by Trivy, Phase 5): the base image ships curl/libcurl (HIGH CVEs) that we
# never use (health checks use busybox wget) → remove them. brotli-libs is needed by NGINX,
# so it is upgraded to the FIXED version, pinned explicitly (reproducible + auditable).
# IF a newer base digest already contains the fix THEN delete the pin (Trivy will show it).
USER 0
RUN apk del --no-cache curl \
 && apk add --no-cache "brotli-libs=1.2.1-r0"

# The official entrypoint renders /etc/nginx/templates/*.template → /etc/nginx/conf.d/.
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --chmod=0755 nginx/40-runtime-config.sh /docker-entrypoint.d/40-runtime-config.sh
COPY --from=build /app/dist /usr/share/nginx/html

# The base image already runs as UID 101 ("nginx"); stated explicitly for clarity and
# so Kubernetes `runAsNonRoot` can verify a numeric UID.
USER 101
EXPOSE 8080

# busybox `wget` exists in Alpine images – no extra package needed. JSON (exec) form: no
# shell wrapper (hadolint DL3025); wget's own non-zero exit marks the container unhealthy.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
