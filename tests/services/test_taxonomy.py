import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.models import PendingTaxonomySuggestion, User
from newsagent.models.base import Base
from newsagent.services.taxonomy import (
    DEFAULT_FIELDS,
    add_field,
    list_fields,
    normalize_taxonomy_text,
    record_field_selection,
    seed_default_fields,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(email="user@example.com"))
        session.commit()
        yield session


def _user(db: Session) -> User:
    return db.scalar(select(User).where(User.email == "user@example.com"))


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


def test_record_field_selection_curated(db: Session):
    add_field(db, "Tech")
    user = _user(db)

    record_field_selection(db, user, field_name="Tech", is_other=False)
    db.refresh(user)

    assert user.field_name == "Tech"
    assert db.scalar(select(PendingTaxonomySuggestion)) is None


def test_record_field_selection_other_creates_pending_suggestion(db: Session):
    user = _user(db)

    record_field_selection(db, user, field_name="Marine Biology", is_other=True)
    db.refresh(user)

    assert user.field_name == "Marine Biology"
    suggestion = db.scalar(select(PendingTaxonomySuggestion))
    assert suggestion is not None
    assert suggestion.kind == "field"
    assert suggestion.field_id is None
    assert suggestion.normalized_text == normalize_taxonomy_text("Marine Biology")
    assert suggestion.submission_count == 1
    assert suggestion.status == "pending"


def test_record_field_selection_other_increments_matching_pending_submission(db: Session):
    user_a = _user(db)
    db.add(User(email="user2@example.com"))
    db.commit()
    user_b = db.scalar(select(User).where(User.email == "user2@example.com"))

    record_field_selection(db, user_a, field_name="Marine Biology", is_other=True)
    record_field_selection(db, user_b, field_name="marine   biology", is_other=True)  # different case/spacing

    suggestions = db.scalars(select(PendingTaxonomySuggestion)).all()
    assert len(suggestions) == 1
    assert suggestions[0].submission_count == 2


def test_record_field_selection_other_does_not_reuse_decided_suggestion(db: Session):
    user = _user(db)
    normalized = normalize_taxonomy_text("Marine Biology")
    decided = PendingTaxonomySuggestion(
        kind="field", field_id=None, normalized_text=normalized, status="approved", submission_count=1
    )
    db.add(decided)
    db.commit()

    record_field_selection(db, user, field_name="Marine Biology", is_other=True)

    suggestions = db.scalars(select(PendingTaxonomySuggestion)).all()
    statuses = sorted(s.status for s in suggestions)
    assert statuses == ["approved", "pending"]
    fresh_pending = next(s for s in suggestions if s.status == "pending")
    assert fresh_pending.submission_count == 1


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
