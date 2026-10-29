"""Shared pytest fixtures.

WHAT:  * `pg_engine` (session): starts ONE real PostgreSQL 17 container via Testcontainers,
         runs the Alembic migrations against it, and yields a SQLAlchemy Engine.
       * `clean_db` (function): empties the table between tests (isolation).
       * `client`: a FastAPI TestClient bound to that engine.
WHY a real database (not SQLite, not mocks)?  The SQL dialect, identity columns, CHECK
       constraints, timestamptz and role permissions are exactly what we must verify.
       SQLite would give false confidence (D-05).
REQUIRES: Docker running (Docker Desktop). IF Docker is not available THEN integration and
       contract tests are SKIPPED with a clear reason, and unit tests still run.
COMMON MISTAKE: "Cannot connect to the Docker daemon" → start Docker Desktop.
LEARN: docs/learning/10-backend-python-fastapi.md §7 (testing)
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, text

from idea_board.core.secrets import DbCredentials
from idea_board.core.settings import Settings
from idea_board.db.engine import create_db_engine
from idea_board.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = "postgres:17-alpine"  # same major version as RDS / Cloud SQL (ADR-013)


def _docker_available() -> bool:
    try:
        import docker  # transitive dependency of testcontainers

        docker.from_env().ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def pg_container() -> Iterator[DbCredentials]:
    if not _docker_available():
        pytest.skip("Docker is not running: integration/contract tests need Testcontainers")
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer(
        POSTGRES_IMAGE, username="owner", password="owner-pass", dbname="ideas"
    ) as pg:
        yield DbCredentials(
            host=pg.get_container_host_ip(),
            port=int(pg.get_exposed_port(5432)),
            dbname="ideas",
            user="owner",
            password=SecretStr("owner-pass"),
            sslmode="disable",
        )


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(app_env="ci", log_level="WARNING", db_pool_size=2, db_max_overflow=2)


def run_alembic(engine: Engine, action: str, target: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        getattr(command, action)(cfg, target)


@pytest.fixture(scope="session")
def pg_engine(pg_container: DbCredentials, test_settings: Settings) -> Iterator[Engine]:
    engine = create_db_engine(pg_container, test_settings)
    run_alembic(engine, "upgrade", "head")
    yield engine
    engine.dispose()


@pytest.fixture
def clean_db(pg_engine: Engine) -> Engine:
    with pg_engine.begin() as conn:
        conn.execute(text("TRUNCATE ideas RESTART IDENTITY"))
    return pg_engine


@pytest.fixture
def client(clean_db: Engine, test_settings: Settings) -> Iterator[TestClient]:
    app = create_app(test_settings, engine=clean_db)
    with TestClient(app) as c:  # `with` runs the lifespan (startup/shutdown)
        yield c
