"""Thin shared HTTP transport for OpenAI-compatible chat-completions endpoints.

Domain-free: no article/topic/suggestion language, no error wrapping. Every
`httpx`/JSON-parsing exception propagates untouched — callers (`llm/external.py`,
`suggestions/llm.py`) each map failures to their own error hierarchy.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

# Enough of the body to identify the shape (an {"error": ...} object, an HTML
# error page, a truncated envelope) without dumping an entire response.
_BODY_LOG_CHARS = 500


def send_chat_completion(
    *,
    base_url: str,
    auth_token: str,
    model: str,
    messages: list[dict[str, str]],
    timeout: float = 30.0,
    client: httpx.Client | None = None,
) -> str:
    payload = {"model": model, "messages": messages}
    headers = {"Authorization": f"Bearer {auth_token}"}
    url = f"{base_url.rstrip('/')}/chat/completions"

    if client is not None:
        response = client.post(url, json=payload, headers=headers, timeout=timeout)
    else:
        response = httpx.post(url, json=payload, headers=headers, timeout=timeout)

    response.raise_for_status()
    try:
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as error:
        # OpenRouter reports upstream provider failures as HTTP 200 with an
        # {"error": ...} body and no "choices", so this is a normal-looking
        # response that never carried content. Callers only see the exception
        # type, and by then the body is gone — log it here, the one place that
        # still has it. The exception propagates untouched: this module maps
        # nothing, by contract.
        # The body length distinguishes a small {"error": ...} object from a
        # truncated or oversized stream; the exception type distinguishes "200
        # JSON without choices" from "the body was not JSON at all" (an HTML
        # error page from a proxy), which are different failures.
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
