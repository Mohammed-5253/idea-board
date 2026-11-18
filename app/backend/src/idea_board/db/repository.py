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

from sqlalchemy import Engine, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from idea_board.db.tables import idea_revisions, ideas


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


class IdeaNotFound(Exception):
    """No idea with that id."""


class VersionMismatch(Exception):
    """The caller's version is not the idea's current version (someone else edited it)."""


def _version(idea_id: object):  # noqa: ANN202 - SQL expression
    """Current version of an idea: 1 + number of edits."""
    return (
        select(func.coalesce(func.max(idea_revisions.c.version), 1))
        .where(idea_revisions.c.idea_id == idea_id)
        .scalar_subquery()
    )


def get_idea(engine: Engine, idea_id: int) -> tuple[IdeaRow, int] | None:
    """Return (idea, current version), or None when it does not exist."""
    stmt = select(
        ideas.c.id, ideas.c.content, ideas.c.created_at, _version(ideas.c.id).label("version")
    ).where(ideas.c.id == idea_id)
    with engine.connect() as conn:
        r = conn.execute(stmt).one_or_none()
    if r is None:
        return None
    return IdeaRow(id=r.id, content=r.content, created_at=r.created_at), r.version


def edit_idea(
    engine: Engine, idea_id: int, content: str, expected_version: int | None
) -> tuple[IdeaRow, int]:
    """Replace an idea's content if it is still at `expected_version`; return (idea, new version).

    The row lock serialises edits of one idea, and the (idea_id, version) primary key is the
    final guard: two edits from the same version can never both commit.
    expected_version None = the caller sent no usable precondition (checked after existence).
    """
    try:
        with engine.begin() as conn:
            row = conn.execute(
                select(ideas.c.content).where(ideas.c.id == idea_id).with_for_update()
            ).one_or_none()
            if row is None:
                raise IdeaNotFound
            current = conn.execute(select(_version(idea_id))).scalar_one()
            if expected_version != current:
                raise VersionMismatch
            conn.execute(
                insert(idea_revisions).values(
                    idea_id=idea_id, version=current + 1, previous_content=row.content
                )
            )
            r = conn.execute(
                update(ideas)
                .where(ideas.c.id == idea_id)
                .values(content=content)
                .returning(ideas.c.id, ideas.c.content, ideas.c.created_at)
            ).one()
    except IntegrityError as exc:  # lost the race on (idea_id, version)
        raise VersionMismatch from exc
    return IdeaRow(id=r.id, content=r.content, created_at=r.created_at), current + 1


def ping(engine: Engine) -> None:
    """Cheapest possible round-trip, used by /readyz. Raises on failure."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
