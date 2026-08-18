from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from newsagent.api.deps import get_db
from newsagent.api.main import app
from newsagent.models import Source, Topic
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


def _make_source(db_session: Session, status: str) -> Source:
    topic = db_session.query(Topic).filter_by(name="AI").first()
    if topic is None:
        topic = Topic(name="AI")
        db_session.add(topic)
        db_session.flush()
    source = Source(topic_id=topic.id, name="Feed", url=f"https://example.com/{status}", status=status)
    db_session.add(source)
    db_session.commit()
    return source


def test_unauthenticated_gets_401(client: TestClient):
    response = client.get("/admin/sources")
    assert response.status_code == 401


def test_non_admin_user_gets_403(as_user: TestClient):
    response = as_user.get("/admin/sources")
    assert response.status_code == 403


def test_admin_gets_200(as_admin: TestClient):
    response = as_admin.get("/admin/sources")
    assert response.status_code == 200
    assert response.json() == []


def test_admin_sees_only_pending_sources(as_admin: TestClient, db_session: Session):
    pending = _make_source(db_session, "pending")
    _make_source(db_session, "approved")

    response = as_admin.get("/admin/sources")
    assert response.status_code == 200
    assert [source["id"] for source in response.json()] == [pending.id]


def test_admin_can_approve_pending_source(as_admin: TestClient, db_session: Session):
    source = _make_source(db_session, "pending")

    response = as_admin.patch(f"/admin/sources/{source.id}", json={"status": "approved"})
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    list_response = as_admin.get("/admin/sources")
    assert list_response.json() == []


def test_patch_rejects_invalid_status(as_admin: TestClient, db_session: Session):
    source = _make_source(db_session, "pending")

    response = as_admin.patch(f"/admin/sources/{source.id}", json={"status": "bogus"})
    assert response.status_code == 422


def test_patch_unknown_source_returns_404(as_admin: TestClient):
    response = as_admin.patch("/admin/sources/999", json={"status": "approved"})
    assert response.status_code == 404
