from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from newsagent.models.base import Base


class Waitlist(Base):
    """A brand-new email captured because it arrived after the self-
    registration cap was full (FR11) - not a User, never signed in."""

    __tablename__ = "waitlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
