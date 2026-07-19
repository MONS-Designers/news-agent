import pytest
from sqlalchemy import create_engine
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


def test_unknown_email_resolves_to_none(db: Session):
    assert resolve_identity(db, "stranger@example.com") is None
