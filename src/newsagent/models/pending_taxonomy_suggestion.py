from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from newsagent.models.base import Base

if TYPE_CHECKING:
    from newsagent.models.field import Field

# PendingTaxonomySuggestion.status values (plain string column, mirrors Source.status).
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

# PendingTaxonomySuggestion.kind values.
KIND_FIELD = "field"
KIND_ROLE = "role"


class PendingTaxonomySuggestion(Base):
    """A free-text "Other" Field or Role submission, queued for admin review.

    One row per unique (kind, field_id, normalized_text, status) — a resubmission
    matching an existing *pending* row increments its submission_count; a
    resubmission matching an already-decided (approved/rejected) row creates a
    fresh pending row instead of reopening or mutating the decided one.
    """

    __tablename__ = "pending_taxonomy_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id"), nullable=True)
    normalized_text: Mapped[str] = mapped_column(String, index=True)
    submission_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String, default=STATUS_PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    field: Mapped["Field | None"] = relationship()
