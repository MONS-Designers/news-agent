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

    # Profile: plain strings, not foreign keys — "Other" is a UI concept only,
    # a curated pick and a typed "Other" value are stored identically (AD-6).
    field_name: Mapped[str | None] = mapped_column(String, nullable=True)
    role_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Stats-only, fixed illustrative set validated in services/profile.py — no
    # "Other" concept here, so unlike field_name/role_name AD-6 doesn't apply.
    experience_bucket: Mapped[str | None] = mapped_column(String, nullable=True)

    topic_preferences: Mapped[list["UserTopicPreference"]] = relationship(back_populates="user")
    digests: Mapped[list["Digest"]] = relationship(back_populates="user")
