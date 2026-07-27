import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.models import Topic, User
from newsagent.models.base import Base
from newsagent.services.preferences import (
    MAX_TOPICS,
    TopicCapExceededError,
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


# --- 4-Topic cap (AD-9) -----------------------------------------------------


@pytest.fixture
def five_topic_db(multi_topic_db: Session) -> Session:
    """multi_topic_db (AI, Cybersecurity, Space) plus two more, for cap tests
    that need more than MAX_TOPICS candidates."""
    multi_topic_db.add_all([Topic(name="Finance"), Topic(name="Health")])
    multi_topic_db.commit()
    return multi_topic_db


def test_set_preferences_exactly_at_cap_succeeds(five_topic_db: Session):
    user = _user(five_topic_db)
    ids = [t for (t,) in five_topic_db.execute(select(Topic.id))][:MAX_TOPICS]

    choices = set_preferences(five_topic_db, user, ids)

    assert sum(c.subscribed for c in choices) == MAX_TOPICS


def test_set_preferences_over_cap_raises(five_topic_db: Session):
    user = _user(five_topic_db)
    ids = [t for (t,) in five_topic_db.execute(select(Topic.id))]
    assert len(ids) == MAX_TOPICS + 1

    with pytest.raises(TopicCapExceededError) as caught:
        set_preferences(five_topic_db, user, ids)

    assert caught.value.detail == {"error": "topic_cap_exceeded", "max_topics": MAX_TOPICS}


def test_set_preferences_cap_checked_before_unknown_id(five_topic_db: Session):
    """A request with both an over-cap count and an unknown id reports the cap
    violation, not the unknown-id one — the two checks' order is deterministic."""
    user = _user(five_topic_db)
    ids = [t for (t,) in five_topic_db.execute(select(Topic.id))][: MAX_TOPICS + 1]
    ids[-1] = 999999  # swap in an unknown id, keeping the count over the cap

    with pytest.raises(TopicCapExceededError):
        set_preferences(five_topic_db, user, ids)


def test_set_preferences_zero_ids_still_succeeds(five_topic_db: Session):
    """The cap is a maximum, not a minimum — saving nothing stays allowed."""
    user = _user(five_topic_db)
    choices = set_preferences(five_topic_db, user, [])
    assert all(not c.subscribed for c in choices)


def test_set_preferences_updates_user_topic_preferences_for_digest(multi_topic_db: Session):
    """Criterion 3: digest.build_digests reads User.topic_preferences directly,
    so proving the relationship reflects the new set is enough to lock the
    behavior without touching the digest pipeline."""
    user = _user(multi_topic_db)
    space_id = _topic_id(multi_topic_db, "Space")

    set_preferences(multi_topic_db, user, [space_id])
    multi_topic_db.refresh(user)

    assert {p.topic_id for p in user.topic_preferences} == {space_id}
