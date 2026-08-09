import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.llm.errors import LLMProviderError
from newsagent.llm.mock import MockLLMProvider
from newsagent.llm.types import ArticleInput, Refusal, SummaryResult, Usage
from newsagent.models import Article, Source, Topic
from newsagent.models.base import Base
from newsagent.pipeline.summarize import (
    SUMMARY_DONE,
    SUMMARY_ERROR,
    SUMMARY_PENDING,
    SUMMARY_REFUSED,
    summarize_relevant_articles,
)

LONG_TEXT = (
    "Researchers announced a new artificial intelligence model today that "
    "outperforms previous systems while using far less compute across tasks."
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        topic = Topic(name="AI")
        session.add(topic)
        session.flush()
        session.add(Source(id=1, topic_id=topic.id, name="Feed", url="feed://ok", status="approved"))
        session.commit()
        yield session


def add_article(
    db: Session,
    *,
    relevance_status: str = "relevant",
    summary_status: str = SUMMARY_PENDING,
    text: str = LONG_TEXT,
    url_suffix: str = "1",
) -> Article:
    article = Article(
        source_id=1,
        title="Some article title",
        url=f"https://example.com/{url_suffix}",
        rss_summary=text,
        relevance_status=relevance_status,
        summary_status=summary_status,
    )
    db.add(article)
    db.commit()
    return article


def test_relevant_article_gets_all_summary_fields(db: Session):
    article = add_article(db)
    report = summarize_relevant_articles(db, MockLLMProvider())
    assert report.summarized == 1
    assert article.summary_status == SUMMARY_DONE
    assert article.summary_he
    assert article.title_he
    assert article.source_language == "en"
    assert article.reading_time_minutes is not None and article.reading_time_minutes >= 1


def test_non_relevant_articles_are_not_summarized(db: Session):
    for i, status in enumerate(["pending", "irrelevant", "refused", "error"]):
        add_article(db, relevance_status=status, url_suffix=f"r{i}")
    report = summarize_relevant_articles(db, MockLLMProvider())
    assert report.summarized == 0


def test_terminal_summary_states_not_rerun(db: Session):
    add_article(db, summary_status=SUMMARY_DONE, url_suffix="a")
    add_article(db, summary_status=SUMMARY_REFUSED, url_suffix="b")
    report = summarize_relevant_articles(db, MockLLMProvider())
    assert report.summarized == 0 and report.refused == 0


def test_error_state_is_retried(db: Session):
    article = add_article(db, summary_status=SUMMARY_ERROR)
    report = summarize_relevant_articles(db, MockLLMProvider())
    assert report.summarized == 1
    assert article.summary_status == SUMMARY_DONE


def test_junk_text_marked_refused(db: Session):
    article = add_article(db, text="tiny")
    report = summarize_relevant_articles(db, MockLLMProvider())
    assert report.refused == 1
    assert article.summary_status == SUMMARY_REFUSED
    assert article.summary_he is None


def test_provider_error_marked_error_and_run_continues(db: Session):
    add_article(db, url_suffix="a")
    provider = MockLLMProvider(fail_transient=10, sleep=lambda _: None)
    report = summarize_relevant_articles(db, provider)
    assert report.errors == 1


class EmptySummaryProvider(MockLLMProvider):
    def _summarize(self, article: ArticleInput) -> SummaryResult | Refusal:
        return SummaryResult(
            summary_he="   ", title_he="t", source_language="en", reading_time_minutes=1
        )


def test_empty_summary_without_refusal_is_an_error(db: Session):
    article = add_article(db)
    report = summarize_relevant_articles(db, EmptySummaryProvider())
    assert report.errors == 1
    assert article.summary_status == SUMMARY_ERROR
    assert article.summary_he is None


def test_usage_is_aggregated(db: Session):
    add_article(db, url_suffix="a")
    add_article(db, url_suffix="b")
    report = summarize_relevant_articles(db, MockLLMProvider())
    assert report.usage_input_units > 0


class BillsThenFailsProvider(MockLLMProvider):
    """Simulates GH #19's actual gap: the provider billed real tokens for this
    call (a valid HTTP 200 with a usage block) but the call still ends in
    LLMProviderError — e.g. GH #38's malformed-output cases. Before this fix
    such a call reported 0 usage, hiding exactly the failures most likely to
    be expensive (see #41's 67k-char runaway)."""

    def _summarize(self, article: ArticleInput) -> SummaryResult | Refusal:
        self._record_usage(Usage(input_units=1200, output_units=340, unit="tokens"))
        raise LLMProviderError("external LLM returned malformed output")


def test_a_billed_but_failed_call_still_counts_toward_usage(db: Session):
    add_article(db)
    report = summarize_relevant_articles(db, BillsThenFailsProvider())
    assert report.errors == 1
    assert (report.usage_input_units, report.usage_output_units) == (1200, 340)
