"""scheduler_lease - mutual exclusion for the delivery loop

Revision ID: d4a7b2c85f16
Revises: c7e2a94f31b8
Create Date: 2026-08-23

No seed row: services/scheduler_lease.acquire() creates it on first claim, so
an empty table means "nobody is delivering" without needing a sentinel value.
"""

import sqlalchemy as sa

from alembic import op

revision = "d4a7b2c85f16"
down_revision = "c7e2a94f31b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduler_lease",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("holder", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("scheduler_lease")
