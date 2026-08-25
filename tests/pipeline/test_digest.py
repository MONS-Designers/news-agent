from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.llm.mock import MockLLMProvider
from newsagent.models import Article, Digest, DigestArticle, Source, Topic, User, UserTopicPreference
from newsagent.models.base import Base
from newsagent.pipeline.digest import VOICE_REUSE_DAYS, build_digests

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


def add_article(
    db: Session,
    *,
    source_id: int,
    summary_status: str = "summarized",
    url_suffix: str = "1",
    relevance_score: float = 0.9,
    interestingness: float | None = 0.5,
) -> Article:
    article = Article(
        source_id=source_id,
        title=f"Article {url_suffix}",
        url=f"https://example.com/{url_suffix}",
        relevance_status="relevant",
        relevance_score=relevance_score,
        interestingness=interestingness,
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


def test_unsubscribed_user_gets_no_digest(db: Session):
    """GH #46: an unsubscribed user's digest isn't even built, not just held
    back at send time."""
    user = db.get(User, 1)
    user.unsubscribed_at = datetime.now()
    db.commit()
    add_article(db, source_id=1, url_suffix="a")

    report = build_digests(db, MockLLMProvider(), for_date=TODAY)

    assert report.users_processed == 0
    assert report.digests_created == 0
    assert db.scalar(select(Digest)) is None


def test_two_users_get_independent_digests(db: Session):
    db.add(User(id=2, email="other@example.com"))
    db.add(UserTopicPreference(user_id=2, topic_id=1))
    db.commit()
    add_article(db, source_id=1, url_suffix="a")
    report = build_digests(db, MockLLMProvider(), for_date=TODAY)
    assert report.digests_created == 2
    assert report.articles_added == 2


def test_same_day_rerun_never_exceeds_cap(db: Session):
    """A same-day rerun tops up today's digest with newly-summarized articles
    (per test_same_day_rerun_appends_to_existing_digest), but the digest's
    total must still never exceed digest_max_articles (GH #25 review finding:
    select_top previously capped only the current call, not the cumulative
    per-digest total)."""
    [add_article(db, source_id=1, url_suffix=f"first{i}") for i in range(settings.digest_max_articles)]
    build_digests(db, MockLLMProvider(), for_date=TODAY)
    add_article(db, source_id=1, url_suffix="late1")
    add_article(db, source_id=1, url_suffix="late2")
    report = build_digests(db, MockLLMProvider(), for_date=TODAY)
    assert report.articles_added == 0  # no remaining slots this run

    digests = list(db.scalars(select(Digest)))
    assert len(digests) == 1
    assert len(digests[0].articles) == settings.digest_max_articles


def test_cap_selects_top_n_and_leaves_rest_undelivered(db: Session):
    """8 undelivered candidates, cap = digest_max_articles (7 by default):
    exactly the cap gets attached this run, and the leftover stay undelivered
    for a future run (GH #25)."""
    articles = [add_article(db, source_id=1, url_suffix=str(i)) for i in range(8)]
    report = build_digests(db, MockLLMProvider(), for_date=TODAY)
    assert report.articles_added == settings.digest_max_articles

    digest = db.scalar(select(Digest))
    assert digest is not None
    assert len(digest.articles) == settings.digest_max_articles

    attached_ids = {entry.article_id for entry in digest.articles}
    leftover_ids = {a.id for a in articles} - attached_ids
    assert len(leftover_ids) == len(articles) - settings.digest_max_articles

    # Leftover candidates weren't dropped - they're still eligible next run.
    report2 = build_digests(db, MockLLMProvider(), for_date=date(2026, 7, 21))
    assert report2.articles_added == len(leftover_ids)


# --- Editorial voice reuse -------------------------------------------------


class CountingProvider(MockLLMProvider):
    """Counts voice compositions, which are the only LLM call a build makes."""

    def __init__(self) -> None:
        super().__init__()
        self.voice_calls = 0

    def compose_digest_voice(self, headlines):
        self.voice_calls += 1
        return super().compose_digest_voice(headlines)


def _newcomer(db: Session, user_id: int) -> None:
    db.add(User(id=user_id, email=f"u{user_id}@example.com"))
    db.flush()
    db.add(UserTopicPreference(user_id=user_id, topic_id=1))
    db.commit()


def test_a_new_signup_reuses_a_recent_voice_instead_of_paying_for_one(db: Session):
    """The case this exists for: someone joins, picks the same topics as an
    existing reader, and lands on an identical top-N because a brand-new user
    has neutral topic affinity. Writing that intro again is pure waste."""
    add_article(db, source_id=1, url_suffix="a")
    provider = CountingProvider()
    build_digests(db, provider, TODAY)
    assert provider.voice_calls == 1

    _newcomer(db, 2)
    build_digests(db, provider, TODAY)

    assert provider.voice_calls == 1  # no second call
    first, second = db.scalars(select(Digest).order_by(Digest.id)).all()
    assert second.intro_he == first.intro_he
    assert second.dad_joke_he == first.dad_joke_he


def test_a_different_article_set_still_composes_its_own_voice(db: Session):
    """The voice is written from the headlines, so borrowing it across
    different articles would open a digest by naming stories it doesn't have."""
    add_article(db, source_id=1, url_suffix="a")
    provider = CountingProvider()
    build_digests(db, provider, TODAY)

    # Newcomer subscribes to Space instead, so their articles differ.
    db.add(User(id=2, email="u2@example.com"))
    db.flush()
    db.add(UserTopicPreference(user_id=2, topic_id=2))
    add_article(db, source_id=2, url_suffix="b")
    db.commit()
    build_digests(db, provider, TODAY)

    assert provider.voice_calls == 2


def test_a_voice_older_than_the_window_is_not_reused(db: Session):
    """A voice describes a moment in the news - past the window it would frame
    a digest around stories that have since moved on."""
    add_article(db, source_id=1, url_suffix="a")
    provider = CountingProvider()
    build_digests(db, provider, TODAY)

    _newcomer(db, 2)
    build_digests(db, provider, TODAY + timedelta(days=VOICE_REUSE_DAYS + 1))

    assert provider.voice_calls == 2
