"""Digest editorial voice: intro_he, dad_joke_he

Revision ID: c5e9a2f34b81
Revises: b8d4f1a90c67
Create Date: 2026-07-20

"""

import sqlalchemy as sa

from alembic import op

revision = "c5e9a2f34b81"
down_revision = "b8d4f1a90c67"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("digests", sa.Column("intro_he", sa.Text(), nullable=True))
    op.add_column("digests", sa.Column("dad_joke_he", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("digests", "dad_joke_he")
    op.drop_column("digests", "intro_he")
