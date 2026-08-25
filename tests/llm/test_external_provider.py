"""Focused unit tests for ExternalLLMProvider beyond the shared contract
suite: junk-refusal without network, error mapping, and retry mechanics."""

import json
import logging

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


def test_non_list_paragraphs_he_maps_to_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps(
            {
                "summary_he": "x",
                "title_he": "x",
                "source_language": "en",
                "reading_time_minutes": 1,
                "paragraphs_he": "not a list",
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
                "paragraphs_he": ["a"],
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


# -- GH #38: stage-labelled diagnostics for malformed output ------------------


def _summarize_returning(content: str) -> ExternalLLMProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return _provider_with_handler(handler)


def test_fenced_json_now_parses_successfully(caplog):
    """GH #40: z-ai/glm-5.2 wraps its JSON in a ```json fence about half the
    time despite the prompt forbidding it - measured as 100% of GH #38's
    sampled failures. The fence is stripped before parsing, so this is a
    success path now, and it must log nothing."""
    provider = _summarize_returning(
        "```json\n"
        + json.dumps(
            {
                "summary_he": "s",
                "title_he": "t",
                "source_language": "en",
                "reading_time_minutes": 2,
                "paragraphs_he": ["a"],
                "interestingness": 0.5,
            }
        )
        + "\n```"
    )

    with caplog.at_level(logging.WARNING):
        result = provider.summarize(ON_TOPIC_ARTICLE)

    assert result.title_he == "t"
    assert caplog.text == ""


def test_prose_before_the_json_still_logs_the_json_stage(caplog):
    """Fence stripping must not paper over genuinely unparseable output - the
    diagnostics still have to fire for anything it cannot rescue."""
    provider = _summarize_returning('Sure! Here you go:\n{"summary_he": "x"}')

    with caplog.at_level(logging.WARNING, logger="newsagent.llm.external"):
        with pytest.raises(LLMProviderError):
            provider.summarize(ON_TOPIC_ARTICLE)

    assert "stage=json" in caplog.text
    assert "Sure! Here you go" in caplog.text, "raw content must stay visible"


def test_truncated_json_logs_the_json_stage_and_the_length(caplog):
    truncated = '{"summary_he": "abc", "title_he": "def", "reading_time'
    provider = _summarize_returning(truncated)

    with caplog.at_level(logging.WARNING, logger="newsagent.llm.external"):
        with pytest.raises(LLMProviderError):
            provider.summarize(ON_TOPIC_ARTICLE)

    assert "stage=json" in caplog.text
    assert f"len={len(truncated)}" in caplog.text


def test_schema_failure_logs_the_schema_stage_not_the_json_stage(caplog):
    """Valid JSON, empty paragraphs_he - a different bug from a parse failure, and
    the log has to say so or the 33 failures stay indistinguishable."""
    provider = _summarize_returning(
        json.dumps(
            {
                "summary_he": "s",
                "title_he": "t",
                "source_language": "en",
                "reading_time_minutes": 2,
                "paragraphs_he": [],
                "interestingness": 0.5,
            }
        )
    )

    with caplog.at_level(logging.WARNING, logger="newsagent.llm.external"):
        with pytest.raises(LLMProviderError):
            provider.summarize(ON_TOPIC_ARTICLE)

    assert "stage=schema" in caplog.text
    assert "stage=json" not in caplog.text
    assert "paragraphs_he" in caplog.text


def test_bad_envelope_logs_the_envelope_stage(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": {"message": "upstream is down"}})

    provider = _provider_with_handler(handler)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(LLMProviderError):
            provider.summarize(ON_TOPIC_ARTICLE)

    assert "stage=envelope" in caplog.text
    assert "upstream is down" in caplog.text, "body comes from the client layer's own log"


def test_long_content_is_clipped_at_both_ends(caplog):
    content = "PREFIX" + ("x" * 5000) + "SUFFIX"
    provider = _summarize_returning(content)

    with caplog.at_level(logging.WARNING, logger="newsagent.llm.external"):
        with pytest.raises(LLMProviderError):
            provider.summarize(ON_TOPIC_ARTICLE)

    assert "PREFIX" in caplog.text, "head shows fencing/prose"
    assert "SUFFIX" in caplog.text, "tail shows truncation"
    assert len(caplog.text) < len(content), "must not dump the whole response"
    assert f"len={len(content)}" in caplog.text


def test_successful_summarize_logs_nothing(caplog):
    provider = _summarize_returning(
        json.dumps(
            {
                "summary_he": "s",
                "title_he": "t",
                "source_language": "en",
                "reading_time_minutes": 2,
                "paragraphs_he": ["a"],
                "interestingness": 0.5,
            }
        )
    )

    with caplog.at_level(logging.WARNING):
        provider.summarize(ON_TOPIC_ARTICLE)

    assert caplog.text == ""


def test_diagnostics_never_log_the_auth_token(caplog):
    provider = _summarize_returning("not json at all")

    with caplog.at_level(logging.WARNING):
        with pytest.raises(LLMProviderError):
            provider.summarize(ON_TOPIC_ARTICLE)

    assert "test-token" not in caplog.text
    assert "Bearer" not in caplog.text


@pytest.mark.parametrize(
    "content", [None, 42, {"summary_he": "x"}, ["a"]], ids=["null", "int", "dict", "list"]
)
def test_non_string_content_stays_inside_the_llm_error_hierarchy(content, caplog):
    """OpenAI-compatible endpoints return "content": null for tool calls,
    filtered completions, and reasoning models that answer in a sibling field.
    If that escapes as a bare TypeError it sails past summarize's `except
    LLMError` and aborts the whole stage, leaving the article unmarked so the
    next run crashes on it again - one article poisons every other."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    provider = _provider_with_handler(handler)

    with caplog.at_level(logging.WARNING, logger="newsagent.llm.external"):
        with pytest.raises(LLMProviderError):
            provider.summarize(ON_TOPIC_ARTICLE)

    assert "stage=json" in caplog.text
    assert type(content).__name__ in caplog.text, "the log must name the type it got"


def test_usage_is_attached_to_the_result_in_tokens():
    """GH #19: the provider-reported counts must reach the pipeline reports,
    tagged as tokens so they never mix with the mock provider's word counts."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps({"score": 0.5})}}],
                "usage": {"prompt_tokens": 900, "completion_tokens": 12},
            },
        )

    result = _provider_with_handler(handler).score_relevance(ON_TOPIC_ARTICLE, TOPIC)

    assert result.usage is not None
    assert (result.usage.input_units, result.usage.output_units) == (900, 12)
    assert result.usage.unit == "tokens"


def test_result_is_unchanged_when_the_backend_reports_no_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps({"score": 0.5})}}]}
        )

    result = _provider_with_handler(handler).score_relevance(ON_TOPIC_ARTICLE, TOPIC)

    assert result.score == 0.5
    assert result.usage is None


def test_json_stage_failure_still_records_usage_for_draining():
    """GH #19: the fix's core acceptance criterion. HTTP 200 with a valid
    usage block, but content that fails json.loads (GH #38's stage=json) -
    the call was billed and must be counted, not silently zero."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "not json at all"}}],
                "usage": {"prompt_tokens": 640, "completion_tokens": 88},
            },
        )

    provider = _provider_with_handler(handler)
    with pytest.raises(LLMProviderError):
        provider.summarize(ON_TOPIC_ARTICLE)

    drained = provider.drain_usage()
    assert len(drained) == 1
    assert (drained[0].input_units, drained[0].output_units) == (640, 88)
    assert drained[0].unit == "tokens"


def test_schema_stage_failure_still_records_usage_for_draining():
    """Same acceptance criterion, for a call that parsed as JSON but failed
    the schema build (GH #38's stage=schema)."""

    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps({"unexpected": "shape"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 300, "completion_tokens": 40},
            },
        )

    provider = _provider_with_handler(handler)
    with pytest.raises(LLMProviderError):
        provider.score_relevance(ON_TOPIC_ARTICLE, TOPIC)

    drained = provider.drain_usage()
    assert (drained[0].input_units, drained[0].output_units) == (300, 40)


def test_successful_call_does_not_double_count_usage():
    """The success path attaches Usage to the result AND records it once for
    draining - these must be the same single billed call, not two counts."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps({"score": 0.5})}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 5},
            },
        )

    provider = _provider_with_handler(handler)
    result = provider.score_relevance(ON_TOPIC_ARTICLE, TOPIC)

    assert result.usage is not None
    drained = provider.drain_usage()
    assert len(drained) == 1
    assert (drained[0].input_units, drained[0].output_units) == (100, 5)


def test_auth_failure_records_no_usage():
    """A 401/403 never reaches a JSON body with a usage block - nothing was
    billed, so drain_usage() must stay empty."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    provider = _provider_with_handler(handler)
    with pytest.raises(LLMProviderError):
        provider.score_relevance(ON_TOPIC_ARTICLE, TOPIC)

    assert provider.drain_usage() == []
