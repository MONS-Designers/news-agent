from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from newsagent.models.base import Base

if TYPE_CHECKING:
    from newsagent.models.digest import Digest
    from newsagent.models.user_topic_preference import UserTopicPreference

# Suggestion polling status (AD-7) - plain string, same shape as Source.status
# and PendingTaxonomySuggestion.status (AD-2's convention).
SUGGESTION_STATUS_NONE = "none"
SUGGESTION_STATUS_PENDING = "pending"
SUGGESTION_STATUS_READY = "ready"
SUGGESTION_STATUS_FAILED = "failed"

# Non-terminal, like "pending" - the run is still working, but one of its two
# concurrent LLM calls has already failed and we are waiting out the survivor's
# retries (GH #36). Pollers must keep polling through it; every run that writes
# it still settles on "ready" or "failed".
SUGGESTION_STATUS_PENDING_SLOW = "pending_slow"

# Digest cadence keys. Defined on the model (not in services/cadence.py) so the
# column default does not import a service; cadence.py owns what each one means
# in days.
FREQUENCY_DAILY = "daily"
FREQUENCY_TWICE_WEEKLY = "twice_weekly"
FREQUENCY_WEEKLY = "weekly"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Raw Google OAuth claims (GH #62), captured only at row creation - see
    # services/identity.py's register_user_if_capacity. None for dev-login,
    # CLI-seeded users, and every row that predates this column. given_name is
    # preferred over `name` for the greeting via first_name() below because it
    # doesn't break for family-name-first cultures the way `name.split()[0]`
    # does; family_name is captured alongside it for completeness but has no
    # reader today.
    given_name: Mapped[str | None] = mapped_column(String, nullable=True)
    family_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Digest delivery opt-out (GH #46) - same nullable-timestamp shape as
    # Digest.opened_at/DigestLink.clicked_at: None = receiving digests,
    # a timestamp = when they stopped. Reversible by clearing it back to None.
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Profile: plain strings, not foreign keys - "Other" is a UI concept only,
    # a curated pick and a typed "Other" value are stored identically (AD-6).
    field_name: Mapped[str | None] = mapped_column(String, nullable=True)
    role_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Stats-only, fixed illustrative set validated in services/profile.py - no
    # "Other" concept here, so unlike field_name/role_name AD-6 doesn't apply.
    experience_bucket: Mapped[str | None] = mapped_column(String, nullable=True)

    # Optional, no "Other" concept - same plain-string shape as experience_bucket.
    interest_free_text: Mapped[str | None] = mapped_column(String, nullable=True)

    # How often this reader wants a digest - a key into
    # services.cadence.INTERVAL_DAYS, not a number of days, so the mapping can
    # change without a data migration. Defaults to the launch cadence.
    digest_frequency: Mapped[str] = mapped_column(
        String, default=FREQUENCY_WEEKLY, server_default=FREQUENCY_WEEKLY
    )

    # When the one-time beta welcome was delivered. Null means it still owes
    # them - a send that fails leaves it null, so the next run retries with the
    # welcome intact rather than silently downgrading to an ordinary digest.
    # Lives on the user, not the digest: the welcome belongs to the person's
    # lifecycle, and the beta-only variant is sent when no digest exists at all.
    welcomed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Set when a profile edit changes an input that topic suggestions are
    # derived from (field/role/interests) while the user already has
    # subscriptions, and cleared the moment they next save their topics.
    # The subscriptions themselves are never touched here: silently unsubscribing
    # a reader is worse than a stale one, so this only records that the two have
    # diverged and lets the UI ask. Same nullable-timestamp shape as
    # unsubscribed_at - it also answers "since when".
    topics_stale_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Suggestion polling (AD-5, AD-7). NOT NULL, unlike the profile fields
    # above - a user who has never saved a profile reads "none"/0, not null.
    suggestion_status: Mapped[str] = mapped_column(
        String, default=SUGGESTION_STATUS_NONE, server_default=SUGGESTION_STATUS_NONE
    )
    suggested_topic_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    suggested_new_topic_names: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    suggestion_request_seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    topic_preferences: Mapped[list["UserTopicPreference"]] = relationship(back_populates="user")
    digests: Mapped[list["Digest"]] = relationship(back_populates="user")


def first_name(user: User) -> str | None:
    if isinstance(user.given_name, str) and user.given_name.strip():
        return user.given_name.strip()
    if user.name and user.name.strip():
        return user.name.split()[0]
    return None
