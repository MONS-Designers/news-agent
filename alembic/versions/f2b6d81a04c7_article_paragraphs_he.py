"""Rename articles.bullets_he to paragraphs_he

Revision ID: f2b6d81a04c7
Revises: e8a1c39d7b45
Create Date: 2026-08-23

The digest body moved from a bullet list to flowing paragraphs, so the column
holds a different kind of content and its name had to follow. Existing rows
carry over as-is: a previously summarized article's three bullets render as
three very short paragraphs until it is summarized again.
"""

from alembic import op

revision = "f2b6d81a04c7"
down_revision = "e8a1c39d7b45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("articles", "bullets_he", new_column_name="paragraphs_he")


def downgrade() -> None:
    op.alter_column("articles", "paragraphs_he", new_column_name="bullets_he")
