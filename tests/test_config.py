"""Confirms the unprefixed EXTERNAL_LLM_*/LOCAL_LLM_* env vars actually reach
Settings via Field(alias=...), bypassing the NEWSAGENT_ prefix every other
setting uses. Constructs a real Settings() from the environment rather than
monkeypatching attributes directly, since attribute-patching would pass even
if the alias wiring in config.py were broken."""

import pytest

from newsagent.config import Settings


def test_database_url_default_is_postgres():
    """Checks the field default directly rather than instantiating Settings()
    — a real .env in this repo overrides database_url with a live Neon
    connection string, and this test must never load or touch that value."""
    assert Settings.model_fields["database_url"].default.startswith("postgresql")


def test_unprefixed_llm_env_vars_populate_via_alias(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EXTERNAL_LLM_BASE_URL", "http://external-model.test")
    monkeypatch.setenv("EXTERNAL_LLM_AUTH_TOKEN", "external-token")
    monkeypatch.setenv("EXTERNAL_LLM_MODEL", "external-model-name")
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://local-model.test")
    monkeypatch.setenv("LOCAL_LLM_AUTH_TOKEN", "local-token")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "local-model-name")

    fresh_settings = Settings()

    assert fresh_settings.external_llm_base_url == "http://external-model.test"
    assert fresh_settings.external_llm_auth_token == "external-token"
    assert fresh_settings.external_llm_model == "external-model-name"
    assert fresh_settings.local_llm_base_url == "http://local-model.test"
    assert fresh_settings.local_llm_auth_token == "local-token"
    assert fresh_settings.local_llm_model == "local-model-name"
