"""Topic.status and User.suggested_new_topic_names (Real Topic Suggestions)

Revision ID: a4b5c6d7e8f9
Revises: e5f6a7b8c9d0
Create Date: 2026-07-30

"""

import sqlalchemy as sa

from alembic import op

revision = "a4b5c6d7e8f9"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "topics",
        sa.Column("status", sa.String(), nullable=False, server_default="approved"),
    )
    op.add_column("users", sa.Column("suggested_new_topic_names", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "suggested_new_topic_names")
    op.drop_column("topics", "status")
