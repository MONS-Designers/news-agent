import pytest

from newsagent.config import Settings, settings


@pytest.fixture(autouse=True)
def _isolate_settings_from_local_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The suite assumes newsagent.config.Settings' code defaults ("mock" LLM,
    "popularity" suggestions, "console" mail, ...). A developer's local .env can
    override any of these for manual QA (e.g. NEWSAGENT_SUGGESTION_PROVIDER=llm),
    which otherwise leaks into every test and makes results depend on whose
    machine runs them - reset the shared settings singleton to Settings' own
    defaults, bypassing .env, before each test."""
    defaults = Settings(_env_file=None)
    for name in Settings.model_fields:
        monkeypatch.setattr(settings, name, getattr(defaults, name))
