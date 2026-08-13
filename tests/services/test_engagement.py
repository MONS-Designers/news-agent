from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.models import Article, Digest, DigestLink, Source, Topic, User
from newsagent.models.base import Base
from newsagent.models.digest_link import KIND_ARTICLE, KIND_PREFERENCES
from newsagent.services.engagement import list_digest_engagement


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        topic = Topic(name="AI")
        session.add(topic)
        session.flush()
        session.add(Source(id=1, topic_id=topic.id, name="TechCrunch", url="feed://ok", status="approved"))
        session.add(User(id=1, email="user@example.com"))
        session.commit()
        yield session


def _add_article(db: Session, *, url: str, title: str = "Title") -> Article:
    article = Article(source_id=1, title=title, title_he=title, url=url)
    db.add(article)
    db.flush()
    return article


def test_unsent_digest_is_excluded(db: Session):
    db.add(Digest(user_id=1, date=date(2026, 8, 3)))
    db.commit()
    assert list_digest_engagement(db) == []


def test_sent_digest_with_no_clicks(db: Session):
    digest = Digest(user_id=1, date=date(2026, 8, 3), sent_at=datetime(2026, 8, 3, 8, 0))
    db.add(digest)
    db.commit()

    [row] = list_digest_engagement(db)
    assert row.user_email == "user@example.com"
    assert row.opened_at is None
    assert row.articles_total == 0
    assert row.articles_clicked == 0
    assert row.clicked_article_titles == []
    assert row.preferences_clicked is False


def test_opened_and_clicked_digest(db: Session):
    article = _add_article(db, url="https://example.com/a", title="כותרת")
    digest = Digest(
        user_id=1,
        date=date(2026, 8, 3),
        sent_at=datetime(2026, 8, 3, 8, 0),
        opened_at=datetime(2026, 8, 3, 9, 0),
    )
    db.add(digest)
    db.flush()
    db.add(
        DigestLink(
            digest_id=digest.id,
            kind=KIND_ARTICLE,
            article_id=article.id,
            target_url=article.url,
            clicked_at=datetime(2026, 8, 3, 9, 5),
        )
    )
    db.add(
        DigestLink(
            digest_id=digest.id,
            kind=KIND_PREFERENCES,
            target_url="https://frontend/preferences",
        )
    )
    db.commit()

    [row] = list_digest_engagement(db)
    assert row.opened_at is not None
    assert row.articles_total == 1
    assert row.articles_clicked == 1
    assert row.clicked_article_titles == ["כותרת"]
    assert row.preferences_clicked is False


def test_most_recent_digest_first(db: Session):
    db.add(Digest(user_id=1, date=date(2026, 7, 27), sent_at=datetime(2026, 7, 27, 8, 0)))
    db.add(Digest(user_id=1, date=date(2026, 8, 3), sent_at=datetime(2026, 8, 3, 8, 0)))
    db.commit()

    rows = list_digest_engagement(db)
    assert [row.date for row in rows] == [date(2026, 8, 3), date(2026, 7, 27)]
