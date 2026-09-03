"""User.given_name/family_name: capture Google OAuth given/family name claims (GH #62)

Revision ID: b7e4a1c9d3f2
Revises: e29c47a1b6d8
Create Date: 2026-08-31

"""

import sqlalchemy as sa

from alembic import op

revision = "b7e4a1c9d3f2"
down_revision = "e29c47a1b6d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("given_name", sa.String(), nullable=True))
    op.add_column("users", sa.Column("family_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "family_name")
    op.drop_column("users", "given_name")
