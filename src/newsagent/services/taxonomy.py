"""Domain service for the Field/Role profile taxonomy and its "Other" review
queue (issue: Profile-Based Topic Suggestions). Follows the same get-or-create
idempotency pattern as services/sources.py."""

import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.models import Field, PendingTaxonomySuggestion, Role
from newsagent.models.pending_taxonomy_suggestion import STATUS_PENDING

# Generic starter Field content (PRD: PM authors initial seed, no real
# dogfood-user data available yet) — mirrors DEFAULT_SOURCES's role in sources.py.
DEFAULT_FIELDS: list[str] = ["Tech", "Finance", "Healthcare", "Education", "Design"]

# Starter Role content per Field, from the approved UX mockup. Admin curates
# from here on (Epic 2 promotes "Other" submissions into this table).
DEFAULT_ROLES: dict[str, list[str]] = {
    "Tech": ["Software Engineer", "Product Manager", "Data Scientist", "Founder / Exec"],
    "Finance": ["Analyst", "Portfolio Manager", "Accountant", "Founder / Exec"],
    "Healthcare": ["Physician", "Nurse", "Researcher", "Administrator"],
    "Education": ["Teacher", "Researcher", "Administrator", "Student"],
    "Design": ["Product Designer", "Researcher", "Art Director", "Student"],
}


def normalize_taxonomy_text(text: str) -> str:
    """Fold a submission to its dedupe key, so variants of the same words land on
    one Pending Taxonomy Suggestion instead of several.

    Beyond case and whitespace this strips Unicode format characters (category
    `Cf` — the invisible RLM/LRM marks a Hebrew or Arabic IME inserts) and
    unifies composition to NFC (macOS submits decomposed text, so "Café" would
    otherwise arrive as two different byte sequences). Both produce rows that
    look identical in the admin queue but never merge.
    """
    composed = unicodedata.normalize("NFC", text)
    without_marks = "".join(ch for ch in composed if unicodedata.category(ch) != "Cf")
    collapsed = re.sub(r"\s+", " ", without_marks.strip()).casefold()
    return unicodedata.normalize("NFC", collapsed)


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


def find_field_by_name(db: Session, name: str) -> Field | None:
    """Resolve a stored field_name against the curated list (AD-6 — the match is
    a name-lookup at use time, never a stored foreign key).

    Compared in Python rather than SQL: the curated list is a handful of rows,
    and LOWER()/collation semantics differ between SQLite and Postgres.
    """
    normalized = normalize_taxonomy_text(name)
    for field in list_fields(db):
        if normalize_taxonomy_text(field.name) == normalized:
            return field
    return None


def add_role(db: Session, field: Field, name: str) -> tuple[Role, bool]:
    """Get-or-create a Role by (field_id, name). Returns (role, created).

    Scoped to the Field, not global — "Researcher" exists under both Healthcare
    and Education, and they are different rows.
    """
    existing = db.scalar(select(Role).where(Role.field_id == field.id, Role.name == name))
    if existing is not None:
        return existing, False
    role = Role(field_id=field.id, name=name)
    db.add(role)
    db.commit()
    return role, True


def list_roles(db: Session, field_id: int) -> list[Role]:
    """Curated Roles under one Field, ordered by name. Unknown field_id -> []."""
    return list(db.scalars(select(Role).where(Role.field_id == field_id).order_by(Role.name)))


def find_role_by_name(db: Session, field_id: int, name: str) -> Role | None:
    """Resolve a stored role_name against the curated list for one Field — the
    Role counterpart to find_field_by_name, same normalized name-lookup (AD-6)."""
    normalized = normalize_taxonomy_text(name)
    for role in list_roles(db, field_id):
        if normalize_taxonomy_text(role.name) == normalized:
            return role
    return None


@dataclass
class SeedReport:
    fields_created: int = 0
    roles_created: int = 0


def seed_default_fields(db: Session) -> SeedReport:
    """Load DEFAULT_FIELDS as curated Fields."""
    report = SeedReport()
    for name in DEFAULT_FIELDS:
        _, created = add_field(db, name)
        report.fields_created += int(created)
    return report


def seed_default_roles(db: Session) -> SeedReport:
    """Load DEFAULT_ROLES under their Fields, creating any missing Field first —
    mirrors seed_default_sources's topic-then-source shape."""
    report = SeedReport()
    for field_name, role_names in DEFAULT_ROLES.items():
        field, created = add_field(db, field_name)
        report.fields_created += int(created)
        for role_name in role_names:
            _, created = add_role(db, field, role_name)
            report.roles_created += int(created)
    return report


def record_pending_suggestion(db: Session, *, kind: str, field_id: int | None, text: str) -> None:
    """Stage a Pending Taxonomy Suggestion for admin review (AD-8).

    Matching is scoped to `status='pending'` rows with the same kind and
    field_id, so a resubmission of text that was already approved/rejected
    creates a fresh pending row rather than reopening the decided one.

    The first submitter's spelling is kept as `raw_text`; later matching
    submissions only bump the count, so the display form stays stable while the
    suggestion sits in the queue.

    Deliberately does NOT commit — the calling service owns the transaction, so
    a profile save and its suggestion writes land (or roll back) together.
    """
    normalized = normalize_taxonomy_text(text)
    pending = db.scalar(
        select(PendingTaxonomySuggestion).where(
            PendingTaxonomySuggestion.kind == kind,
            PendingTaxonomySuggestion.field_id.is_(field_id)
            if field_id is None
            else PendingTaxonomySuggestion.field_id == field_id,
            PendingTaxonomySuggestion.normalized_text == normalized,
            PendingTaxonomySuggestion.status == STATUS_PENDING,
        )
    )
    if pending is not None:
        pending.submission_count += 1
        return

    db.add(
        PendingTaxonomySuggestion(
            kind=kind,
            field_id=field_id,
            normalized_text=normalized,
            raw_text=text.strip(),
            submission_count=1,
            status=STATUS_PENDING,
        )
    )


