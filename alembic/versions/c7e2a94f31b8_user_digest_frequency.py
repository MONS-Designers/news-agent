"""users.digest_frequency - per-reader delivery cadence

Revision ID: c7e2a94f31b8
Revises: b3d8f0c25e47
Create Date: 2026-08-23

Stores the cadence key ("weekly"), not a day count: services/cadence.py owns
what each key means, so changing an interval never needs a data migration.
Existing readers default to the launch cadence, which is what they already had.
"""

import sqlalchemy as sa

from alembic import op

revision = "c7e2a94f31b8"
down_revision = "b3d8f0c25e47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "digest_frequency",
            sa.String(),
            nullable=False,
            server_default="weekly",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "digest_frequency")
