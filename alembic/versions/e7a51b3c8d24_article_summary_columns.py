"""Article summary columns: summary_he, title_he, source_language,
reading_time_minutes, summary_status

Revision ID: e7a51b3c8d24
Revises: c41d8e2f9a03
Create Date: 2026-07-20

"""

import sqlalchemy as sa

from alembic import op

revision = "e7a51b3c8d24"
down_revision = "c41d8e2f9a03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("summary_he", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("title_he", sa.String(), nullable=True))
    op.add_column("articles", sa.Column("source_language", sa.String(), nullable=True))
    op.add_column("articles", sa.Column("reading_time_minutes", sa.Integer(), nullable=True))
    op.add_column(
        "articles",
        sa.Column("summary_status", sa.String(), nullable=False, server_default="pending"),
    )


def downgrade() -> None:
    op.drop_column("articles", "summary_status")
    op.drop_column("articles", "reading_time_minutes")
    op.drop_column("articles", "source_language")
    op.drop_column("articles", "title_he")
    op.drop_column("articles", "summary_he")
