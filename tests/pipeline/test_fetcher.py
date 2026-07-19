import time
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.models import Article, Source, Topic
from newsagent.models.base import Base
from newsagent.pipeline.fetcher import fetch_approved_sources, fetch_source


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        topic = Topic(name="AI")
        session.add(topic)
        session.flush()
        session.add(Source(topic_id=topic.id, name="Approved feed", url="feed://ok", status="approved"))
        session.add(Source(topic_id=topic.id, name="Pending feed", url="feed://pending", status="pending"))
        session.commit()
        yield session


class FakeFeed(dict):
    """Mimics feedparser's result: dict access plus .entries attribute."""

    @property
    def entries(self) -> list[dict[str, Any]]:
        return self.get("entries", [])


def make_parse(feeds: dict[str, Any]):
    def parse(url: str) -> Any:
        value = feeds[url]
        if isinstance(value, Exception):
            raise value
        return value

    return parse


ENTRY = {
    "link": "https://example.com/article-1",
    "title": "New AI model released",
    "published_parsed": time.struct_time((2026, 7, 19, 12, 0, 0, 0, 200, 0)),
}


def approved(db: Session) -> Source:
    source = db.scalar(select(Source).where(Source.status == "approved"))
    assert source is not None
    return source


def test_fetch_inserts_new_articles_with_fields(db: Session):
    parse = make_parse({"feed://ok": FakeFeed(entries=[ENTRY])})
    result = fetch_source(db, approved(db), parse)
    assert result.new_articles == 1
    article = db.scalar(select(Article))
    assert article is not None
    assert article.title == "New AI model released"
    assert article.url == "https://example.com/article-1"
    assert article.published_at is not None
    assert article.published_at.year == 2026


def test_fetch_dedupes_by_url(db: Session):
    parse = make_parse({"feed://ok": FakeFeed(entries=[ENTRY, dict(ENTRY)])})
    result = fetch_source(db, approved(db), parse)
    assert result.new_articles == 1
    assert result.duplicates == 1
    # second run: everything already known
    result = fetch_source(db, approved(db), parse)
    assert result.new_articles == 0
    assert result.duplicates == 2


def test_broken_feed_is_skipped_not_raised(db: Session):
    parse = make_parse({"feed://ok": ConnectionError("dns failure")})
    result = fetch_source(db, approved(db), parse)
    assert result.error is not None
    assert result.new_articles == 0


def test_only_approved_sources_are_fetched(db: Session):
    calls: list[str] = []

    def parse(url: str) -> Any:
        calls.append(url)
        return FakeFeed(entries=[])

    fetch_approved_sources(db, parse)
    assert calls == ["feed://ok"]


def test_entry_without_link_or_title_is_ignored(db: Session):
    parse = make_parse({"feed://ok": FakeFeed(entries=[{"title": "no link"}, {"link": "https://x"}])})
    result = fetch_source(db, approved(db), parse)
    assert result.new_articles == 0
    assert db.scalar(select(Article)) is None
