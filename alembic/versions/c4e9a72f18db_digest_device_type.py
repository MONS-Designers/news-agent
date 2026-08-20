"""digests.opened_device_type + digest_links.device_type

Revision ID: c4e9a72f18db
Revises: b2d8c56187cb
Create Date: 2026-08-20

"""

import sqlalchemy as sa

from alembic import op

revision = "c4e9a72f18db"
down_revision = "b2d8c56187cb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("digests", sa.Column("opened_device_type", sa.String(), nullable=True))
    op.add_column("digest_links", sa.Column("device_type", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("digest_links", "device_type")
    op.drop_column("digests", "opened_device_type")
