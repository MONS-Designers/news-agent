"""Unit tests for the shared chat-completions HTTP helper — offline only, via
httpx.MockTransport. No error mapping happens here (that's each adapter's own
job); this only checks the request shape and that httpx errors propagate raw.
"""

import json
import logging

import httpx
import pytest

from newsagent.http_llm_client import send_chat_completion


def test_happy_path_returns_content_string():
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
    assert result == "hello there"


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
