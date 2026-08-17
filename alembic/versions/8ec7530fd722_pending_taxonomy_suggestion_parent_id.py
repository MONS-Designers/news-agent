"""pending_taxonomy_suggestions.parent_suggestion_id - links an orphan Role
suggestion to the Field suggestion it was submitted alongside, so deciding the
Field can cascade to just its own Roles instead of every open Role suggestion.

Revision ID: 8ec7530fd722
Revises: f3b9d2a71c5e
Create Date: 2026-08-17

"""

import sqlalchemy as sa

from alembic import op

revision = "8ec7530fd722"
down_revision = "f3b9d2a71c5e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        "uq_pending_taxonomy_suggestions_open", table_name="pending_taxonomy_suggestions"
    )

    with op.batch_alter_table("pending_taxonomy_suggestions") as batch:
        batch.add_column(sa.Column("parent_suggestion_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_pending_taxonomy_suggestions_parent_suggestion_id",
            "pending_taxonomy_suggestions",
            ["parent_suggestion_id"],
            ["id"],
        )

    # Re-created with parent_suggestion_id folded in: two orphan Role rows with
    # the same text but different parent Field suggestions must stay distinct
    # rows, or a rejection/approval cascade could not tell them apart.
    op.create_index(
        "uq_pending_taxonomy_suggestions_open",
        "pending_taxonomy_suggestions",
        [
            "kind",
            sa.text("COALESCE(field_id, -1)"),
            sa.text("COALESCE(parent_suggestion_id, -1)"),
            "normalized_text",
        ],
        unique=True,
        sqlite_where=sa.text("status = 'pending'"),
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_pending_taxonomy_suggestions_open", table_name="pending_taxonomy_suggestions"
    )

    with op.batch_alter_table("pending_taxonomy_suggestions") as batch:
        batch.drop_constraint(
            "fk_pending_taxonomy_suggestions_parent_suggestion_id", type_="foreignkey"
        )
        batch.drop_column("parent_suggestion_id")

    op.create_index(
        "uq_pending_taxonomy_suggestions_open",
        "pending_taxonomy_suggestions",
        ["kind", sa.text("COALESCE(field_id, -1)"), "normalized_text"],
        unique=True,
        sqlite_where=sa.text("status = 'pending'"),
        postgresql_where=sa.text("status = 'pending'"),
    )
