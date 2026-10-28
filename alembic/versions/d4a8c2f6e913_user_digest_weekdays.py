"""users.digest_weekdays replaces users.digest_frequency (GH #59, #63)

Revision ID: d4a8c2f6e913
Revises: b7e4a1c9d3f2
Create Date: 2026-09-14

Readers now pick fixed weekdays (date.weekday() numbers, Sunday to Friday)
instead of a minimum gap in days; the frequency is derived from how many days
are chosen, so it is no longer stored. Every existing reader was on the
launch cadence ("weekly"), so all of them start on Sunday via the column
default. Downgrade maps the day count back to the nearest old key.
"""

import sqlalchemy as sa

from alembic import op

revision = "d4a8c2f6e913"
down_revision = "b7e4a1c9d3f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("digest_weekdays", sa.JSON(), nullable=False, server_default="[6]"),
    )
    op.drop_column("users", "digest_frequency")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("digest_frequency", sa.String(), nullable=False, server_default="weekly"),
    )
    op.execute(
        "UPDATE users SET digest_frequency = CASE json_array_length(digest_weekdays) "
        "WHEN 6 THEN 'daily' WHEN 2 THEN 'twice_weekly' ELSE 'weekly' END"
    )
    op.drop_column("users", "digest_weekdays")
