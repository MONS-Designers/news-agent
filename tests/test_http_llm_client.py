"""Unit tests for the shared chat-completions HTTP helper — offline only, via
httpx.MockTransport. No error mapping happens here (that's each adapter's own
job); this only checks the request shape and that httpx errors propagate raw.
"""

import json
import logging

import httpx
import pytest

from newsagent.http_llm_client import send_chat_completion


def test_happy_path_returns_the_content():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hello there"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = send_chat_completion(
        base_url="http://local-model.test",
        auth_token="secret-token",
        model="test-model",
        messages=[{"role": "user", "content": "hi"}],
        client=client,
    )
    assert result.content == "hello there"


def test_token_counts_are_read_from_the_usage_block():
    """GH #19: the counts were already flowing through the reports and the CLI —
    the real provider just never populated them, so runs printed 0 in / 0 out."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1200, "completion_tokens": 340},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = send_chat_completion(
        base_url="http://local-model.test",
        auth_token="t",
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        client=client,
    )

    assert result.prompt_tokens == 1200
    assert result.completion_tokens == 340


@pytest.mark.parametrize(
    "body_extra",
    [{}, {"usage": None}, {"usage": {}}, {"usage": "nonsense"}, {"usage": {"prompt_tokens": "x"}}],
    ids=["absent", "null", "empty", "not-a-dict", "wrong-type"],
)
def test_missing_or_malformed_usage_degrades_to_none(body_extra):
    """A good completion must never fail because the backend omitted or
    mangled its accounting block — local models routinely do."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}], **body_extra}
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = send_chat_completion(
        base_url="http://local-model.test",
        auth_token="t",
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        client=client,
    )

    assert result.content == "ok"
    assert result.prompt_tokens is None


def test_http_error_status_propagates_as_http_status_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        send_chat_completion(
            base_url="http://local-model.test",
            auth_token="secret-token",
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
            client=client,
        )


def test_request_shape_includes_model_messages_and_auth_header():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}]
    send_chat_completion(
        base_url="http://local-model.test",
        auth_token="secret-token",
        model="test-model",
        messages=messages,
        client=client,
    )

    assert len(captured) == 1
    request = captured[0]
    assert request.url == "http://local-model.test/chat/completions"
    assert request.headers["authorization"] == "Bearer secret-token"
    body = json.loads(request.content)
    assert body["model"] == "test-model"
    assert body["messages"] == messages


def test_envelope_without_choices_logs_the_body_and_reraises(caplog):
    """OpenRouter reports upstream provider failures as HTTP 200 with an
    {"error": ...} body and no "choices". The caller only ever sees a KeyError,
    so this layer — the last one holding the body — has to log it."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": {"message": "upstream is down"}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.WARNING, logger="newsagent.http_llm_client"):
        with pytest.raises(KeyError):
            send_chat_completion(
                base_url="http://local-model.test",
                auth_token="secret-token",
                model="test-model",
                messages=[{"role": "user", "content": "hi"}],
                client=client,
            )

    assert "upstream is down" in caplog.text
    assert "test-model" in caplog.text


def test_envelope_logging_never_leaks_the_auth_token(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.WARNING, logger="newsagent.http_llm_client"):
        with pytest.raises(IndexError):
            send_chat_completion(
                base_url="http://local-model.test",
                auth_token="super-secret-token",
                model="test-model",
                messages=[{"role": "user", "content": "hi"}],
                client=client,
            )

    assert "super-secret-token" not in caplog.text
    assert "Bearer" not in caplog.text


def test_successful_call_logs_nothing(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.WARNING, logger="newsagent.http_llm_client"):
        send_chat_completion(
            base_url="http://local-model.test",
            auth_token="secret-token",
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
            client=client,
        )

    assert caplog.text == ""


def test_on_usage_fires_even_when_choices_extraction_fails(caplog):
    """GH #19: OpenRouter can return HTTP 200 with a usage block but no
    choices (upstream provider failure). The caller must still learn what was
    billed, even though the function goes on to raise."""
    calls: list[tuple[int | None, int | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"error": {"message": "upstream is down"}, "usage": {"prompt_tokens": 50}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(KeyError):
        send_chat_completion(
            base_url="http://local-model.test",
            auth_token="t",
            model="m",
            messages=[{"role": "user", "content": "hi"}],
            on_usage=lambda p, c: calls.append((p, c)),
            client=client,
        )

    assert calls == [(50, None)]


def test_on_usage_does_not_fire_when_no_json_body_was_parsed():
    """A non-JSON response (e.g. an HTML error page from a proxy) never
    reaches the usage-extraction step — there is nothing to report."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not json</html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError):
        send_chat_completion(
            base_url="http://local-model.test",
            auth_token="t",
            model="m",
            messages=[{"role": "user", "content": "hi"}],
            on_usage=lambda p, c: calls.append((p, c)),
            client=client,
        )

    assert calls == []


def test_on_usage_not_called_when_usage_block_is_absent():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    send_chat_completion(
        base_url="http://local-model.test",
        auth_token="t",
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        on_usage=lambda p, c: calls.append((p, c)),
        client=client,
    )

    assert calls == []
