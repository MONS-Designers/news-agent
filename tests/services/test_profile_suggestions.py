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
from newsagent.suggestions.types import PromptText, RoleOption


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
