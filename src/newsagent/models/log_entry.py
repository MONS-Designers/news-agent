from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from newsagent.models.base import Base


class LogEntry(Base):
    """One row per emitted log record (see newsagent.logging_setup and
    newsagent.services.log_entries) - the only log destination; there is no
    file/stream fallback. pipeline_run_id starts NULL and is patched in after
    the fact once a pipeline_runs row exists (that row is only created at the
    end of a run - see services.log_entries.attach_pipeline_run)."""

    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    level: Mapped[str] = mapped_column(String)
    logger_name: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String)
    pipeline_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("pipeline_runs.id"), nullable=True, index=True
    )
