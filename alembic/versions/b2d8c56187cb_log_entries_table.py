"""log_entries table

Revision ID: b2d8c56187cb
Revises: 8ec7530fd722
Create Date: 2026-08-20 20:44:49.095792

"""

import sqlalchemy as sa

from alembic import op

revision = "b2d8c56187cb"
down_revision = "8ec7530fd722"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "log_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("level", sa.String(), nullable=False),
        sa.Column("logger_name", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("pipeline_run_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_log_entries_pipeline_run_id"), "log_entries", ["pipeline_run_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_log_entries_pipeline_run_id"), table_name="log_entries")
    op.drop_table("log_entries")
