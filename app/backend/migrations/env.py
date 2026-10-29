"""Alembic runtime environment: how migrations connect to the database.

WHAT:  Called by `alembic upgrade/downgrade`. Builds the Engine from the SAME credentials
       mechanism as the app (core/secrets.py): env vars locally, Dapr secrets in compose/K8s.
WHY:   One credentials path for everything = fewer secrets, fewer surprises.
       The migrate Job simply points DAPR_DB_SECRET_NAME at the OWNER secret (migrations
       need DDL rights; the app role deliberately does not have them).
IF Alembic is invoked by tests with an existing connection (config.attributes["connection"])
THEN we reuse it, so tests can migrate a Testcontainers database without env vars.
LEARN: docs/learning/10-backend-python-fastapi.md §4
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import Connection

from idea_board.core.secrets import load_db_credentials
from idea_board.core.settings import Settings
from idea_board.db.engine import create_db_engine
from idea_board.db.tables import metadata

config = context.config
# Autogenerate (`alembic revision --autogenerate`) compares against this metadata.
target_metadata = metadata


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    existing = config.attributes.get("connection")
    if existing is not None:
        _run(existing)
        return
    settings = Settings()
    engine = create_db_engine(load_db_credentials(settings), settings)
    try:
        with engine.connect() as connection:
            _run(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    # Offline mode (`alembic upgrade head --sql`) renders SQL for review without a DB -
    # useful for DBAs and for the F5 risk reviewer to see exact DDL.
    context.configure(
        url="postgresql+psycopg://",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online()
