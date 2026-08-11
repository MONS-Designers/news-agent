"""Thin shared HTTP transport for OpenAI-compatible chat-completions endpoints.

Domain-free: no article/topic/suggestion language, no error wrapping. Every
`httpx`/JSON-parsing exception propagates untouched — callers (`llm/external.py`,
`suggestions/llm.py`) each map failures to their own error hierarchy.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Enough of the body to identify the shape (an {"error": ...} object, an HTML
# error page, a truncated envelope) without dumping an entire response.
_BODY_LOG_CHARS = 500


@dataclass(frozen=True)
class ChatCompletion:
    """What the endpoint actually returned. Token counts are reported by the
    provider and are absent on backends that omit a `usage` object, so callers
    must treat them as best-effort rather than guaranteed."""

    content: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def send_chat_completion(
    *,
    base_url: str,
    auth_token: str,
    model: str,
    messages: list[dict[str, str]],
    timeout: float = 30.0,
    on_usage: Callable[[int | None, int | None], None] | None = None,
    client: httpx.Client | None = None,
) -> ChatCompletion:
    """`on_usage`, if given, fires with (prompt_tokens, completion_tokens) the
    moment a `usage` block is found in the response body — before `content` is
    even extracted. This is what lets a caller account for a call that billed
    tokens but then failed to yield usable content (e.g. GH #38's malformed-
    output cases): by the time this function raises, on_usage has already run.
    """
    payload = {"model": model, "messages": messages}
    headers = {"Authorization": f"Bearer {auth_token}"}
    url = f"{base_url.rstrip('/')}/chat/completions"

    if client is not None:
        response = client.post(url, json=payload, headers=headers, timeout=timeout)
    else:
        response = httpx.post(url, json=payload, headers=headers, timeout=timeout)

    response.raise_for_status()
    try:
        body = response.json()
    except ValueError as error:
        # The body was not JSON at all (an HTML error page from a proxy, most
        # commonly). Nothing to extract usage from either.
        logger.warning(
            "response body was not JSON (model=%s, %s, body_len=%d, body[:%d]=%r)",
            model,
            type(error).__name__,
            len(response.text),
            _BODY_LOG_CHARS,
            response.text[:_BODY_LOG_CHARS],
        )
        raise

    # `usage` is absent on some backends and is not worth failing a good
    # completion over, so a malformed or missing block degrades to None.
    usage = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(usage, dict):
        usage = {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    prompt_tokens = prompt_tokens if isinstance(prompt_tokens, int) else None
    completion_tokens = completion_tokens if isinstance(completion_tokens, int) else None
    if on_usage is not None and (prompt_tokens is not None or completion_tokens is not None):
        on_usage(prompt_tokens, completion_tokens)

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        # OpenRouter reports upstream provider failures as HTTP 200 with an
        # {"error": ...} body and no "choices", so this is a normal-looking
        # response that never carried content. Callers only see the exception
        # type, and by then the body is gone — log it here, the one place that
        # still has it. The exception propagates untouched: this module maps
        # nothing, by contract.
        logger.warning(
            "could not read message content from response (model=%s, %s, "
            "body_len=%d, body[:%d]=%r)",
            model,
            type(error).__name__,
            len(response.text),
            _BODY_LOG_CHARS,
            response.text[:_BODY_LOG_CHARS],
        )
        raise

    return ChatCompletion(
        content=content, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
    )
