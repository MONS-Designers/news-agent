"""Focused unit tests for LLMSuggestionSource — offline via httpx.MockTransport,
never real network. Mirrors tests/suggestions/test_popularity.py's style."""

import json

import httpx
import pytest

from newsagent.config import settings
from newsagent.suggestions.errors import SuggestionProviderError, SuggestionTransportError
from newsagent.suggestions.llm import LLMSuggestionSource
from newsagent.suggestions.types import PromptText, RoleOption, TopicPopularity, TopicSuggestion

POPULARITY = [
    TopicPopularity(topic_id=1, selection_count=5),
    TopicPopularity(topic_id=2, selection_count=20),
]


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "local_llm_base_url", "http://local-model.test")
    monkeypatch.setattr(settings, "local_llm_auth_token", "test-token")
    monkeypatch.setattr(settings, "local_llm_model", "test-model")


def _source_with_handler(handler, **kwargs) -> LLMSuggestionSource:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return LLMSuggestionSource(client=client, **kwargs)


def _content_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_suggest_roles_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return _content_response(json.dumps({"roles": ["Developer Relations", "Backend Engineer"]}))

    source = _source_with_handler(handler)
    assert source.suggest_roles("Tech") == [
        RoleOption(name="Developer Relations"),
        RoleOption(name="Backend Engineer"),
    ]


def test_suggest_roles_includes_existing_roles_in_the_prompt():
    """existing_roles is context for the model, not something enforced
    client-side — this just proves it reaches the request body."""
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return _content_response(json.dumps({"roles": ["Backend Engineer"]}))

    source = _source_with_handler(handler)
    source.suggest_roles("Tech", existing_roles=["Software Engineer", "Product Manager"])

    assert "Software Engineer" in captured["body"]
    assert "Product Manager" in captured["body"]


def test_suggest_prompts_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return _content_response(json.dumps({"prompts": ["I'm curious about AI safety"]}))

    source = _source_with_handler(handler)
    assert source.suggest_prompts() == [PromptText(text="I'm curious about AI safety")]


def test_suggest_prompts_includes_context_in_the_prompt():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return _content_response(json.dumps({"prompts": ["I'm curious about AI safety"]}))

    source = _source_with_handler(handler)
    source.suggest_prompts(field_name="Tech", role_name="Software Engineer", experience_bucket="3-5")

    assert "Tech" in captured["body"]
    assert "Software Engineer" in captured["body"]
    assert "3-5" in captured["body"]


def test_suggest_prompts_omits_none_context_fields_from_the_prompt():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return _content_response(json.dumps({"prompts": []}))

    source = _source_with_handler(handler)
    source.suggest_prompts(field_name="Tech")

    assert "ROLE" not in captured["body"]
    assert "EXPERIENCE_BUCKET" not in captured["body"]


def test_suggest_topics_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return _content_response(json.dumps({"topic_ids": [2, 1]}))

    source = _source_with_handler(handler)
    result = source.suggest_topics(
        field_name="Tech",
        role_name="Developer Relations",
        interest_free_text="curious about ML",
        popularity=POPULARITY,
    )
    assert result == [TopicSuggestion(topic_id=2), TopicSuggestion(topic_id=1)]


def test_suggest_topics_filters_ids_not_in_candidates():
    """The prompt tells the model to only pick from CANDIDATE_TOPICS, but that
    instruction alone isn't enforceable — a hallucinated id (999, not in
    POPULARITY) must be dropped rather than returned as a real suggestion."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _content_response(json.dumps({"topic_ids": [999, 2]}))

    source = _source_with_handler(handler)
    result = source.suggest_topics(
        field_name="Tech", role_name=None, interest_free_text=None, popularity=POPULARITY
    )
    assert result == [TopicSuggestion(topic_id=2)]


def test_suggest_topics_non_list_field_maps_to_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return _content_response(json.dumps({"topic_ids": "12"}))

    source = _source_with_handler(handler)
    with pytest.raises(SuggestionProviderError):
        source.suggest_topics(
            field_name="Tech", role_name=None, interest_free_text=None, popularity=POPULARITY
        )


def test_suggest_roles_non_list_field_maps_to_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return _content_response(json.dumps({"roles": "Backend Engineer"}))

    source = _source_with_handler(handler)
    with pytest.raises(SuggestionProviderError):
        source.suggest_roles("Tech")


def test_auth_error_maps_to_provider_error_not_retried():
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"})

    source = _source_with_handler(handler, sleep=sleeps.append)
    with pytest.raises(SuggestionProviderError):
        source.suggest_prompts()
    assert sleeps == []


def test_timeout_maps_to_transport_error_and_is_retried():
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    source = _source_with_handler(handler, sleep=sleeps.append)
    with pytest.raises(SuggestionTransportError):
        source.suggest_prompts()
    assert len(sleeps) == 2  # retried up to max_attempts (default 3), then raised


def test_malformed_json_response_maps_to_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return _content_response("not json")

    source = _source_with_handler(handler)
    with pytest.raises(SuggestionProviderError):
        source.suggest_prompts()


def test_missing_field_in_model_output_maps_to_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return _content_response(json.dumps({"unexpected": "shape"}))

    source = _source_with_handler(handler)
    with pytest.raises(SuggestionProviderError):
        source.suggest_prompts()


def test_missing_base_url_raises_value_error_at_construction(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "local_llm_base_url", "")
    with pytest.raises(ValueError):
        LLMSuggestionSource()


def test_missing_model_raises_value_error_at_construction(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "local_llm_model", "")
    with pytest.raises(ValueError):
        LLMSuggestionSource()
