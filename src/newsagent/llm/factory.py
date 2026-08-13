"""Provider selection - swapping providers is a one-line config change
(NEWSAGENT_LLM_PROVIDER)."""

from newsagent.config import settings
from newsagent.llm.base import LLMProvider
from newsagent.llm.external import ExternalLLMProvider
from newsagent.llm.mock import MockLLMProvider

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "mock": MockLLMProvider,
    "external": ExternalLLMProvider,
}


def get_llm_provider() -> LLMProvider:
    provider_class = _PROVIDERS.get(settings.llm_provider)
    if provider_class is None:
        known = ", ".join(sorted(_PROVIDERS))
        raise ValueError(f"Unknown LLM provider {settings.llm_provider!r} (known: {known})")
    return provider_class()
