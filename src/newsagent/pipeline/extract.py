"""Full-text extraction stage (Epic D, Story D.1): fetch the source page for
articles that already passed relevance filtering, pull out just the article
body (not nav/ads/boilerplate) via trafilatura, and store it so summarize.py
writes from the real article instead of the RSS snippet — it already prefers
full_text when present.

A source that can't be fetched or parsed doesn't abort the run (FR6); it's
retried up to a configured cap, then reaches a terminal "failed" state so a
deterministically-broken source stops being fetched forever — same pattern
as Story C.1's summarize retries.

Fetching (Story D.2) uses `httpx` directly instead of trafilatura's own
downloader, so timeout/User-Agent are ours to configure, and runs through a
bounded ThreadPoolExecutor so one slow source can't stall the whole run.
Workers receive plain URLs only — the SQLAlchemy Session is never touched
off the calling thread, same discipline as GH #36's concurrent LLM calls.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx
import trafilatura
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.models import Article
from newsagent.pipeline.relevance import STATUS_RELEVANT

logger = logging.getLogger(__name__)

EXTRACTION_PENDING = "pending"
EXTRACTION_DONE = "done"
EXTRACTION_FAILED = "failed"

_EXTRACTABLE = (EXTRACTION_PENDING,)


@dataclass
class ExtractReport:
    extracted: int = 0
    failed: int = 0


def _fetch_html(url: str) -> str | None:
    """No DB access — safe to run off the main thread in the bounded
    ThreadPoolExecutor below."""
    try:
        response = httpx.get(
            url,
            timeout=settings.extraction_timeout_seconds,
            headers={"User-Agent": settings.extraction_user_agent},
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text
    except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as error:
        logger.warning("Fetch failed for %s: %s", url, error)
        return None


def _extract_text(html: str) -> str | None:
    try:
        return trafilatura.extract(html)
    except Exception as error:  # parse errors vary across trafilatura/lxml
        logger.warning("Extraction error: %s", error)
        return None


def extract_relevant_articles(db: Session) -> ExtractReport:
    report = ExtractReport()

    articles = db.scalars(
        select(Article).where(
            Article.relevance_status == STATUS_RELEVANT,
            Article.extraction_status.in_(_EXTRACTABLE),
        )
    ).all()

    with ThreadPoolExecutor(max_workers=settings.extraction_concurrency) as executor:
        htmls = list(executor.map(_fetch_html, (article.url for article in articles)))

    for article, html in zip(articles, htmls, strict=True):
        text = _extract_text(html) if html is not None else None

        if not text:
            article.extraction_attempts += 1
            if article.extraction_attempts >= settings.max_extraction_attempts:
                article.extraction_status = EXTRACTION_FAILED
            report.failed += 1
            logger.warning(
                "Extraction failed for article %s (attempt %d)",
                article.id,
                article.extraction_attempts,
            )
        else:
            article.full_text = text[: settings.extraction_max_chars]
            article.extraction_status = EXTRACTION_DONE
            report.extracted += 1

        db.commit()

    return report
