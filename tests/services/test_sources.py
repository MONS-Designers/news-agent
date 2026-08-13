import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.models import Source, Topic
from newsagent.models.base import Base
from newsagent.services.sources import (
    DEFAULT_SOURCES,
    add_source,
    add_topic,
    seed_default_sources,
    set_source_status,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_add_topic_and_source_are_idempotent(db: Session):
    topic, created = add_topic(db, "AI")
    assert created is True
    _, created_again = add_topic(db, "AI")
    assert created_again is False

    _, created = add_source(db, topic, "Feed", "https://example.com/feed")
    assert created is True
    _, created_again = add_source(db, topic, "Feed", "https://example.com/feed")
    assert created_again is False


def test_add_topic_defaults_to_approved(db: Session):
    """The admin/seed path calls add_topic without a status arg - must stay
    approved so existing behavior (Source seeding, admin-curated topics) is
    unaffected by the new-topic-suggestion status gate."""
    topic, _ = add_topic(db, "AI")
    assert topic.status == "approved"


def test_add_topic_accepts_explicit_status(db: Session):
    """The new-topic-suggestion save path passes status='pending' explicitly."""
    topic, _ = add_topic(db, "Quantum Computing", status="pending")
    assert topic.status == "pending"


def test_add_topic_get_or_create_ignores_status_on_repeat_call(db: Session):
    """get-or-create is by exact name only - an existing Topic's status is not
    overwritten by a later call with a different status."""
    topic, _ = add_topic(db, "AI", status="approved")
    again, created = add_topic(db, "AI", status="pending")
    assert created is False
    assert again.id == topic.id
    assert again.status == "approved"


def test_seed_creates_all_defaults_as_approved(db: Session):
    report = seed_default_sources(db)
    assert report.topics_created == len(DEFAULT_SOURCES)
    assert report.sources_created == sum(len(feeds) for feeds in DEFAULT_SOURCES.values())
    for source in db.scalars(select(Source)):
        assert source.status == "approved"
    assert {t.name for t in db.scalars(select(Topic))} == set(DEFAULT_SOURCES)


def test_seed_is_idempotent(db: Session):
    seed_default_sources(db)
    report = seed_default_sources(db)
    assert report.topics_created == 0
    assert report.sources_created == 0


def test_set_source_status_updates_existing_source(db: Session):
    topic, _ = add_topic(db, "AI")
    source, _ = add_source(db, topic, "Feed", "https://example.com/feed")
    assert source.status == "pending"

    updated = set_source_status(db, source.id, "approved")
    assert updated is not None
    assert updated.id == source.id
    assert updated.status == "approved"


def test_set_source_status_returns_none_for_missing_id(db: Session):
    assert set_source_status(db, 999, "approved") is None
