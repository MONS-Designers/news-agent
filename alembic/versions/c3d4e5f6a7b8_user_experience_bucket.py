"""User.experience_bucket (Story 1.3)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-27

"""

import sqlalchemy as sa

from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("experience_bucket", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "experience_bucket")
