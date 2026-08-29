"""outbound_call_telemetry - replace pipeline_runs/Usage with outbound_runs +
outbound_calls (ARCHITECTURE-SPINE AD-11 through AD-21)

Revision ID: a06a39402215
Revises: d4a7b2c85f16
Create Date: 2026-08-27

log_entries.pipeline_run_id is migrated to outbound_run_id rather than just
dropped, so the CLI's log/run correlation keeps working - but its *values*
cannot be preserved: pipeline_runs.id and outbound_runs.id are separate
sequences with no relationship between them, and pipeline_runs is dropped in
this same revision (AD-18 - the old mechanism is not kept running alongside
the new one). Any existing non-NULL pipeline_run_id is therefore nulled out
rather than remapped - human sign-off for this was sought and obtained during
implementation; see the spec's Design Notes -> "Human decisions on the frozen
spec's Ask First items" for the two options considered and why this one was
picked.
"""

import sqlalchemy as sa

from alembic import op

revision = "a06a39402215"
down_revision = "d4a7b2c85f16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbound_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("subscriber_count", sa.Integer(), nullable=True),
        sa.Column("intent_summary", sa.Text(), nullable=True),
        sa.Column("succeeded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("refused", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_outbound_runs_user_id"), "outbound_runs", ["user_id"])

    op.create_table(
        "outbound_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False
        ),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("target", sa.String(), server_default="llm", nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("output_chars", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("rate_in_usd_per_mtok", sa.Numeric(12, 6), nullable=True),
        sa.Column("rate_out_usd_per_mtok", sa.Numeric(12, 6), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["outbound_runs.id"]),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_outbound_calls_run_id"), "outbound_calls", ["run_id"])
    op.create_index(op.f("ix_outbound_calls_article_id"), "outbound_calls", ["article_id"])

    # Existing values point at rows in pipeline_runs, a table this same
    # revision drops - there is no outbound_runs row they could correctly
    # point at instead, so the old linkage is dropped, not remapped. Done
    # before the batch below (as a plain UPDATE against the real table,
    # column still under its old name) rather than inside it, since SQLite's
    # batch mode rebuilds the table via a copy and is not the place to also
    # run arbitrary data-migration SQL.
    op.execute(sa.text("UPDATE log_entries SET pipeline_run_id = NULL"))

    # log_entries.pipeline_run_id -> outbound_run_id. batch_alter_table so
    # this also works on SQLite (used in tests), which cannot ALTER/DROP a
    # column or its FK constraint in place.
    with op.batch_alter_table("log_entries", schema=None) as batch_op:
        batch_op.drop_index(op.f("ix_log_entries_pipeline_run_id"))
        batch_op.drop_column("pipeline_run_id")
        batch_op.add_column(sa.Column("outbound_run_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_log_entries_outbound_run_id", "outbound_runs", ["outbound_run_id"], ["id"]
        )
    op.create_index(
        op.f("ix_log_entries_outbound_run_id"), "log_entries", ["outbound_run_id"]
    )

    op.drop_table("pipeline_runs")


def downgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_type", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False
        ),
        sa.Column("succeeded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("refused", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors", sa.Integer(), server_default="0", nullable=False),
        sa.Column("usage_input_units", sa.Integer(), server_default="0", nullable=False),
        sa.Column("usage_output_units", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # No values to restore either way - see upgrade()'s note; a downgrade
    # loses the same linkage the upgrade already lost.
    with op.batch_alter_table("log_entries", schema=None) as batch_op:
        batch_op.drop_constraint("fk_log_entries_outbound_run_id", type_="foreignkey")
        batch_op.drop_index(op.f("ix_log_entries_outbound_run_id"))
        batch_op.drop_column("outbound_run_id")
        batch_op.add_column(sa.Column("pipeline_run_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_log_entries_pipeline_run_id", "pipeline_runs", ["pipeline_run_id"], ["id"]
        )
    op.create_index(
        op.f("ix_log_entries_pipeline_run_id"), "log_entries", ["pipeline_run_id"]
    )

    op.drop_index(op.f("ix_outbound_calls_article_id"), table_name="outbound_calls")
    op.drop_index(op.f("ix_outbound_calls_run_id"), table_name="outbound_calls")
    op.drop_table("outbound_calls")

    op.drop_index(op.f("ix_outbound_runs_user_id"), table_name="outbound_runs")
    op.drop_table("outbound_runs")
