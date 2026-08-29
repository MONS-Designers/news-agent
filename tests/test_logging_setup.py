"""Covers newsagent.logging_setup: the DB handler, level selection, the
uvicorn/noisy-logger re-pointing, and outbound-run correlation.

Two global-state hazards shape this file:

1. configure_logging() mutates the process-wide root logger, so every test runs
   under restore_root_logger. Without it a handler leaks into every sibling suite.
2. These tests read the `settings` singleton, which loads the developer's local
   .env ahead of code defaults - and README tells developers to set exactly
   this variable. Every test therefore pins the value it depends on, including
   the ones asserting "the default", so a local .env can never break them.
"""

import logging

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from newsagent.config import settings
from newsagent.logging_setup import attach_outbound_run, configure_logging, track_outbound_run_logs
from newsagent.models import LogEntry
from newsagent.models.base import Base

_TOUCHED_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access", "httpx", "httpcore")


@pytest.fixture(autouse=True)
def restore_root_logger():
    """configure_logging() mutates root *and* the five loggers it re-points or
    pins, so all six are snapshotted. Restoring only root would leave e.g.
    httpx pinned at WARNING for the rest of the session."""
    root = logging.root
    saved_handlers = root.handlers[:]
    saved_level = root.level
    saved_others = {
        name: (
            logging.getLogger(name).handlers[:],
            logging.getLogger(name).level,
            logging.getLogger(name).propagate,
        )
        for name in _TOUCHED_LOGGERS
    }
    yield
    for handler in root.handlers[:]:
        if handler not in saved_handlers:
            handler.close()
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)
    for name, (handlers, level, propagate) in saved_others.items():
        logger = logging.getLogger(name)
        logger.handlers[:] = handlers
        logger.setLevel(level)
        logger.propagate = propagate


@pytest.fixture
def default_settings(monkeypatch: pytest.MonkeyPatch):
    """Pin the code-level default so a local .env cannot influence the result."""
    monkeypatch.setattr(settings, "log_level", "WARNING")


@pytest.fixture
def db_session(monkeypatch: pytest.MonkeyPatch) -> Session:
    """Point the handler's DB writes at a fresh in-memory sqlite DB instead of
    whatever NEWSAGENT_DATABASE_URL resolves to."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("newsagent.logging_setup.SessionLocal", TestSessionLocal)
    with Session(engine) as session:
        yield session


def test_default_is_a_single_db_handler_at_warning(default_settings, db_session):
    configure_logging()

    assert len(logging.root.handlers) == 1
    from newsagent.logging_setup import _DBHandler

    assert isinstance(logging.root.handlers[0], _DBHandler)
    assert logging.root.level == logging.WARNING


def test_a_warning_record_is_persisted_with_level_logger_and_message(
    default_settings, db_session
):
    configure_logging()
    logging.getLogger("newsagent.pipeline.fetcher").warning("fetch failed")

    entry = db_session.scalar(select(LogEntry))
    assert entry is not None
    assert entry.level == "WARNING"
    assert entry.logger_name == "newsagent.pipeline.fetcher"
    assert "fetch failed" in entry.message


def test_persisted_record_carries_the_app_version(default_settings, db_session):
    from importlib.metadata import version as pkg_version

    configure_logging()
    logging.getLogger("newsagent.pipeline.fetcher").warning("boom")

    entry = db_session.scalar(select(LogEntry))
    assert entry.version == pkg_version("newsagent")


def test_a_fresh_record_has_no_outbound_run_id(default_settings, db_session):
    configure_logging()
    logging.getLogger("newsagent.pipeline.fetcher").warning("boom")

    entry = db_session.scalar(select(LogEntry))
    assert entry.outbound_run_id is None


def test_records_emitted_inside_a_tracked_run_are_attached_afterward(
    default_settings, db_session
):
    configure_logging()
    with track_outbound_run_logs():
        logging.getLogger("newsagent.pipeline.relevance").warning("scored one")
        logging.getLogger("newsagent.pipeline.relevance").warning("scored two")
        attach_outbound_run(db_session, outbound_run_id=42)

    entries = db_session.scalars(select(LogEntry)).all()
    assert len(entries) == 2
    assert all(entry.outbound_run_id == 42 for entry in entries)


def test_records_outside_a_tracked_run_are_unaffected_by_attach(default_settings, db_session):
    configure_logging()
    logging.getLogger("newsagent.pipeline.fetcher").warning("outside any run")
    with track_outbound_run_logs():
        attach_outbound_run(db_session, outbound_run_id=99)

    entry = db_session.scalar(select(LogEntry))
    assert entry.outbound_run_id is None


def test_a_db_write_failure_does_not_raise_and_does_not_crash(default_settings, db_session):
    """No destination fallback is left, so a broken write must degrade to the
    stdlib handleError() path (stderr) rather than propagating - see
    _DBHandler.emit()'s docstring."""
    configure_logging()
    assert len(logging.root.handlers) == 1  # sanity: exactly one handler installed
    from unittest.mock import patch

    with patch("newsagent.services.log_entries.record_log", side_effect=RuntimeError("db down")):
        logging.getLogger("newsagent.pipeline.fetcher").warning("should not crash")  # no raise


def test_debug_level_lets_debug_records_reach_the_destination(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "log_level", "DEBUG")

    configure_logging()
    logging.getLogger("newsagent.pipeline.summarize").debug("raw model response")

    assert logging.root.level == logging.DEBUG
    entry = db_session.scalar(select(LogEntry))
    assert "raw model response" in entry.message


@pytest.mark.parametrize("raw,expected", [("20", logging.INFO), (" debug ", logging.DEBUG)])
def test_level_accepts_numeric_and_padded_names(
    default_settings, db_session, monkeypatch: pytest.MonkeyPatch, raw: str, expected: int
):
    monkeypatch.setattr(settings, "log_level", raw)

    configure_logging()

    assert logging.root.level == expected


def test_unknown_level_names_the_known_values(default_settings, db_session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "log_level", "CHATTY")

    with pytest.raises(ValueError, match="CHATTY") as raised:
        configure_logging()
    assert "WARNING" in str(raised.value)


def test_notset_level_is_rejected(default_settings, db_session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "log_level", "NOTSET")

    with pytest.raises(ValueError, match="NOTSET"):
        configure_logging()


@pytest.mark.parametrize("raw", ["0", " 0 ", "5", "999", "²"])
def test_out_of_range_numeric_levels_are_rejected(
    default_settings, db_session, monkeypatch: pytest.MonkeyPatch, raw: str
):
    """0 is NOTSET by another spelling (emits everything); 999 installs a
    handler that can never emit. Both must fail loudly, not silently."""
    monkeypatch.setattr(settings, "log_level", raw)

    with pytest.raises(ValueError, match="NEWSAGENT_LOG_LEVEL|log level|Log level"):
        configure_logging()


def test_empty_level_falls_back_to_the_default(default_settings, db_session, monkeypatch: pytest.MonkeyPatch):
    """A blank env var means "unset"."""
    monkeypatch.setattr(settings, "log_level", "  ")

    configure_logging()

    assert logging.root.level == logging.WARNING


def test_explicit_access_log_opt_out_is_honored(default_settings, db_session):
    """uvicorn's --no-access-log leaves the logger with no handlers and
    propagate=False. Re-pointing it would resurrect request lines that carry
    tracking-pixel URLs embedding user and article ids."""
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False

    configure_logging()

    assert access.propagate is False


def test_server_handlers_are_closed_when_cleared(default_settings, db_session, tmp_path):
    """Clearing without closing leaks the fd - and on Windows keeps the old
    file locked for the life of the process."""
    stale_path = tmp_path / "stale-uvicorn.log"
    stale = logging.FileHandler(stale_path, encoding="utf-8")
    error_logger = logging.getLogger("uvicorn.error")
    error_logger.addHandler(stale)

    configure_logging()

    assert stale not in error_logger.handlers
    assert stale.stream is None or stale.stream.closed, "handler dropped but never closed"


def test_server_logs_reach_the_destination(default_settings, db_session, monkeypatch: pytest.MonkeyPatch):
    """uvicorn ships propagate=False with its own handlers, so a root-handler
    swap alone would leave every startup/error/access line uncaptured."""
    from logging.config import dictConfig

    from uvicorn.config import LOGGING_CONFIG

    dictConfig(LOGGING_CONFIG)  # what uvicorn does before importing the app
    monkeypatch.setattr(settings, "log_level", "INFO")

    configure_logging()
    logging.getLogger("uvicorn.error").info("Application startup complete")
    logging.getLogger("uvicorn.access").info("GET /health 200")

    messages = [entry.message for entry in db_session.scalars(select(LogEntry)).all()]
    assert "Application startup complete" in messages
    assert "GET /health 200" in messages


def test_log_level_governs_server_and_third_party_loggers(
    default_settings, db_session, monkeypatch: pytest.MonkeyPatch
):
    """uvicorn pins itself to INFO and the noisy pair get a WARNING floor, so a
    stricter LOG_LEVEL must still win - otherwise ERROR silences the application
    while server and transport chatter keeps flowing, the exact inverse of intent."""
    from logging.config import dictConfig

    from uvicorn.config import LOGGING_CONFIG

    dictConfig(LOGGING_CONFIG)
    monkeypatch.setattr(settings, "log_level", "ERROR")

    configure_logging()
    logging.getLogger("uvicorn.access").info("GET /health 200")
    logging.getLogger("uvicorn.error").info("Application startup complete")
    logging.getLogger("httpx").warning("HTTP Request: POST ...")
    logging.getLogger("newsagent.pipeline.fetcher").error("real failure")

    messages = [entry.message for entry in db_session.scalars(select(LogEntry)).all()]
    assert "real failure" in messages
    assert "GET /health 200" not in messages
    assert "Application startup complete" not in messages
    assert not any("HTTP Request" in message for message in messages)


def test_noisy_third_party_loggers_stay_at_warning(
    default_settings, db_session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "log_level", "DEBUG")

    configure_logging()
    logging.getLogger("httpcore.connection").debug("connect_tcp.started")
    logging.getLogger("httpx").debug("HTTP Request: POST ...")
    logging.getLogger("newsagent.pipeline.summarize").debug("raw model response")

    messages = [entry.message for entry in db_session.scalars(select(LogEntry)).all()]
    assert "raw model response" in messages
    assert not any("connect_tcp.started" in message for message in messages)
    assert not any("HTTP Request" in message for message in messages)


def test_calling_twice_does_not_accumulate_handlers(default_settings, db_session):
    configure_logging()
    configure_logging()

    assert len(logging.root.handlers) == 1
