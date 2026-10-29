"""Migrations must round-trip: downgrade to base and upgrade to head again."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, inspect

from tests.conftest import run_alembic

pytestmark = pytest.mark.integration


def test_downgrade_then_upgrade_round_trip(pg_engine: Engine) -> None:
    run_alembic(pg_engine, "downgrade", "base")
    assert "ideas" not in inspect(pg_engine).get_table_names()
    run_alembic(pg_engine, "upgrade", "head")
    assert "ideas" in inspect(pg_engine).get_table_names()
