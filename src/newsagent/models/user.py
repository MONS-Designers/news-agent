from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from newsagent.models.base import Base

if TYPE_CHECKING:
    from newsagent.models.digest import Digest
    from newsagent.models.user_topic_preference import UserTopicPreference

# Suggestion polling status (AD-7) — plain string, same shape as Source.status
# and PendingTaxonomySuggestion.status (AD-2's convention).
SUGGESTION_STATUS_NONE = "none"
SUGGESTION_STATUS_PENDING = "pending"
SUGGESTION_STATUS_READY = "ready"
SUGGESTION_STATUS_FAILED = "failed"

# Non-terminal, like "pending" — the run is still working, but one of its two
# concurrent LLM calls has already failed and we are waiting out the survivor's
# retries (GH #36). Pollers must keep polling through it; every run that writes
# it still settles on "ready" or "failed".
SUGGESTION_STATUS_PENDING_SLOW = "pending_slow"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Digest delivery opt-out (GH #46) — same nullable-timestamp shape as
    # Digest.opened_at/DigestLink.clicked_at: None = receiving digests,
    # a timestamp = when they stopped. Reversible by clearing it back to None.
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Profile: plain strings, not foreign keys — "Other" is a UI concept only,
    # a curated pick and a typed "Other" value are stored identically (AD-6).
    field_name: Mapped[str | None] = mapped_column(String, nullable=True)
    role_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Stats-only, fixed illustrative set validated in services/profile.py — no
    # "Other" concept here, so unlike field_name/role_name AD-6 doesn't apply.
    experience_bucket: Mapped[str | None] = mapped_column(String, nullable=True)

    # Optional, no "Other" concept — same plain-string shape as experience_bucket.
    interest_free_text: Mapped[str | None] = mapped_column(String, nullable=True)

    # Suggestion polling (AD-5, AD-7). NOT NULL, unlike the profile fields
    # above — a user who has never saved a profile reads "none"/0, not null.
    suggestion_status: Mapped[str] = mapped_column(
        String, default=SUGGESTION_STATUS_NONE, server_default=SUGGESTION_STATUS_NONE
    )
    suggested_topic_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    suggested_new_topic_names: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    suggestion_request_seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    topic_preferences: Mapped[list["UserTopicPreference"]] = relationship(back_populates="user")
    digests: Mapped[list["Digest"]] = relationship(back_populates="user")
