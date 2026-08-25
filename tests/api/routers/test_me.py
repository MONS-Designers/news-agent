import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.models import Field, PendingTaxonomySuggestion, Role, Topic, User
from newsagent.models.user import SUGGESTION_STATUS_PENDING_SLOW
from newsagent.services import taxonomy
from newsagent.suggestions.types import RoleOption


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


def test_get_subscription_defaults_to_active(as_user_with_db: TestClient):
    response = as_user_with_db.get("/me/subscription")
    assert response.status_code == 200
    assert response.json() == {"unsubscribed": False}


def test_put_subscription_unsubscribes_then_resubscribes(as_user_with_db: TestClient):
    response = as_user_with_db.put("/me/subscription", json={"unsubscribed": True})
    assert response.status_code == 200
    assert response.json() == {"unsubscribed": True}
    assert as_user_with_db.get("/me/subscription").json() == {"unsubscribed": True}

    response = as_user_with_db.put("/me/subscription", json={"unsubscribed": False})
    assert response.status_code == 200
    assert response.json() == {"unsubscribed": False}


def test_subscription_unauthenticated_gets_401(client: TestClient):
    assert client.get("/me/subscription").status_code == 401
    assert client.put("/me/subscription", json={"unsubscribed": True}).status_code == 401


def test_put_unknown_topic_id_returns_400(as_user_with_db: TestClient):
    response = as_user_with_db.put("/me/preferences", json={"topic_ids": [999]})
    assert response.status_code == 400


def test_put_over_cap_topic_ids_returns_structured_detail(
    as_user_with_db: TestClient, seeded_db: Session
):
    seeded_db.add_all([Topic(name="Finance"), Topic(name="Health")])
    seeded_db.commit()
    ids = [t for (t,) in seeded_db.execute(select(Topic.id))]
    assert len(ids) == 5

    response = as_user_with_db.put("/me/preferences", json={"topic_ids": ids})

    assert response.status_code == 400
    assert response.json()["detail"] == {"error": "topic_cap_exceeded", "max_topics": 4}


# --- New Topic names (Real Topic Suggestions story) --------------------------


def test_put_preferences_with_new_topic_name_creates_pending_topic_and_subscribes(
    as_user_with_db: TestClient, seeded_db: Session
):
    response = as_user_with_db.put(
        "/me/preferences", json={"topic_ids": [], "new_topic_names": ["Quantum Computing"]}
    )
    assert response.status_code == 200
    by_name = {item["name"]: item["subscribed"] for item in response.json()}
    assert by_name["Quantum Computing"] is True

    topic = seeded_db.scalar(select(Topic).where(Topic.name == "Quantum Computing"))
    assert topic is not None
    assert topic.status == "pending"

    get_response = as_user_with_db.get("/me/preferences")
    get_by_name = {item["name"]: item["subscribed"] for item in get_response.json()}
    assert get_by_name["Quantum Computing"] is True


def test_put_preferences_new_topic_name_over_cap_returns_structured_detail(
    as_user_with_db: TestClient, seeded_db: Session
):
    ids = [t for (t,) in seeded_db.execute(select(Topic.id))]  # 3 seeded topics
    assert len(ids) == 3

    response = as_user_with_db.put(
        "/me/preferences",
        json={"topic_ids": ids, "new_topic_names": ["Quantum Computing", "Climate Tech"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {"error": "topic_cap_exceeded", "max_topics": 4}


def test_put_preferences_omitted_new_topic_names_defaults_to_empty(
    as_user_with_db: TestClient,
):
    """Backward-compatible request shape: an existing caller that never learns
    about new_topic_names must keep working unchanged."""
    response = as_user_with_db.put("/me/preferences", json={"topic_ids": []})
    assert response.status_code == 200


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


def test_get_profile_unauthenticated_gets_401(client: TestClient):
    response = client.get("/me/profile")
    assert response.status_code == 401


def test_get_profile_before_any_save_is_all_none(as_user_with_db: TestClient):
    response = as_user_with_db.get("/me/profile")
    assert response.status_code == 200
    assert response.json() == {
        "field_name": None,
        "role_name": None,
        "experience_bucket": None,
        "interest_free_text": None,
        "topics_stale_at": None,
    }


def test_get_profile_reflects_a_prior_save(as_user_with_db: TestClient, seeded_db: Session):
    seeded_db.add(Field(name="Tech"))
    seeded_db.commit()
    as_user_with_db.put("/me/profile", json={"field_name": "Tech", "field_is_other": False})

    response = as_user_with_db.get("/me/profile")

    assert response.status_code == 200
    assert response.json()["field_name"] == "Tech"


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
        "topics_stale_at": None,
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
        "topics_stale_at": None,
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


def test_get_roles_for_unknown_field_returns_404(as_user_with_db: TestClient):
    """Changed by the Role/Prompt Suggestions story: the endpoint now needs the
    Field row itself (to pass field.name into the suggestion source), so a
    missing field_id 404s instead of silently returning []."""
    response = as_user_with_db.get("/me/fields/999/roles")
    assert response.status_code == 404


def test_get_roles_includes_is_curated_flag(as_user_with_db: TestClient, seeded_db: Session):
    tech = Field(name="Tech")
    seeded_db.add(tech)
    seeded_db.commit()
    seeded_db.add(Role(field_id=tech.id, name="Software Engineer"))
    seeded_db.commit()

    response = as_user_with_db.get(f"/me/fields/{tech.id}/roles")
    assert response.status_code == 200
    assert response.json() == [{"name": "Software Engineer", "is_curated": True}]


def test_get_roles_includes_llm_suggestion_as_not_curated(
    as_user_with_db: TestClient, seeded_db: Session, monkeypatch: pytest.MonkeyPatch
):
    """The is_curated: false path (an LLM-invented, not-yet-curated Role) is
    otherwise only exercised at the service level (test_taxonomy.py) - this
    proves it also serializes correctly through the actual RoleOut/router
    boundary, not just the RoleSuggestionView dataclass."""

    class _FakeSource:
        def suggest_roles(self, field_name: str, *, existing_roles=()):
            return [RoleOption(name="Developer Relations")]

    monkeypatch.setattr(taxonomy, "get_suggestion_source", lambda: _FakeSource())

    tech = Field(name="Tech")
    seeded_db.add(tech)
    seeded_db.commit()
    seeded_db.add(Role(field_id=tech.id, name="Software Engineer"))
    seeded_db.commit()

    response = as_user_with_db.get(f"/me/fields/{tech.id}/roles")
    assert response.status_code == 200
    assert response.json() == [
        {"name": "Software Engineer", "is_curated": True},
        {"name": "Developer Relations", "is_curated": False},
    ]


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
        "topics_stale_at": None,
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
        "topics_stale_at": None,
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
        "topics_stale_at": None,
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
        "topics_stale_at": None,
    }


def test_put_profile_over_long_interest_free_text_gets_400(as_user_with_db: TestClient):
    response = as_user_with_db.put(
        "/me/profile", json={"interest_free_text": "x" * 2001}
    )
    assert response.status_code == 400


# --- Topic suggestions (Story 1.6) ------------------------------------------


def test_topic_suggestions_unauthenticated_gets_401(client: TestClient):
    response = client.get("/me/topic-suggestions")
    assert response.status_code == 401


def test_topic_suggestions_before_any_save_is_none(as_user_with_db: TestClient):
    response = as_user_with_db.get("/me/topic-suggestions")
    assert response.status_code == 200
    assert response.json() == {
        "suggestion_status": "none",
        "suggested_topic_ids": None,
        "suggested_new_topic_names": None,
    }


def test_profile_save_triggers_background_computation_visible_via_get(
    as_user_with_db: TestClient, seeded_db: Session
):
    """End-to-end proof the BackgroundTask's engine hand-off (db.get_bind())
    resolves to the *same* database as this test's in-memory seeded_db - not
    the production default. TestClient runs BackgroundTasks synchronously as
    part of the request it's already completed, so by the time this PUT
    returns, the computation has already run."""
    seeded_db.add(Field(name="Tech"))
    seeded_db.commit()

    put_response = as_user_with_db.put(
        "/me/profile", json={"field_name": "Tech", "field_is_other": False}
    )
    assert put_response.status_code == 200

    # The BackgroundTask commits through a second, independent Session bound
    # to the same StaticPool engine - real writes at the DB level, but this
    # fixture's seeded_db is reused across the whole test (unlike production,
    # where every request gets a fresh Session/empty identity map), so its
    # already-loaded User object needs an explicit expire to see them.
    seeded_db.expire_all()

    get_response = as_user_with_db.get("/me/topic-suggestions")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["suggestion_status"] == "ready"
    assert body["suggested_topic_ids"]  # non-empty - the 3 seeded topics


def test_topic_suggestions_surfaces_pending_slow(
    as_user_with_db: TestClient, seeded_db: Session
):
    """The extended-wait notice (GH #36) is only useful if the value actually
    reaches the wizard. This passes today because the response field is a bare
    `str`; it exists so narrowing that field to a Literal/Enum - which the
    frontend's own status union invites - can't silently drop the new value."""
    user = seeded_db.scalar(select(User))
    user.suggestion_status = SUGGESTION_STATUS_PENDING_SLOW
    seeded_db.commit()

    response = as_user_with_db.get("/me/topic-suggestions")

    assert response.status_code == 200
    assert response.json()["suggestion_status"] == "pending_slow"


# --- Prompt suggestions (Role and Prompt Suggestions story) -----------------


def test_prompt_suggestions_unauthenticated_gets_401(client: TestClient):
    response = client.get("/me/prompt-suggestions")
    assert response.status_code == 401


def test_prompt_suggestions_with_popularity_provider_is_empty(as_user_with_db: TestClient):
    """PopularitySuggestionSource (the test default) has nothing to generate -
    this is the same "no error, just no prompts" contract as an LLM failure."""
    response = as_user_with_db.get("/me/prompt-suggestions")
    assert response.status_code == 200
    assert response.json() == []
