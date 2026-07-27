"""roles table, User.role_name, partial unique index on open suggestions (Story 1.2)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-26

"""

import sqlalchemy as sa

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("field_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("field_id", "name", name="uq_roles_field_name"),
    )
    op.create_index(op.f("ix_roles_field_id"), "roles", ["field_id"])
    op.create_index(op.f("ix_roles_name"), "roles", ["name"])

    op.add_column("users", sa.Column("role_name", sa.String(), nullable=True))

    # Preserves the submission's display casing, which normalized_text discards —
    # Story 2.2 promotes from these rows and must not mint lowercase names.
    op.add_column(
        "pending_taxonomy_suggestions", sa.Column("raw_text", sa.String(), nullable=True)
    )

    # AD-8 backstop, added with Story 1.2 because Role submissions multiply the
    # exposure. COALESCE because kind='field' rows carry field_id=NULL and NULLs
    # never collide in a unique index; partial so decided rows stay exempt.
    op.create_index(
        "uq_pending_taxonomy_suggestions_open",
        "pending_taxonomy_suggestions",
        ["kind", sa.text("COALESCE(field_id, -1)"), "normalized_text"],
        unique=True,
        sqlite_where=sa.text("status = 'pending'"),
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_pending_taxonomy_suggestions_open", table_name="pending_taxonomy_suggestions"
    )

    op.drop_column("pending_taxonomy_suggestions", "raw_text")
    op.drop_column("users", "role_name")

    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_index(op.f("ix_roles_field_id"), table_name="roles")
    op.drop_table("roles")
