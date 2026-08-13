from collections.abc import Iterator
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from newsagent.api.deps import get_db
from newsagent.api.main import app
from newsagent.models import Digest, User
from newsagent.models.base import Base


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_unauthenticated_gets_401(client: TestClient):
    response = client.get("/admin/engagement")
    assert response.status_code == 401


def test_non_admin_user_gets_403(as_user: TestClient):
    response = as_user.get("/admin/engagement")
    assert response.status_code == 403


def test_admin_sees_sent_digest_engagement(as_admin: TestClient, db_session: Session):
    db_session.add(User(id=1, email="user@example.com"))
    db_session.flush()
    db_session.add(
        Digest(
            user_id=1,
            date=date(2026, 8, 3),
            sent_at=datetime(2026, 8, 3, 8, 0),
            opened_at=datetime(2026, 8, 3, 9, 0),
        )
    )
    db_session.commit()

    response = as_admin.get("/admin/engagement")
    assert response.status_code == 200
    [row] = response.json()
    assert row["user_email"] == "user@example.com"
    assert row["opened_at"] is not None
    assert row["articles_total"] == 0
    assert row["preferences_clicked"] is False


def test_admin_sees_no_engagement_rows_when_nothing_sent(as_admin: TestClient, db_session: Session):
    response = as_admin.get("/admin/engagement")
    assert response.status_code == 200
    assert response.json() == []
