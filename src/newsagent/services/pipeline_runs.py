"""Persistence for per-run LLM usage history (GH #19 follow-up). One row per
completed `filter`/`summarize` CLI invocation — written from cli.py only."""

from sqlalchemy.orm import Session

from newsagent.models import PipelineRun


def record_run(
    db: Session,
    *,
    run_type: str,
    succeeded: int,
    refused: int,
    errors: int,
    usage_input_units: int,
    usage_output_units: int,
) -> PipelineRun:
    run = PipelineRun(
        run_type=run_type,
        succeeded=succeeded,
        refused=refused,
        errors=errors,
        usage_input_units=usage_input_units,
        usage_output_units=usage_output_units,
    )
    db.add(run)
    db.commit()
    return run
