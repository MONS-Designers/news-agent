import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.llm.mock import MockLLMProvider
from newsagent.llm.types import ArticleInput, Refusal, SummaryResult
from newsagent.models import Article, Source, Topic, User, UserTopicPreference
from newsagent.models.base import Base
from newsagent.pipeline.summarize import (
    SUMMARY_DONE,
    SUMMARY_ERROR,
    SUMMARY_FAILED,
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
        user = User(email="user@example.com")
        session.add(user)
        session.flush()
        session.add(UserTopicPreference(user_id=user.id, topic_id=topic.id))
        session.commit()
        yield session


def add_article(
    db: Session,
    *,
    source_id: int = 1,
    relevance_status: str = "relevant",
    summary_status: str = SUMMARY_PENDING,
    text: str = LONG_TEXT,
    url_suffix: str = "1",
    summarize_attempts: int = 0,
) -> Article:
    article = Article(
        source_id=source_id,
        title="Some article title",
        url=f"https://example.com/{url_suffix}",
        rss_summary=text,
        relevance_status=relevance_status,
        summary_status=summary_status,
        summarize_attempts=summarize_attempts,
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


def test_run_id_is_populated_on_the_report(db: Session):
    add_article(db)
    report = summarize_relevant_articles(db, MockLLMProvider())
    assert report.run_id is not None


def test_failure_increments_attempts_and_stays_error_below_max(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "max_summarize_attempts", 3)
    article = add_article(db)
    report = summarize_relevant_articles(db, MockLLMProvider(fail_permanent=True))
    assert report.errors == 1
    assert article.summarize_attempts == 1
    assert article.summary_status == SUMMARY_ERROR


def test_terminal_failed_state_reached_at_configured_max(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "max_summarize_attempts", 2)
    article = add_article(db)
    provider = MockLLMProvider(fail_permanent=True)

    summarize_relevant_articles(db, provider)
    assert article.summary_status == SUMMARY_ERROR  # 1st failure: still retried

    summarize_relevant_articles(db, provider)
    assert article.summarize_attempts == 2
    assert article.summary_status == SUMMARY_FAILED  # 2nd failure: terminal


def test_failed_articles_are_never_reselected_or_billed(db: Session):
    add_article(db, summary_status=SUMMARY_FAILED, summarize_attempts=3)
    report = summarize_relevant_articles(db, MockLLMProvider(fail_permanent=True))
    assert report.summarized == 0
    assert report.errors == 0


def test_success_after_prior_failures_still_reaches_done(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "max_summarize_attempts", 3)
    article = add_article(db, summary_status=SUMMARY_ERROR, summarize_attempts=2)
    report = summarize_relevant_articles(db, MockLLMProvider())
    assert report.summarized == 1
    assert article.summary_status == SUMMARY_DONE


def test_empty_summary_also_counts_toward_terminal_state(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    """The empty-summary-without-refusal branch is a provider bug indistinguishable
    from a deterministic LLMError from the retry-bound's point of view - it must
    count toward the same terminal state, or a provider that always returns an
    empty string would retry an article forever."""
    monkeypatch.setattr(settings, "max_summarize_attempts", 1)
    article = add_article(db)
    report = summarize_relevant_articles(db, EmptySummaryProvider())
    assert report.errors == 1
    assert article.summarize_attempts == 1
    assert article.summary_status == SUMMARY_FAILED


def test_articles_with_no_subscribed_topic_are_skipped(db: Session):
    """GH #45: summarizing is the paid LLM stage - skipping it for a topic
    nobody subscribes to is where the waste this issue names matters most."""
    unsubscribed_topic = Topic(name="Space")
    db.add(unsubscribed_topic)
    db.flush()
    db.add(
        Source(id=2, topic_id=unsubscribed_topic.id, name="No subscribers", url="feed://sp", status="approved")
    )
    db.commit()
    article = add_article(db, source_id=2, url_suffix="unsub")

    report = summarize_relevant_articles(db, MockLLMProvider())

    assert report.summarized == 0
    assert article.summary_status == SUMMARY_PENDING


# --- Cost: article writing is paid once, globally --------------------------


class CountingSummarizer(MockLLMProvider):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def summarize(self, article: ArticleInput):
        self.calls += 1
        return super().summarize(article)


def test_an_article_is_never_summarized_twice(db: Session):
    """Hebrew text is stored on the Article row, so the paid call happens once
    for the article - not once per reader who receives it."""
    add_article(db)
    provider = CountingSummarizer()

    summarize_relevant_articles(db, provider)
    assert provider.calls == 1

    summarize_relevant_articles(db, provider)
    assert provider.calls == 1


def test_extra_readers_on_the_same_topic_cost_nothing_extra(db: Session):
    """The case worth protecting: ten beta readers on one topic must not mean
    ten translations of the same story."""
    add_article(db)
    provider = CountingSummarizer()
    summarize_relevant_articles(db, provider)

    for user_id in range(2, 12):
        db.add(User(id=user_id, email=f"u{user_id}@example.com"))
        db.flush()
        db.add(UserTopicPreference(user_id=user_id, topic_id=1))
    db.commit()

    summarize_relevant_articles(db, provider)

    assert provider.calls == 1
