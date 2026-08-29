"""Ambient identity for outbound-call telemetry (AD-11): who a call is for
travels only through these two contextvars, never as a parameter through
`llm/`, `suggestions/`, or `http_llm_client`. Two nesting levels, not one:

- `open_run()` opens once per stage invocation (one `filter_pending_articles`
  call, one user's `build_digests` iteration, one suggestion computation).
- `attribute_call()` opens once per unit of work inside it (usually one
  article) and supplies the `purpose`/`article_id` the sink attaches to
  whatever the transport reports while it's open.

A caller that opens neither still gets its calls recorded, as
`purpose='UNATTRIBUTED'` with no run - AD-11 forbids the absence of context
from silencing a row.

`contextvars` do NOT propagate into `ThreadPoolExecutor` worker threads on
their own (see ARCHITECTURE-SPINE's Design Notes) - a caller that fans work
out to a pool must `copy_context()` and submit `ctx.run` itself; nothing here
can do that for it.

A third, narrower scope sits inside `attribute_call()`: `attempt_scope()`,
opened once per attempt by `llm/base.py`'s and `suggestions/base.py`'s own
`_run` retry loops (AD-3 keeps those two files separate - each has to open
it). The transport's `CallMeasurement` is buffered here rather than written
immediately, because the transport cannot yet know whether the body it got
back was usable - only `llm/external.py`/`suggestions/llm.py`, one frame up,
can discover that (`mark_malformed()`) after the transport already returned.
The row is written exactly once, when the attempt scope closes.
"""

import contextvars
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from newsagent.telemetry import sink
from newsagent.telemetry.types import CallAttribution, CallMeasurement, PURPOSE_UNATTRIBUTED, STATUS_MALFORMED

logger = logging.getLogger(__name__)


@dataclass
class RunHandle:
    """Yielded by `open_run()`. Outcome counts are reported once, at the end
    of the stage (AD-13) - not incremented as work happens - so the caller
    calls `close()` right before its own return with the totals its report
    object already computed. If `close()` is never reached (an unhandled
    exception escapes the `with` block), the run still gets `finished_at`
    with whatever counts were last set (0/0/0 by default) rather than being
    left open forever."""

    run_id: int | None
    succeeded: int = 0
    refused: int = 0
    errors: int = 0

    def close(self, *, succeeded: int = 0, refused: int = 0, errors: int = 0) -> None:
        self.succeeded = succeeded
        self.refused = refused
        self.errors = errors


@dataclass
class _CallState:
    purpose: str
    article_id: int | None
    attempt: int = 0


@dataclass
class _AttemptBuffer:
    """Holds the transport's measurement for exactly one attempt, plus
    whatever status a higher layer amends it to before the attempt scope
    closes. `measurement=None` means the transport never ran this attempt
    (e.g. a junk refusal short-circuited before any network call) - nothing
    gets written for it."""

    measurement: CallMeasurement | None = None
    status_override: str | None = None


_current_run: contextvars.ContextVar[RunHandle | None] = contextvars.ContextVar(
    "_current_run", default=None
)
_current_call: contextvars.ContextVar[_CallState | None] = contextvars.ContextVar(
    "_current_call", default=None
)
_current_attempt: contextvars.ContextVar[_AttemptBuffer | None] = contextvars.ContextVar(
    "_current_attempt", default=None
)


@contextmanager
def open_run(
    kind: str,
    *,
    user_id: int | None = None,
    subscriber_count: int | None = None,
    intent_summary: str | None = None,
) -> Iterator[RunHandle]:
    run_id = sink.create_run(
        kind=kind,
        user_id=user_id,
        subscriber_count=subscriber_count,
        intent_summary=intent_summary,
    )
    handle = RunHandle(run_id=run_id)
    token = _current_run.set(handle)
    try:
        yield handle
    finally:
        _current_run.reset(token)
        sink.finish_run(
            run_id, succeeded=handle.succeeded, refused=handle.refused, errors=handle.errors
        )


@contextmanager
def attribute_call(purpose: str, article_id: int | None = None) -> Iterator[None]:
    token = _current_call.set(_CallState(purpose=purpose, article_id=article_id))
    try:
        yield
    finally:
        _current_call.reset(token)


@contextmanager
def attempt_scope() -> Iterator[None]:
    """Opened once per attempt by `_run` (`llm/base.py`, `suggestions/base.py`),
    around exactly one call to the adapter's operation. `sink.report()` buffers
    the transport's measurement here instead of writing it immediately;
    `mark_malformed()` can amend it afterward, still inside this scope, once a
    higher layer discovers a billed call's body was unusable. On exit - success
    or exception, same as `RunHandle` - whatever ended up buffered is written
    exactly once. Nothing is written if the transport never ran this attempt
    at all (e.g. a junk refusal)."""
    token = _current_attempt.set(_AttemptBuffer())
    try:
        yield
    finally:
        buffer = _current_attempt.get()
        _current_attempt.reset(token)
        if buffer is not None and buffer.measurement is not None:
            sink.flush(buffer.measurement, status_override=buffer.status_override)


def buffer_measurement(measurement: CallMeasurement) -> bool:
    """Called by `sink.report()` for every measurement the transport hands
    it. Returns whether an open `attempt_scope()` accepted it for buffering;
    `False` means no `_run` anywhere up the stack is going to close a scope
    for this call (e.g. `send_chat_completion` invoked directly, or a
    caller-reported `avoided` row - AD-15), so the caller must write it now
    instead of waiting forever."""
    buffer = _current_attempt.get()
    if buffer is None:
        return False
    if buffer.measurement is not None:
        # No known caller does this today - one attempt_scope() is opened
        # per _run iteration, and the transport reports at most once per
        # call. Not raising (telemetry must never break the caller), but a
        # silent overwrite here would lose a measurement invisibly if a
        # future caller ever did report twice within one scope.
        logger.warning(
            "Outbound call measurement buffered twice within one attempt scope; "
            "overwriting the earlier one (status=%s) with the new one (status=%s)",
            buffer.measurement.status,
            measurement.status,
        )
    buffer.measurement = measurement
    return True


def mark_malformed() -> None:
    """Called by `llm/external.py` / `suggestions/llm.py` the moment they
    discover a billed call's body was unusable (bad envelope, unparseable
    JSON, failed schema validation) - before re-raising. Amends whatever is
    currently buffered for this attempt so the eventual row reads
    `status='malformed'` instead of the transport's own `ok`/`error` guess.
    No-op outside an open `attempt_scope()`."""
    buffer = _current_attempt.get()
    if buffer is not None:
        buffer.status_override = STATUS_MALFORMED


def increment_attempt() -> int:
    """Called by the one place that knows a network call is about to be
    (re)tried - `llm/base.py`'s `_run` (AD-15) - immediately before each
    attempt. A no-op outside an open `attribute_call()` (returns 1): an
    UNATTRIBUTED row still needs a sane attempt number, it just can't track
    retries without a context to hold the counter."""
    state = _current_call.get()
    if state is None:
        return 1
    state.attempt += 1
    return state.attempt


def current_attribution() -> CallAttribution:
    """Read by the sink the moment a measurement arrives - never by
    `llm/`, `suggestions/`, or the transport (AD-11)."""
    run = _current_run.get()
    run_id = run.run_id if run is not None else None
    call = _current_call.get()
    if call is None:
        return CallAttribution(
            run_id=run_id, purpose=PURPOSE_UNATTRIBUTED, article_id=None, attempt=1
        )
    return CallAttribution(
        run_id=run_id, purpose=call.purpose, article_id=call.article_id, attempt=call.attempt or 1
    )
