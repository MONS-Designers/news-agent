"""Sole writer for outbound-call telemetry (ARCHITECTURE-SPINE AD-13). Every
other module in `newsagent.telemetry` only measures or attributes; this is
the only place that touches `OutboundRun`/`OutboundCall`.

Callers are `newsagent.telemetry.sink` only - it opens its own short-lived
Session for every call here and swallows/logs any exception, so a telemetry
write failure never reaches (or breaks) the business operation. Nothing here
swallows on its own: that responsibility belongs one layer up, same as every
other `services/*.py` module.
"""

import logging
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from newsagent.models import OutboundCall, OutboundRun
from newsagent.telemetry.types import STATUS_AVOIDED, TARGET_LLM, CallMeasurement

logger = logging.getLogger(__name__)

# AD-20 requires intent_summary stay "bounded" - a short description, never a
# raw prompt. Every call site today is a short hand-written f-string, but
# nothing stops a future one from interpolating something unbounded, and this
# is the one place (the sole writer) that can enforce it for all of them.
MAX_INTENT_SUMMARY_LENGTH = 200


def open_run(
    db: Session,
    *,
    kind: str,
    user_id: int | None = None,
    subscriber_count: int | None = None,
    intent_summary: str | None = None,
) -> int:
    if intent_summary is not None and len(intent_summary) > MAX_INTENT_SUMMARY_LENGTH:
        intent_summary = intent_summary[:MAX_INTENT_SUMMARY_LENGTH]
    run = OutboundRun(
        kind=kind,
        user_id=user_id,
        subscriber_count=subscriber_count,
        intent_summary=intent_summary,
    )
    db.add(run)
    db.commit()
    return run.id


def close_run(db: Session, run_id: int, *, succeeded: int, refused: int, errors: int) -> None:
    run = db.get(OutboundRun, run_id)
    if run is None:
        return
    # func.now() (DB clock), not datetime.now() (app-host clock, potentially
    # a different machine and slightly skewed from the DB's) - created_at
    # already comes from the DB via server_default=func.now(), so this keeps
    # both ends of a run's duration on the same clock. A skewed app clock
    # could otherwise read as a negative duration.
    run.finished_at = func.now()
    run.succeeded = succeeded
    run.refused = refused
    run.errors = errors
    db.commit()


def record_call(
    db: Session,
    *,
    run_id: int | None,
    purpose: str,
    article_id: int | None,
    attempt: int,
    measurement: CallMeasurement,
) -> None:
    # A literal zero, not a priced value: "avoided" means the transport never
    # ran, so the cost is known with certainty rather than merely unpriced
    # (AD-16). Every other status is priced below if a rate is on file;
    # otherwise cost_usd/rate_* stay NULL - "unknown", never guessed as 0.
    cost_usd: Decimal | None = Decimal(0) if measurement.status == STATUS_AVOIDED else None
    rate_in_usd_per_mtok: Decimal | None = None
    rate_out_usd_per_mtok: Decimal | None = None
    if (
        measurement.status != STATUS_AVOIDED
        and measurement.model is not None
        and measurement.unit == "tokens"
        and measurement.tokens_in is not None
        and measurement.tokens_out is not None
    ):
        # Local import: telemetry.pricing sits under the same `newsagent.telemetry`
        # package whose __init__ imports telemetry.sink, which imports this module
        # at top level - importing pricing back at module level here would be
        # circular (same reasoning as sink.py's own local import of context.py).
        from newsagent.telemetry.pricing import lookup_rate

        rate = lookup_rate(db, measurement.model)
        if rate is None:
            logger.warning("No price on file for model=%s; cost_usd/rate_* left NULL", measurement.model)
        else:
            rate_in_usd_per_mtok, rate_out_usd_per_mtok = rate
            cost_usd = (
                Decimal(measurement.tokens_in) * rate_in_usd_per_mtok
                + Decimal(measurement.tokens_out) * rate_out_usd_per_mtok
            ) / Decimal(1_000_000)
    db.add(
        OutboundCall(
            run_id=run_id,
            purpose=purpose,
            target=TARGET_LLM,
            status=measurement.status,
            attempt=attempt,
            model=measurement.model,
            duration_ms=measurement.duration_ms,
            article_id=article_id,
            tokens_in=measurement.tokens_in,
            tokens_out=measurement.tokens_out,
            unit=measurement.unit,
            output_chars=measurement.output_chars,
            cost_usd=cost_usd,
            rate_in_usd_per_mtok=rate_in_usd_per_mtok,
            rate_out_usd_per_mtok=rate_out_usd_per_mtok,
        )
    )
    db.commit()
