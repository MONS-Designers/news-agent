import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsagent.models import PendingTaxonomySuggestion
from newsagent.models.base import Base
from newsagent.services.taxonomy import (
    DEFAULT_FIELDS,
    DEFAULT_ROLES,
    add_field,
    add_role,
    find_field_by_name,
    list_fields,
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
