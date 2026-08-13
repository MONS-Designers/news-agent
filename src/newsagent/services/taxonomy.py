"""Domain service for the Field/Role profile taxonomy and its "Other" review
queue (issue: Profile-Based Topic Suggestions). Follows the same get-or-create
idempotency pattern as services/sources.py."""

import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from newsagent.models import Field, PendingTaxonomySuggestion, Role
from newsagent.models.pending_taxonomy_suggestion import (
    KIND_ROLE,
    STATUS_APPROVED,
    STATUS_PENDING,
)
from newsagent.suggestions.errors import SuggestionError
from newsagent.suggestions.factory import get_suggestion_source

# Role picker cap (Story: Role and Prompt Suggestions) - curated Roles always
# shown first, LLM-invented names fill any remaining slots up to this count.
ROLE_SUGGESTION_CAP = 10

# Mirrors services/profile.py's MAX_NAME_LENGTH - an LLM-suggested name past
# this (or blank) would fail save_profile's own check anyway, so it is
# filtered out here rather than offered as a chip that can't actually be saved.
ROLE_NAME_MAX_LENGTH = 100


# Generic starter Field content (PRD: PM authors initial seed, no real
# dogfood-user data available yet) - mirrors DEFAULT_SOURCES's role in sources.py.
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
    `Cf` - the invisible RLM/LRM marks a Hebrew or Arabic IME inserts) and
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
    """Resolve a stored field_name against the curated list (AD-6 - the match is
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

    Scoped to the Field, not global - "Researcher" exists under both Healthcare
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
    """Resolve a stored role_name against the curated list for one Field - the
    Role counterpart to find_field_by_name, same normalized name-lookup (AD-6)."""
    normalized = normalize_taxonomy_text(name)
    for role in list_roles(db, field_id):
        if normalize_taxonomy_text(role.name) == normalized:
            return role
    return None


@dataclass(frozen=True)
class RoleSuggestionView:
    """One Role option shown in the Step 1 Role picker - either curated (already
    a `Role` row) or LLM-invented and not yet reviewed. The router serializes
    this, never a raw `Role`, so an uncurated suggestion has somewhere to live
    without a real `Role.id` (AD-1)."""

    name: str
    is_curated: bool


def suggest_roles_for_field(db: Session, field: Field) -> list[RoleSuggestionView]:
    """Up to `ROLE_SUGGESTION_CAP` Role options for the Step 1 picker: curated
    Roles first (already vetted), then LLM-invented names not duplicating any
    curated Role (`normalize_taxonomy_text`, AD-6), filling any remaining slots.

    If curated Roles alone already reach the cap, they are capped at exactly
    `ROLE_SUGGESTION_CAP` and the LLM is not called at all - there is nothing
    for it to contribute. If the LLM call fails, the curated list is still
    returned in full (up to the cap) - a suggestion failure never blocks Role
    selection, it just means no new names this time.
    """
    curated = list_roles(db, field.id)
    views = [
        RoleSuggestionView(name=role.name, is_curated=True)
        for role in curated[:ROLE_SUGGESTION_CAP]
    ]
    if len(curated) >= ROLE_SUGGESTION_CAP:
        return views

    try:
        suggested = get_suggestion_source().suggest_roles(
            field.name, existing_roles=[role.name for role in curated]
        )
    except SuggestionError:
        suggested = []

    seen = {normalize_taxonomy_text(role.name) for role in curated}
    for option in suggested:
        if len(views) >= ROLE_SUGGESTION_CAP:
            break
        name = option.name.strip()
        if not name or len(name) > ROLE_NAME_MAX_LENGTH:
            continue
        normalized = normalize_taxonomy_text(name)
        if normalized in seen:
            continue
        seen.add(normalized)
        views.append(RoleSuggestionView(name=name, is_curated=False))

    return views


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
    """Load DEFAULT_ROLES under their Fields, creating any missing Field first -
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

    Deliberately does NOT commit - the calling service owns the transaction, so
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


@dataclass(frozen=True)
class PendingSuggestionView:
    """One row of the admin Taxonomy Curation Queue - the plain-data unit the
    router renders, so no model instance crosses the router boundary (AD-1).
    Same role TopicChoice plays for the preferences page."""

    id: int
    kind: str
    field_name: str | None
    text: str
    submission_count: int


def list_pending_suggestions(db: Session) -> list[PendingSuggestionView]:
    """Every open "Other" submission awaiting an admin decision (FR-6).

    No GROUP BY: record_pending_suggestion and the partial unique index already
    guarantee one row per (kind, field_id, normalized_text) among pending rows
    (AD-8), so re-aggregating here would be a second, divergent definition of
    "the same submission".

    Ordered most-requested first - submission_count is the demand signal the
    admin is here to read - with the oldest as a stable tiebreak.
    """
    rows = db.scalars(
        select(PendingTaxonomySuggestion)
        .where(PendingTaxonomySuggestion.status == STATUS_PENDING)
        .options(selectinload(PendingTaxonomySuggestion.field))
        .order_by(
            PendingTaxonomySuggestion.submission_count.desc(),
            PendingTaxonomySuggestion.created_at,
        )
    )
    return [
        PendingSuggestionView(
            id=row.id,
            kind=row.kind,
            field_name=row.field.name if row.field is not None else None,
            # normalized_text is casefolded, so it is the dedupe key, not a
            # display form; raw_text is nullable only for rows written before
            # that column existed.
            text=row.raw_text or row.normalized_text,
            submission_count=row.submission_count,
        )
        for row in rows
    ]




class SuggestionNotPendingError(ValueError):
    """Raised when a decision targets an already-approved/rejected suggestion.

    Decided rows are terminal (AD-8) - a resubmission opens a fresh pending row
    rather than reopening this one. Carries a stable `detail` dict so callers
    identify the failure by code, not by string (same shape as
    preferences.TopicCapExceededError)."""

    def __init__(self) -> None:
        self.detail = {"error": "suggestion_not_pending"}
        super().__init__("Only a pending suggestion can be promoted or dismissed.")


class RoleHasNoFieldError(ValueError):
    """Raised when promoting a Role suggestion that has no Field to live under.

    A Role typed as "Other" underneath a Field that was itself uncurated "Other"
    text carries no field_id, and Role.field_id is a non-nullable FK - there is
    no correct row to write. The admin promotes the parent Field first."""

    def __init__(self) -> None:
        self.detail = {"error": "role_has_no_field"}
        super().__init__("Cannot promote a role suggestion that has no curated field.")


def decide_pending_suggestion(
    db: Session, suggestion_id: int, *, status: str, name: str | None = None
) -> PendingSuggestionView | None:
    """Promote a pending suggestion into the curated list, or dismiss it (FR-7).

    Promoting does two separate things (AD-2): it upserts the real Field/Role
    row, and it transitions the suggestion to `approved`. Dismissing only does
    the latter, with `rejected`.

    `name` lets the admin correct the curated spelling before it is written -
    rows predating the `raw_text` column carry only casefolded text, which would
    otherwise mint a lowercase Field. The suggestion row itself is never
    rewritten; it stays a record of what the user actually typed.

    Deliberately does NOT touch User.field_name/role_name: promotion does not
    migrate earlier free-text submitters (PRD FR-7, AD-6).

    Returns the updated view, or None if the id doesn't exist - same contract as
    sources.set_source_status, which the router already 404s on.
    """
    row = db.get(PendingTaxonomySuggestion, suggestion_id)
    if row is None:
        return None
    if row.status != STATUS_PENDING:
        raise SuggestionNotPendingError()

    if status == STATUS_APPROVED:
        curated_name = (name or row.raw_text or row.normalized_text).strip()
        if not curated_name:
            raise ValueError("A promoted suggestion needs a non-empty name.")
        if row.kind == KIND_ROLE:
            if row.field_id is None:
                raise RoleHasNoFieldError()
            field = db.get(Field, row.field_id)
            if field is None:
                raise RoleHasNoFieldError()
            add_role(db, field, curated_name)
        else:
            add_field(db, curated_name)

    row.status = status
    db.commit()
    return PendingSuggestionView(
        id=row.id,
        kind=row.kind,
        field_name=row.field.name if row.field is not None else None,
        text=row.raw_text or row.normalized_text,
        submission_count=row.submission_count,
    )
