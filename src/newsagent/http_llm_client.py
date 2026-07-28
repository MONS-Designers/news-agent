"""Thin shared HTTP transport for OpenAI-compatible chat-completions endpoints.

Domain-free: no article/topic/suggestion language, no error wrapping. Every
`httpx`/JSON-parsing exception propagates untouched — callers (`llm/external.py`,
`suggestions/llm.py`) each map failures to their own error hierarchy.
"""

import httpx


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
    return response.json()["choices"][0]["message"]["content"]
