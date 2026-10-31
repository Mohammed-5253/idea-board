"""Database credentials provider: from environment variables.

WHAT:  Returns a `DbCredentials` value (host, port, dbname, user, password, sslmode).
WHY:   One small seam between settings and the DB layer, used by the app, Alembic
       (migrations/env.py) and db-bootstrap.
INPUTS: Settings (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_SSLMODE).
       Locally docker-compose sets them; on EKS/GKE they come from the Kubernetes Secrets
       `backend-db` / `db-migrate`, written by terraform (modules/common/app-db-secret).
OUTPUTS: DbCredentials, or raises CredentialsError when no password is set.
SECURITY NOTE: the password is wrapped in SecretStr and never logged.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import SecretStr

from idea_board.core.settings import Settings


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
    """Return credentials from the settings (env vars); fail fast without a password."""
    if not settings.db_password.get_secret_value():
        raise CredentialsError("DB_PASSWORD is not set")
    return DbCredentials(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        sslmode=settings.db_sslmode,
    )
