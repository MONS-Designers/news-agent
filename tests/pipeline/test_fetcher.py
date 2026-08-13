import time
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.models import Article, Source, Topic, User, UserTopicPreference
from newsagent.models.base import Base
from newsagent.pipeline.fetcher import extract_image_url, fetch_approved_sources, fetch_source


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
        user = User(email="user@example.com")
        session.add(user)
        session.flush()
        session.add(UserTopicPreference(user_id=user.id, topic_id=topic.id))
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
    "summary": "A short RSS description of the article.",
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
    assert article.rss_summary == "A short RSS description of the article."
    assert article.relevance_status == "pending"


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


def test_sources_with_no_subscribed_topic_are_skipped(db: Session):
    """GH #45: fetching a source nobody subscribes to is pure waste - the
    approved-but-unsubscribed source must never even be polled."""
    unsubscribed_topic = Topic(name="Space")
    db.add(unsubscribed_topic)
    db.flush()
    db.add(
        Source(
            topic_id=unsubscribed_topic.id,
            name="No subscribers",
            url="feed://nobody",
            status="approved",
        )
    )
    db.commit()

    calls: list[str] = []

    def parse(url: str) -> Any:
        calls.append(url)
        return FakeFeed(entries=[])

    fetch_approved_sources(db, parse)
    assert calls == ["feed://ok"]
    assert "feed://nobody" not in calls


def test_entry_without_link_or_title_is_ignored(db: Session):
    parse = make_parse({"feed://ok": FakeFeed(entries=[{"title": "no link"}, {"link": "https://x"}])})
    result = fetch_source(db, approved(db), parse)
    assert result.new_articles == 0
    assert db.scalar(select(Article)) is None


# --- Image extraction (issue #24) -----------------------------------------


def test_extract_image_prefers_media_content():
    entry = {
        "media_content": [{"url": "https://img/content.jpg"}],
        "media_thumbnail": [{"url": "https://img/thumb.jpg"}],
    }
    assert extract_image_url(entry) == "https://img/content.jpg"


def test_extract_image_falls_back_to_thumbnail():
    entry = {"media_thumbnail": [{"url": "https://img/thumb.jpg"}]}
    assert extract_image_url(entry) == "https://img/thumb.jpg"


def test_extract_image_falls_back_to_image_enclosure():
    entry = {"enclosures": [{"href": "https://img/enc.png", "type": "image/png"}]}
    assert extract_image_url(entry) == "https://img/enc.png"


def test_extract_image_ignores_non_image_enclosure():
    # A podcast audio / PDF enclosure must not be mistaken for a lead image.
    entry = {"enclosures": [{"href": "https://cdn/ep.mp3", "type": "audio/mpeg"}]}
    assert extract_image_url(entry) is None


def test_extract_image_skips_media_entries_without_url():
    entry = {"media_content": [{"medium": "image"}, {"url": "https://img/second.jpg"}]}
    assert extract_image_url(entry) == "https://img/second.jpg"


def test_extract_image_returns_none_when_absent():
    assert extract_image_url({"title": "no media at all"}) is None


def test_fetch_persists_extracted_image_url(db: Session):
    entry = dict(ENTRY, media_content=[{"url": "https://img/lead.jpg"}])
    parse = make_parse({"feed://ok": FakeFeed(entries=[entry])})
    fetch_source(db, approved(db), parse)
    article = db.scalar(select(Article))
    assert article is not None
    assert article.image_url == "https://img/lead.jpg"


def test_fetch_leaves_image_url_null_when_feed_has_no_image(db: Session):
    parse = make_parse({"feed://ok": FakeFeed(entries=[ENTRY])})
    fetch_source(db, approved(db), parse)
    article = db.scalar(select(Article))
    assert article is not None
    assert article.image_url is None
