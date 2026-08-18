from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from newsagent.models.base import Base

if TYPE_CHECKING:
    from newsagent.models.source import Source
    from newsagent.models.user_topic_preference import UserTopicPreference

# Topic.status values (plain string column, mirrors Source.status). REJECTED is
# unused by this spec - defined now so the deferred admin-approval follow-up
# needs no further migration.
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    status: Mapped[str] = mapped_column(
        String, default=STATUS_APPROVED, server_default=STATUS_APPROVED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    sources: Mapped[list["Source"]] = relationship(back_populates="topic")
    user_preferences: Mapped[list["UserTopicPreference"]] = relationship(back_populates="topic")
