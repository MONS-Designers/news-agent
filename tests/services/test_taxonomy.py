import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsagent.models import Field, PendingTaxonomySuggestion, Role, User
from newsagent.models.base import Base
from newsagent.services.taxonomy import (
    DEFAULT_FIELDS,
    DEFAULT_ROLES,
    RoleHasNoFieldError,
    SuggestionNotPendingError,
    add_field,
    add_role,
    decide_pending_suggestion,
    find_field_by_name,
    list_fields,
    list_pending_suggestions,
    list_roles,
    normalize_taxonomy_text,
    record_pending_suggestion,
    seed_default_fields,
    seed_default_roles,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_add_field_is_idempotent(db: Session):
    _, created = add_field(db, "Tech")
    assert created is True
    _, created_again = add_field(db, "Tech")
    assert created_again is False


def test_list_fields_ordered_by_name(db: Session):
    add_field(db, "Finance")
    add_field(db, "Design")
    add_field(db, "Tech")

    names = [f.name for f in list_fields(db)]
    assert names == ["Design", "Finance", "Tech"]


def test_add_role_is_idempotent(db: Session):
    field, _ = add_field(db, "Tech")

    _, created = add_role(db, field, "Software Engineer")
    assert created is True
    _, created_again = add_role(db, field, "Software Engineer")
    assert created_again is False


def test_same_role_name_coexists_under_two_fields(db: Session):
    healthcare, _ = add_field(db, "Healthcare")
    education, _ = add_field(db, "Education")

    add_role(db, healthcare, "Researcher")
    add_role(db, education, "Researcher")

    assert [r.name for r in list_roles(db, healthcare.id)] == ["Researcher"]
    assert [r.name for r in list_roles(db, education.id)] == ["Researcher"]


def test_list_roles_is_field_scoped_and_ordered(db: Session):
    tech, _ = add_field(db, "Tech")
    finance, _ = add_field(db, "Finance")
    add_role(db, tech, "Product Manager")
    add_role(db, tech, "Data Scientist")
    add_role(db, finance, "Analyst")

    assert [r.name for r in list_roles(db, tech.id)] == ["Data Scientist", "Product Manager"]


def test_list_roles_for_unknown_field_is_empty(db: Session):
    assert list_roles(db, 999) == []


def test_find_field_by_name_matches_case_and_whitespace_variants(db: Session):
    add_field(db, "Tech")

    for variant in ("Tech", "tech", "  TECH  "):
        found = find_field_by_name(db, variant)
        assert found is not None
        assert found.name == "Tech"


def test_find_field_by_name_returns_none_for_uncurated_text(db: Session):
    add_field(db, "Tech")
    assert find_field_by_name(db, "Marine Biology") is None


def test_record_pending_suggestion_does_not_commit(db: Session):
    """profile.save_profile owns the single commit — this helper must only stage
    the write, so a later failure rolls the whole save back (AC #9)."""
    record_pending_suggestion(db, kind="field", field_id=None, text="Marine Biology")
    db.rollback()

    assert db.scalar(select(PendingTaxonomySuggestion)) is None


def test_record_pending_suggestion_scopes_match_by_kind_and_field(db: Session):
    tech, _ = add_field(db, "Tech")
    finance, _ = add_field(db, "Finance")

    record_pending_suggestion(db, kind="role", field_id=tech.id, text="DevRel")
    record_pending_suggestion(db, kind="role", field_id=finance.id, text="DevRel")
    record_pending_suggestion(db, kind="field", field_id=None, text="DevRel")
    db.commit()

    suggestions = db.scalars(select(PendingTaxonomySuggestion)).all()
    assert len(suggestions) == 3
    assert all(s.submission_count == 1 for s in suggestions)


def test_seed_default_roles_creates_roles_under_their_fields(db: Session):
    report = seed_default_roles(db)

    assert report.roles_created == sum(len(roles) for roles in DEFAULT_ROLES.values())
    tech = find_field_by_name(db, "Tech")
    assert tech is not None
    assert [r.name for r in list_roles(db, tech.id)] == sorted(DEFAULT_ROLES["Tech"])


def test_seed_default_roles_is_idempotent(db: Session):
    seed_default_roles(db)
    report = seed_default_roles(db)

    assert report.roles_created == 0
    assert report.fields_created == 0


def test_normalize_strips_invisible_bidi_marks():
    """A Hebrew/Arabic IME inserts category-Cf marks that render as nothing —
    without stripping them the queue grows lookalike duplicate rows."""
    with_rlm = "‏Tech‎"
    assert normalize_taxonomy_text(with_rlm) == normalize_taxonomy_text("Tech")


def test_normalize_unifies_unicode_composition():
    decomposed = "Café"  # macOS submits NFD
    composed = "Café"
    assert normalize_taxonomy_text(decomposed) == normalize_taxonomy_text(composed)


def test_open_suggestions_are_unique_per_field_row(db: Session):
    """The partial unique index must cover kind='field' rows too — their
    field_id is always NULL, and NULLs never collide in a plain unique index."""
    record_pending_suggestion(db, kind="field", field_id=None, text="Marine Biology")
    db.commit()

    db.add(
        PendingTaxonomySuggestion(
            kind="field",
            field_id=None,
            normalized_text=normalize_taxonomy_text("Marine Biology"),
            submission_count=1,
            status="pending",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_open_suggestions_are_unique_per_role_row(db: Session):
    field, _ = add_field(db, "Tech")
    record_pending_suggestion(db, kind="role", field_id=field.id, text="DevRel")
    db.commit()

    db.add(
        PendingTaxonomySuggestion(
            kind="role",
            field_id=field.id,
            normalized_text=normalize_taxonomy_text("DevRel"),
            submission_count=1,
            status="pending",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_decided_suggestions_are_exempt_from_the_unique_index(db: Session):
    """The same text may legitimately be rejected, resubmitted and rejected
    again — only open rows are constrained."""
    normalized = normalize_taxonomy_text("Marine Biology")
    for _ in range(2):
        db.add(
            PendingTaxonomySuggestion(
                kind="field",
                field_id=None,
                normalized_text=normalized,
                submission_count=1,
                status="rejected",
            )
        )
    db.commit()

    assert db.query(PendingTaxonomySuggestion).count() == 2


def test_normalize_taxonomy_text_case_and_whitespace():
    assert normalize_taxonomy_text("  Marine   Biology ") == normalize_taxonomy_text("marine biology")


def test_seed_creates_all_default_fields(db: Session):
    report = seed_default_fields(db)
    assert report.fields_created == len(DEFAULT_FIELDS)
    assert {f.name for f in list_fields(db)} == set(DEFAULT_FIELDS)


def test_seed_default_fields_is_idempotent(db: Session):
    seed_default_fields(db)
    report = seed_default_fields(db)
    assert report.fields_created == 0


def test_list_pending_suggestions_is_empty_by_default(db: Session):
    assert list_pending_suggestions(db) == []


def test_list_pending_suggestions_resolves_field_name_per_kind(db: Session):
    tech, _ = add_field(db, "Tech")
    record_pending_suggestion(db, kind="field", field_id=None, text="Marine Biology")
    record_pending_suggestion(db, kind="role", field_id=tech.id, text="DevRel")
    db.commit()

    by_text = {view.text: view for view in list_pending_suggestions(db)}

    assert by_text["Marine Biology"].kind == "field"
    assert by_text["Marine Biology"].field_name is None
    assert by_text["DevRel"].kind == "role"
    assert by_text["DevRel"].field_name == "Tech"


def test_list_pending_suggestions_excludes_decided_rows(db: Session):
    record_pending_suggestion(db, kind="field", field_id=None, text="Still open")
    db.add(
        PendingTaxonomySuggestion(
            kind="field",
            field_id=None,
            normalized_text="promoted",
            raw_text="Promoted",
            submission_count=1,
            status="approved",
        )
    )
    db.add(
        PendingTaxonomySuggestion(
            kind="field",
            field_id=None,
            normalized_text="dismissed",
            raw_text="Dismissed",
            submission_count=1,
            status="rejected",
        )
    )
    db.commit()

    assert [view.text for view in list_pending_suggestions(db)] == ["Still open"]


def test_list_pending_suggestions_groups_normalized_variants_with_a_count(db: Session):
    """AC #2 — the queue must never show the same normalized text twice; the
    write side already merged them (AD-8), so the read side just reports."""
    record_pending_suggestion(db, kind="field", field_id=None, text="Marine Biology")
    record_pending_suggestion(db, kind="field", field_id=None, text="  marine   biology ")
    db.commit()

    views = list_pending_suggestions(db)

    assert len(views) == 1
    assert views[0].submission_count == 2
    # The first submitter's spelling is what the admin reads, not the casefolded key.
    assert views[0].text == "Marine Biology"


def test_list_pending_suggestions_ranks_most_requested_first(db: Session):
    record_pending_suggestion(db, kind="field", field_id=None, text="Rare")
    record_pending_suggestion(db, kind="field", field_id=None, text="Popular")
    record_pending_suggestion(db, kind="field", field_id=None, text="Popular")
    db.commit()

    assert [view.text for view in list_pending_suggestions(db)] == ["Popular", "Rare"]


def test_list_pending_suggestions_falls_back_to_normalized_text(db: Session):
    """raw_text is nullable — rows written before that column existed have none,
    and an admin still needs something readable to decide on."""
    db.add(
        PendingTaxonomySuggestion(
            kind="field",
            field_id=None,
            normalized_text="legacy row",
            raw_text=None,
            submission_count=1,
        )
    )
    db.commit()

    assert [view.text for view in list_pending_suggestions(db)] == ["legacy row"]


def _pending_id(db: Session, text: str) -> int:
    """The id of the one open suggestion matching `text`."""
    return next(v.id for v in list_pending_suggestions(db) if v.text == text)


def test_promoting_a_field_creates_it_and_marks_the_row_approved(db: Session):
    record_pending_suggestion(db, kind="field", field_id=None, text="Marine Biology")
    db.commit()

    view = decide_pending_suggestion(
        db, _pending_id(db, "Marine Biology"), status="approved"
    )

    assert view is not None
    assert [f.name for f in list_fields(db)] == ["Marine Biology"]
    assert db.get(PendingTaxonomySuggestion, view.id).status == "approved"
    assert list_pending_suggestions(db) == []


def test_promoting_a_field_that_already_exists_reuses_it(db: Session):
    add_field(db, "Marine Biology")
    record_pending_suggestion(db, kind="field", field_id=None, text="Marine Biology")
    db.commit()

    decide_pending_suggestion(db, _pending_id(db, "Marine Biology"), status="approved")

    assert len(list_fields(db)) == 1


def test_promoting_a_role_scopes_it_to_its_own_field(db: Session):
    tech, _ = add_field(db, "Tech")
    finance, _ = add_field(db, "Finance")
    record_pending_suggestion(db, kind="role", field_id=tech.id, text="DevRel")
    db.commit()

    decide_pending_suggestion(db, _pending_id(db, "DevRel"), status="approved")

    assert [r.name for r in list_roles(db, tech.id)] == ["DevRel"]
    assert list_roles(db, finance.id) == []


def test_promoting_a_role_without_a_field_is_refused_and_writes_nothing(db: Session):
    """Role.field_id is a non-nullable FK, so there is no correct row to write.
    A Role typed under an "Other" Field legitimately reaches this state."""
    record_pending_suggestion(db, kind="role", field_id=None, text="Reef Survey Lead")
    db.commit()
    suggestion_id = _pending_id(db, "Reef Survey Lead")

    with pytest.raises(RoleHasNoFieldError) as raised:
        decide_pending_suggestion(db, suggestion_id, status="approved")

    assert raised.value.detail == {"error": "role_has_no_field"}
    assert db.query(Role).count() == 0
    assert db.get(PendingTaxonomySuggestion, suggestion_id).status == "pending"


def test_dismissing_creates_no_curated_row(db: Session):
    tech, _ = add_field(db, "Tech")
    record_pending_suggestion(db, kind="role", field_id=tech.id, text="DevRel")
    db.commit()
    suggestion_id = _pending_id(db, "DevRel")

    decide_pending_suggestion(db, suggestion_id, status="rejected")

    assert db.get(PendingTaxonomySuggestion, suggestion_id).status == "rejected"
    assert db.query(Role).count() == 0
    assert list_pending_suggestions(db) == []


def test_a_decided_suggestion_cannot_be_decided_again(db: Session):
    record_pending_suggestion(db, kind="field", field_id=None, text="Marine Biology")
    db.commit()
    suggestion_id = _pending_id(db, "Marine Biology")
    decide_pending_suggestion(db, suggestion_id, status="rejected")

    with pytest.raises(SuggestionNotPendingError) as raised:
        decide_pending_suggestion(db, suggestion_id, status="approved")

    assert raised.value.detail == {"error": "suggestion_not_pending"}
    assert db.query(Field).count() == 0
    assert db.get(PendingTaxonomySuggestion, suggestion_id).status == "rejected"


def test_deciding_an_unknown_suggestion_returns_none(db: Session):
    assert decide_pending_suggestion(db, 999, status="approved") is None


def test_promoting_with_a_name_override_curates_the_edited_name(db: Session):
    """Rows written before raw_text existed carry only casefolded text, so the
    admin edits the name rather than minting a lowercase Field."""
    db.add(
        PendingTaxonomySuggestion(
            kind="field", field_id=None, normalized_text="marine biology", raw_text=None
        )
    )
    db.commit()
    suggestion_id = _pending_id(db, "marine biology")

    decide_pending_suggestion(db, suggestion_id, status="approved", name="Marine Biology")

    assert [f.name for f in list_fields(db)] == ["Marine Biology"]
    # The queue row itself is a record of what the user typed — never rewritten.
    assert db.get(PendingTaxonomySuggestion, suggestion_id).normalized_text == "marine biology"


def test_promoting_without_an_override_falls_back_to_normalized_text(db: Session):
    db.add(
        PendingTaxonomySuggestion(
            kind="field", field_id=None, normalized_text="marine biology", raw_text=None
        )
    )
    db.commit()

    decide_pending_suggestion(db, _pending_id(db, "marine biology"), status="approved")

    assert [f.name for f in list_fields(db)] == ["marine biology"]


def test_promoting_with_a_blank_name_is_rejected(db: Session):
    record_pending_suggestion(db, kind="field", field_id=None, text="Marine Biology")
    db.commit()

    with pytest.raises(ValueError):
        decide_pending_suggestion(
            db, _pending_id(db, "Marine Biology"), status="approved", name="   "
        )


def test_promotion_does_not_migrate_earlier_submitters(db: Session):
    """PRD FR-7's explicit consequence: the user who typed the free text keeps
    it verbatim. This test exists to stop a future backfill being added."""
    db.add(User(email="submitter@example.com", field_name="Marine Biology"))
    record_pending_suggestion(db, kind="field", field_id=None, text="Marine Biology")
    db.commit()

    decide_pending_suggestion(db, _pending_id(db, "Marine Biology"), status="approved")

    user = db.scalar(select(User).where(User.email == "submitter@example.com"))
    assert user.field_name == "Marine Biology"


def test_resubmitting_decided_text_opens_a_fresh_row(db: Session):
    """AD-8: a decision is terminal. The admin's pending list must never miss a
    resubmission behind an invisible approved/rejected row."""
    record_pending_suggestion(db, kind="field", field_id=None, text="Marine Biology")
    db.commit()
    decide_pending_suggestion(db, _pending_id(db, "Marine Biology"), status="rejected")

    record_pending_suggestion(db, kind="field", field_id=None, text="Marine Biology")
    db.commit()

    views = list_pending_suggestions(db)
    assert len(views) == 1
    assert views[0].submission_count == 1
    assert db.query(PendingTaxonomySuggestion).count() == 2
