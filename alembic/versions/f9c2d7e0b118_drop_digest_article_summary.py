"""Drop digest_articles.summary_he — the summary lives on Article (issue #11
decision: DigestArticle references the article, it doesn't own the summary).

Revision ID: f9c2d7e0b118
Revises: e7a51b3c8d24
Create Date: 2026-07-20

"""

import sqlalchemy as sa

from alembic import op

revision = "f9c2d7e0b118"
down_revision = "e7a51b3c8d24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("digest_articles") as batch:
        batch.drop_column("summary_he")


def downgrade() -> None:
    with op.batch_alter_table("digest_articles") as batch:
        batch.add_column(sa.Column("summary_he", sa.Text(), nullable=True))
