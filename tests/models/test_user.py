from newsagent.models import User
from newsagent.models.user import first_name


def test_first_name_prefers_given_name_over_name_split():
    user = User(email="user@example.com", name="Nagy János", given_name="Nagy")
    assert first_name(user) == "Nagy"


def test_first_name_strips_whitespace_padded_given_name():
    """Review-found edge case (spec-gh-62, review_loop_iteration 1): the
    previous helper checked `.strip()` for truthiness but returned the
    unstripped value, leaking stray whitespace into the greeting."""
    user = User(email="user@example.com", name="Nagy János", given_name=" Nagy ")
    assert first_name(user) == "Nagy"


def test_first_name_falls_through_to_name_split_for_non_string_given_name():
    """Review-found edge case (spec-gh-62, review_loop_iteration 1): a
    malformed OAuth claim could make given_name a non-string; the old helper
    would raise AttributeError from .strip() instead of falling back."""
    user = User(email="user@example.com", name="דנה לוי-כהן", given_name=123)
    assert first_name(user) == "דנה"


def test_first_name_falls_back_to_name_split_when_given_name_absent():
    user = User(email="user@example.com", name="דנה לוי-כהן")
    assert first_name(user) == "דנה"


def test_first_name_none_when_no_name_at_all():
    user = User(email="user@example.com")
    assert first_name(user) is None
