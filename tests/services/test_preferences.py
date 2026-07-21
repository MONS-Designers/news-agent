import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.models import Topic, User
from newsagent.models.base import Base
from newsagent.services.preferences import (
    list_topic_choices,
    set_preferences,
    subscribe,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(email="user@example.com"))
        session.add(Topic(name="AI"))
        session.commit()
        yield session


@pytest.fixture
def multi_topic_db(db: Session) -> Session:
    """The single-topic db fixture plus two more topics, for choice/set tests."""
    db.add(Topic(name="Cybersecurity"))
    db.add(Topic(name="Space"))
    db.commit()
    return db


def _user(db: Session) -> User:
    return db.scalar(select(User).where(User.email == "user@example.com"))


def _topic_id(db: Session, name: str) -> int:
    return db.scalar(select(Topic.id).where(Topic.name == name))


def test_subscribe_creates_preference(db: Session):
    _, created = subscribe(db, "user@example.com", "AI")
    assert created is True


def test_subscribe_is_idempotent(db: Session):
    subscribe(db, "user@example.com", "AI")
    _, created = subscribe(db, "user@example.com", "AI")
    assert created is False


def test_unknown_user_raises(db: Session):
    with pytest.raises(ValueError, match="add-user"):
        subscribe(db, "stranger@example.com", "AI")


def test_unknown_topic_raises_with_known_list(db: Session):
    with pytest.raises(ValueError, match="AI"):
        subscribe(db, "user@example.com", "Sports")


def test_list_topic_choices_marks_subscribed_vs_not(multi_topic_db: Session):
    user = _user(multi_topic_db)
    subscribe(multi_topic_db, "user@example.com", "AI")
    multi_topic_db.refresh(user)

    choices = list_topic_choices(multi_topic_db, user)

    by_name = {c.name: c.subscribed for c in choices}
    assert by_name == {"AI": True, "Cybersecurity": False, "Space": False}


def test_set_preferences_adds_and_removes(multi_topic_db: Session):
    user = _user(multi_topic_db)
    subscribe(multi_topic_db, "user@example.com", "AI")
    multi_topic_db.refresh(user)

    cyber_id = _topic_id(multi_topic_db, "Cybersecurity")
    space_id = _topic_id(multi_topic_db, "Space")

    choices = set_preferences(multi_topic_db, user, [cyber_id, space_id])

    by_name = {c.name: c.subscribed for c in choices}
    assert by_name == {"AI": False, "Cybersecurity": True, "Space": True}


def test_set_preferences_is_idempotent(multi_topic_db: Session):
    user = _user(multi_topic_db)
    ai_id = _topic_id(multi_topic_db, "AI")

    first = set_preferences(multi_topic_db, user, [ai_id])
    second = set_preferences(multi_topic_db, user, [ai_id])

    assert first == second


def test_set_preferences_unknown_id_raises(multi_topic_db: Session):
    user = _user(multi_topic_db)
    with pytest.raises(ValueError, match="Unknown topic id"):
        set_preferences(multi_topic_db, user, [999])


def test_set_preferences_updates_user_topic_preferences_for_digest(multi_topic_db: Session):
    """Criterion 3: digest.build_digests reads User.topic_preferences directly,
    so proving the relationship reflects the new set is enough to lock the
    behavior without touching the digest pipeline."""
    user = _user(multi_topic_db)
    space_id = _topic_id(multi_topic_db, "Space")

    set_preferences(multi_topic_db, user, [space_id])
    multi_topic_db.refresh(user)

    assert {p.topic_id for p in user.topic_preferences} == {space_id}
