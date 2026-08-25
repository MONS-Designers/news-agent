"""Domain service for user topic subscriptions (the remaining piece of #20)."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.models import Topic, User, UserTopicPreference
from newsagent.models.topic import STATUS_APPROVED as TOPIC_STATUS_APPROVED
from newsagent.models.topic import STATUS_PENDING as TOPIC_STATUS_PENDING
from newsagent.services import sources

# Platform-wide hard cap (FR-10), enforced here - the single mutation point
# for UserTopicPreference - so every save path (old raw toggle grid, new
# guided flow) shares one rule (AD-9).
MAX_TOPICS = 4

# Mirrors services/profile.py's MAX_NAME_LENGTH - an invented Topic name is
# just as unbounded an input as a Field/Role "Other" submission, so it gets
# the same cap rather than being stored without one.
MAX_NAME_LENGTH = 100


class TopicCapExceededError(ValueError):
    """Raised when a save would leave more than MAX_TOPICS topics selected.

    Carries a stable, identifiable `detail` dict so every caller surfaces the
    same failure shape, rather than a bare string a caller would have to
    sniff (AD-9)."""

    def __init__(self) -> None:
        self.detail = {"error": "topic_cap_exceeded", "max_topics": MAX_TOPICS}
        super().__init__(f"Cannot select more than {MAX_TOPICS} topics.")


@dataclass(frozen=True)
class TopicChoice:
    """A topic paired with whether the user is currently subscribed - the unit
    the preferences page renders as one toggle."""

    topic_id: int
    name: str
    subscribed: bool


def list_topic_choices(db: Session, user: User) -> list[TopicChoice]:
    """Every `approved` Topic, plus any `pending`/`rejected` Topic this user is
    personally subscribed to - status only gates visibility to *other* users,
    never the owning user's own pick (spec boundary), so an other user's still-
    pending Topic must not leak into this list."""
    subscribed_ids = {pref.topic_id for pref in user.topic_preferences}
    topics = db.scalars(select(Topic).order_by(Topic.name))
    return [
        TopicChoice(topic_id=topic.id, name=topic.name, subscribed=topic.id in subscribed_ids)
        for topic in topics
        if topic.status == TOPIC_STATUS_APPROVED or topic.id in subscribed_ids
    ]


def set_preferences(
    db: Session, user: User, topic_ids: list[int], new_topic_names: Sequence[str] = ()
) -> list[TopicChoice]:
    """Replace the user's subscription set with exactly ``topic_ids`` plus any
    ``new_topic_names``.

    Idempotent and source-agnostic: the ids may come from a human toggle or a
    future LLM suggestion - this function doesn't care. Each name in
    ``new_topic_names`` is resolved to a real `Topic` row via `add_topic`'s
    get-or-create-by-exact-name idempotency (whitespace-strip only, no fuzzy
    matching), created as `status='pending'` if new, and folded into the
    desired id set before the cap/known-id checks below - so the cap counts
    the combined set of existing-id picks and new-name picks correctly.

    The cap (and the per-name length check) is evaluated on the raw,
    pre-resolution counts *before* any `Topic` row is created - a rejected
    over-cap save must never leave an orphan `pending` Topic committed with
    no owning preference, and an oversized ``new_topic_names`` list must be
    rejected before it can create an unbounded number of rows. Raises
    ValueError if any id is not a real topic or any name exceeds
    MAX_NAME_LENGTH; raises TopicCapExceededError if the combined selection
    would exceed MAX_TOPICS.
    """
    cleaned_names = {name.strip() for name in new_topic_names if name.strip()}
    for name in cleaned_names:
        if len(name) > MAX_NAME_LENGTH:
            raise ValueError(f"Topic name too long (max {MAX_NAME_LENGTH} characters)")

    if len(set(topic_ids)) + len(cleaned_names) > MAX_TOPICS:
        raise TopicCapExceededError()

    resolved_new_ids = set()
    for name in cleaned_names:
        topic, _ = sources.add_topic(db, name, status=TOPIC_STATUS_PENDING)
        resolved_new_ids.add(topic.id)

    desired = set(topic_ids) | resolved_new_ids
    if len(desired) > MAX_TOPICS:
        raise TopicCapExceededError()

    known_ids = {topic_id for (topic_id,) in db.execute(select(Topic.id))}
    unknown = desired - known_ids
    if unknown:
        raise ValueError(f"Unknown topic id(s): {sorted(unknown)}")

    current = {pref.topic_id: pref for pref in user.topic_preferences}
    for topic_id in desired - current.keys():
        db.add(UserTopicPreference(user_id=user.id, topic_id=topic_id))
    for topic_id in current.keys() - desired:
        db.delete(current[topic_id])
    # This save is what re-aligns the topics with the profile, whatever the
    # user picked - so it clears the divergence flag services/profile.py set.
    user.topics_stale_at = None
    db.commit()
    db.refresh(user)
    return list_topic_choices(db, user)


def subscribe(db: Session, email: str, topic_name: str) -> tuple[UserTopicPreference, bool]:
    """Get-or-create a subscription. Raises ValueError for unknown user/topic."""
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise ValueError(f"No user with email {email!r} - add them with add-user first")
    topic = db.scalar(select(Topic).where(Topic.name == topic_name))
    if topic is None:
        known = ", ".join(t.name for t in db.scalars(select(Topic)))
        raise ValueError(f"No topic named {topic_name!r} (known: {known})")

    existing = db.scalar(
        select(UserTopicPreference).where(
            UserTopicPreference.user_id == user.id,
            UserTopicPreference.topic_id == topic.id,
        )
    )
    if existing is not None:
        return existing, False
    preference = UserTopicPreference(user_id=user.id, topic_id=topic.id)
    db.add(preference)
    db.commit()
    return preference, True
