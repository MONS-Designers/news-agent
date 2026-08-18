"""User.interest_free_text (Story 1.4)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-27

"""

import sqlalchemy as sa

from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("interest_free_text", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "interest_free_text")
