"""SQLAlchemy Engine (connection pool) construction.

WHAT:  Builds one Engine per process from DbCredentials + pool settings.
WHY:   Opening a PostgreSQL connection costs a TCP + TLS handshake + authentication
       (tens of ms, more across clouds). A POOL keeps a few connections open and lends
       them to requests. One engine per process is the SQLAlchemy best practice.
DRIVER: psycopg 3 (`postgresql+psycopg://`), the official PostgreSQL adapter (ADR-012).

Key settings and the WHY behind each:
  pool_pre_ping=True     IF a connection died (DB failover, RDS maintenance, idle timeout
                         on a NAT/LB) THEN SQLAlchemy detects it before use and reconnects,
                         BUT it costs one tiny round-trip per checkout - worth it.
  pool_recycle=1800      Recycle connections after 30 min: avoids silent drops by network
                         middleboxes and picks up rotated passwords on reconnect.
  statement_timeout      Server-side cap per statement (Settings.db_statement_timeout_ms).
  timezone=UTC           created_at is always serialised in UTC regardless of server config.
  application_name       Shows up in pg_stat_activity → you can see which service holds
                         which connections when debugging pool exhaustion.

SECURITY NOTE: `URL.create` escapes special characters in the password (no string
       formatting of credentials into a DSN - a classic injection/escaping bug).
COMMON MISTAKE: creating an Engine per request → connection storm → "too many clients".
LEARN: docs/learning/10-backend-python-fastapi.md §4 (pools)
"""

from __future__ import annotations

from sqlalchemy import URL, Engine, create_engine

from idea_board.core.secrets import DbCredentials
from idea_board.core.settings import Settings


def build_url(creds: DbCredentials) -> URL:
    """Return a SQLAlchemy URL for psycopg 3 (password safely escaped)."""
    return URL.create(
        drivername="postgresql+psycopg",
        username=creds.user,
        password=creds.password.get_secret_value(),
        host=creds.host,
        port=creds.port,
        database=creds.dbname,
    )


def create_db_engine(creds: DbCredentials, settings: Settings) -> Engine:
    """Create the process-wide Engine (does NOT connect yet - connections are lazy)."""
    return create_engine(
        build_url(creds),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_s,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={
            "sslmode": creds.sslmode,
            "connect_timeout": settings.db_connect_timeout_s,
            "application_name": "idea-board-backend",
            # libpq "options": per-session server settings.
            "options": f"-c statement_timeout={settings.db_statement_timeout_ms} -c timezone=UTC",
        },
    )
