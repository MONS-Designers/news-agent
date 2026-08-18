"""The async suggestion-computation BackgroundTask body (Story 1.6) - a
distinct concern from save_profile's own validation, covered separately from
test_profile.py."""

import threading
import time

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.models import Topic, User, UserTopicPreference
from newsagent.models.base import Base
from newsagent.models.user import (
    SUGGESTION_STATUS_FAILED,
    SUGGESTION_STATUS_PENDING_SLOW,
    SUGGESTION_STATUS_READY,
)
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
    """AC #3 - the race guard: a newer save happened while this computation
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


# --- Concurrent execution + extended-wait notice (GH #36) --------------------


class _RendezvousSource(SuggestionSource):
    """Both adapter methods must be in flight at the same moment to clear the
    barrier. A sequential implementation can never satisfy it: the first call
    waits alone, times out, and raises BrokenBarrierError out of the service."""

    def __init__(self, barrier: threading.Barrier, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._barrier = barrier

    def _suggest_roles(self, field_name: str, *, existing_roles=()) -> list[RoleOption]:
        return []

    def _suggest_prompts(self, *, field_name=None, role_name=None, experience_bucket=None):
        return []

    def _suggest_topics(self, *, field_name, role_name, interest_free_text, popularity):
        self._barrier.wait()
        return [TopicSuggestion(topic_id=p.topic_id) for p in popularity]

    def _suggest_new_topics(self, *, field_name, role_name, interest_free_text, existing_topic_names):
        self._barrier.wait()
        return [TopicOption(name="Invented")]


class _PartialFailureSource(SuggestionSource):
    """One adapter method raises; the other blocks on `gate` until released, so
    the "one failed while the other is still running" window is deterministic
    rather than a race."""

    def __init__(
        self, *, failing: str, gate: threading.Event | None = None, **kwargs: object
    ) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._failing = failing
        self._gate = gate

    def _suggest_roles(self, field_name: str, *, existing_roles=()) -> list[RoleOption]:
        return []

    def _suggest_prompts(self, *, field_name=None, role_name=None, experience_bucket=None):
        return []

    def _run_side(self, side: str, result):
        if self._failing == side:
            raise SuggestionProviderError(f"injected {side} failure")
        if self._gate is not None:
            assert self._gate.wait(timeout=5), "gate was never released"
        return result

    def _suggest_topics(self, *, field_name, role_name, interest_free_text, popularity):
        return self._run_side("topics", [])

    def _suggest_new_topics(self, *, field_name, role_name, interest_free_text, existing_topic_names):
        return self._run_side("new_topics", [])


def _spy_on_pending_slow(
    monkeypatch: pytest.MonkeyPatch, observed: list[str], gate: threading.Event | None = None
) -> None:
    """Wrap the real interim write so a test can see the status it committed -
    reading it from another thread would mean sharing the Session, which is
    exactly what this feature must never do. Releasing `gate` here (after the
    write) lets the blocked survivor finish."""
    real = profile_service._mark_pending_slow

    def spy(db: Session, user: User, expected_seq: int) -> None:
        real(db, user, expected_seq)
        observed.append(user.suggestion_status)
        if gate is not None:
            gate.set()

    monkeypatch.setattr(profile_service, "_mark_pending_slow", spy)


def test_the_two_suggestion_calls_run_concurrently(db: Session, monkeypatch: pytest.MonkeyPatch):
    """GH #36's whole point: sequential execution cannot pass this."""
    # Generous on purpose: the timeout is a wall-clock safety net for a hung
    # test, not the correctness signal. A correct concurrent implementation
    # clears the barrier immediately regardless of machine load; only a
    # sequential one waits it out, and a slow failure there is fine.
    barrier = threading.Barrier(2, timeout=30)
    monkeypatch.setattr(
        profile_service, "get_suggestion_source", lambda: _RendezvousSource(barrier)
    )
    user = _user(db)
    user.suggestion_request_seq = 1
    db.commit()

    _compute_and_store_suggestions(db, user.id, expected_seq=1)

    assert not barrier.broken
    assert user.suggestion_status == SUGGESTION_STATUS_READY


@pytest.mark.parametrize("failing", ["topics", "new_topics"])
def test_a_failure_in_either_call_alone_still_fails_the_run(
    db: Session, monkeypatch: pytest.MonkeyPatch, failing: str
):
    monkeypatch.setattr(
        profile_service, "get_suggestion_source", lambda: _PartialFailureSource(failing=failing)
    )
    user = _user(db)
    user.suggestion_request_seq = 1
    user.suggested_topic_ids = [999]
    user.suggested_new_topic_names = ["Kept"]
    db.commit()

    _compute_and_store_suggestions(db, user.id, expected_seq=1)

    assert user.suggestion_status == SUGGESTION_STATUS_FAILED
    # Both stored fields, not just the ids - the Boundary names both, and a
    # regression that nulls only the names would slip past a one-field check.
    assert user.suggested_topic_ids == [999]
    assert user.suggested_new_topic_names == ["Kept"]


@pytest.mark.parametrize("failing", ["topics", "new_topics"])
def test_pending_slow_is_written_while_waiting_out_the_survivor(
    db: Session, monkeypatch: pytest.MonkeyPatch, failing: str
):
    gate = threading.Event()
    monkeypatch.setattr(
        profile_service,
        "get_suggestion_source",
        lambda: _PartialFailureSource(failing=failing, gate=gate),
    )
    observed: list[str] = []
    _spy_on_pending_slow(monkeypatch, observed, gate)
    user = _user(db)
    user.suggestion_request_seq = 1
    db.commit()

    _compute_and_store_suggestions(db, user.id, expected_seq=1)

    assert observed == [SUGGESTION_STATUS_PENDING_SLOW]
    # Never terminal: the run still settles, and the poller is never stranded.
    assert user.suggestion_status == SUGGESTION_STATUS_FAILED


def test_no_pending_slow_when_both_calls_succeed(db: Session, monkeypatch: pytest.MonkeyPatch):
    # Pinned to a stub: without this the source comes from settings, and a
    # local .env pointing at a real provider turns this into two paid LLM
    # calls with retries.
    monkeypatch.setattr(profile_service, "get_suggestion_source", _StubSource)
    observed: list[str] = []
    _spy_on_pending_slow(monkeypatch, observed)
    user = _user(db)
    user.suggestion_request_seq = 1
    db.commit()

    _compute_and_store_suggestions(db, user.id, expected_seq=1)

    assert observed == []
    assert user.suggestion_status == SUGGESTION_STATUS_READY


class _FailsLastSource(SuggestionSource):
    """The successful call finishes first; the failure arrives with nothing
    left to wait for, so there is no extended wait to announce."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._ranking_returned = threading.Event()

    def _suggest_roles(self, field_name: str, *, existing_roles=()) -> list[RoleOption]:
        return []

    def _suggest_prompts(self, *, field_name=None, role_name=None, experience_bucket=None):
        return []

    def _suggest_topics(self, *, field_name, role_name, interest_free_text, popularity):
        self._ranking_returned.set()
        return []

    def _suggest_new_topics(self, *, field_name, role_name, interest_free_text, existing_topic_names):
        assert self._ranking_returned.wait(timeout=5)
        # The event fires just *before* the sibling returns, so give the
        # executor a moment to mark that future done - otherwise this raises
        # into a still-"running" sibling and the assertion below is testing a
        # different scenario than the one it names.
        time.sleep(0.05)
        raise SuggestionProviderError("injected late failure")


def test_no_pending_slow_when_the_failure_arrives_last(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(profile_service, "get_suggestion_source", _FailsLastSource)
    observed: list[str] = []
    _spy_on_pending_slow(monkeypatch, observed)
    user = _user(db)
    user.suggestion_request_seq = 1
    db.commit()

    _compute_and_store_suggestions(db, user.id, expected_seq=1)

    assert observed == []
    assert user.suggestion_status == SUGGESTION_STATUS_FAILED


def test_stale_seq_skips_the_pending_slow_write(db: Session, monkeypatch: pytest.MonkeyPatch):
    """The interim write is seq-guarded like the final one - a superseded
    computation must not stamp a status onto a newer request."""
    gate = threading.Event()
    monkeypatch.setattr(
        profile_service,
        "get_suggestion_source",
        lambda: _PartialFailureSource(failing="topics", gate=gate),
    )
    observed: list[str] = []
    _spy_on_pending_slow(monkeypatch, observed, gate)
    user = _user(db)
    user.suggestion_request_seq = 2  # a later save already advanced this
    user.suggestion_status = "pending"
    db.commit()

    _compute_and_store_suggestions(db, user.id, expected_seq=1)  # stale

    assert observed == ["pending"]  # _mark_pending_slow ran but wrote nothing
    assert user.suggestion_status == "pending"  # unchanged, start to finish


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
