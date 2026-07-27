from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, text
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

    # DB backstop for AD-8's "one pending row per normalized text" rule: the
    # service's SELECT-then-INSERT is not atomic, so two concurrent submissions
    # would otherwise create two count=1 rows instead of one at 2 — corrupting
    # the demand signal Epic 2 ranks by.
    #
    # COALESCE, not a bare field_id: NULLs never compare equal in a unique
    # index, and kind='field' rows always carry field_id=NULL — a plain
    # three-column index would silently protect Role rows only.
    #
    # Partial (WHERE status='pending') so decided rows stay outside it: the same
    # text may legitimately be rejected, resubmitted, and rejected again.
    __table_args__ = (
        Index(
            "uq_pending_taxonomy_suggestions_open",
            "kind",
            text("COALESCE(field_id, -1)"),
            "normalized_text",
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id"), nullable=True)
    normalized_text: Mapped[str] = mapped_column(String, index=True)
    # The submission as typed. normalized_text is the dedupe key and is
    # casefolded, so promoting a suggestion without this would mint a lowercase
    # "marine biology" sitting next to "Tech" (Story 2.2). Nullable because rows
    # written before this column existed genuinely have no display form.
    raw_text: Mapped[str | None] = mapped_column(String, nullable=True)
    submission_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String, default=STATUS_PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    field: Mapped["Field | None"] = relationship()
