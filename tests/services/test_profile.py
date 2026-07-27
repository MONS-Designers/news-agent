import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.models import PendingTaxonomySuggestion, User
from newsagent.models.base import Base
from newsagent.services.profile import INVALID_PROFILE, MAX_NAME_LENGTH, save_profile
from newsagent.services.taxonomy import add_field, add_role, normalize_taxonomy_text


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


def _save(db: Session, user: User, **overrides) -> User:
    kwargs = {
        "field_name": "Tech",
        "field_is_other": False,
        "role_name": None,
        "role_is_other": False,
    }
    kwargs.update(overrides)
    return save_profile(db, user, **kwargs)


# --- Field ---------------------------------------------------------------


def test_curated_field_saves_name_without_a_suggestion(db: Session):
    add_field(db, "Tech")
    user = _user(db)

    _save(db, user, field_name="Tech")

    assert user.field_name == "Tech"
    assert db.scalar(select(PendingTaxonomySuggestion)) is None


def test_other_field_creates_pending_suggestion(db: Session):
    user = _user(db)

    _save(db, user, field_name="Marine Biology", field_is_other=True)

    assert user.field_name == "Marine Biology"
    suggestion = db.scalar(select(PendingTaxonomySuggestion))
    assert suggestion is not None
    assert suggestion.kind == "field"
    assert suggestion.field_id is None
    assert suggestion.normalized_text == normalize_taxonomy_text("Marine Biology")
    assert suggestion.submission_count == 1
    assert suggestion.status == "pending"


def test_other_field_increments_matching_pending_submission(db: Session):
    user_a = _user(db)
    db.add(User(email="user2@example.com"))
    db.commit()
    user_b = db.scalar(select(User).where(User.email == "user2@example.com"))

    _save(db, user_a, field_name="Marine Biology", field_is_other=True)
    _save(db, user_b, field_name="marine   biology", field_is_other=True)  # different case/spacing

    suggestions = db.scalars(select(PendingTaxonomySuggestion)).all()
    assert len(suggestions) == 1
    assert suggestions[0].submission_count == 2


def test_other_field_does_not_reuse_decided_suggestion(db: Session):
    user = _user(db)
    db.add(
        PendingTaxonomySuggestion(
            kind="field",
            field_id=None,
            normalized_text=normalize_taxonomy_text("Marine Biology"),
            status="approved",
            submission_count=1,
        )
    )
    db.commit()

    _save(db, user, field_name="Marine Biology", field_is_other=True)

    suggestions = db.scalars(select(PendingTaxonomySuggestion)).all()
    assert sorted(s.status for s in suggestions) == ["approved", "pending"]
    fresh_pending = next(s for s in suggestions if s.status == "pending")
    assert fresh_pending.submission_count == 1


# --- Role ----------------------------------------------------------------


def test_curated_role_saves_name_without_a_suggestion(db: Session):
    field, _ = add_field(db, "Tech")
    add_role(db, field, "Software Engineer")
    user = _user(db)

    _save(db, user, field_name="Tech", role_name="Software Engineer")

    assert user.role_name == "Software Engineer"
    assert db.scalar(select(PendingTaxonomySuggestion)) is None


def test_other_role_suggestion_is_scoped_to_the_curated_field(db: Session):
    field, _ = add_field(db, "Tech")
    user = _user(db)

    _save(db, user, field_name="Tech", role_name="Developer Relations", role_is_other=True)

    assert user.role_name == "Developer Relations"
    suggestion = db.scalar(select(PendingTaxonomySuggestion))
    assert suggestion is not None
    assert suggestion.kind == "role"
    assert suggestion.field_id == field.id
    assert suggestion.normalized_text == normalize_taxonomy_text("Developer Relations")


def test_other_role_under_uncurated_other_field_gets_null_field_id(db: Session):
    """AC #5 — an unmatchable Field must not lose the Role submission."""
    user = _user(db)

    _save(
        db,
        user,
        field_name="Marine Biology",
        field_is_other=True,
        role_name="Reef Survey Lead",
        role_is_other=True,
    )

    by_kind = {s.kind: s for s in db.scalars(select(PendingTaxonomySuggestion)).all()}
    assert set(by_kind) == {"field", "role"}
    assert by_kind["role"].field_id is None
    assert by_kind["role"].normalized_text == normalize_taxonomy_text("Reef Survey Lead")


def test_other_role_increments_matching_pending_submission(db: Session):
    add_field(db, "Tech")
    user_a = _user(db)
    db.add(User(email="user2@example.com"))
    db.commit()
    user_b = db.scalar(select(User).where(User.email == "user2@example.com"))

    _save(db, user_a, field_name="Tech", role_name="Developer Relations", role_is_other=True)
    _save(db, user_b, field_name="Tech", role_name="developer   relations", role_is_other=True)

    suggestions = db.scalars(select(PendingTaxonomySuggestion)).all()
    assert len(suggestions) == 1
    assert suggestions[0].submission_count == 2


def test_other_role_does_not_reuse_decided_suggestion(db: Session):
    field, _ = add_field(db, "Tech")
    user = _user(db)
    db.add(
        PendingTaxonomySuggestion(
            kind="role",
            field_id=field.id,
            normalized_text=normalize_taxonomy_text("Developer Relations"),
            status="approved",
            submission_count=1,
        )
    )
    db.commit()

    _save(db, user, field_name="Tech", role_name="Developer Relations", role_is_other=True)

    suggestions = db.scalars(select(PendingTaxonomySuggestion)).all()
    assert sorted(s.status for s in suggestions) == ["approved", "pending"]


def test_role_name_none_leaves_existing_role_untouched(db: Session):
    field, _ = add_field(db, "Tech")
    add_role(db, field, "Software Engineer")
    user = _user(db)
    _save(db, user, field_name="Tech", role_name="Software Engineer")

    _save(db, user, field_name="Finance", field_is_other=True, role_name=None)

    assert user.field_name == "Finance"
    assert user.role_name == "Software Engineer"


# --- Validation ----------------------------------------------------------


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_field_name_is_rejected(db: Session, blank: str):
    with pytest.raises(ValueError):
        _save(db, _user(db), field_name=blank)


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_role_name_is_rejected(db: Session, blank: str):
    add_field(db, "Tech")
    with pytest.raises(ValueError):
        _save(db, _user(db), field_name="Tech", role_name=blank)


def test_over_long_name_is_rejected(db: Session):
    with pytest.raises(ValueError):
        _save(db, _user(db), field_name="x" * (MAX_NAME_LENGTH + 1), field_is_other=True)


def test_multi_word_name_stays_valid(db: Session):
    user = _user(db)
    _save(db, user, field_name="Marine Biology", field_is_other=True)
    assert user.field_name == "Marine Biology"


def test_claiming_curated_for_an_uncurated_field_is_rejected(db: Session):
    """A client-declared is_other=false must not be enough to store arbitrary
    text as curated and skip the review queue."""
    add_field(db, "Tech")

    with pytest.raises(ValueError):
        _save(db, _user(db), field_name="Totally Made Up", field_is_other=False)

    assert db.scalar(select(PendingTaxonomySuggestion)) is None


def test_claiming_curated_for_an_uncurated_role_is_rejected(db: Session):
    add_field(db, "Tech")

    with pytest.raises(ValueError):
        _save(db, _user(db), field_name="Tech", role_name="Totally Made Up", role_is_other=False)


def test_every_rejection_uses_the_same_message(db: Session):
    add_field(db, "Tech")
    messages = set()

    for kwargs in (
        {"field_name": "   "},
        {"field_name": "x" * (MAX_NAME_LENGTH + 1), "field_is_other": True},
        {"field_name": "Totally Made Up"},
        {"field_name": "Tech", "role_name": "Totally Made Up"},
    ):
        with pytest.raises(ValueError) as caught:
            _save(db, _user(db), **kwargs)
        messages.add(str(caught.value))

    assert messages == {INVALID_PROFILE}


def test_curated_pick_is_stored_with_its_canonical_spelling(db: Session):
    """AD-6's name-lookup is what every later consumer depends on, so padded or
    differently-cased input must not become a value that never matches again."""
    field, _ = add_field(db, "Tech")
    add_role(db, field, "Software Engineer")
    user = _user(db)

    _save(db, user, field_name="  tech  ", role_name="SOFTWARE ENGINEER")

    assert user.field_name == "Tech"
    assert user.role_name == "Software Engineer"


def test_suggestion_preserves_the_submitted_spelling(db: Session):
    """normalized_text is casefolded for deduping; Story 2.2 promotes from
    raw_text, so it must keep the display form."""
    user = _user(db)

    _save(db, user, field_name="Marine Biology", field_is_other=True)

    suggestion = db.scalar(select(PendingTaxonomySuggestion))
    assert suggestion.raw_text == "Marine Biology"
    assert suggestion.normalized_text == "marine biology"


def test_repeat_submission_keeps_the_first_spelling(db: Session):
    user_a = _user(db)
    db.add(User(email="user2@example.com"))
    db.commit()
    user_b = db.scalar(select(User).where(User.email == "user2@example.com"))

    _save(db, user_a, field_name="Marine Biology", field_is_other=True)
    _save(db, user_b, field_name="marine biology", field_is_other=True)

    suggestion = db.scalar(select(PendingTaxonomySuggestion))
    assert suggestion.raw_text == "Marine Biology"
    assert suggestion.submission_count == 2


def test_other_text_is_stored_trimmed(db: Session):
    user = _user(db)

    _save(db, user, field_name="  Marine Biology  ", field_is_other=True)

    assert user.field_name == "Marine Biology"


def test_rejected_save_persists_nothing(db: Session):
    """AC #9 — the profile write and its suggestion upserts share one commit."""
    user = _user(db)

    with pytest.raises(ValueError):
        _save(db, user, field_name="Marine Biology", field_is_other=True, role_name="  ")

    db.rollback()
    assert user.field_name is None
    assert db.scalar(select(PendingTaxonomySuggestion)) is None
