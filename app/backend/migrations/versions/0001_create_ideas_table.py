"""Create the ideas table (spec: id, content, created_at).

Revision ID: 0001
Revises:
Create Date: 2026-10-28

The ONLY table the specification asks for. Column types approved in Phase 0 (Q13);
see src/idea_board/db/tables.py for the reasoning behind each choice.
A contract test asserts the live columns are exactly (id, content, created_at).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ideas",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(content) BETWEEN 1 AND 500", name="ck_ideas_content_length"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ideas"),
    )
    # Supports GET /api/ideas ordering (created_at DESC, id DESC); a B-tree is scanned
    # backwards for DESC, so ascending column order is fine.
    op.create_index("ix_ideas_created_at_id", "ideas", ["created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_ideas_created_at_id", table_name="ideas")
    op.drop_table("ideas")
