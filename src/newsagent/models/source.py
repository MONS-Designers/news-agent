from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from newsagent.models.base import Base

if TYPE_CHECKING:
    from newsagent.models.article import Article
    from newsagent.models.topic import Topic

# Source.status values (plain string column, no enum/constraint).
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    url: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default=STATUS_PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    topic: Mapped["Topic"] = relationship(back_populates="sources")
    articles: Mapped[list["Article"]] = relationship(back_populates="source")
