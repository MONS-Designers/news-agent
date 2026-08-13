"""Full-text extraction stage (Epic D, Story D.1): fetch the source page for
articles that already passed relevance filtering, pull out just the article
body (not nav/ads/boilerplate) via trafilatura, and store it so summarize.py
writes from the real article instead of the RSS snippet — it already prefers
full_text when present.

A source that can't be fetched or parsed doesn't abort the run (FR6); it's
retried up to a configured cap, then reaches a terminal "failed" state so a
deterministically-broken source stops being fetched forever — same pattern
as Story C.1's summarize retries. No timeout/concurrency bound here by
design: that's Story D.2's networking-politeness concern.
"""

import logging
from dataclasses import dataclass

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


def _fetch_and_extract(url: str) -> str | None:
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            return None
        return trafilatura.extract(downloaded)
    except Exception as error:  # fetch/parse errors vary across trafilatura/httpx/lxml
        logger.warning("Fetch/extract error for %s: %s", url, error)
        return None


def extract_relevant_articles(db: Session) -> ExtractReport:
    report = ExtractReport()

    articles = db.scalars(
        select(Article).where(
            Article.relevance_status == STATUS_RELEVANT,
            Article.extraction_status.in_(_EXTRACTABLE),
        )
    ).all()

    for article in articles:
        text = _fetch_and_extract(article.url)

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
