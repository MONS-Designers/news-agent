from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.models import Field, PendingTaxonomySuggestion


def test_unauthenticated_gets_401(client: TestClient):
    response = client.get("/me/preferences")
    assert response.status_code == 401


def test_user_gets_all_topics_none_subscribed(as_user_with_db: TestClient):
    response = as_user_with_db.get("/me/preferences")
    assert response.status_code == 200
    body = response.json()
    assert {item["name"] for item in body} == {"AI", "Cybersecurity", "Space"}
    assert all(item["subscribed"] is False for item in body)


def test_put_then_get_reflects_new_subscriptions(as_user_with_db: TestClient):
    get_response = as_user_with_db.get("/me/preferences")
    ai_id = next(item["topic_id"] for item in get_response.json() if item["name"] == "AI")

    put_response = as_user_with_db.put("/me/preferences", json={"topic_ids": [ai_id]})
    assert put_response.status_code == 200
    put_body = {item["name"]: item["subscribed"] for item in put_response.json()}
    assert put_body == {"AI": True, "Cybersecurity": False, "Space": False}

    get_response = as_user_with_db.get("/me/preferences")
    get_body = {item["name"]: item["subscribed"] for item in get_response.json()}
    assert get_body == put_body


def test_put_unknown_topic_id_returns_400(as_user_with_db: TestClient):
    response = as_user_with_db.put("/me/preferences", json={"topic_ids": [999]})
    assert response.status_code == 400


def test_fields_unauthenticated_gets_401(client: TestClient):
    response = client.get("/me/fields")
    assert response.status_code == 401


def test_get_fields_returns_seeded_fields(as_user_with_db: TestClient, seeded_db: Session):
    seeded_db.add_all([Field(name="Tech"), Field(name="Finance")])
    seeded_db.commit()

    response = as_user_with_db.get("/me/fields")
    assert response.status_code == 200
    assert {item["name"] for item in response.json()} == {"Tech", "Finance"}


def test_put_profile_unauthenticated_gets_401(client: TestClient):
    response = client.put("/me/profile", json={"field_name": "Tech", "is_other": False})
    assert response.status_code == 401


def test_put_profile_curated_field_saves_field_name(as_user_with_db: TestClient, seeded_db: Session):
    seeded_db.add(Field(name="Tech"))
    seeded_db.commit()

    response = as_user_with_db.put("/me/profile", json={"field_name": "Tech", "is_other": False})
    assert response.status_code == 200
    assert response.json() == {"field_name": "Tech"}
    assert seeded_db.scalar(select(Field)) is not None
    assert seeded_db.query(PendingTaxonomySuggestion).count() == 0


def test_put_profile_other_field_creates_pending_suggestion(
    as_user_with_db: TestClient, seeded_db: Session
):
    response = as_user_with_db.put(
        "/me/profile", json={"field_name": "Marine Biology", "is_other": True}
    )
    assert response.status_code == 200
    assert response.json() == {"field_name": "Marine Biology"}

    suggestion = seeded_db.scalar(select(PendingTaxonomySuggestion))
    assert suggestion is not None
    assert suggestion.kind == "field"
    assert suggestion.status == "pending"
