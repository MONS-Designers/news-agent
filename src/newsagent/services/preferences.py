"""Domain service for user topic subscriptions (the remaining piece of #20)."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.models import Topic, User, UserTopicPreference


@dataclass(frozen=True)
class TopicChoice:
    """A topic paired with whether the user is currently subscribed — the unit
    the preferences page renders as one toggle."""

    topic_id: int
    name: str
    subscribed: bool


def list_topic_choices(db: Session, user: User) -> list[TopicChoice]:
    """Every topic, flagged with the user's current subscription state."""
    subscribed_ids = {pref.topic_id for pref in user.topic_preferences}
    topics = db.scalars(select(Topic).order_by(Topic.name))
    return [
        TopicChoice(topic_id=topic.id, name=topic.name, subscribed=topic.id in subscribed_ids)
        for topic in topics
    ]


def set_preferences(db: Session, user: User, topic_ids: list[int]) -> list[TopicChoice]:
    """Replace the user's subscription set with exactly ``topic_ids``.

    Idempotent and source-agnostic: the ids may come from a human toggle or a
    future LLM suggestion — this function doesn't care. Raises ValueError if any
    id is not a real topic.
    """
    desired = set(topic_ids)
    known_ids = {topic_id for (topic_id,) in db.execute(select(Topic.id))}
    unknown = desired - known_ids
    if unknown:
        raise ValueError(f"Unknown topic id(s): {sorted(unknown)}")

    current = {pref.topic_id: pref for pref in user.topic_preferences}
    for topic_id in desired - current.keys():
        db.add(UserTopicPreference(user_id=user.id, topic_id=topic_id))
    for topic_id in current.keys() - desired:
        db.delete(current[topic_id])
    db.commit()
    db.refresh(user)
    return list_topic_choices(db, user)


def subscribe(db: Session, email: str, topic_name: str) -> tuple[UserTopicPreference, bool]:
    """Get-or-create a subscription. Raises ValueError for unknown user/topic."""
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise ValueError(f"No user with email {email!r} — add them with add-user first")
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
