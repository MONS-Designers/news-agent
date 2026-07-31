"""Domain service for writing a user's profile (issue: Profile-Based Topic
Suggestions). Owns the profile-save transaction; delegates every taxonomy
lookup and review-queue write to services/taxonomy.py. Also owns the async
suggestion-computation BackgroundTask this triggers (AD-5) — the only file
that imports from newsagent.suggestions (AD-3's profile -> suggestions
dependency direction)."""

from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsagent.models import Topic, User, UserTopicPreference
from newsagent.models.pending_taxonomy_suggestion import KIND_FIELD, KIND_ROLE
from newsagent.models.topic import STATUS_APPROVED as TOPIC_STATUS_APPROVED
from newsagent.models.user import (
    SUGGESTION_STATUS_FAILED,
    SUGGESTION_STATUS_PENDING,
    SUGGESTION_STATUS_READY,
)
from newsagent.services import taxonomy
from newsagent.suggestions import SuggestionError, TopicPopularity, get_suggestion_source

MAX_NAME_LENGTH = 100

# Generous cap on free text — this eventually feeds an LLM prompt (FR-8), so
# unbounded text is a real cost/abuse surface even before that path exists.
MAX_INTEREST_LENGTH = 2000

# Fixed illustrative set (PRD FR-3) — no "Other" path, unlike Field/Role, so
# these are validated as a closed set rather than resolved against a curated
# DB table. Values are storage keys; display labels ("0–2 yrs" etc.) are a
# frontend-only concern.
EXPERIENCE_BUCKETS: list[str] = ["0-2", "3-5", "6-10", "10+"]

# Cap for suggest_prompts_for_user (FR-5: "up to 3 example prompts").
PROMPT_SUGGESTION_CAP = 3

# Merged existing+new Topic suggestion-grid display cap (Real Topic
# Suggestions story), matching ROLE_SUGGESTION_CAP's convention.
TOPIC_SUGGESTION_CAP = 10

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


def _clean_interest(text: str) -> str:
    """Unlike `_clean`, blank is not an error — only validates the length cap
    and strips. Deliberately does NOT collapse blank to None here: that
    conversion happens in `_apply`, at the point of assignment, so a
    submitted-but-blank string (clear the field) stays distinguishable from a
    not-submitted field (leave it untouched) all the way through."""
    cleaned = text.strip()
    if len(cleaned) > MAX_INTEREST_LENGTH:
        raise ValueError(INVALID_PROFILE)
    return cleaned


def save_profile(
    db: Session,
    user: User,
    *,
    field_name: str | None,
    field_is_other: bool,
    role_name: str | None,
    role_is_other: bool,
    experience_bucket: str | None,
    interest_free_text: str | None,
) -> User:
    """Save the user's chosen Field, Role, Experience Bucket and/or Interest
    Free-Text in a single transaction.

    Field and Role are stored as plain strings on User whether they came from
    the curated list or were typed via "Other" (AD-6). Each "Other" value also
    stages a Pending Taxonomy Suggestion for admin review. Experience Bucket and
    Interest Free-Text have no "Other" path — Experience Bucket is validated
    against a fixed set, Interest Free-Text is free text with only a length
    cap — and neither ever queues a suggestion.

    The `*_is_other` flags are claims, not instructions: a request asserting a
    curated pick is rejected unless the name actually resolves against the
    curated list, so a hand-built request cannot store arbitrary text as
    "curated" and skip the review queue.

    `field_name`/`role_name`/`experience_bucket`/`interest_free_text` of `None`
    mean "not submitted in this request" and leave the existing value
    untouched — this is what lets a later step (e.g. Interest Free-Text alone)
    save without resubmitting Field/Role and double-counting an "Other"
    suggestion. Blank or over-long name input, any experience_bucket outside
    the fixed set, and over-long interest text are rejected; a blank interest
    text is not an error, it just stores as None. Submitting `role_name`
    without `field_name` is rejected — a Role can never be resolved without a
    Field, curated or "Other," in the same request.

    All writes share one commit, so a rejected input persists nothing.
    """
    if field_name is not None:
        field_name = _clean(field_name)
    if role_name is not None:
        role_name = _clean(role_name)
    if experience_bucket is not None and experience_bucket not in EXPERIENCE_BUCKETS:
        raise ValueError(INVALID_PROFILE)
    if interest_free_text is not None:
        interest_free_text = _clean_interest(interest_free_text)

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
                interest_free_text=interest_free_text,
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
    field_name: str | None,
    field_is_other: bool,
    role_name: str | None,
    role_is_other: bool,
    experience_bucket: str | None,
    interest_free_text: str | None,
) -> User:
    # A Role can only ever be resolved against a Field supplied in the same
    # request — reject up front rather than reaching for an undefined `field`
    # below. No caller needs this combination today (Step 1 always sends both
    # together; Step 2 sends neither), so this is a defensive 400, not a gap.
    if role_name is not None and field_name is None:
        raise ValueError(INVALID_PROFILE)

    if field_name is not None:
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

    if interest_free_text is not None:
        # A submitted-but-blank string clears the field to NULL; a field that
        # was never submitted at all (None, filtered out above this line) is
        # left untouched — see _clean_interest's docstring.
        user.interest_free_text = interest_free_text or None

    if experience_bucket is not None:
        user.experience_bucket = experience_bucket

    # Unconditional on every successful save, regardless of which fields this
    # particular request touched (AD-5) — the seq race-guard in
    # _compute_and_store_suggestions makes a premature/redundant trigger from
    # an earlier step harmless, so there is no need to distinguish "which
    # step" called this.
    user.suggestion_status = SUGGESTION_STATUS_PENDING
    user.suggestion_request_seq = (user.suggestion_request_seq or 0) + 1

    db.commit()
    db.refresh(user)
    return user


def suggest_prompts_for_user(user: User) -> list[str]:
    """Up to `PROMPT_SUGGESTION_CAP` illustrative example prompts for the
    Interests step (FR-5), generated from the user's already-saved
    Field/Role/Experience Bucket. Fetching never writes anything (FR-5) — a
    failure just means no prompts show, matching the pre-LLM behavior, not an
    error surfaced to the user."""
    try:
        prompts = get_suggestion_source().suggest_prompts(
            field_name=user.field_name,
            role_name=user.role_name,
            experience_bucket=user.experience_bucket,
        )
    except SuggestionError:
        return []
    texts = [p.text.strip() for p in prompts if p.text.strip()]
    return texts[:PROMPT_SUGGESTION_CAP]


# -- Async suggestion computation (AD-5, AD-7) -------------------------------


def _topic_popularity(db: Session) -> list[TopicPopularity]:
    """Every *approved* Topic's cross-user selection count, including zero — a
    topic nobody has picked yet is still a valid fallback candidate, and
    dropping it would risk an empty popularity list (breaking FR-9's
    non-empty guarantee) the moment no topic has ever been selected
    system-wide. Starting the query from Topic with an outer join (not from
    UserTopicPreference) is what keeps zero-selection topics in the result.

    Filtered to `status='approved'` (CAP-3) — a still-`pending` Topic (e.g.
    another user's not-yet-reviewed invented name) must never be offered as a
    candidate to anyone else. Carries `name` alongside `topic_id` +
    `selection_count` so a provider can reason about (and avoid duplicating)
    a topic it can otherwise only see as an opaque id.
    """
    rows = db.execute(
        select(Topic.id, Topic.name, func.count(UserTopicPreference.id))
        .select_from(Topic)
        .outerjoin(UserTopicPreference, UserTopicPreference.topic_id == Topic.id)
        .where(Topic.status == TOPIC_STATUS_APPROVED)
        .group_by(Topic.id)
        .order_by(Topic.id)
    ).all()
    return [
        TopicPopularity(topic_id=topic_id, name=name, selection_count=count)
        for topic_id, name, count in rows
    ]


def _compute_and_store_suggestions(db: Session, user_id: int, expected_seq: int) -> None:
    """BackgroundTask body (session-agnostic — the caller owns the session's
    lifecycle). Computes suggestions for `user_id` and writes the result only
    if `expected_seq` still matches the current `User.suggestion_request_seq`
    at write time — a superseded (re-saved-over) computation discards its
    result instead of overwriting a newer one.
    """
    user = db.get(User, user_id)
    if user is None:
        return  # user deleted mid-flight

    try:
        popularity = _topic_popularity(db)
        approved_names = [p.name for p in popularity]
        source = get_suggestion_source()
        suggestions = source.suggest_topics(
            field_name=user.field_name,
            role_name=user.role_name,
            interest_free_text=user.interest_free_text,
            popularity=popularity,
        )
        new_options = source.suggest_new_topics(
            field_name=user.field_name,
            role_name=user.role_name,
            interest_free_text=user.interest_free_text,
            existing_topic_names=approved_names,
        )

        computed_topic_ids = [s.topic_id for s in suggestions][:TOPIC_SUGGESTION_CAP]

        # Dedupe invented names against the approved catalog (case/whitespace
        # -insensitive, AD-6's normalize_taxonomy_text) — "ai" must not show
        # as a separate pill next to an existing "AI" Topic. Fill only the
        # slots the existing-topic picks above didn't already use, so the
        # merged existing+new total never exceeds TOPIC_SUGGESTION_CAP.
        seen = {taxonomy.normalize_taxonomy_text(name) for name in approved_names}
        remaining = TOPIC_SUGGESTION_CAP - len(computed_topic_ids)
        computed_new_names: list[str] = []
        for option in new_options:
            if remaining <= 0:
                break
            name = option.name.strip()
            if not name:
                continue
            normalized = taxonomy.normalize_taxonomy_text(name)
            if normalized in seen:
                continue
            seen.add(normalized)
            computed_new_names.append(name)
            remaining -= 1

        topic_ids: list[int] | None = computed_topic_ids
        new_names: list[str] | None = computed_new_names
        status = SUGGESTION_STATUS_READY
    except SuggestionError:
        topic_ids = None
        new_names = None
        status = SUGGESTION_STATUS_FAILED

    # Race guard, checked immediately before the write, not at function entry:
    # a concurrent save may have advanced suggestion_request_seq while
    # suggest_topics/suggest_new_topics (above) were running, so the check
    # must happen after that work, on freshly-read state, not on the `user`
    # object as it looked when this function started.
    db.refresh(user)
    if user.suggestion_request_seq != expected_seq:
        return

    user.suggestion_status = status
    if topic_ids is not None:
        user.suggested_topic_ids = topic_ids
    if new_names is not None:
        user.suggested_new_topic_names = new_names
    db.commit()


def run_suggestion_computation(engine: Engine | Connection, user_id: int, expected_seq: int) -> None:
    """The actual FastAPI BackgroundTask target. Opens its own session bound
    to `engine` — the request-scoped session from Depends(get_db) is already
    closed by the time a BackgroundTask runs, so it cannot be reused here."""
    with Session(engine) as db:
        _compute_and_store_suggestions(db, user_id, expected_seq)
