"""PopularitySuggestionSource's own behavior, plus the shared retry mechanics
it inherits from base.py (CAP-3 equivalent for this provider family)."""

import pytest

from newsagent.suggestions.base import SuggestionSource
from newsagent.suggestions.errors import SuggestionProviderError, SuggestionTransportError
from newsagent.suggestions.popularity import PopularitySuggestionSource
from newsagent.suggestions.types import PromptText, RoleOption, TopicPopularity, TopicSuggestion

POPULARITY = [
    TopicPopularity(topic_id=1, selection_count=5),
    TopicPopularity(topic_id=2, selection_count=20),
    TopicPopularity(topic_id=3, selection_count=0),
]


def test_suggest_roles_returns_empty():
    assert PopularitySuggestionSource().suggest_roles("Tech") == []


def test_suggest_roles_returns_empty_with_existing_roles_context():
    assert (
        PopularitySuggestionSource().suggest_roles(
            "Tech", existing_roles=["Software Engineer"]
        )
        == []
    )


def test_suggest_prompts_returns_empty():
    assert PopularitySuggestionSource().suggest_prompts() == []


def test_suggest_prompts_returns_empty_with_context():
    assert (
        PopularitySuggestionSource().suggest_prompts(
            field_name="Tech", role_name="Software Engineer", experience_bucket="3-5"
        )
        == []
    )


def test_suggest_topics_with_no_profile_match_returns_non_empty_ranked_list():
    result = PopularitySuggestionSource().suggest_topics(
        field_name=None, role_name=None, interest_free_text=None, popularity=POPULARITY
    )
    assert result == [
        TopicSuggestion(topic_id=2),
        TopicSuggestion(topic_id=1),
        TopicSuggestion(topic_id=3),
    ]


def test_suggest_topics_ignores_profile_data():
    """Two different profiles against the same popularity data get the same
    result — the fallback genuinely doesn't key off Field/Role/interest text."""
    provider = PopularitySuggestionSource()
    no_profile = provider.suggest_topics(
        field_name=None, role_name=None, interest_free_text=None, popularity=POPULARITY
    )
    with_profile = provider.suggest_topics(
        field_name="Tech",
        role_name="Developer Relations",
        interest_free_text="curious about ML",
        popularity=POPULARITY,
    )
    assert no_profile == with_profile


def test_suggest_topics_keeps_zero_selection_candidates():
    result = PopularitySuggestionSource().suggest_topics(
        field_name=None, role_name=None, interest_free_text=None, popularity=POPULARITY
    )
    assert TopicSuggestion(topic_id=3) in result


def test_suggest_topics_empty_popularity_returns_empty():
    """Not this provider's job to guarantee non-emptiness against an empty
    input — that's the calling service's query responsibility (Story 1.6)."""
    result = PopularitySuggestionSource().suggest_topics(
        field_name=None, role_name=None, interest_free_text=None, popularity=[]
    )
    assert result == []


# --- Retry mechanics (inherited from base.py, exercised via a local double) -


class _FlakySource(SuggestionSource):
    """Minimal SuggestionSource double with fail-injection knobs, analogous to
    MockLLMProvider — exists only to exercise base.py's shared _run retry
    loop. PopularitySuggestionSource has no real failure mode of its own."""

    def __init__(self, *, fail_transient: int = 0, fail_permanent: bool = False, **kwargs: object):
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._fail_transient = fail_transient
        self._fail_permanent = fail_permanent

    def _maybe_fail(self) -> None:
        if self._fail_permanent:
            raise SuggestionProviderError("injected permanent failure")
        if self._fail_transient > 0:
            self._fail_transient -= 1
            raise SuggestionTransportError("injected transient failure")

    def _suggest_roles(self, field_name: str, *, existing_roles=()) -> list[RoleOption]:
        self._maybe_fail()
        return []

    def _suggest_prompts(
        self, *, field_name=None, role_name=None, experience_bucket=None
    ) -> list[PromptText]:
        self._maybe_fail()
        return []

    def _suggest_topics(self, *, field_name, role_name, interest_free_text, popularity):
        self._maybe_fail()
        return []


def test_transient_failures_are_retried_then_succeed():
    sleeps: list[float] = []
    source = _FlakySource(fail_transient=2, sleep=sleeps.append)
    source.suggest_prompts()
    assert len(sleeps) == 2


def test_transient_failures_beyond_attempts_surface_typed_error():
    source = _FlakySource(fail_transient=10, sleep=lambda _: None)
    with pytest.raises(SuggestionTransportError):
        source.suggest_prompts()


def test_permanent_failure_is_not_retried():
    sleeps: list[float] = []
    source = _FlakySource(fail_permanent=True, sleep=sleeps.append)
    with pytest.raises(SuggestionProviderError):
        source.suggest_prompts()
    assert sleeps == []


def test_backoff_grows_exponentially():
    sleeps: list[float] = []
    source = _FlakySource(fail_transient=2, backoff_seconds=1.0, sleep=sleeps.append)
    source.suggest_prompts()
    assert sleeps == [1.0, 2.0]
