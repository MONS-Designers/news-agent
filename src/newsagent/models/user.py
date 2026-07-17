from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from newsagent.models.base import Base

if TYPE_CHECKING:
    from newsagent.models.digest import Digest
    from newsagent.models.user_topic_preference import UserTopicPreference


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    topic_preferences: Mapped[list["UserTopicPreference"]] = relationship(back_populates="user")
    digests: Mapped[list["Digest"]] = relationship(back_populates="user")
