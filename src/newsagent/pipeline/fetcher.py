"""RSS fetch stage (issue #8): poll approved sources, insert new articles,
dedupe by URL. A broken feed is logged and skipped — one bad source never
kills the run."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.models import Article, Source

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


def fetch_source(db: Session, source: Source, parse: ParseFunc = feedparser.parse) -> SourceResult:
    result = SourceResult(source_name=source.name)
    try:
        feed = parse(source.url)
    except Exception as error:  # network/parse failures must not kill the run
        result.error = str(error)
        logger.warning("Fetch failed for %s: %s", source.name, error)
        return result

    entries = getattr(feed, "entries", None) or feed.get("entries", [])
    if not entries and feed.get("bozo"):
        result.error = str(feed.get("bozo_exception", "malformed feed"))
        logger.warning("Malformed feed for %s: %s", source.name, result.error)
        return result

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
            )
        )
        result.new_articles += 1
    db.commit()
    return result


def fetch_approved_sources(db: Session, parse: ParseFunc = feedparser.parse) -> FetchReport:
    report = FetchReport()
    sources = db.scalars(select(Source).where(Source.status == "approved")).all()
    for source in sources:
        report.results.append(fetch_source(db, source, parse))
    return report
