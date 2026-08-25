from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.models import Digest, User
from newsagent.models.base import Base
from newsagent.models.user import (
    FREQUENCY_DAILY,
    FREQUENCY_TWICE_WEEKLY,
    FREQUENCY_WEEKLY,
)
from newsagent.services.cadence import due_user_ids, interval_days

TODAY = date(2026, 8, 23)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _user(db: Session, user_id: int, frequency: str = FREQUENCY_WEEKLY, **kwargs) -> User:
    user = User(id=user_id, email=f"u{user_id}@example.com", digest_frequency=frequency, **kwargs)
    db.add(user)
    db.commit()
    return user


def _sent_digest(db: Session, user: User, on: date) -> None:
    db.add(Digest(user_id=user.id, date=on, sent_at=datetime(on.year, on.month, on.day)))
    db.commit()


def test_user_who_never_received_a_digest_is_due(db: Session):
    _user(db, 1)
    assert due_user_ids(db, TODAY) == [1]


def test_weekly_user_is_not_due_before_the_interval_elapses(db: Session):
    user = _user(db, 1, FREQUENCY_WEEKLY)
    _sent_digest(db, user, date(2026, 8, 20))  # 3 days ago

    assert due_user_ids(db, TODAY) == []


def test_weekly_user_is_due_once_the_interval_elapses(db: Session):
    user = _user(db, 1, FREQUENCY_WEEKLY)
    _sent_digest(db, user, date(2026, 8, 16))  # 7 days ago

    assert due_user_ids(db, TODAY) == [1]


def test_daily_user_is_due_the_next_day(db: Session):
    user = _user(db, 1, FREQUENCY_DAILY)
    _sent_digest(db, user, date(2026, 8, 22))

    assert due_user_ids(db, TODAY) == [1]


def test_frequencies_are_independent_per_user(db: Session):
    """The whole point of the column: one sweep, different cadences."""
    daily = _user(db, 1, FREQUENCY_DAILY)
    twice = _user(db, 2, FREQUENCY_TWICE_WEEKLY)
    weekly = _user(db, 3, FREQUENCY_WEEKLY)
    for user in (daily, twice, weekly):
        _sent_digest(db, user, date(2026, 8, 20))  # 3 days ago

    assert due_user_ids(db, TODAY) == [1, 2]


def test_unsubscribed_user_is_never_due(db: Session):
    _user(db, 1, unsubscribed_at=datetime(2026, 8, 1))
    assert due_user_ids(db, TODAY) == []


def test_a_built_but_unsent_digest_does_not_start_the_clock(db: Session):
    """Only delivery counts - a digest that failed to send must not push the
    reader's next one a full interval into the future."""
    user = _user(db, 1, FREQUENCY_WEEKLY)
    db.add(Digest(user_id=user.id, date=TODAY, sent_at=None))
    db.commit()

    assert due_user_ids(db, TODAY) == [1]


def test_unknown_frequency_falls_back_to_the_default(db: Session):
    """A row written by another version of the app must not stop that reader's
    mail - it just gets the default cadence."""
    assert interval_days("fortnightly-ish") == interval_days(FREQUENCY_WEEKLY)
    assert interval_days(None) == interval_days(FREQUENCY_WEEKLY)
