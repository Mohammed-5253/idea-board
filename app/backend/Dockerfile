# syntax=docker/dockerfile:1
# =============================================================================
# FILE: app/backend/Dockerfile
# WHAT: Production image for the Idea Board API (FastAPI + Uvicorn), also used for the
#       one-shot jobs (db-bootstrap, migrate, seed) – one image, several commands.
# SPEC: Part 2 – "Create a Dockerfile for your Python backend."
# HOW:  docker build -t idea-board-backend ./app/backend
#       docker buildx build --platform linux/amd64,linux/arm64 ...   (multi-arch, Phase 5 CI)
#
# DESIGN (two stages, ADR-014):
#   builder  python:3.13-slim + uv → resolves the locked dependencies into /app/.venv
#   runtime  python:3.13-slim + ONLY the venv, migrations and alembic.ini
#            → no uv, no compiler, no cache, no tests, no source tree in the final image.
# WHY NOT ALPINE? musl libc: many Python wheels are glibc-only → slow source builds and
#   subtle bugs (D-07). Debian slim keeps glibc with a small footprint.
# SECURITY NOTE: base images pinned by DIGEST (immutable) + tag (readable). Dependabot
#   (Phase 5) proposes digest bumps as reviewed PRs. Runs as non-root UID 10001.
# ALTERNATIVE: distroless python (no shell, smaller attack surface) – documented as the
#   production hardening step; debugging without a shell is harder.
# LEARN: docs/learning/12-containers-docker.md
# =============================================================================

ARG PYTHON_IMAGE=python:3.13-slim@sha256:2d44738ebf4ce5f63b9d9ea871e9c7cfdc0426f7b0c97cac915fd88ded1d86bb
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff

# ---------------------------------------------------------------------------
# Stage 0: the uv binary (copied, never installed with pip → exact, verified version)
# ---------------------------------------------------------------------------
FROM ${UV_IMAGE} AS uv

# ---------------------------------------------------------------------------
# Stage 1: builder – create the virtual environment from uv.lock
# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS builder
COPY --from=uv /uv /usr/local/bin/uv

# UV_COMPILE_BYTECODE: pre-compile .pyc at build time → faster container start.
# UV_LINK_MODE=copy: the cache is a separate mount, hard links across mounts don't work.
# UV_PYTHON_DOWNLOADS=never: use the image's Python; never download another interpreter.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Layer 1: dependencies only. Copying just the lockfile + pyproject first means this slow
# layer is cached until dependencies change – editing source code does NOT reinstall deps.
# --mount=type=cache keeps uv's download cache on the BUILD HOST, not in the image.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

# Layer 2: the project itself, installed NON-editable (a normal wheel inside the venv),
# so the runtime stage needs no source tree.
# COMMON MISTAKE: `uv sync` without --frozen silently re-resolves → image ≠ tested lock.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---------------------------------------------------------------------------
# Stage 2: runtime – minimal, non-root
# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

# OCI labels: provenance metadata visible in registries and `docker inspect`.
LABEL org.opencontainers.image.title="idea-board-backend" \
      org.opencontainers.image.description="Idea Board REST API (FastAPI)" \
      org.opencontainers.image.source="https://github.com/<owner>/idea-board" \
      org.opencontainers.image.licenses="UNLICENSED"

# PYTHONDONTWRITEBYTECODE: no .pyc writes at runtime (read-only root filesystem in K8s).
# PYTHONUNBUFFERED: logs reach stdout immediately (no lost lines on crash).
# PATH: the venv first, so `uvicorn`, `alembic`, `idea-board-seed` resolve without activation.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

# Fixed numeric UID/GID: Kubernetes `runAsNonRoot` can verify a NUMERIC user; 10001 avoids
# colliding with host users (UID 1000 is often a real developer account).
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
 # SECURITY (found by Trivy, Phase 5): the base image's own `pip` vendors msgpack/urllib3
 # and ships setuptools via ensurepip – HIGH CVEs in code our app never runs. The runtime
 # needs no package manager at all (deps are already in /app/.venv), so remove it:
 # smaller attack surface, zero findings. IF you need pip for debugging THEN use the
 # builder stage (`docker build --target builder`), not production images.
 && python -m pip uninstall --yes pip \
 && rm -rf /usr/local/lib/python3.13/ensurepip

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
# Migrations ship with the image so the SAME artifact migrates every environment.
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations

# Image tag passed by CI (--build-arg APP_VERSION=<tag>); served at GET /api/version.
# Declared late so a new tag only rebuilds this tiny layer, not the dependency layers.
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

USER 10001:10001
EXPOSE 8000

# Docker-level health check (used by docker-compose `depends_on: service_healthy`).
# Kubernetes ignores HEALTHCHECK and uses its own probes (/healthz, /readyz) instead.
# No curl in slim images → a one-line stdlib Python request (no extra package).
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=2).status == 200 else 1)"]

# Exec form (JSON array): Uvicorn is PID 1 and receives SIGTERM directly → graceful
# shutdown (in-flight requests finish, the DB pool is disposed).
# --proxy-headers / --forwarded-allow-ips: trust X-Forwarded-* from the gateway in front.
# SECURITY NOTE: '*' is acceptable because the pod is only reachable through Envoy/nginx
#   (NetworkPolicy); IF exposed directly THEN restrict to the proxy's IP range.
CMD ["uvicorn", "idea_board.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--timeout-graceful-shutdown", "20"]
