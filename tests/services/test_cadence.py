from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.models import Digest, User
from newsagent.models.base import Base
from newsagent.services.cadence import (
    DAILY,
    TWICE_WEEKLY,
    WEEKLY,
    due_user_ids,
    effective_weekdays,
    frequency_of,
    local_today,
)

# date.weekday() numbering: Monday=0 ... Sunday=6.
SUN, MON, TUE, WED, THU, FRI, SAT = 6, 0, 1, 2, 3, 4, 5

TODAY = date(2026, 8, 23)  # a Sunday


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _user(db: Session, user_id: int, weekdays: list[int] | None = None, **kwargs) -> User:
    if weekdays is not None:
        kwargs["digest_weekdays"] = weekdays
    user = User(id=user_id, email=f"u{user_id}@example.com", **kwargs)
    db.add(user)
    db.commit()
    return user


def _sent_digest(db: Session, user: User, on: date) -> None:
    db.add(Digest(user_id=user.id, date=on, sent_at=datetime(on.year, on.month, on.day)))
    db.commit()


def test_new_user_defaults_to_sunday():
    assert TODAY.weekday() == SUN
    assert effective_weekdays(None) == [SUN]


def test_user_is_due_on_a_chosen_day(db: Session):
    _user(db, 1, [SUN])
    assert due_user_ids(db, TODAY) == [1]


def test_user_is_not_due_on_a_day_they_did_not_choose(db: Session):
    _user(db, 1, [THU])
    assert due_user_ids(db, TODAY) == []


def test_one_send_per_chosen_day(db: Session):
    """A second tick on the same day must not owe a second digest."""
    user = _user(db, 1, [SUN])
    _sent_digest(db, user, TODAY)

    assert due_user_ids(db, TODAY) == []


def test_a_missed_day_is_not_made_up_the_next_day(db: Session):
    """Monday is not a chosen day, so the reader waits for the next one -
    unsent articles simply roll into that digest."""
    _user(db, 1, [SUN])
    assert due_user_ids(db, date(2026, 8, 24)) == []


def test_schedules_are_independent_per_user(db: Session):
    """The whole point of the column: one sweep, different schedules."""
    _user(db, 1, [SUN, MON, TUE, WED, THU, FRI])
    _user(db, 2, [SUN, WED])
    _user(db, 3, [THU])

    assert due_user_ids(db, TODAY) == [1, 2]


def test_unsubscribed_user_is_never_due(db: Session):
    _user(db, 1, [SUN], unsubscribed_at=datetime(2026, 8, 1))
    assert due_user_ids(db, TODAY) == []


def test_a_built_but_unsent_digest_does_not_count_as_delivered(db: Session):
    """Only delivery counts - a digest that failed to send must be retried
    the same day, not skipped until the reader's next chosen day."""
    user = _user(db, 1, [SUN])
    db.add(Digest(user_id=user.id, date=TODAY, sent_at=None))
    db.commit()

    assert due_user_ids(db, TODAY) == [1]


@pytest.mark.parametrize(
    ("weekdays", "expected"),
    [
        ([SUN, MON, TUE, WED, THU, FRI], DAILY),
        ([FRI, THU, WED, TUE, MON, SUN], DAILY),
        ([SUN, WED], TWICE_WEEKLY),
        ([THU], WEEKLY),
    ],
)
def test_frequency_is_derived_from_the_chosen_days(weekdays, expected):
    assert frequency_of(weekdays) == expected


@pytest.mark.parametrize(
    "weekdays",
    [
        [],
        [SAT],  # never a send day
        [SUN, SAT],
        [SUN, SUN],  # duplicates
        [SUN, MON, TUE],  # no three-day frequency
        [SUN, MON, TUE, WED, THU],
        [7],
        [True],  # bool is an int subclass in Python
        "0",
        None,
    ],
)
def test_invalid_day_sets_have_no_frequency(weekdays):
    assert frequency_of(weekdays) is None


def test_invalid_stored_days_fall_back_to_the_default():
    """A row written by another version of the app must not stop that reader's
    mail - it just gets the default schedule."""
    assert effective_weekdays([SAT]) == [SUN]
    assert effective_weekdays("garbage") == [SUN]


def test_stored_days_are_returned_in_week_order():
    assert effective_weekdays([WED, SUN]) == [SUN, WED]


def test_local_today_uses_israel_time_not_utc():
    """22:30 UTC on Saturday is already Sunday in Israel (UTC+3 in summer)."""
    assert local_today(datetime(2026, 8, 22, 22, 30, tzinfo=UTC)) == date(2026, 8, 23)
