"""Queries for the `ideas` table (the only place SQL is executed for the API).

WHY SQLAlchemy Core (not raw strings, not the full ORM):
  * Every value is sent as a bound PARAMETER, never concatenated into SQL text, so
    SQL injection is impossible by construction (capability requirement "safe database
    access"). e.g. content = "x'); DROP TABLE ideas;--" is stored literally as text.
  * Core is a thin, explicit layer - you can read exactly which SQL runs.
    ALTERNATIVE: the ORM (sessions, identity map) is unnecessary for one table.
TRANSACTIONS: `engine.begin()` opens a transaction and COMMITs on success / ROLLs BACK on
  exception. Reads use `engine.connect()` (no explicit write transaction needed).
LEARN: docs/learning/10-backend-python-fastapi.md §4
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from sqlalchemy import Engine, insert, select, text

from idea_board.db.tables import ideas


class IdeaRow(TypedDict):
    """One row of the ideas table, as returned to the API layer."""

    id: int
    content: str
    created_at: datetime


def list_ideas(engine: Engine) -> list[IdeaRow]:
    """Return ALL ideas, newest first (spec: "Returns a JSON array of all ideas").

    Ordering is not specified by the spec; we chose newest-first (Phase 0, Q10) and add
    `id DESC` as a tie-breaker so two ideas created in the same microsecond still have a
    deterministic order (stable tests, stable UI).
    """
    stmt = select(ideas.c.id, ideas.c.content, ideas.c.created_at).order_by(
        ideas.c.created_at.desc(), ideas.c.id.desc()
    )
    with engine.connect() as conn:
        return [
            IdeaRow(id=r.id, content=r.content, created_at=r.created_at) for r in conn.execute(stmt)
        ]


def create_idea(engine: Engine, content: str) -> IdeaRow:
    """Insert one idea and return the stored row (id and created_at come from the DB)."""
    stmt = (
        insert(ideas)
        .values(content=content)
        .returning(ideas.c.id, ideas.c.content, ideas.c.created_at)
    )
    with engine.begin() as conn:
        row = conn.execute(stmt).one()
    return IdeaRow(id=row.id, content=row.content, created_at=row.created_at)


def ping(engine: Engine) -> None:
    """Cheapest possible round-trip, used by /readyz. Raises on failure."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
