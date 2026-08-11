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


def test_list_topic_choices_hides_other_users_pending_topic(multi_topic_db: Session):
    """A pending Topic created by one user must not leak into a different
    user's preferences grid — status only gates visibility to *other* users,
    and this grid is also what Step 3's failed-suggestion fallback renders."""
    multi_topic_db.add(User(email="creator@example.com"))
    multi_topic_db.commit()
    creator = multi_topic_db.scalar(select(User).where(User.email == "creator@example.com"))
    set_preferences(multi_topic_db, creator, [], new_topic_names=["Quantum Computing"])

    other = _user(multi_topic_db)
    choices = list_topic_choices(multi_topic_db, other)

    assert "Quantum Computing" not in {c.name for c in choices}


def test_list_topic_choices_shows_own_pending_topic(multi_topic_db: Session):
    """The reverse of the above: the creator's own pick stays visible to them."""
    user = _user(multi_topic_db)
    set_preferences(multi_topic_db, user, [], new_topic_names=["Quantum Computing"])
    multi_topic_db.refresh(user)

    choices = list_topic_choices(multi_topic_db, user)

    by_name = {c.name: c.subscribed for c in choices}
    assert by_name["Quantum Computing"] is True


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


def test_set_preferences_creates_pending_topic_from_new_name(multi_topic_db: Session):
    user = _user(multi_topic_db)

    choices = set_preferences(multi_topic_db, user, [], new_topic_names=["Quantum Computing"])

    topic = multi_topic_db.scalar(select(Topic).where(Topic.name == "Quantum Computing"))
    assert topic is not None
    assert topic.status == "pending"
    by_name = {c.name: c.subscribed for c in choices}
    assert by_name["Quantum Computing"] is True


def test_set_preferences_new_name_reuses_existing_topic(multi_topic_db: Session):
    """get-or-create by exact name (whitespace-strip only) — a new-name pick
    that matches an existing Topic must not create a duplicate row."""
    user = _user(multi_topic_db)
    ai_id = _topic_id(multi_topic_db, "AI")

    set_preferences(multi_topic_db, user, [], new_topic_names=["AI"])

    ai_topics = multi_topic_db.scalars(select(Topic).where(Topic.name == "AI")).all()
    assert len(ai_topics) == 1
    assert {p.topic_id for p in user.topic_preferences} == {ai_id}


def test_set_preferences_blank_new_name_is_skipped(multi_topic_db: Session):
    user = _user(multi_topic_db)

    choices = set_preferences(multi_topic_db, user, [], new_topic_names=["   "])

    assert all(not c.subscribed for c in choices)
    assert multi_topic_db.scalar(select(Topic).where(Topic.name == "")) is None


def test_set_preferences_new_name_over_cap_raises(five_topic_db: Session):
    user = _user(five_topic_db)
    ids = [t for (t,) in five_topic_db.execute(select(Topic.id))][:MAX_TOPICS]

    with pytest.raises(TopicCapExceededError):
        set_preferences(five_topic_db, user, ids, new_topic_names=["Quantum Computing"])


def test_set_preferences_three_ids_plus_two_new_names_over_cap_raises(five_topic_db: Session):
    """I/O matrix: 3 existing ids + 2 new names, all distinct -> cap exceeded."""
    user = _user(five_topic_db)
    ids = [t for (t,) in five_topic_db.execute(select(Topic.id))][:3]

    with pytest.raises(TopicCapExceededError):
        set_preferences(
            five_topic_db, user, ids, new_topic_names=["Quantum Computing", "Climate Tech"]
        )


def test_set_preferences_over_cap_new_names_create_no_orphan_topics(multi_topic_db: Session):
    """A save rejected for exceeding the cap must not leave any invented Topic
    row committed — the cap check runs before any Topic is created, not after."""
    user = _user(multi_topic_db)

    with pytest.raises(TopicCapExceededError):
        set_preferences(
            multi_topic_db,
            user,
            [],
            new_topic_names=["Quantum Computing", "Climate Tech", "Robotics", "Biotech", "Fusion"],
        )

    assert multi_topic_db.scalar(select(Topic).where(Topic.name == "Quantum Computing")) is None


def test_set_preferences_oversized_new_name_list_creates_no_topics(multi_topic_db: Session):
    """An unbounded new_topic_names list must not be able to create an
    unbounded number of pending Topic rows — the cap check runs first."""
    user = _user(multi_topic_db)
    names = [f"Topic {i}" for i in range(50)]

    with pytest.raises(TopicCapExceededError):
        set_preferences(multi_topic_db, user, [], new_topic_names=names)

    count = multi_topic_db.scalar(select(Topic.id).where(Topic.name == "Topic 0"))
    assert count is None


def test_set_preferences_new_name_too_long_raises(multi_topic_db: Session):
    user = _user(multi_topic_db)
    long_name = "x" * 101

    with pytest.raises(ValueError, match="too long"):
        set_preferences(multi_topic_db, user, [], new_topic_names=[long_name])

    assert multi_topic_db.scalar(select(Topic).where(Topic.name == long_name)) is None


def test_set_preferences_duplicate_ids_in_topic_ids_not_double_counted(multi_topic_db: Session):
    """Repeats of the same id in topic_ids must count once toward the cap, not
    once per repetition — the pre-resolution cap check dedupes before counting."""
    user = _user(multi_topic_db)
    ai_id = _topic_id(multi_topic_db, "AI")

    choices = set_preferences(multi_topic_db, user, [ai_id, ai_id, ai_id, ai_id, ai_id])

    by_name = {c.name: c.subscribed for c in choices}
    assert by_name["AI"] is True


def test_set_preferences_new_ids_and_names_together_stay_at_cap(five_topic_db: Session):
    user = _user(five_topic_db)
    ids = [t for (t,) in five_topic_db.execute(select(Topic.id))][:3]

    choices = set_preferences(five_topic_db, user, ids, new_topic_names=["Quantum Computing"])

    assert sum(c.subscribed for c in choices) == MAX_TOPICS


def test_set_preferences_updates_user_topic_preferences_for_digest(multi_topic_db: Session):
    """Criterion 3: digest.build_digests reads User.topic_preferences directly,
    so proving the relationship reflects the new set is enough to lock the
    behavior without touching the digest pipeline."""
    user = _user(multi_topic_db)
    space_id = _topic_id(multi_topic_db, "Space")

    set_preferences(multi_topic_db, user, [space_id])
    multi_topic_db.refresh(user)

    assert {p.topic_id for p in user.topic_preferences} == {space_id}
