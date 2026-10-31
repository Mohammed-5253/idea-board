"""Typed application settings, read from environment variables (12-factor, factor III).

WHAT:  One immutable `Settings` object holding every configurable value of the backend.
WHY:   The same container image must run locally, on AWS and on GCP (ADR "build once,
       promote the digest"). Anything that differs between environments therefore comes
       from the ENVIRONMENT, never from code or from files baked into the image.
INPUTS: environment variables (optionally a local `.env` file for developer convenience).
OUTPUTS: a validated `Settings` instance; the app refuses to start on invalid config
       (fail fast at boot instead of failing on the first request at 3 a.m.).
HOW TO TEST: tests/unit/test_settings.py

SECURITY NOTE: secrets (the DB password) are `SecretStr`, so they never appear in
       `repr()`, logs or tracebacks. In the cloud the DB_* values come from a Kubernetes
       Secret written by terraform, never from Git.
ALTERNATIVE: plain `os.environ[...]` - no types, no validation, typos found at runtime.
LEARN: docs/learning/10-backend-python-fastapi.md §5, §6 (settings walkthrough)
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Field names map to UPPER_CASE env vars automatically."""

    # `extra="ignore"`: the container environment contains many unrelated variables
    # (PATH, KUBERNETES_*, …); we must not crash on them.
    # `frozen=True`: settings are read once at startup and never mutated at runtime.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    # --- General ---------------------------------------------------------------
    app_env: str = Field(default="local", description="local | ci | staging | prod | preview")
    log_level: str = Field(default="INFO", description="DEBUG | INFO | WARNING | ERROR")
    # When true, logs are rendered human-friendly instead of JSON (local terminal only).
    # PRODUCTION NOTE: keep false in every deployed environment; the OTel Collector and
    # the F1 AI health analyst both expect one JSON object per line.
    log_pretty: bool = False

    # --- Database connection (DB_* env vars) -----------------------------------------
    db_host: str = "localhost"
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "ideas"
    db_user: str = "ideas_app"
    db_password: SecretStr = SecretStr("")
    # TLS to PostgreSQL. `prefer` locally (the dev container has no TLS);
    # IF deployed to RDS / Cloud SQL THEN the terraform-written Secret sets `require`
    # (both enforce TLS).
    # PRODUCTION NOTE: `verify-full` + the provider CA bundle is the hardened setting.
    db_sslmode: str = Field(
        default="prefer", pattern="^(disable|prefer|require|verify-ca|verify-full)$"
    )

    # --- Connection pool (D-35, ADR-013) ---------------------------------------------
    # SCALE NOTE: total DB connections = replicas x (pool_size + max_overflow).
    # It must stay below the server's max_connections (≈ 80-100 on micro tiers).
    # At 2-4 replicas x 10 = 40 connections we are safe; beyond that → PgBouncer.
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    db_pool_timeout_s: float = Field(default=5.0, gt=0)
    # Server-side guard: any single statement is cancelled after this many milliseconds,
    # so a slow query cannot pin a pool connection forever.
    db_statement_timeout_ms: int = Field(default=5000, ge=100)
    db_connect_timeout_s: int = Field(default=5, ge=1)

    # --- Demo fault injection (ADR-038, approved non-breaking extra) -----------------
    # Fraction (0..1) of /api/* requests that deliberately return HTTP 500.
    # Default 0 = OFF, so normal behaviour matches the spec exactly. Only the investor
    # demo's "bad release" sets it, so the deterministic health gate trips and rolls back.
    # SECURITY NOTE: harmless by design (no data change), but the admission/CI policy
    # rejects non-zero values in prod overlays except the explicitly-labelled demo release.
    fault_injection_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    # Image tag baked in by CI (Dockerfile ARG APP_VERSION); "dev" for local runs.
    app_version: str = "dev"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings (read from the environment exactly once).

    `lru_cache` makes this a cheap singleton; tests bypass it by constructing
    `Settings(...)` directly and passing it to `create_app(settings)`.
    """
    return Settings()
