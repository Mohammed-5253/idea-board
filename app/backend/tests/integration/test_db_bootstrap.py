"""The app role created by db_bootstrap can read/insert ideas but cannot change the schema."""

from __future__ import annotations

import pytest
from pydantic import SecretStr
from sqlalchemy import Engine, text
from sqlalchemy.exc import ProgrammingError

from idea_board.core.secrets import DbCredentials
from idea_board.core.settings import Settings
from idea_board.db import repository
from idea_board.db.engine import create_db_engine
from idea_board.scripts.db_bootstrap import bootstrap, ensure_database

pytestmark = pytest.mark.integration


def test_least_privileged_app_role(
    pg_container: DbCredentials, clean_db: Engine, test_settings: Settings
) -> None:
    app_creds = DbCredentials(
        host=pg_container.host,
        port=pg_container.port,
        dbname=pg_container.dbname,
        user="ideas_app",
        password=SecretStr("app-pass"),
        sslmode="disable",
    )
    bootstrap(pg_container, app_creds)
    bootstrap(pg_container, app_creds)  # idempotent: second run must not fail

    app_engine = create_db_engine(app_creds, test_settings)
    try:
        created = repository.create_idea(app_engine, "from app role")
        assert repository.list_ideas(app_engine)[0]["id"] == created["id"]
        with (
            pytest.raises(ProgrammingError, match=r"permission denied|must be owner"),
            app_engine.begin() as conn,
        ):
            conn.execute(text("DROP TABLE ideas"))
        with pytest.raises(ProgrammingError, match="permission denied"), app_engine.begin() as conn:
            conn.execute(text("DELETE FROM ideas"))
    finally:
        app_engine.dispose()


def test_ensure_database_creates_missing_db_once(pg_container: DbCredentials) -> None:
    target = DbCredentials(
        host=pg_container.host,
        port=pg_container.port,
        dbname="ideas_staging_test",
        user=pg_container.user,
        password=pg_container.password,
        sslmode="disable",
    )
    assert ensure_database(target) is True  # first run creates it
    assert ensure_database(target) is False  # idempotent second run
