"""pipeline_runs table for per-run usage logging (GH #19 follow-up)

Revision ID: 7fe4f7681621
Revises: a4b5c6d7e8f9
Create Date: 2026-08-09

"""

import sqlalchemy as sa

from alembic import op

revision = "7fe4f7681621"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("succeeded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("refused", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors", sa.Integer(), server_default="0", nullable=False),
        sa.Column("usage_input_units", sa.Integer(), server_default="0", nullable=False),
        sa.Column("usage_output_units", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("pipeline_runs")
