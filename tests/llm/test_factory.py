import pytest

from newsagent.config import settings
from newsagent.llm.external import ExternalLLMProvider
from newsagent.llm.factory import get_llm_provider
from newsagent.llm.mock import MockLLMProvider


def test_default_provider_is_mock():
    assert isinstance(get_llm_provider(), MockLLMProvider)


def test_unknown_provider_raises_clear_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "llm_provider", "no-such-provider")
    with pytest.raises(ValueError, match="no-such-provider"):
        get_llm_provider()


def test_external_provider_resolves_when_configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "llm_provider", "external")
    monkeypatch.setattr(settings, "external_llm_base_url", "http://external-model.test")
    monkeypatch.setattr(settings, "external_llm_model", "test-model")
    assert isinstance(get_llm_provider(), ExternalLLMProvider)
