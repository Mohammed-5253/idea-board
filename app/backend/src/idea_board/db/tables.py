"""The `ideas` table - exactly the columns the specification requires.

SPEC: "A PostgreSQL database with a single ideas table (id, content, created_at)."
      This module is the single Python definition of that table. Alembic migrations
      create it in the database; repository.py queries it. A contract test
      (tests/contract/test_schema_contract.py) fails the build if the real database
      ever has different columns.

Column choices (approved in Phase 0, Q13):
  id          BIGINT GENERATED ALWAYS AS IDENTITY  - the SQL-standard auto-increment;
              "ALWAYS" forbids clients from inserting their own ids (data integrity).
              ALTERNATIVE: UUID - globally unique, but bigger and unordered; overkill here.
  content     TEXT NOT NULL + CHECK length 1..500  - the API validates first, the database
              enforces it again (defence in depth: a buggy script cannot bypass the API rule).
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()   - timezone-aware, set by the DATABASE
              clock (one clock for all replicas and both clouds, no app-server skew).

An extra INDEX (not a column) supports the API's ordering "newest first". Indexes do not
change the table's columns, so the spec's schema is preserved.
SCALE NOTE: at 1000x data the GET "all ideas" query becomes the bottleneck (full scan +
       sort is avoided by the index, but the response size grows). The spec requires ALL
       ideas; optional pagination would be a separately-approved extra (Phase 0 Q15 deferred it).
LEARN: docs/learning/10-backend-python-fastapi.md §4
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Identity,
    Index,
    MetaData,
    Table,
    Text,
    func,
)

# Shared constant: the API schema and the DB CHECK constraint use the SAME limit.
CONTENT_MAX_LENGTH = 500

# Deterministic constraint names → Alembic autogenerate and future migrations stay stable
# across environments (unnamed constraints get random names per database).
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "pk": "pk_%(table_name)s",
    }
)

ideas = Table(
    "ideas",
    metadata,
    Column("id", BigInteger, Identity(always=True), primary_key=True),
    Column("content", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # database clock, see module docstring
    ),
    CheckConstraint(
        f"char_length(content) BETWEEN 1 AND {CONTENT_MAX_LENGTH}",
        name="content_length",
    ),
    # Matches ORDER BY created_at DESC, id DESC in repository.list_ideas().
    Index("ix_ideas_created_at_id", "created_at", "id"),
)
