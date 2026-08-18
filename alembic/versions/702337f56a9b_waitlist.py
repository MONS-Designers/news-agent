"""waitlist table for capacity-full self-registration attempts (FR11)

Revision ID: 702337f56a9b
Revises: 7fe4f7681621
Create Date: 2026-08-11

"""

import sqlalchemy as sa

from alembic import op

revision = "702337f56a9b"
down_revision = "7fe4f7681621"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "waitlist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_waitlist_email"), "waitlist", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_waitlist_email"), table_name="waitlist")
    op.drop_table("waitlist")
