import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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


@pytest.fixture
def telemetry_db():
    """A throwaway in-memory sqlite DB standing in for the real one, for
    tests that want to inspect what telemetry actually wrote (see the
    autouse fixture below, which every test gets whether it asks for this
    one or not).

    StaticPool + check_same_thread=False: telemetry.sink opens a fresh
    SessionLocal() per write, and a couple of thread-propagation tests in
    tests/telemetry/test_call_recording.py deliberately write from a
    ThreadPoolExecutor worker. Plain sqlite:///:memory: hands each new
    connection its own empty in-memory database (SQLAlchemy's default pool
    for it is one connection per thread), so a worker thread's write would
    silently land in a different, tableless DB than the one
    Base.metadata.create_all() populated here. StaticPool forces every
    connection - main thread or worker - through the same one.

    Fast, and correct for a single writer at a time (every test here except
    one). It is NOT safe under genuinely concurrent multi-threaded writes -
    see test_call_recording.py's own local override of this fixture for the
    one test that needs that, and why this default isn't just made safe for
    it instead.
    """
    from newsagent.models.base import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _isolate_telemetry_from_real_db(monkeypatch: pytest.MonkeyPatch, telemetry_db) -> None:
    """newsagent.telemetry.sink and newsagent.logging_setup's _DBHandler each
    open their own SessionLocal for every write, specifically so a caller
    deep inside pipeline/ or suggestions/ (or anything that merely logs)
    never has to plumb a Session through just to report a call or a line.

    That SessionLocal is bound at import time to whatever NEWSAGENT_DATABASE_URL
    resolves to - the real, shared Neon Postgres instance in this repo's .env,
    not a local dev DB (or, in CI with no .env, a placeholder connection
    string that fails DNS resolution on first use). Without this fixture,
    *every* test that exercises send_chat_completion (most of tests/llm,
    tests/pipeline, and tests/suggestions) would attempt a real write against
    it on every run - and once any test triggers configure_logging()
    (api.main.create_app() does, at collection time via tests/api/conftest.py),
    _DBHandler stays installed on the root logger for the rest of the
    process, so *any* later log call anywhere in the suite would too. This
    fixture is autouse specifically so no individual test file has to know
    either risk exists."""
    monkeypatch.setattr("newsagent.telemetry.sink.SessionLocal", telemetry_db)
    monkeypatch.setattr("newsagent.logging_setup.SessionLocal", telemetry_db)
