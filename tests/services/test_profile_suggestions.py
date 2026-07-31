"""The async suggestion-computation BackgroundTask body (Story 1.6) — a
distinct concern from save_profile's own validation, covered separately from
test_profile.py."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.models import Topic, User, UserTopicPreference
from newsagent.models.base import Base
from newsagent.models.user import SUGGESTION_STATUS_FAILED, SUGGESTION_STATUS_READY
from newsagent.services import profile as profile_service
from newsagent.services.profile import _compute_and_store_suggestions, _topic_popularity
from newsagent.suggestions import SuggestionProviderError
from newsagent.suggestions.base import SuggestionSource
from newsagent.suggestions.types import PromptText, RoleOption, TopicOption, TopicSuggestion


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="user@example.com")
        session.add(user)
        session.add_all([Topic(name="AI"), Topic(name="Space")])
        session.commit()
        yield session


def _user(db: Session) -> User:
    return db.scalar(select(User).where(User.email == "user@example.com"))


def _topic(db: Session, name: str) -> Topic:
    return db.scalar(select(Topic).where(Topic.name == name))


# --- _topic_popularity -------------------------------------------------------


def test_topic_popularity_includes_zero_selection_topics(db: Session):
    ai = _topic(db, "AI")
    space = _topic(db, "Space")
    user_a = _user(db)
    db.add(User(email="user2@example.com"))
    db.commit()
    user_b = db.scalar(select(User).where(User.email == "user2@example.com"))
    db.add_all(
        [
            UserTopicPreference(user_id=user_a.id, topic_id=ai.id),
            UserTopicPreference(user_id=user_b.id, topic_id=ai.id),
        ]
    )
    db.commit()

    popularity = {p.topic_id: p.selection_count for p in _topic_popularity(db)}

    assert popularity[ai.id] == 2
    assert popularity[space.id] == 0  # never selected, still present


def test_topic_popularity_carries_name(db: Session):
    ai = _topic(db, "AI")
    by_id = {p.topic_id: p.name for p in _topic_popularity(db)}
    assert by_id[ai.id] == "AI"


def test_topic_popularity_excludes_pending_topics(db: Session):
    """CAP-3: a still-pending Topic must never be offered as a candidate to
    any user's suggestion computation."""
    ai = _topic(db, "AI")
    space = _topic(db, "Space")
    space.status = "pending"
    db.commit()

    ids = {p.topic_id for p in _topic_popularity(db)}

    assert ai.id in ids
    assert space.id not in ids


# --- _compute_and_store_suggestions ------------------------------------------


def test_computes_and_stores_ready_suggestions(db: Session):
    user = _user(db)
    user.suggestion_request_seq = 1
    db.commit()

    _compute_and_store_suggestions(db, user.id, expected_seq=1)

    assert user.suggestion_status == SUGGESTION_STATUS_READY
    assert user.suggested_topic_ids
    assert set(user.suggested_topic_ids) == {_topic(db, "AI").id, _topic(db, "Space").id}


def test_stale_seq_discards_the_result(db: Session):
    """AC #3 — the race guard: a newer save happened while this computation
    was 'running', so its result must not overwrite the current state."""
    user = _user(db)
    user.suggestion_request_seq = 2  # a later save already advanced this
    user.suggestion_status = "pending"
    user.suggested_topic_ids = None
    db.commit()

    _compute_and_store_suggestions(db, user.id, expected_seq=1)  # stale

    assert user.suggestion_status == "pending"  # unchanged
    assert user.suggested_topic_ids is None  # unchanged


class _FailingSource(SuggestionSource):
    def _suggest_roles(self, field_name: str) -> list[RoleOption]:
        return []

    def _suggest_prompts(self) -> list[PromptText]:
        return []

    def _suggest_topics(self, *, field_name, role_name, interest_free_text, popularity):
        raise SuggestionProviderError("injected failure")

    def _suggest_new_topics(self, *, field_name, role_name, interest_free_text, existing_topic_names):
        raise SuggestionProviderError("injected failure")


def test_failure_sets_failed_status_and_leaves_topic_ids_untouched(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(profile_service, "get_suggestion_source", lambda: _FailingSource())
    user = _user(db)
    user.suggestion_request_seq = 1
    user.suggested_topic_ids = [999]  # pre-existing value must survive a failure
    db.commit()

    _compute_and_store_suggestions(db, user.id, expected_seq=1)

    assert user.suggestion_status == SUGGESTION_STATUS_FAILED
    assert user.suggested_topic_ids == [999]  # not overwritten
    assert db.scalar(select(UserTopicPreference)) is None  # no Topic selection touched


def test_deleted_user_is_a_no_op(db: Session):
    _compute_and_store_suggestions(db, user_id=999999, expected_seq=1)  # must not raise


# --- Merged existing + new-name suggestions (Real Topic Suggestions story) --


class _StubSource(SuggestionSource):
    """Configurable double for exercising _compute_and_store_suggestions's
    merge/dedupe/cap logic without a real LLM."""

    def __init__(
        self,
        *,
        topic_ids: list[int] | None = None,
        new_names: list[str] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._topic_ids = topic_ids or []
        self._new_names = new_names or []

    def _suggest_roles(self, field_name: str, *, existing_roles=()) -> list[RoleOption]:
        return []

    def _suggest_prompts(self, *, field_name=None, role_name=None, experience_bucket=None):
        return []

    def _suggest_topics(self, *, field_name, role_name, interest_free_text, popularity):
        return [TopicSuggestion(topic_id=topic_id) for topic_id in self._topic_ids]

    def _suggest_new_topics(self, *, field_name, role_name, interest_free_text, existing_topic_names):
        return [TopicOption(name=name) for name in self._new_names]


def test_merges_existing_and_new_topic_suggestions_under_cap(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    ai = _topic(db, "AI")
    space = _topic(db, "Space")
    monkeypatch.setattr(
        profile_service,
        "get_suggestion_source",
        lambda: _StubSource(topic_ids=[ai.id, space.id], new_names=["New A", "New B", "New C"]),
    )
    user = _user(db)
    user.suggestion_request_seq = 1
    db.commit()

    _compute_and_store_suggestions(db, user.id, expected_seq=1)

    assert user.suggested_topic_ids == [ai.id, space.id]
    assert user.suggested_new_topic_names == ["New A", "New B", "New C"]


def test_new_topic_name_deduped_against_approved_case_and_whitespace_insensitively(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    """'ai' must not show as a separate pill next to the existing 'AI' Topic."""
    monkeypatch.setattr(
        profile_service,
        "get_suggestion_source",
        lambda: _StubSource(topic_ids=[], new_names=["ai", "  Space  "]),
    )
    user = _user(db)
    user.suggestion_request_seq = 1
    db.commit()

    _compute_and_store_suggestions(db, user.id, expected_seq=1)

    assert user.suggested_new_topic_names == []


def test_merged_existing_and_new_total_capped_at_ten(db: Session, monkeypatch: pytest.MonkeyPatch):
    db.add_all([Topic(name=f"Topic {i}") for i in range(10)])
    db.commit()
    all_ids = [topic_id for (topic_id,) in db.execute(select(Topic.id))]
    assert len(all_ids) == 12  # AI, Space + 10 new

    monkeypatch.setattr(
        profile_service,
        "get_suggestion_source",
        lambda: _StubSource(topic_ids=all_ids, new_names=["New A", "New B", "New C"]),
    )
    user = _user(db)
    user.suggestion_request_seq = 1
    db.commit()

    _compute_and_store_suggestions(db, user.id, expected_seq=1)

    assert len(user.suggested_topic_ids) == 10
    assert user.suggested_new_topic_names == []


def test_ranking_matches_popularity_regardless_of_profile(db: Session):
    """Sanity check that the real PopularitySuggestionSource path (no mocking)
    is wired correctly end to end through this function."""
    ai = _topic(db, "AI")
    user = _user(db)
    user.field_name = "Tech"
    user.suggestion_request_seq = 1
    db.add(UserTopicPreference(user_id=user.id, topic_id=ai.id))
    db.commit()

    _compute_and_store_suggestions(db, user.id, expected_seq=1)

    assert user.suggested_topic_ids[0] == ai.id  # AI has 1 selection, Space has 0
    assert set(user.suggested_topic_ids) == {ai.id, _topic(db, "Space").id}
