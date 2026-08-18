from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from newsagent.models.base import Base

if TYPE_CHECKING:
    from newsagent.models.article import Article
    from newsagent.models.digest import Digest


class DigestArticle(Base):
    __tablename__ = "digest_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    digest_id: Mapped[int] = mapped_column(ForeignKey("digests.id"))
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    digest: Mapped["Digest"] = relationship(back_populates="articles")
    article: Mapped["Article"] = relationship(back_populates="digest_entries")
