import secrets
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from newsagent.models.base import Base

if TYPE_CHECKING:
    from newsagent.models.article import Article
    from newsagent.models.digest import Digest

KIND_ARTICLE = "article"
KIND_PREFERENCES = "preferences"
KIND_UNSUBSCRIBE = "unsubscribe"
# One-tap feedback from inside the email. Carries article_id for a per-article
# thumb, or null for the digest-level pair in the footer - the same
# (digest, kind, article) uniqueness that keeps article links stable.
KIND_FEEDBACK_UP = "feedback_up"
KIND_FEEDBACK_DOWN = "feedback_down"

FEEDBACK_KINDS = {KIND_FEEDBACK_UP: "up", KIND_FEEDBACK_DOWN: "down"}


def _generate_link_token() -> str:
    return secrets.token_urlsafe(24)


class DigestLink(Base):
    """A click-trackable link embedded in a sent digest (FR12). Same shape as
    Digest.opened_at: an unguessable per-link token, and clicked_at set once on
    first click. One row per (digest, kind, article) - get-or-created at render
    time so a retried send reuses the same token instead of minting a new one."""

    __tablename__ = "digest_links"
    __table_args__ = (UniqueConstraint("digest_id", "kind", "article_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    digest_id: Mapped[int] = mapped_column(ForeignKey("digests.id"))
    token: Mapped[str] = mapped_column(String, unique=True, default=_generate_link_token)
    kind: Mapped[str] = mapped_column(String)
    # Set only for kind=article; null for the digest's single preferences link.
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), nullable=True)
    target_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Device that made the first click (mobile/tablet/desktop/bot/unknown - see
    # services.device_detection). Set once, alongside clicked_at.
    device_type: Mapped[str | None] = mapped_column(String, nullable=True)

    digest: Mapped["Digest"] = relationship(back_populates="links")
    article: Mapped["Article | None"] = relationship()
