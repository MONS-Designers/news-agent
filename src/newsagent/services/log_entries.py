"""Persistence for log records - the single place that knows how a log record
becomes a `log_entries` row. Every writer (the logging handler in
newsagent.logging_setup, the CLI's outbound-run correlation patch) goes
through this module rather than touching LogEntry/SQLAlchemy directly, so a
future change to storage shape or backend has one call site to change."""

from sqlalchemy import update
from sqlalchemy.orm import Session

from newsagent.models import LogEntry


def record_log(
    db: Session,
    *,
    level: str,
    logger_name: str,
    message: str,
    version: str,
) -> LogEntry:
    """Persist one log record. outbound_run_id starts NULL - a run's own
    `outbound_runs` row doesn't exist until the run finishes, so records
    emitted during the run are correlated after the fact via attach_outbound_run."""
    entry = LogEntry(level=level, logger_name=logger_name, message=message, version=version)
    db.add(entry)
    db.commit()
    return entry


def attach_outbound_run(db: Session, log_entry_ids: list[int], outbound_run_id: int) -> None:
    """Back-fill outbound_run_id on records emitted during a run, once that
    run's `outbound_runs` row - and therefore its id - exists."""
    if not log_entry_ids:
        return
    db.execute(
        update(LogEntry)
        .where(LogEntry.id.in_(log_entry_ids))
        .values(outbound_run_id=outbound_run_id)
    )
    db.commit()
