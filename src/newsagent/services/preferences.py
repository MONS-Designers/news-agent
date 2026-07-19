"""Domain service for user topic subscriptions (the remaining piece of #20)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.models import Topic, User, UserTopicPreference


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
