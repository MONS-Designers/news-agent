from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from newsagent.models.base import Base


class OutboundCall(Base):
    """One row per outbound HTTP attempt - the atom of this telemetry system
    (ARCHITECTURE-SPINE AD-13). The sole source of truth for spend, latency,
    and result; `outbound_runs` never duplicates these as its own columns.

    `run_id` is nullable: a call made with no open `open_run()` is still
    recorded, as `purpose='UNATTRIBUTED'` (AD-11) - the spine's ERD does not
    mark it nullable, but there is no run to attach to in that case, and the
    alternative (silently fabricating an owning run) would misrepresent what
    happened. Flagged for human confirmation - see the implementation report.

    `cost_usd`/`rate_*_usd_per_mtok` stay NULL for every ok/error row in this
    revision - no pricing lookup is implemented (deferred, see
    deferred-work.md). The one exception is `status='avoided'`, where
    `cost_usd=0` is a literal written by the caller (nothing was spent, with
    total certainty - not a priced value), per the frozen I/O matrix.
    """

    __tablename__ = "outbound_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("outbound_runs.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    purpose: Mapped[str] = mapped_column(String)
    # "llm" / "email" / "rss" (AD-17) - only "llm" is ever written this revision.
    target: Mapped[str] = mapped_column(String, default="llm", server_default="llm")
    status: Mapped[str] = mapped_column(String)  # ok / error / malformed / avoided
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    article_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("articles.id"), nullable=True, index=True
    )
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)  # tokens / words
    output_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    rate_in_usd_per_mtok: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    rate_out_usd_per_mtok: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
