from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from newsagent.models.base import Base


class OutboundRun(Base):
    """One row per stage invocation - the context an `outbound_calls` row
    belongs to (ARCHITECTURE-SPINE AD-13). Created via `open_run()`
    (`newsagent.telemetry`), always exactly once per invocation, even one
    that never places a single call. `succeeded`/`refused`/`errors` are
    written once, at close, from the stage's own report - never incremented
    live (AD-13). Token/cost/duration totals are deliberately NOT columns
    here: they are always `SUM(outbound_calls...)` over this run's children.
    """

    __tablename__ = "outbound_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    kind: Mapped[str] = mapped_column(String)
    # NULL for the shared stages (filter, summarize) - populated only when
    # the work was actually done for one user (digest_build, profile_suggestions).
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    # Active subscriber count the run touched - only meaningful for the
    # shared stages; NULL for per-user runs (AD-14).
    subscriber_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Bounded, never a raw prompt or user-authored free text (AD-20).
    intent_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    succeeded: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    refused: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    errors: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
