from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.models import Field, PendingTaxonomySuggestion, Role


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
    response = client.put("/me/profile", json={"field_name": "Tech", "field_is_other": False})
    assert response.status_code == 401


def test_put_profile_curated_field_saves_field_name(as_user_with_db: TestClient, seeded_db: Session):
    seeded_db.add(Field(name="Tech"))
    seeded_db.commit()

    response = as_user_with_db.put(
        "/me/profile", json={"field_name": "Tech", "field_is_other": False}
    )
    assert response.status_code == 200
    assert response.json() == {
        "field_name": "Tech",
        "role_name": None,
        "experience_bucket": None,
        "interest_free_text": None,
    }
    assert seeded_db.query(PendingTaxonomySuggestion).count() == 0


def test_put_profile_other_field_creates_pending_suggestion(
    as_user_with_db: TestClient, seeded_db: Session
):
    response = as_user_with_db.put(
        "/me/profile", json={"field_name": "Marine Biology", "field_is_other": True}
    )
    assert response.status_code == 200
    assert response.json() == {
        "field_name": "Marine Biology",
        "role_name": None,
        "experience_bucket": None,
        "interest_free_text": None,
    }

    suggestion = seeded_db.scalar(select(PendingTaxonomySuggestion))
    assert suggestion is not None
    assert suggestion.kind == "field"
    assert suggestion.status == "pending"


def test_roles_unauthenticated_gets_401(client: TestClient):
    response = client.get("/me/fields/1/roles")
    assert response.status_code == 401


def test_get_roles_is_scoped_to_the_field(as_user_with_db: TestClient, seeded_db: Session):
    tech = Field(name="Tech")
    finance = Field(name="Finance")
    seeded_db.add_all([tech, finance])
    seeded_db.commit()
    seeded_db.add_all(
        [
            Role(field_id=tech.id, name="Software Engineer"),
            Role(field_id=tech.id, name="Data Scientist"),
            Role(field_id=finance.id, name="Analyst"),
        ]
    )
    seeded_db.commit()

    response = as_user_with_db.get(f"/me/fields/{tech.id}/roles")
    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["Data Scientist", "Software Engineer"]


def test_get_roles_for_unknown_field_returns_empty_list(as_user_with_db: TestClient):
    response = as_user_with_db.get("/me/fields/999/roles")
    assert response.status_code == 200
    assert response.json() == []


def test_put_profile_curated_role_saves_role_name(as_user_with_db: TestClient, seeded_db: Session):
    field = Field(name="Tech")
    seeded_db.add(field)
    seeded_db.commit()
    seeded_db.add(Role(field_id=field.id, name="Software Engineer"))
    seeded_db.commit()

    response = as_user_with_db.put(
        "/me/profile",
        json={"field_name": "Tech", "field_is_other": False, "role_name": "Software Engineer"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "field_name": "Tech",
        "role_name": "Software Engineer",
        "experience_bucket": None,
        "interest_free_text": None,
    }
    assert seeded_db.query(PendingTaxonomySuggestion).count() == 0


def test_put_profile_other_role_creates_field_scoped_suggestion(
    as_user_with_db: TestClient, seeded_db: Session
):
    field = Field(name="Tech")
    seeded_db.add(field)
    seeded_db.commit()

    response = as_user_with_db.put(
        "/me/profile",
        json={
            "field_name": "Tech",
            "field_is_other": False,
            "role_name": "Developer Relations",
            "role_is_other": True,
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "field_name": "Tech",
        "role_name": "Developer Relations",
        "experience_bucket": None,
        "interest_free_text": None,
    }

    suggestion = seeded_db.scalar(select(PendingTaxonomySuggestion))
    assert suggestion is not None
    assert suggestion.kind == "role"
    assert suggestion.field_id == field.id
    assert suggestion.status == "pending"


def test_put_profile_blank_role_name_gets_400(as_user_with_db: TestClient, seeded_db: Session):
    seeded_db.add(Field(name="Tech"))
    seeded_db.commit()

    response = as_user_with_db.put(
        "/me/profile", json={"field_name": "Tech", "field_is_other": False, "role_name": "   "}
    )
    assert response.status_code == 400


def test_put_profile_cannot_pass_off_free_text_as_curated(
    as_user_with_db: TestClient, seeded_db: Session
):
    """Declaring field_is_other=false must not be enough to store arbitrary text
    as curated and bypass the admin review queue."""
    seeded_db.add(Field(name="Tech"))
    seeded_db.commit()

    response = as_user_with_db.put(
        "/me/profile", json={"field_name": "Totally Made Up", "field_is_other": False}
    )
    assert response.status_code == 400
    assert seeded_db.query(PendingTaxonomySuggestion).count() == 0


def test_put_profile_rejections_do_not_disclose_the_cause(
    as_user_with_db: TestClient, seeded_db: Session
):
    seeded_db.add(Field(name="Tech"))
    seeded_db.commit()

    blank = as_user_with_db.put("/me/profile", json={"field_name": "   "})
    uncurated = as_user_with_db.put(
        "/me/profile", json={"field_name": "Totally Made Up", "field_is_other": False}
    )

    assert blank.status_code == uncurated.status_code == 400
    assert blank.json()["detail"] == uncurated.json()["detail"]


def test_put_profile_valid_experience_bucket_saves(as_user_with_db: TestClient, seeded_db: Session):
    seeded_db.add(Field(name="Tech"))
    seeded_db.commit()

    response = as_user_with_db.put(
        "/me/profile",
        json={"field_name": "Tech", "field_is_other": False, "experience_bucket": "6-10"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "field_name": "Tech",
        "role_name": None,
        "experience_bucket": "6-10",
        "interest_free_text": None,
    }


def test_put_profile_invalid_experience_bucket_gets_400(
    as_user_with_db: TestClient, seeded_db: Session
):
    seeded_db.add(Field(name="Tech"))
    seeded_db.commit()

    response = as_user_with_db.put(
        "/me/profile",
        json={"field_name": "Tech", "field_is_other": False, "experience_bucket": "not-a-bucket"},
    )
    assert response.status_code == 400


def test_put_profile_interest_free_text_alone_saves(
    as_user_with_db: TestClient, seeded_db: Session
):
    """The call shape InterestsStep.vue actually uses: no field_name key in the
    body at all, on top of a profile already saved by a prior Step 1 call."""
    seeded_db.add(Field(name="Tech"))
    seeded_db.commit()
    as_user_with_db.put("/me/profile", json={"field_name": "Tech", "field_is_other": False})

    response = as_user_with_db.put("/me/profile", json={"interest_free_text": "curious about ML"})
    assert response.status_code == 200
    assert response.json() == {
        "field_name": "Tech",
        "role_name": None,
        "experience_bucket": None,
        "interest_free_text": "curious about ML",
    }


def test_put_profile_over_long_interest_free_text_gets_400(as_user_with_db: TestClient):
    response = as_user_with_db.put(
        "/me/profile", json={"interest_free_text": "x" * 2001}
    )
    assert response.status_code == 400
