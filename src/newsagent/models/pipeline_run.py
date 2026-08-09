from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from newsagent.models.base import Base

# PipelineRun.run_type values.
RUN_TYPE_FILTER = "filter"
RUN_TYPE_SUMMARIZE = "summarize"


class PipelineRun(Base):
    """One row per completed `filter`/`summarize` CLI run — coarse spend/volume
    trend history. Schema + write path only; no reporting UI reads this yet."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_type: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    succeeded: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    refused: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    errors: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    usage_input_units: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    usage_output_units: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
