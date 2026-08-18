"""Article.summarize_attempts: bounded-retry counter for the terminal
"failed" summary_status (Epic C, Story C.1)

Revision ID: c961e3e70dbf
Revises: 9bb9befd45ff
Create Date: 2026-08-11

"""

import sqlalchemy as sa

from alembic import op

revision = "c961e3e70dbf"
down_revision = "9bb9befd45ff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("summarize_attempts", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("articles", "summarize_attempts")
