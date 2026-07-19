import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.models.base import Base
from newsagent.services.identity import add_admin, add_user


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
