import pytest

from newsagent.config import settings
from newsagent.suggestions.factory import get_suggestion_source
from newsagent.suggestions.popularity import PopularitySuggestionSource


def test_default_provider_is_popularity():
    assert isinstance(get_suggestion_source(), PopularitySuggestionSource)


def test_unknown_provider_raises_clear_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "suggestion_provider", "no-such-provider")
    with pytest.raises(ValueError, match="no-such-provider"):
        get_suggestion_source()
