"""Article filtering columns: rss_summary, relevance_score, relevance_status

Revision ID: c41d8e2f9a03
Revises: 7de791f6b76c
Create Date: 2026-07-20

"""

import sqlalchemy as sa

from alembic import op

revision = "c41d8e2f9a03"
down_revision = "7de791f6b76c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("rss_summary", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("relevance_score", sa.Float(), nullable=True))
    op.add_column(
        "articles",
        sa.Column("relevance_status", sa.String(), nullable=False, server_default="pending"),
    )


def downgrade() -> None:
    op.drop_column("articles", "relevance_status")
    op.drop_column("articles", "relevance_score")
    op.drop_column("articles", "rss_summary")
