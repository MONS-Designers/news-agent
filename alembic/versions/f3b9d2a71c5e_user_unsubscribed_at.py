"""User.unsubscribed_at: digest delivery opt-out (GH #46)

Revision ID: f3b9d2a71c5e
Revises: a2f7c8e1b4d9
Create Date: 2026-08-12

"""

import sqlalchemy as sa

from alembic import op

revision = "f3b9d2a71c5e"
down_revision = "a2f7c8e1b4d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("unsubscribed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "unsubscribed_at")
