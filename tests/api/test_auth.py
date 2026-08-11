import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.api.auth import resolve_identity
from newsagent.models import Admin, User
from newsagent.models.base import Base


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Admin(email="admin@example.com"))
        session.add(User(email="user@example.com"))
        session.commit()
        yield session


def test_admin_email_resolves_as_admin(db: Session):
    identity = resolve_identity(db, "admin@example.com")
    assert identity is not None
    assert identity.is_admin is True
    assert identity.user_id is None


def test_user_email_resolves_with_user_id(db: Session):
    identity = resolve_identity(db, "user@example.com")
    assert identity is not None
    assert identity.is_admin is False
    assert identity.user_id is not None


def test_unknown_email_self_registers_when_cap_allows(db: Session):
    identity = resolve_identity(db, "stranger@example.com", name="Stranger", cap=10)
    assert identity is not None
    assert identity.is_admin is False
    assert identity.user_id is not None
    created = db.scalar(select(User).where(User.email == "stranger@example.com"))
    assert created is not None
    assert created.name == "Stranger"


def test_unknown_email_resolves_to_none_when_cap_is_full(db: Session):
    # The cap counts the `users` table only (self-registered friends), not
    # admins — db already has 1 User row from the fixture, so cap=1 is full.
    assert resolve_identity(db, "stranger@example.com", cap=1) is None
    assert db.scalar(select(User).where(User.email == "stranger@example.com")) is None


def test_existing_email_ignores_cap(db: Session):
    # A cap of 0 must never affect an email that already has a row (NFR4).
    identity = resolve_identity(db, "user@example.com", cap=0)
    assert identity is not None
    assert identity.is_admin is False
