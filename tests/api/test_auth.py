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


def test_admin_email_also_self_registers_when_cap_allows(db: Session):
    identity = resolve_identity(db, "admin@example.com", name="Admin", cap=10)
    assert identity is not None
    assert identity.is_admin is True
    assert identity.user_id is not None
    created = db.scalar(select(User).where(User.email == "admin@example.com"))
    assert created is not None


def test_admin_still_signs_in_when_cap_is_full(db: Session):
    # The cap gates self-registration, never login: an Admin must always be
    # able to sign in, even with no room left to also become a User.
    identity = resolve_identity(db, "admin@example.com", cap=1)
    assert identity is not None
    assert identity.is_admin is True
    assert identity.user_id is None


def test_admin_with_existing_user_row_resolves_both(db: Session):
    db.add(User(email="admin@example.com", name="Admin"))
    db.commit()

    identity = resolve_identity(db, "admin@example.com")
    assert identity is not None
    assert identity.is_admin is True
    assert identity.user_id is not None


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
    # admins - db already has 1 User row from the fixture, so cap=1 is full.
    assert resolve_identity(db, "stranger@example.com", cap=1) is None
    assert db.scalar(select(User).where(User.email == "stranger@example.com")) is None


def test_existing_email_ignores_cap(db: Session):
    # A cap of 0 must never affect an email that already has a row (NFR4).
    identity = resolve_identity(db, "user@example.com", cap=0)
    assert identity is not None
    assert identity.is_admin is False


def test_new_row_gets_given_and_family_name(db: Session):
    """GH #62: forwarded into brand-new-row creation."""
    identity = resolve_identity(
        db,
        "stranger@example.com",
        name="Nagy János",
        cap=10,
        given_name="Nagy",
        family_name="János",
    )
    assert identity is not None
    created = db.scalar(select(User).where(User.email == "stranger@example.com"))
    assert created is not None
    assert created.given_name == "Nagy"
    assert created.family_name == "János"


def test_existing_row_never_receives_given_or_family_name(db: Session):
    """An existing user re-authenticating must never be mutated - the
    existing-row branch stays read-only even if given_name/family_name are
    passed in."""
    identity = resolve_identity(
        db, "user@example.com", name="Someone", given_name="Given", family_name="Family"
    )
    assert identity is not None
    existing = db.scalar(select(User).where(User.email == "user@example.com"))
    assert existing is not None
    assert existing.given_name is None
    assert existing.family_name is None
