"""Restore users.digest_frequency for the current scheduler code

Revision ID: e1b2c3d4f5a6
Revises: d4a8c2f6e913
Create Date: 2026-10-13

The production database reached d4a8c2f6e913, which replaced digest_frequency
with digest_weekdays, while this checkout's scheduler still reads
digest_frequency. Recreate the old column from the weekday count and keep
digest_weekdays intact so no fixed-day preference data is discarded.
"""

import sqlalchemy as sa

from alembic import op

revision = "e1b2c3d4f5a6"
down_revision = "d4a8c2f6e913"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("digest_frequency", sa.String(), nullable=False, server_default="weekly"),
    )
    op.execute(
        "UPDATE users SET digest_frequency = CASE json_array_length(digest_weekdays) "
        "WHEN 6 THEN 'daily' WHEN 2 THEN 'twice_weekly' ELSE 'weekly' END"
    )


def downgrade() -> None:
    op.drop_column("users", "digest_frequency")
