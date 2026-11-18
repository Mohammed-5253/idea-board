"""Create the idea_revisions table (one row per successful edit of an idea).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14

Edits use optimistic concurrency: an idea's version is 1 + its number of revisions (the
ETag). Versions live here so `ideas` keeps exactly the spec columns. The primary key
(idea_id, version) makes "one winner per version" a database rule, so two concurrent edits
from the same ETag cannot both succeed. Insert-only history: the app role gets SELECT/INSERT
here through bootstrap's default privileges, and UPDATE on ideas.content only (granted below
to the roles that already write ideas, because bootstrap may have run before this migration).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Roles (other than the owner running the migration) that may INSERT into ideas = the app role.
_APP_ROLES = """
    SELECT DISTINCT grantee FROM information_schema.role_table_grants
    WHERE table_schema = 'public' AND table_name = 'ideas'
      AND privilege_type = 'INSERT' AND grantee <> current_user
"""


def upgrade() -> None:
    op.create_table(
        "idea_revisions",
        sa.Column("idea_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("previous_content", sa.Text(), nullable=False),
        sa.Column(
            "edited_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version >= 2", name="ck_idea_revisions_version"),
        sa.ForeignKeyConstraint(
            ["idea_id"], ["ideas.id"], name="fk_idea_revisions_idea_id_ideas", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("idea_id", "version", name="pk_idea_revisions"),
    )
    op.execute(f"""
        DO $$ DECLARE r record; BEGIN
          FOR r IN {_APP_ROLES} LOOP
            EXECUTE format('GRANT UPDATE (content) ON public.ideas TO %I', r.grantee);
          END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute(f"""
        DO $$ DECLARE r record; BEGIN
          FOR r IN {_APP_ROLES} LOOP
            EXECUTE format('REVOKE UPDATE (content) ON public.ideas FROM %I', r.grantee);
          END LOOP;
        END $$;
    """)
    op.drop_table("idea_revisions")
