import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.models.base import Base
from newsagent.services.identity import add_admin, add_user, register_user_if_capacity


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_add_admin_creates_row(db: Session):
    admin, created = add_admin(db, "admin@example.com")
    assert created is True
    assert admin.id is not None
    assert admin.email == "admin@example.com"


def test_add_admin_is_idempotent(db: Session):
    first, _ = add_admin(db, "admin@example.com")
    second, created = add_admin(db, "admin@example.com")
    assert created is False
    assert second.id == first.id


def test_add_admin_normalizes_email(db: Session):
    add_admin(db, "  Admin@Example.COM ")
    _, created = add_admin(db, "admin@example.com")
    assert created is False


def test_add_user_creates_row_with_name(db: Session):
    user, created = add_user(db, "user@example.com", name="Nomi")
    assert created is True
    assert user.name == "Nomi"


def test_add_user_is_idempotent(db: Session):
    first, _ = add_user(db, "user@example.com")
    second, created = add_user(db, "user@example.com")
    assert created is False
    assert second.id == first.id


def test_register_user_if_capacity_creates_row_under_cap(db: Session):
    user = register_user_if_capacity(db, "friend@example.com", "Friend", cap=10)
    assert user is not None
    assert user.email == "friend@example.com"
    assert user.name == "Friend"


def test_register_user_if_capacity_stores_given_and_family_name(db: Session):
    """GH #62: the raw Google OAuth claims land on the row at creation."""
    user = register_user_if_capacity(
        db, "nagy@example.com", "Nagy János", cap=10, given_name="Nagy", family_name="János"
    )
    assert user is not None
    assert user.given_name == "Nagy"
    assert user.family_name == "János"


def test_register_user_if_capacity_defaults_given_and_family_name_to_none(db: Session):
    user = register_user_if_capacity(db, "plain@example.com", "Plain", cap=10)
    assert user is not None
    assert user.given_name is None
    assert user.family_name is None


def test_register_user_if_capacity_refuses_at_cap(db: Session):
    register_user_if_capacity(db, "first@example.com", None, cap=1)
    second = register_user_if_capacity(db, "second@example.com", None, cap=1)
    assert second is None


def test_register_user_if_capacity_boundary_exact_cap(db: Session):
    # cap=2: two slots total, both fill, third is refused.
    a = register_user_if_capacity(db, "a@example.com", None, cap=2)
    b = register_user_if_capacity(db, "b@example.com", None, cap=2)
    c = register_user_if_capacity(db, "c@example.com", None, cap=2)
    assert a is not None
    assert b is not None
    assert c is None


def test_register_user_if_capacity_concurrent_race_never_exceeds_cap(tmp_path):
    """FR3: two callers racing for the last slot - exactly one must win.

    Uses a real file-backed SQLite DB (not :memory:) with two independent
    connections/sessions on separate threads, synchronized with a barrier so
    both attempt their INSERT...SELECT...WHERE at essentially the same
    instant. SQLite's default busy_timeout (5s, set by Python's sqlite3
    module) makes the second writer wait for the first's lock rather than
    erroring, so this exercises the real atomicity guarantee end to end.
    """
    db_path = tmp_path / "race.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    cap = 1  # exactly one slot - the scenario the AC describes
    barrier = threading.Barrier(2)
    results: list[object] = [None, None]

    def attempt(index: int, email: str) -> None:
        with Session(engine) as session:
            barrier.wait()
            results[index] = register_user_if_capacity(session, email, None, cap)

    t1 = threading.Thread(target=attempt, args=(0, "racer-a@example.com"))
    t2 = threading.Thread(target=attempt, args=(1, "racer-b@example.com"))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    winners = [r for r in results if r is not None]
    assert len(winners) == 1, f"expected exactly one winner, got {results}"

    with Session(engine) as session:
        from sqlalchemy import func, select

        from newsagent.models import User

        total = session.scalar(select(func.count()).select_from(User))
        assert total == 1
