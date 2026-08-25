"""users.welcomed_at - one-time beta welcome delivery

Revision ID: b3d8f0c25e47
Revises: a9c4e71b3f60
Create Date: 2026-08-23

Backfilled for users who already received a digest: they are past the welcome
moment, and stamping them here stops the first send after this deploy from
greeting an existing reader as brand new.
"""

import sqlalchemy as sa

from alembic import op

revision = "b3d8f0c25e47"
down_revision = "a9c4e71b3f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("welcomed_at", sa.DateTime(), nullable=True))
    op.execute(
        "UPDATE users SET welcomed_at = CURRENT_TIMESTAMP "
        "WHERE EXISTS (SELECT 1 FROM digests d WHERE d.user_id = users.id AND d.sent_at IS NOT NULL)"
    )


def downgrade() -> None:
    op.drop_column("users", "welcomed_at")
