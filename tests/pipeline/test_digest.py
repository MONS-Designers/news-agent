from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.llm.mock import MockLLMProvider
from newsagent.models import Article, Digest, DigestArticle, Source, Topic, User, UserTopicPreference
from newsagent.models.base import Base
from newsagent.pipeline.digest import build_digests

TODAY = date(2026, 7, 20)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ai = Topic(id=1, name="AI")
        space = Topic(id=2, name="Space")
        session.add_all([ai, space])
        session.add(Source(id=1, topic_id=1, name="AI feed", url="feed://ai", status="approved"))
        session.add(Source(id=2, topic_id=2, name="Space feed", url="feed://sp", status="approved"))
        session.add(User(id=1, email="user@example.com"))
        session.add(UserTopicPreference(user_id=1, topic_id=1))  # subscribed to AI only
        session.commit()
        yield session


def add_article(db: Session, *, source_id: int, summary_status: str = "summarized", url_suffix: str = "1") -> Article:
    article = Article(
        source_id=source_id,
        title=f"Article {url_suffix}",
        url=f"https://example.com/{url_suffix}",
        relevance_status="relevant",
        summary_status=summary_status,
        summary_he="סיכום",
    )
    db.add(article)
    db.commit()
    return article


def test_digest_contains_only_subscribed_topics(db: Session):
    ai_article = add_article(db, source_id=1, url_suffix="ai")
    add_article(db, source_id=2, url_suffix="space")  # not subscribed
    report = build_digests(db, MockLLMProvider(), for_date=TODAY)
    assert report.digests_created == 1
    assert report.articles_added == 1
    entry = db.scalar(select(DigestArticle))
    assert entry is not None and entry.article_id == ai_article.id


def test_build_composes_digest_voice(db: Session):
    add_article(db, source_id=1, url_suffix="ai")
    build_digests(db, MockLLMProvider(), for_date=TODAY)
    digest = db.scalar(select(Digest))
    assert digest is not None
    assert digest.intro_he
    assert digest.dad_joke_he


def test_only_summarized_articles_enter(db: Session):
    add_article(db, source_id=1, summary_status="pending", url_suffix="a")
    add_article(db, source_id=1, summary_status="refused", url_suffix="b")
    report = build_digests(db, MockLLMProvider(), for_date=TODAY)
    assert report.digests_created == 0
    assert report.articles_added == 0


def test_no_empty_digest_created(db: Session):
    report = build_digests(db, MockLLMProvider(), for_date=TODAY)
    assert report.digests_created == 0
    assert db.scalar(select(Digest)) is None


def test_delivered_articles_never_repeat(db: Session):
    add_article(db, source_id=1, url_suffix="a")
    build_digests(db, MockLLMProvider(), for_date=TODAY)
    report = build_digests(db, MockLLMProvider(), for_date=date(2026, 7, 21))
    assert report.digests_created == 0
    assert report.articles_added == 0


def test_same_day_rerun_appends_to_existing_digest(db: Session):
    add_article(db, source_id=1, url_suffix="a")
    build_digests(db, MockLLMProvider(), for_date=TODAY)
    add_article(db, source_id=1, url_suffix="b")
    report = build_digests(db, MockLLMProvider(), for_date=TODAY)
    assert report.digests_created == 0  # reused today's digest
    assert report.articles_added == 1
    digests = list(db.scalars(select(Digest)))
    assert len(digests) == 1
    assert len(digests[0].articles) == 2


def test_two_users_get_independent_digests(db: Session):
    db.add(User(id=2, email="other@example.com"))
    db.add(UserTopicPreference(user_id=2, topic_id=1))
    db.commit()
    add_article(db, source_id=1, url_suffix="a")
    report = build_digests(db, MockLLMProvider(), for_date=TODAY)
    assert report.digests_created == 2
    assert report.articles_added == 2
