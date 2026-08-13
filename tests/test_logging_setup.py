"""Covers the destination/level selection in newsagent.logging_setup.

Two global-state hazards shape this file:

1. configure_logging() mutates the process-wide root logger, so every test runs
   under restore_root_logger. Without it a handler leaks into every sibling suite.
2. These tests read the `settings` singleton, which loads the developer's local
   .env ahead of code defaults - and README now tells developers to set exactly
   these variables. Every test therefore pins the values it depends on, including
   the ones asserting "the default", so a local .env can never break them.
"""

import logging
import sys
from pathlib import Path

import pytest

from newsagent.config import settings
from newsagent.logging_setup import configure_logging


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
    """Pin the code-level defaults so a local .env cannot influence the result."""
    monkeypatch.setattr(settings, "log_destination", "stderr")
    monkeypatch.setattr(settings, "log_level", "WARNING")
    monkeypatch.setattr(settings, "log_file", "")


@pytest.fixture
def log_to(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Point logging at a fresh file and hand back the path."""

    def _configure(name: str = "newsagent.log", level: str = "WARNING") -> Path:
        path = tmp_path / name
        monkeypatch.setattr(settings, "log_destination", "file")
        monkeypatch.setattr(settings, "log_file", str(path))
        monkeypatch.setattr(settings, "log_level", level)
        return path

    return _configure


def test_default_is_a_single_stderr_handler_at_warning(default_settings):
    configure_logging()

    assert len(logging.root.handlers) == 1
    handler = logging.root.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stderr
    assert logging.root.level == logging.WARNING


def test_stdout_destination_selects_stdout_stream(
    default_settings, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "log_destination", "stdout")

    configure_logging()

    assert len(logging.root.handlers) == 1
    assert logging.root.handlers[0].stream is sys.stdout


def test_file_destination_writes_records_to_the_file(log_to):
    log_file = log_to()

    configure_logging()
    logging.getLogger("newsagent.pipeline.fetcher").warning("fetch failed")

    assert len(logging.root.handlers) == 1
    assert isinstance(logging.root.handlers[0], logging.FileHandler)
    contents = log_file.read_text(encoding="utf-8")
    assert "fetch failed" in contents
    assert "newsagent.pipeline.fetcher" in contents


def test_record_format_carries_a_timestamp(log_to):
    """The spec's stated justification for owning the format is that a file log
    without timestamps is not diagnosable - so pin it, or a format regression
    would pass every other test in this file."""
    log_file = log_to()

    configure_logging()
    logging.getLogger("newsagent.pipeline.fetcher").warning("boom")

    line = log_file.read_text(encoding="utf-8").splitlines()[0]
    assert line[:4].isdigit() and line[4] == "-", f"expected leading timestamp, got {line!r}"
    assert "WARNING" in line


def test_file_destination_appends_rather_than_truncates(log_to):
    log_file = log_to()

    configure_logging()
    logging.getLogger("newsagent.pipeline.fetcher").warning("first")
    configure_logging()
    logging.getLogger("newsagent.pipeline.fetcher").warning("second")

    contents = log_file.read_text(encoding="utf-8")
    assert "first" in contents and "second" in contents


def test_missing_parent_directory_is_created(log_to, tmp_path: Path):
    log_file = log_to(name="nested/deeper/na.log")
    assert not log_file.parent.exists()

    configure_logging()
    logging.getLogger("newsagent.pipeline.fetcher").warning("created")

    assert log_file.read_text(encoding="utf-8").strip().endswith("created")


def test_unopenable_log_file_raises_naming_the_setting(
    default_settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    a_directory = tmp_path / "not-a-file"
    a_directory.mkdir()
    monkeypatch.setattr(settings, "log_destination", "file")
    monkeypatch.setattr(settings, "log_file", str(a_directory))

    with pytest.raises(ValueError, match="NEWSAGENT_LOG_FILE"):
        configure_logging()


def test_file_destination_without_path_raises(
    default_settings, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "log_destination", "file")
    monkeypatch.setattr(settings, "log_file", "   ")

    with pytest.raises(ValueError, match="NEWSAGENT_LOG_FILE"):
        configure_logging()


def test_unknown_destination_names_the_known_values(
    default_settings, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "log_destination", "kafka")

    with pytest.raises(ValueError, match="kafka") as raised:
        configure_logging()
    for known in ("stderr", "stdout", "file"):
        assert known in str(raised.value)


@pytest.mark.parametrize("raw", [" STDERR ", "StdErr", "stderr "])
def test_destination_is_case_and_whitespace_insensitive(
    default_settings, monkeypatch: pytest.MonkeyPatch, raw: str
):
    monkeypatch.setattr(settings, "log_destination", raw)

    configure_logging()

    assert logging.root.handlers[0].stream is sys.stderr


def test_empty_destination_falls_back_to_the_default(
    default_settings, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "log_destination", "")

    configure_logging()

    assert logging.root.handlers[0].stream is sys.stderr


def test_debug_level_lets_debug_records_reach_the_destination(log_to):
    log_file = log_to(name="debug.log", level="DEBUG")

    configure_logging()
    logging.getLogger("newsagent.pipeline.summarize").debug("raw model response")

    assert logging.root.level == logging.DEBUG
    assert "raw model response" in log_file.read_text(encoding="utf-8")


@pytest.mark.parametrize("raw,expected", [("20", logging.INFO), (" debug ", logging.DEBUG)])
def test_level_accepts_numeric_and_padded_names(
    default_settings, monkeypatch: pytest.MonkeyPatch, raw: str, expected: int
):
    monkeypatch.setattr(settings, "log_level", raw)

    configure_logging()

    assert logging.root.level == expected


def test_unknown_level_names_the_known_values(
    default_settings, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "log_level", "CHATTY")

    with pytest.raises(ValueError, match="CHATTY") as raised:
        configure_logging()
    assert "WARNING" in str(raised.value)


def test_notset_level_is_rejected(default_settings, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "log_level", "NOTSET")

    with pytest.raises(ValueError, match="NOTSET"):
        configure_logging()


def test_explicit_access_log_opt_out_is_honored(log_to):
    """uvicorn's --no-access-log leaves the logger with no handlers and
    propagate=False. Re-pointing it would resurrect request lines that carry
    tracking-pixel URLs embedding user and article ids."""
    log_to(name="optout.log", level="INFO")
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False

    configure_logging()

    assert access.propagate is False


def test_server_handlers_are_closed_when_cleared(log_to, tmp_path: Path):
    """Clearing without closing leaks the fd - and on Windows keeps the old
    file locked for the life of the process."""
    log_to(name="closed.log", level="INFO")
    stale_path = tmp_path / "stale-uvicorn.log"
    stale = logging.FileHandler(stale_path, encoding="utf-8")
    error_logger = logging.getLogger("uvicorn.error")
    error_logger.addHandler(stale)

    configure_logging()

    assert stale not in error_logger.handlers
    assert stale.stream is None or stale.stream.closed, "handler dropped but never closed"


def test_unencodable_characters_do_not_drop_the_record(
    default_settings, monkeypatch: pytest.MonkeyPatch, capsys
):
    """Source articles are any language; a legacy console code page must not
    make a record vanish inside emit()."""
    monkeypatch.setattr(settings, "log_destination", "stdout")

    configure_logging()
    logging.getLogger("newsagent.pipeline.summarize").warning("title: 人工智能 / Прорыв")

    assert logging.root.handlers[0].stream.errors in ("backslashreplace", "replace")


@pytest.mark.parametrize("raw", ["0", " 0 ", "5", "999", "²"])
def test_out_of_range_numeric_levels_are_rejected(
    default_settings, monkeypatch: pytest.MonkeyPatch, raw: str
):
    """0 is NOTSET by another spelling (emits everything); 999 installs a
    handler that can never emit. Both must fail loudly, not silently."""
    monkeypatch.setattr(settings, "log_level", raw)

    with pytest.raises(ValueError, match="NEWSAGENT_LOG_LEVEL|log level|Log level"):
        configure_logging()


def test_empty_level_falls_back_to_the_default(
    default_settings, monkeypatch: pytest.MonkeyPatch
):
    """Mirrors the empty-destination rule - a blank env var means "unset"."""
    monkeypatch.setattr(settings, "log_level", "  ")

    configure_logging()

    assert logging.root.level == logging.WARNING


def test_server_logs_reach_the_configured_destination(log_to):
    """uvicorn ships propagate=False with its own handlers, so a root-handler
    swap alone would leave every startup/error/access line on the console."""
    from logging.config import dictConfig

    from uvicorn.config import LOGGING_CONFIG

    dictConfig(LOGGING_CONFIG)  # what uvicorn does before importing the app
    log_file = log_to(name="server.log", level="INFO")

    configure_logging()
    logging.getLogger("uvicorn.error").info("Application startup complete")
    logging.getLogger("uvicorn.access").info("GET /health 200")

    contents = log_file.read_text(encoding="utf-8")
    assert "Application startup complete" in contents
    assert "GET /health 200" in contents


def test_log_level_governs_server_and_third_party_loggers(log_to):
    """uvicorn pins itself to INFO and the noisy pair get a WARNING floor, so a
    stricter LOG_LEVEL must still win - otherwise ERROR silences the application
    while server and transport chatter keeps flowing, the exact inverse of intent."""
    from logging.config import dictConfig

    from uvicorn.config import LOGGING_CONFIG

    dictConfig(LOGGING_CONFIG)
    log_file = log_to(name="strict.log", level="ERROR")

    configure_logging()
    logging.getLogger("uvicorn.access").info("GET /health 200")
    logging.getLogger("uvicorn.error").info("Application startup complete")
    logging.getLogger("httpx").warning("HTTP Request: POST ...")
    logging.getLogger("newsagent.pipeline.fetcher").error("real failure")

    contents = log_file.read_text(encoding="utf-8")
    assert "real failure" in contents
    assert "GET /health 200" not in contents
    assert "Application startup complete" not in contents
    assert "HTTP Request" not in contents


def test_noisy_third_party_loggers_stay_at_warning(log_to):
    log_file = log_to(name="quiet.log", level="DEBUG")

    configure_logging()
    logging.getLogger("httpcore.connection").debug("connect_tcp.started")
    logging.getLogger("httpx").debug("HTTP Request: POST ...")
    logging.getLogger("newsagent.pipeline.summarize").debug("raw model response")

    contents = log_file.read_text(encoding="utf-8")
    assert "raw model response" in contents
    assert "connect_tcp.started" not in contents
    assert "HTTP Request" not in contents


def test_calling_twice_does_not_accumulate_handlers(default_settings):
    configure_logging()
    configure_logging()

    assert len(logging.root.handlers) == 1
