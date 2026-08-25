import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.models import PendingTaxonomySuggestion, Topic, User, UserTopicPreference
from newsagent.models.base import Base
from newsagent.models.user import SUGGESTION_STATUS_NONE, SUGGESTION_STATUS_PENDING
from newsagent.services import profile as profile_module
from newsagent.services.profile import (
    EXPERIENCE_BUCKETS,
    INVALID_PROFILE,
    MAX_INTEREST_LENGTH,
    MAX_NAME_LENGTH,
    save_profile,
    suggest_prompts_for_user,
)
from newsagent.services.preferences import set_preferences
from newsagent.services.sources import add_topic
from newsagent.services.taxonomy import add_field, add_role, normalize_taxonomy_text
from newsagent.suggestions.errors import SuggestionError
from newsagent.suggestions.types import PromptText


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
        "experience_bucket": None,
        "interest_free_text": None,
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
    """AC #5 - an unmatchable Field must not lose the Role submission."""
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


# --- Experience Bucket ----------------------------------------------------


@pytest.mark.parametrize("bucket", EXPERIENCE_BUCKETS)
def test_each_valid_bucket_saves(db: Session, bucket: str):
    add_field(db, "Tech")
    user = _user(db)
    _save(db, user, experience_bucket=bucket)
    assert user.experience_bucket == bucket


def test_invalid_bucket_is_rejected(db: Session):
    add_field(db, "Tech")
    with pytest.raises(ValueError):
        _save(db, _user(db), experience_bucket="not-a-real-bucket")


def test_experience_bucket_none_leaves_existing_value_untouched(db: Session):
    add_field(db, "Tech")
    add_field(db, "Finance")
    user = _user(db)
    _save(db, user, experience_bucket="6-10")

    _save(db, user, field_name="Finance", experience_bucket=None)

    assert user.field_name == "Finance"
    assert user.experience_bucket == "6-10"


def test_experience_bucket_never_creates_a_suggestion(db: Session):
    """No 'Other' concept for buckets - a fixed set has nothing to queue."""
    add_field(db, "Tech")
    user = _user(db)
    _save(db, user, experience_bucket="10+")
    assert db.scalar(select(PendingTaxonomySuggestion)) is None


# --- Interest Free-Text ---------------------------------------------------


def test_interest_free_text_saves_trimmed(db: Session):
    add_field(db, "Tech")
    user = _user(db)
    _save(db, user, interest_free_text="  building a side project  ")
    assert user.interest_free_text == "building a side project"


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_interest_free_text_stores_none(db: Session, blank: str):
    """A submitted-but-blank string clears the field to NULL, not ''."""
    add_field(db, "Tech")
    user = _user(db)
    _save(db, user, interest_free_text="something")
    assert user.interest_free_text == "something"

    _save(db, user, field_name=None, interest_free_text=blank)
    assert user.interest_free_text is None


def test_interest_free_text_none_leaves_existing_value_untouched(db: Session):
    """None means 'not submitted' - distinct from submitting blank text."""
    add_field(db, "Tech")
    user = _user(db)
    _save(db, user, interest_free_text="something")

    _save(db, user, field_name=None, interest_free_text=None)

    assert user.interest_free_text == "something"


def test_over_long_interest_free_text_is_rejected(db: Session):
    with pytest.raises(ValueError):
        _save(db, _user(db), interest_free_text="x" * (MAX_INTEREST_LENGTH + 1))


def test_interest_free_text_never_creates_a_suggestion(db: Session):
    add_field(db, "Tech")
    user = _user(db)
    _save(db, user, interest_free_text="something")
    assert db.scalar(select(PendingTaxonomySuggestion)) is None


# --- field_name=None (Step 2's call shape) ---------------------------------


def test_field_name_none_leaves_field_and_role_untouched(db: Session):
    """The call shape InterestsStep.vue actually uses: interest text alone,
    with Field/Role already saved by an earlier Step 1 call."""
    field, _ = add_field(db, "Tech")
    add_role(db, field, "Software Engineer")
    user = _user(db)
    _save(db, user, field_name="Tech", role_name="Software Engineer")

    result = _save(db, user, field_name=None, interest_free_text="curious about ML")

    assert result.field_name == "Tech"
    assert result.role_name == "Software Engineer"
    assert result.interest_free_text == "curious about ML"


def test_role_name_without_field_name_is_rejected(db: Session):
    add_field(db, "Tech")
    with pytest.raises(ValueError):
        _save(db, _user(db), field_name=None, role_name="Software Engineer")


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
        {"experience_bucket": "not-a-real-bucket"},
        {"interest_free_text": "x" * (MAX_INTEREST_LENGTH + 1)},
        {"field_name": None, "role_name": "Software Engineer"},
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
    """AC #9 - the profile write and its suggestion upserts share one commit."""
    user = _user(db)

    with pytest.raises(ValueError):
        _save(db, user, field_name="Marine Biology", field_is_other=True, role_name="  ")

    db.rollback()
    assert user.field_name is None
    assert db.scalar(select(PendingTaxonomySuggestion)) is None
    assert user.suggestion_request_seq == 0
    assert user.suggestion_status == SUGGESTION_STATUS_NONE


# --- Suggestion polling: pending + seq bump (Story 1.6) --------------------


def test_successful_save_sets_pending_and_bumps_seq(db: Session):
    add_field(db, "Tech")
    user = _user(db)
    assert user.suggestion_status == SUGGESTION_STATUS_NONE
    assert user.suggestion_request_seq == 0

    _save(db, user)

    assert user.suggestion_status == SUGGESTION_STATUS_PENDING
    assert user.suggestion_request_seq == 1


def test_second_successful_save_bumps_seq_again(db: Session):
    add_field(db, "Tech")
    user = _user(db)
    _save(db, user)
    assert user.suggestion_request_seq == 1

    _save(db, user, field_name=None, interest_free_text="curious about ML")

    assert user.suggestion_status == SUGGESTION_STATUS_PENDING
    assert user.suggestion_request_seq == 2


# --- suggest_prompts_for_user (Role and Prompt Suggestions story) ---------


class _FakeSource:
    """Minimal double for get_suggestion_source()'s return value - only
    suggest_prompts is exercised here."""

    def __init__(self, texts: list[str] | None = None, error: Exception | None = None):
        self._texts = texts or []
        self._error = error
        self.calls: list[tuple] = []

    def suggest_prompts(self, *, field_name=None, role_name=None, experience_bucket=None):
        self.calls.append((field_name, role_name, experience_bucket))
        if self._error is not None:
            raise self._error
        return [PromptText(text=text) for text in self._texts]


def test_suggest_prompts_for_user_returns_texts_using_saved_profile(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    add_field(db, "Tech")
    user = _user(db)
    _save(db, user, field_name="Tech", experience_bucket="3-5")
    user.role_name = "Software Engineer"

    source = _FakeSource(texts=["What excites you about AI?", "Any favorite newsletters?"])
    monkeypatch.setattr(profile_module, "get_suggestion_source", lambda: source)

    result = suggest_prompts_for_user(user)

    assert result == ["What excites you about AI?", "Any favorite newsletters?"]
    assert source.calls == [("Tech", "Software Engineer", "3-5")]


def test_suggest_prompts_for_user_returns_empty_on_suggestion_error(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    user = _user(db)
    source = _FakeSource(error=SuggestionError("local LLM unreachable"))
    monkeypatch.setattr(profile_module, "get_suggestion_source", lambda: source)

    assert suggest_prompts_for_user(user) == []


def test_suggest_prompts_for_user_caps_at_three(db: Session, monkeypatch: pytest.MonkeyPatch):
    """FR-5: "up to 3" is a contract of the service, not just a frontend
    .slice(0, 3) - the API itself must not return more."""
    user = _user(db)
    source = _FakeSource(texts=[f"Prompt {i}" for i in range(5)])
    monkeypatch.setattr(profile_module, "get_suggestion_source", lambda: source)

    assert suggest_prompts_for_user(user) == ["Prompt 0", "Prompt 1", "Prompt 2"]


def test_suggest_prompts_for_user_skips_blank_prompts(db: Session, monkeypatch: pytest.MonkeyPatch):
    user = _user(db)
    source = _FakeSource(texts=["  ", "What excites you about AI?"])
    monkeypatch.setattr(profile_module, "get_suggestion_source", lambda: source)

    assert suggest_prompts_for_user(user) == ["What excites you about AI?"]


# --- Topic staleness on profile edit --------------------------------------


def _subscribe(db: Session, user: User) -> None:
    topic, _ = add_topic(db, "בינה מלאכותית")
    db.add(UserTopicPreference(user_id=user.id, topic_id=topic.id))
    db.commit()
    db.refresh(user)


def test_first_run_profile_save_does_not_flag_topics_stale(db: Session):
    """A brand-new user has no subscriptions to diverge from - flagging here
    would greet them with an "out of date" banner before they picked any."""
    user = _user(db)
    add_field(db, "Tech")

    _save(db, user)

    assert user.topics_stale_at is None


def test_changing_field_flags_saved_topics_as_stale(db: Session):
    user = _user(db)
    add_field(db, "Tech")
    add_field(db, "Design")
    _save(db, user)
    _subscribe(db, user)

    _save(db, user, field_name="Design")

    assert user.topics_stale_at is not None


def test_changing_interest_text_flags_saved_topics_as_stale(db: Session):
    """Interests feed suggest_topics just as much as Field/Role do."""
    user = _user(db)
    add_field(db, "Tech")
    _save(db, user)
    _subscribe(db, user)

    _save(db, user, interest_free_text="כלי פיתוח ובדיקות אוטומטיות")

    assert user.topics_stale_at is not None


def test_resaving_the_same_profile_does_not_flag_topics_stale(db: Session):
    """The flag tracks a real divergence, not the act of pressing save."""
    user = _user(db)
    add_field(db, "Tech")
    _save(db, user)
    _subscribe(db, user)

    _save(db, user, field_name="Tech")

    assert user.topics_stale_at is None


def test_saving_topics_clears_the_stale_flag(db: Session):
    user = _user(db)
    add_field(db, "Tech")
    add_field(db, "Design")
    _save(db, user)
    _subscribe(db, user)
    _save(db, user, field_name="Design")
    assert user.topics_stale_at is not None

    topic = db.scalar(select(Topic).where(Topic.name == "בינה מלאכותית"))
    set_preferences(db, user, [topic.id])

    assert user.topics_stale_at is None
