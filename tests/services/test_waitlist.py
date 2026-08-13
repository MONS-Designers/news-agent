import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from newsagent.models import Waitlist
from newsagent.models.base import Base
from newsagent.services.waitlist import _insert_for_dialect, capture_to_waitlist


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_capture_creates_row_with_name_and_timestamp(db: Session):
    entry = capture_to_waitlist(db, "friend@example.com", "Friend")
    assert entry.id is not None
    assert entry.email == "friend@example.com"
    assert entry.name == "Friend"
    assert entry.captured_at is not None


def test_capture_normalizes_email(db: Session):
    capture_to_waitlist(db, "  Friend@Example.COM ", None)
    entry = db.scalar(select(Waitlist).where(Waitlist.email == "friend@example.com"))
    assert entry is not None


def test_repeat_capture_updates_timestamp_not_duplicate_row(db: Session):
    first = capture_to_waitlist(db, "friend@example.com", "Friend")
    second = capture_to_waitlist(db, "friend@example.com", "Friend")
    assert second.id == first.id
    rows = list(db.scalars(select(Waitlist)))
    assert len(rows) == 1
    assert second.captured_at >= first.captured_at


def test_repeat_capture_refreshes_name(db: Session):
    capture_to_waitlist(db, "friend@example.com", None)
    second = capture_to_waitlist(db, "friend@example.com", "Friend Now")
    assert second.name == "Friend Now"


def test_insert_for_dialect_picks_postgresql():
    assert _insert_for_dialect("postgresql") is postgresql_insert


def test_insert_for_dialect_picks_sqlite():
    assert _insert_for_dialect("sqlite") is sqlite_insert


def test_insert_for_dialect_rejects_unsupported_dialect():
    with pytest.raises(NotImplementedError):
        _insert_for_dialect("mysql")
