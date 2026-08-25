"""The dev-login route must not merely be disabled in production - it must
not exist. These tests reload the router module under each setting so the
registration decision itself is what is being verified, not a runtime flag.
"""

import importlib
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from newsagent.api.deps import get_db
from newsagent.config import settings
from newsagent.models import Admin, User
from newsagent.models.base import Base

USER_EMAIL = "reader@example.com"
ADMIN_EMAIL = "boss@example.com"


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(email=USER_EMAIL))
        session.add(User(email=ADMIN_EMAIL))
        session.add(Admin(email=ADMIN_EMAIL))
        session.commit()
        yield session


def _client(db_session, monkeypatch: pytest.MonkeyPatch, dev_email: str) -> TestClient:
    monkeypatch.setattr(settings, "dev_auth_email", dev_email)

    from newsagent.api.routers import auth as auth_router

    importlib.reload(auth_router)

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(auth_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture(autouse=True)
def _restore_router():
    """Reloading the module mutates global state, so put it back afterwards or
    every later test in the session sees whichever variant ran last."""
    yield
    from newsagent.api.routers import auth as auth_router

    importlib.reload(auth_router)


def test_route_does_not_exist_when_the_setting_is_empty(db, monkeypatch):
    client = _client(db, monkeypatch, "")

    assert client.get("/auth/dev-login", follow_redirects=False).status_code == 404


def test_dev_login_signs_in_the_configured_address(db, monkeypatch):
    client = _client(db, monkeypatch, USER_EMAIL)

    response = client.get("/auth/dev-login", follow_redirects=False)

    assert response.status_code == 307
    assert client.get("/auth/me").json()["email"] == USER_EMAIL


def test_dev_login_can_switch_to_another_seeded_account(db, monkeypatch):
    """Moving between an admin and a reader without editing config is the
    reason the override exists."""
    client = _client(db, monkeypatch, USER_EMAIL)

    client.get(f"/auth/dev-login?email={ADMIN_EMAIL}", follow_redirects=False)

    identity = client.get("/auth/me").json()
    assert identity["email"] == ADMIN_EMAIL
    assert identity["is_admin"] is True
