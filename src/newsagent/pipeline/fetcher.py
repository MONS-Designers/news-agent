"""RSS fetch stage (issue #8): poll approved sources, insert new articles,
dedupe by URL. A broken feed is logged and skipped - one bad source never
kills the run.

Parsing each source's feed (network I/O) runs through a bounded
ThreadPoolExecutor (issue #XX) so one slow feed can't stall the whole run -
same discipline as extract.py's page fetches: workers receive plain URLs
only, never the Session, so the DB writes that follow stay single-threaded.
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.models import Article, Source, UserTopicPreference
from newsagent.models.source import STATUS_APPROVED

logger = logging.getLogger(__name__)

ParseFunc = Callable[[str], Any]


@dataclass
class SourceResult:
    source_name: str
    new_articles: int = 0
    duplicates: int = 0
    error: str | None = None


@dataclass
class FetchReport:
    results: list[SourceResult] = field(default_factory=list)

    @property
    def total_new(self) -> int:
        return sum(r.new_articles for r in self.results)

    @property
    def failed_sources(self) -> list[SourceResult]:
        return [r for r in self.results if r.error is not None]


def _entry_published_at(entry: Any) -> datetime | None:
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_time is None:
        return None
    return datetime(*parsed_time[:6])


def _first_media_url(items: Any) -> str | None:
    """Return the first non-empty ``url`` from a feedparser media list (a list of
    dicts). Feedparser puts ``media:content`` under ``media_content`` and
    ``media:thumbnail`` under ``media_thumbnail``, each as [{'url': ...}, ...]."""
    if not isinstance(items, list):
        return None
    for item in items:
        url = item.get("url") if isinstance(item, dict) else None
        if url:
            return url
    return None


def extract_image_url(entry: Any) -> str | None:
    """Pick a lead image from an RSS entry, in priority order:
    ``media:content`` -> ``media:thumbnail`` -> an image ``enclosure``.

    Returns None when the feed carries no image - the article then renders as a
    text-only card (issue #24). The article-page ``og:image`` fallback is left to
    #9 (full-text extraction), which owns the page fetch; wiring it in here is a
    one-line addition once that lands."""
    media_url = _first_media_url(entry.get("media_content")) or _first_media_url(
        entry.get("media_thumbnail")
    )
    if media_url:
        return media_url
    # Enclosures: RSS <enclosure>. feedparser exposes them as `enclosures` (list
    # of dicts) and also folds them into `links` with rel="enclosure". Accept only
    # image/* to avoid grabbing a podcast audio/PDF enclosure as a "lead image".
    for enclosure in entry.get("enclosures") or []:
        if not isinstance(enclosure, dict):
            continue
        mime = enclosure.get("type") or ""
        href = enclosure.get("href") or enclosure.get("url")
        if href and mime.startswith("image/"):
            return href
    return None


def _parse_feed(url: str, parse: ParseFunc) -> tuple[Any | None, str | None]:
    """No DB access - safe to run off the main thread in the bounded
    ThreadPoolExecutor below. Returns (feed, error); at most one is set."""
    try:
        feed = parse(url)
    except Exception as error:  # network/parse failures must not kill the run
        return None, str(error)

    entries = getattr(feed, "entries", None) or feed.get("entries", [])
    if not entries and feed.get("bozo"):
        return None, str(feed.get("bozo_exception", "malformed feed"))
    return feed, None


def _write_feed_to_db(db: Session, source: Source, feed: Any) -> SourceResult:
    result = SourceResult(source_name=source.name)
    entries = getattr(feed, "entries", None) or feed.get("entries", [])
    for entry in entries:
        url = entry.get("link")
        title = entry.get("title")
        if not url or not title:
            continue
        if db.scalar(select(Article).where(Article.url == url)) is not None:
            result.duplicates += 1
            continue
        db.add(
            Article(
                source_id=source.id,
                title=title,
                url=url,
                published_at=_entry_published_at(entry),
                rss_summary=entry.get("summary") or None,
                image_url=extract_image_url(entry),
            )
        )
        result.new_articles += 1
    db.commit()
    return result


def fetch_source(db: Session, source: Source, parse: ParseFunc = feedparser.parse) -> SourceResult:
    feed, error = _parse_feed(source.url, parse)
    if error is not None:
        logger.warning("Fetch failed for %s: %s", source.name, error)
        return SourceResult(source_name=source.name, error=error)
    return _write_feed_to_db(db, source, feed)


def fetch_approved_sources(db: Session, parse: ParseFunc = feedparser.parse) -> FetchReport:
    """Approved sources whose topic nobody is subscribed to are skipped
    entirely (GH #45) - fetching them for no one is pure waste that then
    compounds through relevance-scoring and summarize's paid LLM calls."""
    report = FetchReport()
    subscribed_topic_ids = select(UserTopicPreference.topic_id)
    sources = db.scalars(
        select(Source).where(
            Source.status == STATUS_APPROVED, Source.topic_id.in_(subscribed_topic_ids)
        )
    ).all()

    with ThreadPoolExecutor(max_workers=settings.fetch_concurrency) as executor:
        parsed = list(executor.map(lambda source: _parse_feed(source.url, parse), sources))

    for source, (feed, error) in zip(sources, parsed, strict=True):
        if error is not None:
            logger.warning("Fetch failed for %s: %s", source.name, error)
            report.results.append(SourceResult(source_name=source.name, error=error))
        else:
            report.results.append(_write_feed_to_db(db, source, feed))
    return report
