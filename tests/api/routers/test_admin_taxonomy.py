from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from newsagent.api.deps import get_db
from newsagent.api.main import app
from newsagent.models import PendingTaxonomySuggestion
from newsagent.models.base import Base
from newsagent.services.taxonomy import add_field, list_fields, record_pending_suggestion


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
    db_session.flush()
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


def _seed_field_suggestion(db_session: Session, text: str = "Marine Biology") -> int:
    record_pending_suggestion(db_session, kind="field", field_id=None, text=text)
    db_session.commit()
    return db_session.query(PendingTaxonomySuggestion).filter_by(status="pending").one().id


def test_patch_unauthenticated_gets_401(client: TestClient, db_session: Session):
    suggestion_id = _seed_field_suggestion(db_session)
    response = client.patch(f"/admin/taxonomy/{suggestion_id}", json={"status": "approved"})
    assert response.status_code == 401


def test_patch_non_admin_gets_403(as_user: TestClient, db_session: Session):
    suggestion_id = _seed_field_suggestion(db_session)
    response = as_user.patch(f"/admin/taxonomy/{suggestion_id}", json={"status": "approved"})
    assert response.status_code == 403


def test_admin_can_promote_a_field_suggestion(as_admin: TestClient, db_session: Session):
    suggestion_id = _seed_field_suggestion(db_session)

    response = as_admin.patch(f"/admin/taxonomy/{suggestion_id}", json={"status": "approved"})
    assert response.status_code == 200
    assert response.json()["text"] == "Marine Biology"

    assert [f.name for f in list_fields(db_session)] == ["Marine Biology"]
    assert as_admin.get("/admin/taxonomy").json() == []


def test_admin_can_promote_under_an_edited_name(as_admin: TestClient, db_session: Session):
    suggestion_id = _seed_field_suggestion(db_session, "marine biology")

    response = as_admin.patch(
        f"/admin/taxonomy/{suggestion_id}", json={"status": "approved", "name": "Marine Biology"}
    )
    assert response.status_code == 200
    assert [f.name for f in list_fields(db_session)] == ["Marine Biology"]


def test_admin_can_dismiss_without_curating(as_admin: TestClient, db_session: Session):
    suggestion_id = _seed_field_suggestion(db_session)

    response = as_admin.patch(f"/admin/taxonomy/{suggestion_id}", json={"status": "rejected"})
    assert response.status_code == 200
    assert list_fields(db_session) == []
    assert as_admin.get("/admin/taxonomy").json() == []


def test_promoting_a_role_without_a_field_returns_a_typed_400(
    as_admin: TestClient, db_session: Session
):
    record_pending_suggestion(db_session, kind="role", field_id=None, text="Reef Survey Lead")
    db_session.commit()
    suggestion_id = db_session.query(PendingTaxonomySuggestion).one().id

    response = as_admin.patch(f"/admin/taxonomy/{suggestion_id}", json={"status": "approved"})
    assert response.status_code == 400
    assert response.json()["detail"] == {"error": "role_has_no_field"}
    # Still in the queue, nothing written.
    assert len(as_admin.get("/admin/taxonomy").json()) == 1


def test_deciding_a_decided_suggestion_returns_a_typed_400(
    as_admin: TestClient, db_session: Session
):
    suggestion_id = _seed_field_suggestion(db_session)
    as_admin.patch(f"/admin/taxonomy/{suggestion_id}", json={"status": "rejected"})

    response = as_admin.patch(f"/admin/taxonomy/{suggestion_id}", json={"status": "approved"})
    assert response.status_code == 400
    assert response.json()["detail"] == {"error": "suggestion_not_pending"}


def test_patch_unknown_suggestion_returns_404(as_admin: TestClient):
    response = as_admin.patch("/admin/taxonomy/999", json={"status": "approved"})
    assert response.status_code == 404


def test_patch_rejects_invalid_status(as_admin: TestClient, db_session: Session):
    suggestion_id = _seed_field_suggestion(db_session)
    response = as_admin.patch(f"/admin/taxonomy/{suggestion_id}", json={"status": "bogus"})
    assert response.status_code == 422
