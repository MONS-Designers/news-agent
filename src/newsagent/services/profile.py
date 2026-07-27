"""Domain service for writing a user's profile (issue: Profile-Based Topic
Suggestions). Owns the profile-save transaction; delegates every taxonomy
lookup and review-queue write to services/taxonomy.py."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsagent.models import User
from newsagent.models.pending_taxonomy_suggestion import KIND_FIELD, KIND_ROLE
from newsagent.services import taxonomy

MAX_NAME_LENGTH = 100

# Fixed illustrative set (PRD FR-3) — no "Other" path, unlike Field/Role, so
# these are validated as a closed set rather than resolved against a curated
# DB table. Values are storage keys; display labels ("0–2 yrs" etc.) are a
# frontend-only concern.
EXPERIENCE_BUCKETS: list[str] = ["0-2", "3-5", "6-10", "10+"]

# One fixed message for every rejection cause. Which check failed (blank, too
# long, not actually curated) is deliberately not disclosed — the frontend
# validates before submitting, so a user only reaches this via a hand-built
# request, and a probe should not be able to enumerate the curated list.
INVALID_PROFILE = "Invalid profile selection."


def _clean(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or len(cleaned) > MAX_NAME_LENGTH:
        raise ValueError(INVALID_PROFILE)
    return cleaned


def save_profile(
    db: Session,
    user: User,
    *,
    field_name: str,
    field_is_other: bool,
    role_name: str | None,
    role_is_other: bool,
    experience_bucket: str | None,
) -> User:
    """Save the user's chosen Field, Role and Experience Bucket in a single
    transaction.

    Field and Role are stored as plain strings on User whether they came from
    the curated list or were typed via "Other" (AD-6). Each "Other" value also
    stages a Pending Taxonomy Suggestion for admin review. Experience Bucket has
    no "Other" path — it is validated against a fixed set and never queues a
    suggestion.

    The `*_is_other` flags are claims, not instructions: a request asserting a
    curated pick is rejected unless the name actually resolves against the
    curated list, so a hand-built request cannot store arbitrary text as
    "curated" and skip the review queue.

    `role_name`/`experience_bucket` of `None` mean "not submitted in this
    request" and leave the existing value untouched; blank or over-long name
    input, and any experience_bucket outside the fixed set, are rejected.

    All writes share one commit, so a rejected input persists nothing.
    """
    field_name = _clean(field_name)
    if role_name is not None:
        role_name = _clean(role_name)
    if experience_bucket is not None and experience_bucket not in EXPERIENCE_BUCKETS:
        raise ValueError(INVALID_PROFILE)

    # A concurrent submission of the same "Other" text can win the race between
    # our lookup and our insert; the partial unique index turns that into an
    # IntegrityError. Retrying re-runs the lookup, which now finds the winner's
    # row and increments it instead.
    for attempt in (1, 2):
        try:
            return _apply(
                db,
                user,
                field_name=field_name,
                field_is_other=field_is_other,
                role_name=role_name,
                role_is_other=role_is_other,
                experience_bucket=experience_bucket,
            )
        except IntegrityError:
            db.rollback()
            if attempt == 2:
                raise

    raise AssertionError("unreachable")


def _apply(
    db: Session,
    user: User,
    *,
    field_name: str,
    field_is_other: bool,
    role_name: str | None,
    role_is_other: bool,
    experience_bucket: str | None,
) -> User:
    field = taxonomy.find_field_by_name(db, field_name)
    if not field_is_other and field is None:
        raise ValueError(INVALID_PROFILE)

    # Store the curated spelling, not the client's casing — AD-6's name-lookup
    # is what every later consumer depends on, and "  tech " must not become a
    # value that never matches "Tech" again.
    user.field_name = field.name if field is not None and not field_is_other else field_name

    if field_is_other:
        taxonomy.record_pending_suggestion(db, kind=KIND_FIELD, field_id=None, text=field_name)

    if role_name is not None:
        role = (
            taxonomy.find_role_by_name(db, field.id, role_name) if field is not None else None
        )
        if not role_is_other and role is None:
            raise ValueError(INVALID_PROFILE)

        user.role_name = role.name if role is not None and not role_is_other else role_name

        if role_is_other:
            # A Role suggestion records which Field it was submitted under so the
            # admin queue can scope it. The Field itself may be uncurated "Other"
            # text with no row to point at — then field_id stays None rather than
            # dropping the submission.
            taxonomy.record_pending_suggestion(
                db,
                kind=KIND_ROLE,
                field_id=field.id if field is not None else None,
                text=role_name,
            )

    if experience_bucket is not None:
        user.experience_bucket = experience_bucket

    db.commit()
    db.refresh(user)
    return user
