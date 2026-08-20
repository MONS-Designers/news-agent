"""Every log record is written to the DB via a custom logging.Handler - there
is no other destination. See newsagent.services.log_entries for the actual
persistence (the single service every writer here goes through).

Called once per process from every runnable entrypoint: cli.main(),
api.main.create_app(), and llm.demo's __main__ block.
"""

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Iterator

from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.db import SessionLocal
from newsagent.services import log_entries

try:
    _VERSION = _pkg_version("newsagent")
except PackageNotFoundError:
    _VERSION = "unknown"

# Only the message + any exception traceback - level/logger/timestamp are
# already structured columns on log_entries, so duplicating them into the text
# would be redundant now that the destination isn't a flat stream/file.
_FORMAT = "%(message)s"

# uvicorn installs its own handlers and sets propagate=False, so its startup,
# error, and access records bypass the root logger entirely. Re-point them so
# the DB destination captures the whole deployment, not just newsagent.* records.
_SERVER_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")

# Transport-level DEBUG (per-connection traces, per-request lines) drowns out the
# application records LOG_LEVEL=DEBUG exists to surface.
_NOISY_LOGGERS = ("httpx", "httpcore")

# None outside a tracked pipeline run; a list of emitted LogEntry ids while one
# is in progress - see track_pipeline_run_logs()/attach_pipeline_run() below.
_tracked_ids: ContextVar[list[int] | None] = ContextVar("_tracked_ids", default=None)


class _DBHandler(logging.Handler):
    """Writes each emitted record to the DB via services.log_entries. Never
    lets a DB failure crash the process or raise into application code - with
    no fallback destination left, that would mean silent total logging loss
    *and* a crashing app, so a write failure instead goes through the stdlib
    handleError() path (default: printed to stderr)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            with SessionLocal() as db:
                entry = log_entries.record_log(
                    db,
                    level=record.levelname,
                    logger_name=record.name,
                    message=message,
                    version=_VERSION,
                )
            run_ids = _tracked_ids.get()
            if run_ids is not None:
                run_ids.append(entry.id)
        except Exception:
            self.handleError(record)


@contextmanager
def track_pipeline_run_logs() -> Iterator[None]:
    """Wrap a filter/summarize CLI run so every log record emitted inside
    is remembered for attach_pipeline_run() to correlate afterward, once
    that run's pipeline_runs row (and therefore its id) exists."""
    token = _tracked_ids.set([])
    try:
        yield
    finally:
        _tracked_ids.reset(token)


def attach_pipeline_run(db: Session, pipeline_run_id: int) -> None:
    """Call after pipeline_runs.record_run() returns, from inside the same
    track_pipeline_run_logs() block, to back-fill pipeline_run_id on every
    record emitted during that run."""
    ids = _tracked_ids.get()
    log_entries.attach_pipeline_run(db, ids or [], pipeline_run_id)


def _resolve_level() -> int:
    raw = settings.log_level.strip()
    if not raw:
        return logging.WARNING
    if raw.isdecimal():
        # isdecimal, not isdigit: the latter accepts superscripts like "²",
        # which int() then rejects with an error naming neither the setting.
        numeric = int(raw)
        if not logging.DEBUG <= numeric <= logging.CRITICAL:
            raise ValueError(
                f"Log level {settings.log_level!r} is out of range (expected "
                f"{logging.DEBUG}-{logging.CRITICAL}); anything lower emits every "
                f"record from every library"
            )
        return numeric
    names = logging.getLevelNamesMapping()
    level = names.get(raw.upper())
    if level is None:
        raise ValueError(
            f"Unknown log level {settings.log_level!r} "
            f"(known: {', '.join(n for n in names if n != 'NOTSET')})"
        )
    if level == logging.NOTSET:
        # Root at 0 emits every record from every library, which is never what
        # an operator setting a level means.
        raise ValueError("NOTSET is not a usable root log level")
    return level


def configure_logging() -> None:
    """Install the DB handler on the root logger.

    force=True closes and removes any handlers already on root, so calling this
    twice in one process leaves exactly one handler rather than duplicating
    output. Note it also discards handlers owned by others - including pytest's
    caplog - so tests that capture logs around an entrypoint must reconfigure.
    """
    level = _resolve_level()
    logging.basicConfig(handlers=[_DBHandler()], level=level, format=_FORMAT, force=True)
    for name in _SERVER_LOGGERS:
        server_logger = logging.getLogger(name)
        # No handlers *and* propagate off is uvicorn's signature for an explicit
        # operator opt-out (`--no-access-log`). Re-pointing it would silently
        # resurrect records they asked not to produce - access lines carry the
        # tracking-pixel URLs, which embed user and article ids.
        if not server_logger.handlers and not server_logger.propagate:
            continue
        for handler in server_logger.handlers[:]:
            server_logger.removeHandler(handler)
            handler.close()  # else the fd leaks, and on Windows locks its file
        server_logger.propagate = True
        # A record is filtered by the level of the logger that emitted it, not
        # by root's. uvicorn pins these to INFO, so without resetting them to
        # NOTSET (inherit) a LOG_LEVEL of ERROR would silence the application
        # while server INFO kept flowing.
        server_logger.setLevel(logging.NOTSET)
    for name in _NOISY_LOGGERS:
        # Floor of WARNING, but never louder than the operator asked for.
        logging.getLogger(name).setLevel(max(level, logging.WARNING))
