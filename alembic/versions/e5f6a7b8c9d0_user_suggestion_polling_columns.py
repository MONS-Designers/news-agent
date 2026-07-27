"""User suggestion polling columns (Story 1.6)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-27

"""

import sqlalchemy as sa

from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("suggestion_status", sa.String(), nullable=False, server_default="none"),
    )
    op.add_column("users", sa.Column("suggested_topic_ids", sa.JSON(), nullable=True))
    op.add_column(
        "users",
        sa.Column("suggestion_request_seq", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "suggestion_request_seq")
    op.drop_column("users", "suggested_topic_ids")
    op.drop_column("users", "suggestion_status")
