"""Thin shared HTTP transport for OpenAI-compatible chat-completions endpoints.

Domain-free: no article/topic/suggestion language, no error wrapping, no DB
access. Every `httpx`/JSON-parsing exception propagates untouched - callers
(`llm/external.py`, `suggestions/llm.py`) each map failures to their own
error hierarchy.

The one thing this module does beyond the raw HTTP call is measure: it times
every attempt and reports a `CallMeasurement` to `newsagent.telemetry.sink`
on every exit path, including failure ones (ARCHITECTURE-SPINE AD-12) - that
report is a default, not something a caller opts into. The sink itself
swallows any write failure, so this never changes what a caller here sees.
"""

import logging
import time
from dataclasses import dataclass

import httpx

from newsagent.telemetry import sink
from newsagent.telemetry.types import STATUS_ERROR, STATUS_OK, CallMeasurement

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
    client: httpx.Client | None = None,
) -> ChatCompletion:
    payload = {"model": model, "messages": messages}
    headers = {"Authorization": f"Bearer {auth_token}"}
    url = f"{base_url.rstrip('/')}/chat/completions"

    start = time.monotonic()
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    output_chars: int | None = None
    status = STATUS_ERROR
    try:
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
        raw_prompt_tokens = usage.get("prompt_tokens")
        raw_completion_tokens = usage.get("completion_tokens")
        prompt_tokens = raw_prompt_tokens if isinstance(raw_prompt_tokens, int) else None
        completion_tokens = (
            raw_completion_tokens if isinstance(raw_completion_tokens, int) else None
        )

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            # OpenRouter reports upstream provider failures as HTTP 200 with an
            # {"error": ...} body and no "choices", so this is a normal-looking
            # response that never carried content. Callers only see the exception
            # type, and by then the body is gone - log it here, the one place that
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

        status = STATUS_OK
        output_chars = len(content) if isinstance(content, str) else None
        return ChatCompletion(
            content=content, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        )
    finally:
        # Reported on every exit path, including every `raise` above (AD-12):
        # a call that billed tokens (usage already parsed) but then failed to
        # yield usable content still shows up, with status="error" and the
        # tokens it billed - never silently free.
        duration_ms = int((time.monotonic() - start) * 1000)
        sink.report(
            CallMeasurement(
                status=status,
                duration_ms=duration_ms,
                model=model,
                tokens_in=prompt_tokens,
                tokens_out=completion_tokens,
                unit="tokens" if (prompt_tokens is not None or completion_tokens is not None)
                else None,
                output_chars=output_chars,
            )
        )
