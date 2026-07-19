import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.models import Source, Topic
from newsagent.models.base import Base
from newsagent.services.sources import DEFAULT_SOURCES, add_source, add_topic, seed_default_sources


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
