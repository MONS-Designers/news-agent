import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.models import User
from newsagent.models.base import Base
from newsagent.services.subscription import set_unsubscribed


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(id=1, email="user@example.com"))
        session.commit()
        yield session


def test_unsubscribing_sets_timestamp(db: Session):
    user = db.get(User, 1)
    set_unsubscribed(db, user, True)
    assert user.unsubscribed_at is not None


def test_resubscribing_clears_timestamp(db: Session):
    user = db.get(User, 1)
    set_unsubscribed(db, user, True)
    set_unsubscribed(db, user, False)
    assert user.unsubscribed_at is None


def test_unsubscribing_twice_is_idempotent(db: Session):
    user = db.get(User, 1)
    set_unsubscribed(db, user, True)
    first = user.unsubscribed_at
    set_unsubscribed(db, user, True)
    assert user.unsubscribed_at == first


def test_resubscribing_when_already_active_is_a_no_op(db: Session):
    user = db.get(User, 1)
    set_unsubscribed(db, user, False)
    assert user.unsubscribed_at is None
