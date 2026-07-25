"""Domain service for the Field/Role profile taxonomy and its "Other" review
queue (issue: Profile-Based Topic Suggestions). Follows the same get-or-create
idempotency pattern as services/sources.py."""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.models import Field, PendingTaxonomySuggestion, User
from newsagent.models.pending_taxonomy_suggestion import KIND_FIELD, STATUS_PENDING

# Generic starter Field content (PRD: PM authors initial seed, no real
# dogfood-user data available yet) — mirrors DEFAULT_SOURCES's role in sources.py.
DEFAULT_FIELDS: list[str] = ["Tech", "Finance", "Healthcare", "Education", "Design"]


def normalize_taxonomy_text(text: str) -> str:
    """Case-fold + whitespace-collapse, so 'Marine  Biology' and 'marine biology'
    dedupe to the same Pending Taxonomy Suggestion."""
    return re.sub(r"\s+", " ", text.strip().casefold())


def add_field(db: Session, name: str) -> tuple[Field, bool]:
    """Get-or-create a Field by name. Returns (field, created)."""
    existing = db.scalar(select(Field).where(Field.name == name))
    if existing is not None:
        return existing, False
    field = Field(name=name)
    db.add(field)
    db.commit()
    return field, True


def list_fields(db: Session) -> list[Field]:
    """Every admin-curated Field, ordered by name."""
    return list(db.scalars(select(Field).order_by(Field.name)))


@dataclass
class SeedReport:
    fields_created: int = 0


def seed_default_fields(db: Session) -> SeedReport:
    """Load DEFAULT_FIELDS as curated Fields."""
    report = SeedReport()
    for name in DEFAULT_FIELDS:
        _, created = add_field(db, name)
        report.fields_created += int(created)
    return report


def record_field_selection(db: Session, user: User, *, field_name: str, is_other: bool) -> User:
    """Save the user's chosen Field.

    Stored identically whether `field_name` came from the curated list or was
    typed via "Other" (AD-6 — Field is a plain string on User, not a foreign
    key). When `is_other` is true, also records/increments a Pending Taxonomy
    Suggestion for admin review — scoped to `status='pending'` only, so a
    resubmission matching an already-decided (approved/rejected) row creates a
    fresh pending row instead of reusing it.
    """
    user.field_name = field_name

    if is_other:
        normalized = normalize_taxonomy_text(field_name)
        pending = db.scalar(
            select(PendingTaxonomySuggestion).where(
                PendingTaxonomySuggestion.kind == KIND_FIELD,
                PendingTaxonomySuggestion.field_id.is_(None),
                PendingTaxonomySuggestion.normalized_text == normalized,
                PendingTaxonomySuggestion.status == STATUS_PENDING,
            )
        )
        if pending is not None:
            pending.submission_count += 1
        else:
            db.add(
                PendingTaxonomySuggestion(
                    kind=KIND_FIELD,
                    field_id=None,
                    normalized_text=normalized,
                    submission_count=1,
                    status=STATUS_PENDING,
                )
            )

    db.commit()
    db.refresh(user)
    return user
