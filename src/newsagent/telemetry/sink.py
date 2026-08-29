"""Joins a `CallMeasurement` (from the transport, or a caller standing in for
an avoided call - AD-15) with the ambient `CallAttribution`, and hands both
to the sole DB writer (`services/telemetry.py`). Also owns run creation/
closing on behalf of `telemetry/context.py`'s `open_run()`.

Opens its own short-lived `SessionLocal()` for every write - exactly like
`logging_setup`'s DB handler - rather than requiring every caller deep inside
`pipeline/`, `suggestions/`, or the transport to plumb a `Session` through.
That also means a telemetry write can never share a transaction with (and so
can never roll back) the business operation it's describing.

Every public function here swallows and logs at ERROR: a telemetry failure
must never break the business operation it's recording (AD-13's error rule,
AD-15's "swallow, log ERROR, continue").
"""

import dataclasses
import logging

from newsagent.db import SessionLocal
from newsagent.services import telemetry as telemetry_service
from newsagent.telemetry.types import STATUS_AVOIDED, CallMeasurement

logger = logging.getLogger(__name__)


def report(measurement: CallMeasurement) -> None:
    """Called by the transport on every outbound attempt (AD-12), and
    directly by a caller reporting an avoided call (AD-15).

    Does NOT write immediately in the common case: the measurement is
    handed to whatever `attempt_scope()` is open (`llm/base.py` /
    `suggestions/base.py`'s `_run`), which writes it once, when that scope
    closes - not here - because at report() time nobody yet knows whether
    the body was usable (AD-15's `malformed` amendment). If no scope is
    open (a direct `send_chat_completion` call, or a caller-reported
    `avoided` row), nothing will ever close one, so it's written now.
    """
    try:
        # Local import, inside the try: telemetry.context imports this
        # module at load time (to call create_run()/finish_run()/flush()),
        # so importing it back at module level here would be circular - it
        # genuinely fails if this module loads first (verified: context.py
        # hasn't yet defined buffer_measurement by the point it reaches
        # `from newsagent.telemetry import sink`). By the time report()
        # actually runs, both modules are fully loaded, so this always
        # succeeds in practice - but report() is called from the
        # transport's `finally:` block on every attempt, and if the import
        # itself ever did raise, it must not propagate uncaught and mask
        # the real exception the caller was already handling (AD-12; Review
        # Finding, 2026-08-27 - this used to sit above the try).
        from newsagent.telemetry.context import buffer_measurement

        buffered = buffer_measurement(measurement)
    except Exception:
        logger.error("Failed to buffer outbound call telemetry", exc_info=True)
        return
    if buffered:
        return
    _write(measurement, status_override=None)


def flush(measurement: CallMeasurement, *, status_override: str | None) -> None:
    """Called by `attempt_scope()` when it closes - the one place a buffered
    measurement is actually written."""
    _write(measurement, status_override=status_override)


def _write(measurement: CallMeasurement, *, status_override: str | None) -> None:
    try:
        from newsagent.telemetry.context import current_attribution

        attribution = current_attribution()
        final_measurement = (
            measurement
            if status_override is None
            else dataclasses.replace(measurement, status=status_override)
        )
        with SessionLocal() as db:
            telemetry_service.record_call(
                db,
                run_id=attribution.run_id,
                purpose=attribution.purpose,
                article_id=attribution.article_id,
                attempt=attribution.attempt,
                measurement=final_measurement,
            )
    except Exception:
        logger.error("Failed to record outbound call telemetry", exc_info=True)


def report_avoided(duration_ms: int) -> None:
    """The one path where a row is written without the transport ever having
    run (AD-15) - e.g. `digest.py`'s voice-reuse cache hit."""
    report(CallMeasurement(status=STATUS_AVOIDED, duration_ms=duration_ms))


def create_run(
    *,
    kind: str,
    user_id: int | None,
    subscriber_count: int | None,
    intent_summary: str | None,
) -> int | None:
    try:
        with SessionLocal() as db:
            return telemetry_service.open_run(
                db,
                kind=kind,
                user_id=user_id,
                subscriber_count=subscriber_count,
                intent_summary=intent_summary,
            )
    except Exception:
        logger.error("Failed to open outbound_runs row (kind=%s)", kind, exc_info=True)
        return None


def finish_run(run_id: int | None, *, succeeded: int, refused: int, errors: int) -> None:
    if run_id is None:
        return
    try:
        with SessionLocal() as db:
            telemetry_service.close_run(
                db, run_id, succeeded=succeeded, refused=refused, errors=errors
            )
    except Exception:
        logger.error("Failed to close outbound_runs row (id=%s)", run_id, exc_info=True)
