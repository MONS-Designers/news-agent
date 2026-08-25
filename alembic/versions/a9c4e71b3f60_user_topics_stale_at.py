"""users.topics_stale_at - profile edits diverging from saved topics

Revision ID: a9c4e71b3f60
Revises: f2b6d81a04c7
Create Date: 2026-08-23

"""

import sqlalchemy as sa

from alembic import op

revision = "a9c4e71b3f60"
down_revision = "f2b6d81a04c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("topics_stale_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "topics_stale_at")
