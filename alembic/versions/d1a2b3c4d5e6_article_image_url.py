"""Article image_url field for lead images (issue #24)

Revision ID: d1a2b3c4d5e6
Revises: c5e9a2f34b81
Create Date: 2026-07-21

"""

import sqlalchemy as sa

from alembic import op

revision = "d1a2b3c4d5e6"
down_revision = "c5e9a2f34b81"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("image_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("articles", "image_url")
