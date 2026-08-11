import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.llm.errors import LLMProviderError
from newsagent.llm.mock import MockLLMProvider
from newsagent.llm.types import ArticleInput, Refusal, RelevanceScore, Usage
from newsagent.models import Article, Source, Topic
from newsagent.models.base import Base
from newsagent.pipeline.relevance import (
    STATUS_ERROR,
    STATUS_IRRELEVANT,
    STATUS_PENDING,
    STATUS_REFUSED,
    STATUS_RELEVANT,
    filter_pending_articles,
)

ON_TOPIC_SUMMARY = (
    "A deep look at artificial intelligence research: new artificial "
    "intelligence models show intelligence gains across benchmarks."
)
OFF_TOPIC_SUMMARY = (
    "The championship final was decided on penalties after a goalless draw "
    "that kept fans on their feet all night long."
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        topic = Topic(name="artificial intelligence")
        session.add(topic)
        session.flush()
        session.add(
            Source(id=1, topic_id=topic.id, name="Approved", url="feed://ok", status="approved")
        )
        session.add(
            Source(id=2, topic_id=topic.id, name="Rejected", url="feed://bad", status="rejected")
        )
        session.commit()
        yield session


def add_article(db: Session, *, source_id: int = 1, status: str = STATUS_PENDING, summary: str | None = ON_TOPIC_SUMMARY, url_suffix: str = "1") -> Article:
    article = Article(
        source_id=source_id,
        title="Some article title",
        url=f"https://example.com/{url_suffix}",
        rss_summary=summary,
        relevance_status=status,
    )
    db.add(article)
    db.commit()
    return article


def test_on_topic_article_marked_relevant_with_score(db: Session):
    article = add_article(db)
    report = filter_pending_articles(db, MockLLMProvider())
    assert report.relevant == 1
    assert article.relevance_status == STATUS_RELEVANT
    assert article.relevance_score is not None
    assert article.relevance_score >= 0.7


def test_off_topic_article_marked_irrelevant(db: Session):
    article = add_article(db, summary=OFF_TOPIC_SUMMARY)
    report = filter_pending_articles(db, MockLLMProvider())
    assert report.irrelevant == 1
    assert article.relevance_status == STATUS_IRRELEVANT


def test_junk_article_marked_refused_without_score(db: Session):
    article = add_article(db, summary="tiny")
    report = filter_pending_articles(db, MockLLMProvider())
    assert report.refused == 1
    assert article.relevance_status == STATUS_REFUSED
    assert article.relevance_score is None


def test_terminal_states_are_never_rescored(db: Session):
    add_article(db, status=STATUS_RELEVANT, url_suffix="a")
    add_article(db, status=STATUS_IRRELEVANT, url_suffix="b")
    add_article(db, status=STATUS_REFUSED, url_suffix="c")
    report = filter_pending_articles(db, MockLLMProvider())
    assert report.scored == 0 and report.refused == 0


def test_error_state_is_retried_next_run(db: Session):
    article = add_article(db, status=STATUS_ERROR)
    report = filter_pending_articles(db, MockLLMProvider())
    assert report.relevant == 1
    assert article.relevance_status == STATUS_RELEVANT


def test_provider_error_marks_error_and_run_continues(db: Session):
    add_article(db, url_suffix="a")
    add_article(db, url_suffix="b")
    provider = MockLLMProvider(fail_transient=10, sleep=lambda _: None)
    report = filter_pending_articles(db, provider)
    assert report.errors >= 1
    statuses = {a.relevance_status for a in db.scalars(select(Article))}
    assert STATUS_ERROR in statuses


def test_articles_from_unapproved_sources_are_skipped(db: Session):
    article = add_article(db, source_id=2)
    report = filter_pending_articles(db, MockLLMProvider())
    assert report.scored == 0
    assert article.relevance_status == STATUS_PENDING


def test_threshold_comes_from_argument(db: Session):
    article = add_article(db, summary=OFF_TOPIC_SUMMARY)
    filter_pending_articles(db, MockLLMProvider(), threshold=0.0)
    assert article.relevance_status == STATUS_RELEVANT


def test_usage_is_aggregated(db: Session):
    add_article(db, url_suffix="a")
    add_article(db, url_suffix="b")
    report = filter_pending_articles(db, MockLLMProvider())
    assert report.usage_input_units > 0


class BillsThenFailsProvider(MockLLMProvider):
    """GH #19: a call that billed tokens (valid HTTP 200 + usage block) but
    still ends in LLMProviderError — e.g. GH #38's malformed-output cases —
    used to report 0 usage, hiding exactly the failures likely to run up cost."""

    def _score_relevance(
        self, article: ArticleInput, topic: str, preference_history
    ) -> RelevanceScore | Refusal:
        self._record_usage(Usage(input_units=900, output_units=12, unit="tokens"))
        raise LLMProviderError("external LLM returned malformed output")


def test_a_billed_but_failed_call_still_counts_toward_usage(db: Session):
    add_article(db)
    report = filter_pending_articles(db, BillsThenFailsProvider())
    assert report.errors == 1
    assert (report.usage_input_units, report.usage_output_units) == (900, 12)
