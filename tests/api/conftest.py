from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from newsagent.api.auth import Identity, require_identity, require_user
from newsagent.api.deps import get_db
from newsagent.api.main import app
from newsagent.models import Topic, User
from newsagent.models.base import Base


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def as_admin(client: TestClient) -> TestClient:
    app.dependency_overrides[require_identity] = lambda: Identity(
        email="admin@example.com", is_admin=True, user_id=None
    )
    return client


@pytest.fixture
def as_user(client: TestClient) -> TestClient:
    app.dependency_overrides[require_identity] = lambda: Identity(
        email="user@example.com", is_admin=False, user_id=1
    )
    app.dependency_overrides[require_user] = lambda: User(id=1, email="user@example.com")
    return client


@pytest.fixture
def seeded_db() -> Iterator[Session]:
    """An in-memory DB with one user and the 3 dogfood topics — for endpoints
    (like /me/preferences) that read/write real rows, not just check auth."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(email="user@example.com"))
        session.add_all([Topic(name="AI"), Topic(name="Cybersecurity"), Topic(name="Space")])
        session.commit()
        yield session


@pytest.fixture
def as_user_with_db(client: TestClient, seeded_db: Session) -> TestClient:
    """Like as_user, but backed by seeded_db so the injected user has a real,
    session-bound row (relationships lazy-load correctly)."""
    user = seeded_db.scalar(select(User).where(User.email == "user@example.com"))
    app.dependency_overrides[require_identity] = lambda: Identity(
        email="user@example.com", is_admin=False, user_id=user.id
    )
    app.dependency_overrides[require_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: seeded_db
    return client
