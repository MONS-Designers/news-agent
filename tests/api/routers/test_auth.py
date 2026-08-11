import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.api.auth import Identity
from newsagent.api.routers.auth import _redirect_destination
from newsagent.config import settings
from newsagent.models import User
from newsagent.models.base import Base


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_redirect_destination_admin_goes_to_admin(db: Session):
    identity = Identity(email="admin@example.com", is_admin=True, user_id=None)
    assert _redirect_destination(db, identity) == "/admin"


def test_redirect_destination_first_run_user_goes_home(db: Session):
    user = User(email="new@example.com")
    db.add(user)
    db.commit()
    identity = Identity(email="new@example.com", is_admin=False, user_id=user.id)
    assert _redirect_destination(db, identity) == "/"


def test_redirect_destination_returning_user_goes_to_preferences(db: Session):
    user = User(email="returning@example.com", field_name="Software Engineering")
    db.add(user)
    db.commit()
    identity = Identity(email="returning@example.com", is_admin=False, user_id=user.id)
    assert _redirect_destination(db, identity) == "/preferences"


def test_me_unauthenticated_gets_401(client: TestClient):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_returns_identity(as_admin: TestClient):
    response = as_admin.get("/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "admin@example.com"
    assert body["is_admin"] is True
    assert body["user_id"] is None


def test_login_without_config_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    # Force unconfigured OAuth regardless of the local .env — clear error, not a crash.
    monkeypatch.setattr(settings, "google_client_id", "")
    response = client.get("/auth/login")
    assert response.status_code == 503


def test_logout_clears_session(client: TestClient):
    response = client.post("/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"status": "signed_out"}
