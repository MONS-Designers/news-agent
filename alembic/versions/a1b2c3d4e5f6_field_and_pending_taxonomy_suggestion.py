"""Field, pending_taxonomy_suggestions, User.field_name (Story 1.1)

Revision ID: a1b2c3d4e5f6
Revises: d1a2b3c4d5e6
Create Date: 2026-07-25

"""

import sqlalchemy as sa

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "d1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fields",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fields_name"), "fields", ["name"], unique=True)

    op.create_table(
        "pending_taxonomy_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("field_id", sa.Integer(), nullable=True),
        sa.Column("normalized_text", sa.String(), nullable=False),
        sa.Column("submission_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pending_taxonomy_suggestions_kind"), "pending_taxonomy_suggestions", ["kind"]
    )
    op.create_index(
        op.f("ix_pending_taxonomy_suggestions_normalized_text"),
        "pending_taxonomy_suggestions",
        ["normalized_text"],
    )
    op.create_index(
        op.f("ix_pending_taxonomy_suggestions_status"), "pending_taxonomy_suggestions", ["status"]
    )

    op.add_column("users", sa.Column("field_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "field_name")

    op.drop_index(
        op.f("ix_pending_taxonomy_suggestions_status"), table_name="pending_taxonomy_suggestions"
    )
    op.drop_index(
        op.f("ix_pending_taxonomy_suggestions_normalized_text"),
        table_name="pending_taxonomy_suggestions",
    )
    op.drop_index(
        op.f("ix_pending_taxonomy_suggestions_kind"), table_name="pending_taxonomy_suggestions"
    )
    op.drop_table("pending_taxonomy_suggestions")

    op.drop_index(op.f("ix_fields_name"), table_name="fields")
    op.drop_table("fields")
