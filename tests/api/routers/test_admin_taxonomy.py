from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from newsagent.api.deps import get_db
from newsagent.api.main import app
from newsagent.models.base import Base
from newsagent.services.taxonomy import add_field, record_pending_suggestion


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
    response = client.get("/admin/taxonomy")
    assert response.status_code == 401


def test_non_admin_user_gets_403(as_user: TestClient):
    response = as_user.get("/admin/taxonomy")
    assert response.status_code == 403


def test_admin_gets_empty_queue(as_admin: TestClient):
    response = as_admin.get("/admin/taxonomy")
    assert response.status_code == 200
    assert response.json() == []


def test_admin_sees_pending_suggestions_ranked_by_count(as_admin: TestClient, db_session: Session):
    tech, _ = add_field(db_session, "Tech")
    record_pending_suggestion(db_session, kind="role", field_id=tech.id, text="DevRel")
    record_pending_suggestion(db_session, kind="field", field_id=None, text="Marine Biology")
    record_pending_suggestion(db_session, kind="field", field_id=None, text="marine biology")
    db_session.commit()

    response = as_admin.get("/admin/taxonomy")
    assert response.status_code == 200

    body = response.json()
    assert [row["text"] for row in body] == ["Marine Biology", "DevRel"]
    assert body[0]["kind"] == "field"
    assert body[0]["field_name"] is None
    assert body[0]["submission_count"] == 2
    assert body[1] == {
        "id": body[1]["id"],
        "kind": "role",
        "field_name": "Tech",
        "text": "DevRel",
        "submission_count": 1,
    }
