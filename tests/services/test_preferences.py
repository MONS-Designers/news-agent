import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.models import Topic, User
from newsagent.models.base import Base
from newsagent.services.preferences import subscribe


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(email="user@example.com"))
        session.add(Topic(name="AI"))
        session.commit()
        yield session


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
