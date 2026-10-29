"""Seed data: inserts samples into an empty table, is idempotent, refuses staging/prod."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, func, select

from idea_board.core.secrets import DbCredentials
from idea_board.db.tables import ideas
from idea_board.scripts import seed

pytestmark = pytest.mark.integration


def _env(monkeypatch: pytest.MonkeyPatch, c: DbCredentials, app_env: str = "local") -> None:
    for k, v in {
        "APP_ENV": app_env,
        "DB_HOST": c.host,
        "DB_PORT": str(c.port),
        "DB_NAME": c.dbname,
        "DB_USER": c.user,
        "DB_PASSWORD": c.password.get_secret_value(),
        "DB_SSLMODE": "disable",
    }.items():
        monkeypatch.setenv(k, v)


def _count(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(ideas)).scalar_one())


def test_seed_inserts_once(
    monkeypatch: pytest.MonkeyPatch, pg_container: DbCredentials, clean_db: Engine
) -> None:
    _env(monkeypatch, pg_container)
    assert seed.main() == 0
    assert _count(clean_db) == len(seed.SAMPLE_IDEAS)
    assert seed.main() == 0  # second run: skipped, no duplicates
    assert _count(clean_db) == len(seed.SAMPLE_IDEAS)


def test_seed_refuses_prod(
    monkeypatch: pytest.MonkeyPatch, pg_container: DbCredentials, clean_db: Engine
) -> None:
    _env(monkeypatch, pg_container, app_env="prod")
    assert seed.main() == 1
    assert _count(clean_db) == 0
