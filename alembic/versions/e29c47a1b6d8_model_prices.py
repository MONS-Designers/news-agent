"""model_prices - per-model $/Mtok rates, append-only (ARCHITECTURE-SPINE AD-16,
AD-21)

Revision ID: e29c47a1b6d8
Revises: a06a39402215
Create Date: 2026-08-30

No FK from outbound_calls: the rate in effect at write time is copied onto
the outbound_call row itself (AD-16), so this table is never joined against
for historical cost - only queried for "the latest rate as of now" when a
new call is being priced.
"""

import sqlalchemy as sa

from alembic import op

revision = "e29c47a1b6d8"
down_revision = "a06a39402215"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("rate_in_usd_per_mtok", sa.Numeric(12, 6), nullable=False),
        sa.Column("rate_out_usd_per_mtok", sa.Numeric(12, 6), nullable=False),
        sa.Column(
            "effective_from", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False
        ),
        sa.Column("source", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_model_prices_model"), "model_prices", ["model"])


def downgrade() -> None:
    op.drop_index(op.f("ix_model_prices_model"), table_name="model_prices")
    op.drop_table("model_prices")
