import pytest

from newsagent.config import settings
from newsagent.suggestions.factory import get_suggestion_source
from newsagent.suggestions.llm import LLMSuggestionSource
from newsagent.suggestions.popularity import PopularitySuggestionSource


def test_default_provider_is_popularity():
    assert isinstance(get_suggestion_source(), PopularitySuggestionSource)


def test_unknown_provider_raises_clear_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "suggestion_provider", "no-such-provider")
    with pytest.raises(ValueError, match="no-such-provider"):
        get_suggestion_source()


def test_llm_provider_resolves_when_configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "suggestion_provider", "llm")
    monkeypatch.setattr(settings, "local_llm_base_url", "http://local-model.test")
    monkeypatch.setattr(settings, "local_llm_model", "test-model")
    assert isinstance(get_suggestion_source(), LLMSuggestionSource)
