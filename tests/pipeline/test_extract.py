import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.models import Article, Source, Topic
from newsagent.models.base import Base
from newsagent.pipeline.extract import (
    EXTRACTION_DONE,
    EXTRACTION_FAILED,
    EXTRACTION_PENDING,
    extract_relevant_articles,
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
    extraction_status: str = EXTRACTION_PENDING,
    extraction_attempts: int = 0,
    url_suffix: str = "1",
) -> Article:
    article = Article(
        source_id=1,
        title="Headline",
        url=f"https://example.com/{url_suffix}",
        rss_summary="A short snippet.",
        relevance_status=relevance_status,
        extraction_status=extraction_status,
        extraction_attempts=extraction_attempts,
    )
    db.add(article)
    db.commit()
    return article


def _mock_success(monkeypatch: pytest.MonkeyPatch, text: str = "The full article body." * 10):
    monkeypatch.setattr(
        "newsagent.pipeline.extract.trafilatura.fetch_url", lambda url: "<html>...</html>"
    )
    monkeypatch.setattr("newsagent.pipeline.extract.trafilatura.extract", lambda html: text)


def _mock_fetch_failure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("newsagent.pipeline.extract.trafilatura.fetch_url", lambda url: None)


def _mock_extract_failure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "newsagent.pipeline.extract.trafilatura.fetch_url", lambda url: "<html>...</html>"
    )
    monkeypatch.setattr("newsagent.pipeline.extract.trafilatura.extract", lambda html: None)


def test_successful_extraction_stores_full_text_and_marks_done(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    _mock_success(monkeypatch, text="Real article content.")
    article = add_article(db)

    report = extract_relevant_articles(db)

    assert report.extracted == 1
    assert report.failed == 0
    assert article.full_text == "Real article content."
    assert article.extraction_status == EXTRACTION_DONE


def test_fetch_failure_increments_attempts_and_stays_pending_below_cap(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "max_extraction_attempts", 2)
    _mock_fetch_failure(monkeypatch)
    article = add_article(db)

    report = extract_relevant_articles(db)

    assert report.failed == 1
    assert article.extraction_attempts == 1
    assert article.extraction_status == EXTRACTION_PENDING
    assert article.full_text is None


def test_terminal_failed_state_reached_at_configured_max(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "max_extraction_attempts", 2)
    _mock_fetch_failure(monkeypatch)
    article = add_article(db)

    extract_relevant_articles(db)
    assert article.extraction_status == EXTRACTION_PENDING  # 1st failure: still retried

    extract_relevant_articles(db)
    assert article.extraction_attempts == 2
    assert article.extraction_status == EXTRACTION_FAILED  # 2nd failure: terminal


def test_failed_articles_are_never_reselected(db: Session, monkeypatch: pytest.MonkeyPatch):
    _mock_success(monkeypatch)
    add_article(db, extraction_status=EXTRACTION_FAILED, extraction_attempts=2)

    report = extract_relevant_articles(db)

    assert report.extracted == 0
    assert report.failed == 0


def test_irrelevant_articles_are_not_selected(db: Session, monkeypatch: pytest.MonkeyPatch):
    _mock_success(monkeypatch)
    add_article(db, relevance_status="irrelevant")

    report = extract_relevant_articles(db)

    assert report.extracted == 0
    assert report.failed == 0


def test_empty_extraction_result_counts_as_failure(db: Session, monkeypatch: pytest.MonkeyPatch):
    """extract() returning None is a parse failure, not "no article" — must count
    toward the same bounded-retry terminal state as a fetch failure."""
    monkeypatch.setattr(settings, "max_extraction_attempts", 1)
    _mock_extract_failure(monkeypatch)
    article = add_article(db)

    report = extract_relevant_articles(db)

    assert report.failed == 1
    assert article.extraction_status == EXTRACTION_FAILED
    assert article.full_text is None


def test_extracted_text_is_truncated_to_configured_cap(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "extraction_max_chars", 20)
    _mock_success(monkeypatch, text="x" * 100)
    article = add_article(db)

    extract_relevant_articles(db)

    assert article.full_text == "x" * 20
