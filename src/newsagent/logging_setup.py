"""Log destination selection — pointing logs somewhere else is a one-line config
change (NEWSAGENT_LOG_DESTINATION), no code edit at any call site.

Called once per process from every runnable entrypoint: cli.main(),
api.main.create_app(), and llm.demo's __main__ block.
"""

import logging
import sys
from pathlib import Path

from newsagent.config import settings

_DESTINATIONS = ("stderr", "stdout", "file")

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# uvicorn installs its own handlers and sets propagate=False, so its startup,
# error, and access records bypass the root logger entirely. Re-point them so a
# file destination captures the whole deployment, not just newsagent.* records.
_SERVER_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")

# Transport-level DEBUG (per-connection traces, per-request lines) drowns out the
# application records LOG_LEVEL=DEBUG exists to surface.
_NOISY_LOGGERS = ("httpx", "httpcore")


def _build_handler() -> logging.Handler:
    destination = settings.log_destination.strip().lower() or "stderr"
    if destination in ("stderr", "stdout"):
        stream = sys.stderr if destination == "stderr" else sys.stdout
        # Windows consoles use a legacy code page (cp1255 on this project's dev
        # machines). sys.stdout encodes strictly, so a Chinese or Russian source
        # title raises inside emit() and the record is lost outright — sys.stderr
        # already defaults to backslashreplace. Degrade to escapes rather than
        # dropping the record. The file destination pins utf-8 and needs none of this.
        if getattr(stream, "errors", None) not in ("backslashreplace", "replace") and hasattr(
            stream, "reconfigure"
        ):
            stream.reconfigure(errors="backslashreplace")
        return logging.StreamHandler(stream)
    if destination == "file":
        return _build_file_handler()
    raise ValueError(
        f"Unknown log destination {settings.log_destination!r} "
        f"(known: {', '.join(_DESTINATIONS)})"
    )


def _build_file_handler() -> logging.Handler:
    path_value = settings.log_file.strip()
    if not path_value:
        raise ValueError("log_destination='file' requires NEWSAGENT_LOG_FILE to be set")
    try:
        # expanduser() is inside the guard: on a host with no resolvable home
        # directory a "~/..." path raises RuntimeError, which would otherwise
        # escape as a bare traceback from create_app() at import.
        path = Path(path_value).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Opened eagerly (not delay=True) so a bad path fails here, with the
        # setting named, instead of as a bare OSError on the first record.
        return logging.FileHandler(path, encoding="utf-8")
    except (OSError, RuntimeError) as error:
        raise ValueError(f"NEWSAGENT_LOG_FILE {path_value!r} is unusable: {error}") from error


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
    """Install the configured handler on the root logger.

    force=True closes and removes any handlers already on root, so calling this
    twice in one process leaves exactly one handler rather than duplicating
    output. Note it also discards handlers owned by others — including pytest's
    caplog — so tests that capture logs around an entrypoint must reconfigure.
    """
    level = _resolve_level()
    logging.basicConfig(handlers=[_build_handler()], level=level, format=_FORMAT, force=True)
    for name in _SERVER_LOGGERS:
        server_logger = logging.getLogger(name)
        # No handlers *and* propagate off is uvicorn's signature for an explicit
        # operator opt-out (`--no-access-log`). Re-pointing it would silently
        # resurrect records they asked not to produce — access lines carry the
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
