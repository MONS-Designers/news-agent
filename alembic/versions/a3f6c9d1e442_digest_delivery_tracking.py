"""Digest delivery tracking: tracking_token, sent_at, opened_at

Revision ID: a3f6c9d1e442
Revises: f9c2d7e0b118
Create Date: 2026-07-20

"""

import secrets

import sqlalchemy as sa

from alembic import op

revision = "a3f6c9d1e442"
down_revision = "f9c2d7e0b118"
branch_labels = None
depends_on = None

digests = sa.table("digests", sa.column("id", sa.Integer), sa.column("tracking_token", sa.String))


def upgrade() -> None:
    op.add_column("digests", sa.Column("tracking_token", sa.String(), nullable=True))
    op.add_column("digests", sa.Column("sent_at", sa.DateTime(), nullable=True))
    op.add_column("digests", sa.Column("opened_at", sa.DateTime(), nullable=True))

    conn = op.get_bind()
    for (digest_id,) in conn.execute(sa.select(digests.c.id)):
        conn.execute(
            digests.update()
            .where(digests.c.id == digest_id)
            .values(tracking_token=secrets.token_urlsafe(24))
        )

    with op.batch_alter_table("digests") as batch:
        batch.alter_column("tracking_token", nullable=False)
        batch.create_unique_constraint("uq_digests_tracking_token", ["tracking_token"])


def downgrade() -> None:
    with op.batch_alter_table("digests") as batch:
        batch.drop_constraint("uq_digests_tracking_token", type_="unique")
        batch.drop_column("opened_at")
        batch.drop_column("sent_at")
        batch.drop_column("tracking_token")
