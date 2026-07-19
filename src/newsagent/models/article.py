from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from newsagent.models.base import Base

if TYPE_CHECKING:
    from newsagent.models.digest_article import DigestArticle
    from newsagent.models.source import Source


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String, unique=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    rss_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Filtering: score is the provider's fact; status is the pipeline's verdict.
    # pending -> relevant | irrelevant | refused (terminal) | error (retried next run)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_status: Mapped[str] = mapped_column(String, default="pending", server_default="pending")

    source: Mapped["Source"] = relationship(back_populates="articles")
    digest_entries: Mapped[list["DigestArticle"]] = relationship(back_populates="article")
