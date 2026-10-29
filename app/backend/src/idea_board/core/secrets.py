"""Database credentials provider: from environment variables OR from the Dapr secrets API.

WHAT:  Returns a `DbCredentials` value (host, port, dbname, user, password).
WHY:   This is THE place where Dapr makes the backend cloud-agnostic (ADR-018, ADR-020).
       The code below calls ONE local HTTP endpoint:
           GET http://localhost:3500/v1.0/secrets/secretstore/idea-board-db-app
       and the Dapr *component* behind the name "secretstore" is:
           local/compose  -> secretstores.local.file
           AWS            -> secretstores.aws.secretmanager (via IRSA)
           GCP            -> secretstores.gcp.secretmanager (via Workload Identity)
       The application never imports boto3 or google-cloud-*; switching clouds is a YAML
       change in deploy/ overlays, not a code change.
INPUTS: Settings (source, Dapr port/store/secret name, env fallbacks).
OUTPUTS: DbCredentials, or raises CredentialsError after the startup timeout.

IF the Dapr sidecar is not ready yet when we start (common: sidecar and app start in
   parallel) THEN we retry with exponential backoff up to `dapr_startup_timeout_s`,
   BUT we never crash-loop immediately - Kubernetes would mark the pod unhealthy for a
   race that resolves itself within seconds.
IF the secret is missing / malformed THEN we fail fast with a clear message (retrying
   cannot fix a wrong secret name).
SECURITY NOTE: the password is wrapped in SecretStr and never logged. We use the stdlib
   `urllib` (approved AD-12) so no extra HTTP client enters the runtime image.
ALTERNATIVE: the official Dapr Python SDK - nicer API, but another runtime dependency
   for a single GET request.
COMMON MISTAKE: forgetting `dapr.io/enabled: "true"` on the pod → connection refused on
   localhost:3500 → this module times out with "Dapr sidecar not reachable".
LEARN: docs/learning/10-backend-python-fastapi.md §5 (credentials), Dapr doc in Phase 4.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from pydantic import SecretStr

from idea_board.core.logging import get_logger
from idea_board.core.settings import CredentialsSource, Settings

log = get_logger(__name__)


class CredentialsError(RuntimeError):
    """Raised when database credentials cannot be obtained."""


@dataclass(frozen=True, slots=True)
class DbCredentials:
    """Everything needed to open a PostgreSQL connection. Immutable on purpose."""

    host: str
    port: int
    dbname: str
    user: str
    password: SecretStr
    sslmode: str


def load_db_credentials(settings: Settings) -> DbCredentials:
    """Return credentials from the configured source."""
    if settings.db_credentials_source is CredentialsSource.ENV:
        return DbCredentials(
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            sslmode=settings.db_sslmode,
        )
    secret = _fetch_dapr_secret(settings)
    return _credentials_from_secret(secret, settings)


def _fetch_dapr_secret(settings: Settings) -> dict[str, str]:
    """GET the secret from the local Dapr sidecar, retrying while it starts up."""
    store = urllib.parse.quote(settings.dapr_secret_store, safe="")
    name = urllib.parse.quote(settings.dapr_db_secret_name, safe="")
    # Always localhost: the sidecar shares the pod's (or compose service's) network namespace.
    url = f"http://127.0.0.1:{settings.dapr_http_port}/v1.0/secrets/{store}/{name}"

    deadline = time.monotonic() + settings.dapr_startup_timeout_s
    delay = 0.5
    attempt = 0
    while True:
        attempt += 1
        try:
            # S310 (bandit) flags urlopen because it accepts file:// URLs; ours is a fixed
            # http://127.0.0.1 URL built above, so the warning does not apply.
            with urllib.request.urlopen(url, timeout=3) as resp:
                body: Any = json.loads(resp.read().decode("utf-8"))
                if not isinstance(body, dict) or not body:
                    raise CredentialsError(f"Dapr returned an empty/invalid secret for '{name}'")
                return {str(k): str(v) for k, v in body.items()}
        except urllib.error.HTTPError as exc:
            # 4xx/5xx from Dapr = sidecar is up but the store/secret is wrong. Retrying is
            # pointless for 4xx; 5xx may be the cloud API being briefly unavailable.
            if exc.code < 500 or time.monotonic() >= deadline:
                raise CredentialsError(
                    f"Dapr secret lookup failed (HTTP {exc.code}) for store='{store}' "
                    f"secret='{name}'. Check the component and IAM permissions."
                ) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if time.monotonic() >= deadline:
                raise CredentialsError(
                    f"Dapr sidecar not reachable at 127.0.0.1:{settings.dapr_http_port} "
                    f"after {settings.dapr_startup_timeout_s:.0f}s ({exc})."
                ) from exc
        log.info("waiting_for_dapr_secret", attempt=attempt, retry_in_s=delay)
        time.sleep(delay)
        delay = min(delay * 2, 5.0)  # exponential backoff, capped


def _credentials_from_secret(secret: dict[str, str], settings: Settings) -> DbCredentials:
    """Normalise the two shapes a Dapr secret can have.

    Shape A (multi-key store, e.g. local.file with nested JSON, or K8s secrets):
        {"username": "...", "password": "...", "host": "...", "port": "5432", "dbname": "..."}
    Shape B (single-value stores, e.g. AWS Secrets Manager / GCP Secret Manager):
        {"idea-board-db-app": "{\"username\": \"...\", \"password\": \"...\", ...}"}
    Terraform writes the secret as a JSON document, so shape B is the JSON string.
    Missing keys fall back to the non-secret settings (host/port/dbname may be plain env).
    """
    data: dict[str, Any] = dict(secret)
    if "password" not in data and len(data) == 1:
        (only_value,) = data.values()
        try:
            parsed = json.loads(only_value)
        except json.JSONDecodeError as exc:
            raise CredentialsError("Secret value is not JSON with a 'password' key") from exc
        if not isinstance(parsed, dict):
            raise CredentialsError("Secret JSON must be an object")
        data = parsed

    if not data.get("password"):
        raise CredentialsError("Secret has no 'password' key")

    return DbCredentials(
        host=str(data.get("host", settings.db_host)),
        port=int(data.get("port", settings.db_port)),
        dbname=str(data.get("dbname", settings.db_name)),
        user=str(data.get("username", data.get("user", settings.db_user))),
        password=SecretStr(str(data["password"])),
        sslmode=str(data.get("sslmode", settings.db_sslmode)),
    )
