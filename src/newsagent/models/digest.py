import secrets
from datetime import date as date_
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from newsagent.models.base import Base

if TYPE_CHECKING:
    from newsagent.models.digest_article import DigestArticle
    from newsagent.models.digest_link import DigestLink
    from newsagent.models.user import User


def _generate_tracking_token() -> str:
    return secrets.token_urlsafe(24)


class Digest(Base):
    __tablename__ = "digests"
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date: Mapped[date_] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Opaque, unguessable — never the sequential id — so the public open-tracking
    # endpoint can't be walked to forge opens for other users' digests.
    tracking_token: Mapped[str] = mapped_column(
        String, unique=True, default=_generate_tracking_token
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Digest-level editorial voice (LLM-composed from the week's headlines):
    # a warm personal opener and a light closing joke tied to the news.
    intro_he: Mapped[str | None] = mapped_column(Text, nullable=True)
    dad_joke_he: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="digests")
    articles: Mapped[list["DigestArticle"]] = relationship(back_populates="digest")
    links: Mapped[list["DigestLink"]] = relationship(back_populates="digest")
