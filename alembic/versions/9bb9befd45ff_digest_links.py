"""digest_links table for click tracking on sent digests (FR12)

Revision ID: 9bb9befd45ff
Revises: 702337f56a9b
Create Date: 2026-08-11

"""

import sqlalchemy as sa

from alembic import op

revision = "9bb9befd45ff"
down_revision = "702337f56a9b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "digest_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("digest_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("clicked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["digest_id"], ["digests.id"]),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_digest_links_token"),
        sa.UniqueConstraint("digest_id", "kind", "article_id", name="uq_digest_links_digest_kind_article"),
    )


def downgrade() -> None:
    op.drop_table("digest_links")
