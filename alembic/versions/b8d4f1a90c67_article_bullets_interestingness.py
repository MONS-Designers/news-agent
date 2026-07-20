"""Article bullets_he + interestingness (LLM contract extension)

Revision ID: b8d4f1a90c67
Revises: a3f6c9d1e442
Create Date: 2026-07-20

"""

import sqlalchemy as sa

from alembic import op

revision = "b8d4f1a90c67"
down_revision = "a3f6c9d1e442"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("bullets_he", sa.JSON(), nullable=True))
    op.add_column("articles", sa.Column("interestingness", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("articles", "interestingness")
    op.drop_column("articles", "bullets_he")
