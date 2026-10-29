"""Create the least-privileged application role and grant it access to the `ideas` table.

WHAT:  Idempotently ensures that (1) the target DATABASE exists (created on first run -
       RDS/Cloud SQL instances start with only a maintenance database, and AWS has no API to
       create PostgreSQL databases), and (2) role `<app user>` exists with the app password and
       only CONNECT + USAGE + SELECT/INSERT on `ideas` (+ default privileges for future tables).
WHY:   Least privilege (ADR-020, architecture 03 §2): the API runs with a role that cannot
       DROP tables, ALTER schema, or read other databases. Only migrations/bootstrap use the
       OWNER role. IF the API is ever compromised THEN the blast radius is "read/insert ideas",
       not "destroy the database".
WHY a Job and not Terraform?  AWS has no API to create PostgreSQL roles inside RDS (GCP does),
       so we use this one SQL script on BOTH clouds for symmetry (ADR-040, R-3).
ORDER: runs BEFORE migrations (Argo CD PreSync wave -2) - grants for the table are applied
       via ALTER DEFAULT PRIVILEGES so they also cover the table that migrations create next,
       and are re-applied directly if the table already exists.

INPUTS (env vars):
  Owner connection: BOOTSTRAP_OWNER_* env vars or `.env` (or, in Dapr mode, the secret
                    named by DAPR_DB_OWNER_SECRET_NAME)
  App role:         the normal app credentials (DB_USER/DB_PASSWORD or the Dapr app secret)
HOW TO RUN: uv run idea-board-db-bootstrap
SECURITY NOTE: role and database names are passed through `psycopg.sql.Identifier` and the
       password through a bound literal - never string-formatted into SQL.
LEARN: docs/learning/10-backend-python-fastapi.md §4 (roles & least privilege)
"""

from __future__ import annotations

import sys

import psycopg
from psycopg import sql
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from idea_board.core.logging import configure_logging, get_logger
from idea_board.core.secrets import DbCredentials, load_db_credentials
from idea_board.core.settings import CredentialsSource, Settings

log = get_logger(__name__)


class OwnerSettings(BaseSettings):
    """Owner (DDL-capable) connection settings, read from env vars AND `.env` like Settings.

    Using pydantic-settings here (instead of os.environ) means the documented local
    workflow (`cp .env.example .env`) works for this script too.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    bootstrap_owner_user: str = ""
    bootstrap_owner_password: SecretStr = SecretStr("")
    bootstrap_owner_host: str | None = None  # default: same host as the app
    bootstrap_owner_port: int | None = None
    bootstrap_owner_db: str | None = None
    # Database used to run CREATE DATABASE (every PostgreSQL server has "postgres").
    bootstrap_maintenance_db: str = "postgres"
    # Dapr mode: the owner secret's name in the same secret store.
    dapr_db_owner_secret_name: str = "idea-board-db-owner"  # noqa: S105 (a name, not a password)


def _owner_credentials(app_settings: Settings, owner: OwnerSettings) -> DbCredentials:
    """Owner credentials: same source mechanism as the app, different secret/user."""
    if app_settings.db_credentials_source is CredentialsSource.DAPR:
        owner_app_settings = app_settings.model_copy(
            update={"dapr_db_secret_name": owner.dapr_db_owner_secret_name}
        )
        return load_db_credentials(owner_app_settings)
    if not owner.bootstrap_owner_user or not owner.bootstrap_owner_password.get_secret_value():
        raise ValueError("Set BOOTSTRAP_OWNER_USER and BOOTSTRAP_OWNER_PASSWORD (env or .env)")
    return DbCredentials(
        host=owner.bootstrap_owner_host or app_settings.db_host,
        port=owner.bootstrap_owner_port or app_settings.db_port,
        dbname=owner.bootstrap_owner_db or app_settings.db_name,
        user=owner.bootstrap_owner_user,
        password=owner.bootstrap_owner_password,
        sslmode=app_settings.db_sslmode,
    )


def _conninfo(creds: DbCredentials, dbname: str) -> str:
    return psycopg.conninfo.make_conninfo(
        host=creds.host,
        port=creds.port,
        dbname=dbname,
        user=creds.user,
        password=creds.password.get_secret_value(),
        sslmode=creds.sslmode,
        connect_timeout=10,
    )


def ensure_database(owner: DbCredentials, maintenance_db: str = "postgres") -> bool:
    """Create the owner's target database if missing. Returns True if it was created.

    CREATE DATABASE cannot run inside a transaction and has no IF NOT EXISTS in PostgreSQL,
    so we check pg_database first (idempotent) and use autocommit.
    IF two bootstrap Jobs race (e.g. a retried Job) THEN one gets "already exists" - we treat
    that as success.
    """
    with psycopg.connect(_conninfo(owner, maintenance_db), autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (owner.dbname,)
        ).fetchone()
        if exists:
            return False
        try:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(owner.dbname)))
        except psycopg.errors.DuplicateDatabase:
            return False
        log.info("database_created", database=owner.dbname)
        return True


def bootstrap(owner: DbCredentials, app: DbCredentials) -> None:
    """Run the idempotent role/grant SQL as the owner (the target database must exist)."""
    conninfo = _conninfo(owner, owner.dbname)
    role = sql.Identifier(app.user)
    with psycopg.connect(conninfo, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (app.user,)).fetchone()
        # CREATE/ALTER ROLE cannot take bind parameters for the password, so we build a
        # properly-quoted SQL literal with psycopg.sql.Literal (safe escaping, not f-strings).
        password = sql.Literal(app.password.get_secret_value())
        if exists:
            conn.execute(sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(role, password))
            log.info("app_role_updated", role=app.user)
        else:
            conn.execute(sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(role, password))
            log.info("app_role_created", role=app.user)

        conn.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(owner.dbname), role)
        )
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
        # Future tables created by the owner (i.e. by migrations) get SELECT/INSERT for the app.
        conn.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT ON TABLES TO {}"
            ).format(role)
        )
        # IF the ideas table already exists (re-run after migrations) THEN grant directly too.
        table_exists = conn.execute("SELECT to_regclass('public.ideas')").fetchone()
        if table_exists and table_exists[0] is not None:
            conn.execute(sql.SQL("GRANT SELECT, INSERT ON public.ideas TO {}").format(role))
        log.info("app_role_grants_applied", role=app.user, database=owner.dbname)


def main() -> int:
    settings = Settings()
    configure_logging(settings.log_level, settings.log_pretty)
    owner_settings = OwnerSettings()
    try:
        owner = _owner_credentials(settings, owner_settings)
        ensure_database(owner, owner_settings.bootstrap_maintenance_db)
        bootstrap(owner, load_db_credentials(settings))
    except Exception:
        log.exception("db_bootstrap_failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
