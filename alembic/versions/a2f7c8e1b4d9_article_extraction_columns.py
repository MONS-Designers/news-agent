"""Article.extraction_status/extraction_attempts: full-text extraction
tracking with a bounded-retry terminal state (Epic D, Story D.1)

Revision ID: a2f7c8e1b4d9
Revises: c961e3e70dbf
Create Date: 2026-08-12

"""

import sqlalchemy as sa

from alembic import op

revision = "a2f7c8e1b4d9"
down_revision = "c961e3e70dbf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("extraction_status", sa.String(), nullable=False, server_default="pending"),
    )
    op.add_column(
        "articles",
        sa.Column("extraction_attempts", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("articles", "extraction_attempts")
    op.drop_column("articles", "extraction_status")
