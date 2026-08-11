"""Persistence for per-run LLM usage history (GH #19 follow-up). One row per
completed `filter`/`summarize` CLI invocation — written from cli.py only."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from newsagent.models import PipelineRun


@dataclass
class StageUsage:
    run_type: str
    usage_input_units: int
    usage_output_units: int


@dataclass
class DailyUsage:
    day: str
    usage_input_units: int
    usage_output_units: int


@dataclass
class UsageReport:
    by_stage: list[StageUsage]
    by_day: list[DailyUsage]


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


def build_usage_report(db: Session) -> UsageReport:
    """Total LLM usage per stage and per day, straight from pipeline_runs —
    the CLI's answer to "what has this cost so far" without grepping logs."""
    by_stage_rows = db.execute(
        select(
            PipelineRun.run_type,
            func.sum(PipelineRun.usage_input_units),
            func.sum(PipelineRun.usage_output_units),
        )
        .group_by(PipelineRun.run_type)
        .order_by(PipelineRun.run_type)
    ).all()
    by_day_rows = db.execute(
        select(
            func.date(PipelineRun.created_at),
            func.sum(PipelineRun.usage_input_units),
            func.sum(PipelineRun.usage_output_units),
        )
        .group_by(func.date(PipelineRun.created_at))
        .order_by(func.date(PipelineRun.created_at))
    ).all()
    return UsageReport(
        by_stage=[StageUsage(run_type, in_units, out_units) for run_type, in_units, out_units in by_stage_rows],
        by_day=[DailyUsage(day, in_units, out_units) for day, in_units, out_units in by_day_rows],
    )
