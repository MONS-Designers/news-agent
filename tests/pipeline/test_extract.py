import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.models import Article, Source, Topic, User, UserTopicPreference
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
    extraction_status: str = EXTRACTION_PENDING,
    extraction_attempts: int = 0,
    url_suffix: str = "1",
) -> Article:
    article = Article(
        source_id=source_id,
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


def _mock_fetch_success(monkeypatch: pytest.MonkeyPatch, html: str = "<html>...</html>"):
    monkeypatch.setattr("newsagent.pipeline.extract._fetch_html", lambda url: html)


def _mock_fetch_failure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("newsagent.pipeline.extract._fetch_html", lambda url: None)


def _mock_extract_text(monkeypatch: pytest.MonkeyPatch, text: str | None):
    monkeypatch.setattr("newsagent.pipeline.extract.trafilatura.extract", lambda html: text)


def test_successful_extraction_stores_full_text_and_marks_done(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    _mock_fetch_success(monkeypatch)
    _mock_extract_text(monkeypatch, "Real article content.")
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
    _mock_fetch_success(monkeypatch)
    _mock_extract_text(monkeypatch, "content")
    add_article(db, extraction_status=EXTRACTION_FAILED, extraction_attempts=2)

    report = extract_relevant_articles(db)

    assert report.extracted == 0
    assert report.failed == 0


def test_irrelevant_articles_are_not_selected(db: Session, monkeypatch: pytest.MonkeyPatch):
    _mock_fetch_success(monkeypatch)
    _mock_extract_text(monkeypatch, "content")
    add_article(db, relevance_status="irrelevant")

    report = extract_relevant_articles(db)

    assert report.extracted == 0
    assert report.failed == 0


def test_articles_with_no_subscribed_topic_are_skipped(db: Session, monkeypatch: pytest.MonkeyPatch):
    """GH #45: fetching + parsing full text for a topic nobody subscribes to
    is wasted network and CPU cost."""
    _mock_fetch_success(monkeypatch)
    _mock_extract_text(monkeypatch, "content")
    unsubscribed_topic = Topic(name="Space")
    db.add(unsubscribed_topic)
    db.flush()
    db.add(
        Source(id=2, topic_id=unsubscribed_topic.id, name="No subscribers", url="feed://sp", status="approved")
    )
    db.commit()
    add_article(db, source_id=2, url_suffix="unsub")

    report = extract_relevant_articles(db)

    assert report.extracted == 0
    assert report.failed == 0


def test_empty_extraction_result_counts_as_failure(db: Session, monkeypatch: pytest.MonkeyPatch):
    """trafilatura.extract() returning None is a parse failure, not "no
    article" — must count toward the same bounded-retry terminal state as a
    fetch failure."""
    monkeypatch.setattr(settings, "max_extraction_attempts", 1)
    _mock_fetch_success(monkeypatch)
    _mock_extract_text(monkeypatch, None)
    article = add_article(db)

    report = extract_relevant_articles(db)

    assert report.failed == 1
    assert article.extraction_status == EXTRACTION_FAILED
    assert article.full_text is None


def test_extracted_text_is_truncated_to_configured_cap(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "extraction_max_chars", 20)
    _mock_fetch_success(monkeypatch)
    _mock_extract_text(monkeypatch, "x" * 100)
    article = add_article(db)

    extract_relevant_articles(db)

    assert article.full_text == "x" * 20


# -- Story D.2: timeout, User-Agent, bounded concurrency ---------------------


def test_fetch_sends_configured_timeout_and_user_agent(monkeypatch: pytest.MonkeyPatch):
    from newsagent.pipeline.extract import _fetch_html

    monkeypatch.setattr(settings, "extraction_timeout_seconds", 7.5)
    monkeypatch.setattr(settings, "extraction_user_agent", "TestAgent/1.0")
    captured = {}

    def fake_get(url, *, timeout, headers, follow_redirects):
        captured["timeout"] = timeout
        captured["headers"] = headers
        captured["follow_redirects"] = follow_redirects
        return httpx.Response(200, text="<html>ok</html>", request=httpx.Request("GET", url))

    monkeypatch.setattr("newsagent.pipeline.extract.httpx.get", fake_get)

    result = _fetch_html("https://example.com/article")

    assert result == "<html>ok</html>"
    assert captured["timeout"] == 7.5
    assert captured["headers"] == {"User-Agent": "TestAgent/1.0"}
    assert captured["follow_redirects"] is True


def test_fetch_timeout_is_treated_as_failure(monkeypatch: pytest.MonkeyPatch):
    from newsagent.pipeline.extract import _fetch_html

    def raise_timeout(url, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("newsagent.pipeline.extract.httpx.get", raise_timeout)

    assert _fetch_html("https://example.com/slow") is None


def test_fetch_http_error_status_is_treated_as_failure(monkeypatch: pytest.MonkeyPatch):
    from newsagent.pipeline.extract import _fetch_html

    def fake_get(url, **kwargs):
        request = httpx.Request("GET", url)
        return httpx.Response(404, text="not found", request=request)

    monkeypatch.setattr("newsagent.pipeline.extract.httpx.get", fake_get)

    assert _fetch_html("https://example.com/missing") is None


def test_concurrent_fetches_are_bounded_by_configured_limit(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "extraction_concurrency", 3)
    _mock_fetch_success(monkeypatch)
    _mock_extract_text(monkeypatch, "content")
    add_article(db, url_suffix="1")
    add_article(db, url_suffix="2")

    captured_max_workers = {}
    from newsagent.pipeline import extract as extract_module

    real_executor = extract_module.ThreadPoolExecutor

    def spying_executor(*, max_workers):
        captured_max_workers["value"] = max_workers
        return real_executor(max_workers=max_workers)

    monkeypatch.setattr("newsagent.pipeline.extract.ThreadPoolExecutor", spying_executor)

    extract_relevant_articles(db)

    assert captured_max_workers["value"] == 3
