"""Focused unit tests for ExternalLLMProvider beyond the shared contract
suite: junk-refusal without network, error mapping, and retry mechanics."""

import json

import httpx
import pytest

from newsagent.config import settings
from newsagent.llm.errors import LLMProviderError, LLMTransportError
from newsagent.llm.external import ExternalLLMProvider
from tests.llm.provider_contract import JUNK_ARTICLE, ON_TOPIC_ARTICLE, TOPIC


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "external_llm_base_url", "http://external-model.test")
    monkeypatch.setattr(settings, "external_llm_auth_token", "test-token")
    monkeypatch.setattr(settings, "external_llm_model", "test-model")


def _provider_with_handler(handler) -> ExternalLLMProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ExternalLLMProvider(client=client, sleep=lambda _: None)


def test_junk_input_refused_without_network_call():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    provider = _provider_with_handler(handler)
    from newsagent.llm.types import Refusal

    result = provider.score_relevance(JUNK_ARTICLE, TOPIC)
    assert isinstance(result, Refusal)
    assert calls == []


def test_auth_error_maps_to_provider_error_not_retried():
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ExternalLLMProvider(client=client, sleep=sleeps.append)
    with pytest.raises(LLMProviderError):
        provider.score_relevance(ON_TOPIC_ARTICLE, TOPIC)
    assert sleeps == []


def test_timeout_maps_to_transport_error_and_is_retried():
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ExternalLLMProvider(client=client, sleep=sleeps.append)
    with pytest.raises(LLMTransportError):
        provider.score_relevance(ON_TOPIC_ARTICLE, TOPIC)
    assert len(sleeps) == 2  # retried up to max_attempts (default 3), then raised


def test_malformed_json_response_maps_to_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    provider = _provider_with_handler(handler)
    with pytest.raises(LLMProviderError):
        provider.score_relevance(ON_TOPIC_ARTICLE, TOPIC)


def test_missing_field_in_model_output_maps_to_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps({"unexpected": "shape"})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    provider = _provider_with_handler(handler)
    with pytest.raises(LLMProviderError):
        provider.score_relevance(ON_TOPIC_ARTICLE, TOPIC)


def test_out_of_range_score_maps_to_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps({"score": 1.7})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    provider = _provider_with_handler(handler)
    with pytest.raises(LLMProviderError):
        provider.score_relevance(ON_TOPIC_ARTICLE, TOPIC)


def test_non_list_bullets_he_maps_to_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps(
            {
                "summary_he": "x",
                "title_he": "x",
                "source_language": "en",
                "reading_time_minutes": 1,
                "bullets_he": "not a list",
                "interestingness": 0.5,
            }
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    provider = _provider_with_handler(handler)
    with pytest.raises(LLMProviderError):
        provider.summarize(ON_TOPIC_ARTICLE)


def test_zero_reading_time_maps_to_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps(
            {
                "summary_he": "x",
                "title_he": "x",
                "source_language": "en",
                "reading_time_minutes": 0,
                "bullets_he": ["a"],
                "interestingness": 0.5,
            }
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    provider = _provider_with_handler(handler)
    with pytest.raises(LLMProviderError):
        provider.summarize(ON_TOPIC_ARTICLE)


def test_transient_status_408_is_retried():
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(408, json={"error": "request timeout"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ExternalLLMProvider(client=client, sleep=sleeps.append)
    with pytest.raises(LLMTransportError):
        provider.score_relevance(ON_TOPIC_ARTICLE, TOPIC)
    assert len(sleeps) == 2


def test_missing_base_url_raises_value_error_at_construction(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "external_llm_base_url", "")
    with pytest.raises(ValueError):
        ExternalLLMProvider()


def test_missing_model_raises_value_error_at_construction(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "external_llm_model", "")
    with pytest.raises(ValueError):
        ExternalLLMProvider()
