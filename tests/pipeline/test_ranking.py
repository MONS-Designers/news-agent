"""Unit tests for the weighted ranking engine (issue #25): score computation
and top-N selection, isolated from build_digests's DB wiring. Covers the I/O
& edge-case matrix from spec-gh-25-weighted-digest-ranking.md.
"""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.models import Digest, DigestArticle, Source, Topic, User
from newsagent.models.article import Article
from newsagent.models.base import Base
from newsagent.pipeline.ranking import score_article, select_top, topic_affinity

TODAY = date(2026, 7, 31)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        topic_a = Topic(id=1, name="AI")
        topic_b = Topic(id=2, name="Space")
        session.add_all([topic_a, topic_b])
        session.add(Source(id=1, topic_id=1, name="AI feed", url="feed://ai", status="approved"))
        session.add(Source(id=2, topic_id=2, name="Space feed", url="feed://sp", status="approved"))
        session.add(User(id=1, email="user@example.com"))
        session.commit()
        yield session


def add_article(
    db: Session,
    *,
    source_id: int = 1,
    url_suffix: str,
    relevance_score: float = 0.9,
    interestingness: float | None = 0.5,
    published_at: datetime | None = None,
    scraped_at: datetime | None = None,
) -> Article:
    kwargs = {}
    if scraped_at is not None:
        kwargs["scraped_at"] = scraped_at
    article = Article(
        source_id=source_id,
        title=f"Article {url_suffix}",
        url=f"https://example.com/{url_suffix}",
        relevance_status="relevant",
        relevance_score=relevance_score,
        interestingness=interestingness,
        summary_status="summarized",
        summary_he="סיכום",
        published_at=published_at,
        **kwargs,
    )
    db.add(article)
    db.commit()
    return article


def test_no_open_history_defaults_to_neutral_and_ranking_completes(db: Session):
    user = db.get(User, 1)
    assert topic_affinity(db, user, TODAY) == {}

    articles = [add_article(db, url_suffix="a")]
    selected = select_top(db, user, articles, TODAY)
    assert len(selected) == 1


def test_fewer_candidates_than_cap_selects_all_no_padding(db: Session):
    user = db.get(User, 1)
    articles = [add_article(db, url_suffix=str(i)) for i in range(3)]
    selected = select_top(db, user, articles, TODAY)
    assert len(selected) == 3
    assert {a.id for a in selected} == {a.id for a in articles}


def test_more_candidates_than_cap_keeps_top_n_by_score(db: Session):
    user = db.get(User, 1)
    now = datetime.now()
    scores = [0.1, 0.9, 0.5, 0.95, 0.3, 0.7, 0.2, 0.8]
    articles = [
        add_article(db, url_suffix=str(i), relevance_score=score, published_at=now)
        for i, score in enumerate(scores)
    ]
    selected = select_top(db, user, articles, TODAY)
    assert len(selected) == settings.digest_max_articles
    assert sorted((a.relevance_score for a in selected), reverse=True) == sorted(
        scores, reverse=True
    )[: settings.digest_max_articles]


def test_missing_published_at_falls_back_to_scraped_at(db: Session):
    reference = datetime(2026, 7, 29, 8, 0, 0)
    with_published = add_article(db, url_suffix="pub", published_at=reference)
    without_published = add_article(
        db, url_suffix="noPub", published_at=None, scraped_at=reference
    )
    now = datetime(2026, 7, 31, 8, 0, 0)
    score_pub = score_article(with_published, now=now, topic_affinities={})
    score_no_pub = score_article(without_published, now=now, topic_affinities={})
    assert score_pub == score_no_pub


def test_missing_interestingness_treated_as_neutral(db: Session):
    fixed_time = datetime(2026, 7, 30, 12, 0, 0)
    with_interest = add_article(
        db, url_suffix="a", interestingness=0.5, published_at=fixed_time
    )
    without_interest = add_article(
        db, url_suffix="b", interestingness=None, published_at=fixed_time
    )
    now = datetime(2026, 7, 31, 8, 0, 0)
    score_with = score_article(with_interest, now=now, topic_affinities={})
    score_without = score_article(without_interest, now=now, topic_affinities={})
    assert score_with == score_without


def test_repeat_opener_bias_ranks_preferred_topic_higher(db: Session):
    user = db.get(User, 1)

    # 5 past sent digests containing Topic A (source_id=1), all opened.
    for i in range(5):
        digest = Digest(
            user_id=1,
            date=date(2026, 7, 1) + timedelta(days=i),
            sent_at=datetime(2026, 7, 1),
            opened_at=datetime(2026, 7, 1),
        )
        db.add(digest)
        db.flush()
        article = add_article(db, source_id=1, url_suffix=f"histA{i}")
        db.add(DigestArticle(digest_id=digest.id, article_id=article.id))
    db.commit()

    # 5 past sent digests containing Topic B (source_id=2), none opened.
    for i in range(5):
        digest = Digest(
            user_id=1,
            date=date(2026, 6, 1) + timedelta(days=i),
            sent_at=datetime(2026, 6, 1),
            opened_at=None,
        )
        db.add(digest)
        db.flush()
        article = add_article(db, source_id=2, url_suffix=f"histB{i}")
        db.add(DigestArticle(digest_id=digest.id, article_id=article.id))
    db.commit()

    affinities = topic_affinity(db, user, TODAY)
    assert affinities[1] == 1.0  # Topic A: opened 5/5
    assert affinities[2] == 0.0  # Topic B: opened 0/5

    candidate_a = add_article(db, source_id=1, url_suffix="candA")
    candidate_b = add_article(db, source_id=2, url_suffix="candB")
    selected = select_top(db, user, [candidate_b, candidate_a], TODAY)
    assert selected[0].id == candidate_a.id


def test_diversity_floor_guarantees_low_volume_topic_a_slot(db: Session):
    """Without the floor, Topic A's 10 higher-scoring candidates alone would
    fill every slot in the default digest_max_articles=7 cap, leaving Topic
    B's subscriber with nothing from that topic - GH #37."""
    user = db.get(User, 1)
    topic_a_articles = [
        add_article(db, source_id=1, url_suffix=f"a{i}", relevance_score=0.9) for i in range(10)
    ]
    topic_b_article = add_article(db, source_id=2, url_suffix="b0", relevance_score=0.1)

    selected = select_top(db, user, [*topic_a_articles, topic_b_article], TODAY)

    assert len(selected) == settings.digest_max_articles
    assert topic_b_article.id in {a.id for a in selected}


def test_diversity_floor_ranks_guaranteed_slots_by_each_topics_best_score(db: Session):
    """N (3 topics) > L (2 slots): the guaranteed slots go to the two topics
    whose single best candidate scores highest - not to the two
    highest-scoring candidates overall, which could both come from one topic."""
    user = db.get(User, 1)
    topic_c = Topic(id=3, name="Climate")
    db.add(topic_c)
    db.add(Source(id=3, topic_id=3, name="Climate feed", url="feed://cl", status="approved"))
    db.commit()

    best_a = add_article(db, source_id=1, url_suffix="a-best", relevance_score=0.9)
    best_b = add_article(db, source_id=2, url_suffix="b-best", relevance_score=0.7)
    best_c = add_article(db, source_id=3, url_suffix="c-best", relevance_score=0.3)

    selected = select_top(db, user, [best_a, best_b, best_c], TODAY, limit=2)

    assert {a.id for a in selected} == {best_a.id, best_b.id}


def test_zero_candidate_topic_wastes_no_slot(db: Session):
    """A user subscribed to Topic B who simply has no eligible Topic B
    candidate this run gets Topic A's candidates filling every slot, not an
    empty/wasted slot reserved for a topic with nothing to show."""
    user = db.get(User, 1)
    topic_a_articles = [
        add_article(db, source_id=1, url_suffix=f"a{i}", relevance_score=0.9) for i in range(3)
    ]

    selected = select_top(db, user, topic_a_articles, TODAY, limit=5)

    assert len(selected) == 3


def test_diversity_floor_skips_already_represented_topics_on_rerun(db: Session):
    """A same-day rerun where Topic A already has an attached article: Topic
    A's higher-scoring candidate must NOT take the single remaining guaranteed
    slot over Topic B, which has none yet - the floor isn't recomputed from
    zero (GH #37 AC4)."""
    user = db.get(User, 1)
    candidate_a = add_article(db, source_id=1, url_suffix="a0", relevance_score=0.9)
    candidate_b = add_article(db, source_id=2, url_suffix="b0", relevance_score=0.3)

    fresh_run = select_top(db, user, [candidate_a, candidate_b], TODAY, limit=1)
    assert fresh_run[0].id == candidate_a.id  # no prior attachment: Topic A wins on score

    rerun = select_top(
        db,
        user,
        [candidate_a, candidate_b],
        TODAY,
        limit=1,
        already_represented_topic_ids={1},  # Topic A already attached earlier today
    )
    assert rerun[0].id == candidate_b.id  # Topic A's floor is already satisfied
