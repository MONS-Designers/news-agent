"""Provider selection — swapping providers is a one-line config change
(NEWSAGENT_SUGGESTION_PROVIDER). Independent of NEWSAGENT_LLM_PROVIDER (AD-3)."""

from newsagent.config import settings
from newsagent.suggestions.base import SuggestionSource
from newsagent.suggestions.llm import LLMSuggestionSource
from newsagent.suggestions.popularity import PopularitySuggestionSource

_PROVIDERS: dict[str, type[SuggestionSource]] = {
    "popularity": PopularitySuggestionSource,
    "llm": LLMSuggestionSource,
}


def get_suggestion_source() -> SuggestionSource:
    provider_class = _PROVIDERS.get(settings.suggestion_provider)
    if provider_class is None:
        known = ", ".join(sorted(_PROVIDERS))
        raise ValueError(f"Unknown suggestion provider {settings.suggestion_provider!r} (known: {known})")
    return provider_class()
