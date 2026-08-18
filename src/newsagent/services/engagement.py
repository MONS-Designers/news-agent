"""Digest engagement reporting (FR13): opens (already tracked via
Digest.opened_at) and clicks (DigestLink.clicked_at, new in this story) exposed
per sent digest, so an operator can see them without a manual DB query."""

from dataclasses import dataclass
from datetime import date as date_
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.models import Digest
from newsagent.models.digest_link import KIND_ARTICLE, KIND_PREFERENCES


@dataclass
class DigestEngagement:
    digest_id: int
    user_email: str
    date: date_
    sent_at: datetime | None
    opened_at: datetime | None
    articles_total: int
    articles_clicked: int
    clicked_article_titles: list[str]
    preferences_clicked: bool


def list_digest_engagement(db: Session, limit: int = 100) -> list[DigestEngagement]:
    """Sent digests, most recent first. Unsent digests are excluded - their
    links don't exist yet (created at render time, immediately before send)."""
    digests = db.scalars(
        select(Digest)
        .where(Digest.sent_at.is_not(None))
        .order_by(Digest.date.desc(), Digest.id.desc())
        .limit(limit)
    ).all()

    results = []
    for digest in digests:
        article_links = [link for link in digest.links if link.kind == KIND_ARTICLE]
        clicked_article_links = [link for link in article_links if link.clicked_at is not None]
        preferences_link = next(
            (link for link in digest.links if link.kind == KIND_PREFERENCES), None
        )
        results.append(
            DigestEngagement(
                digest_id=digest.id,
                user_email=digest.user.email,
                date=digest.date,
                sent_at=digest.sent_at,
                opened_at=digest.opened_at,
                articles_total=len(article_links),
                articles_clicked=len(clicked_article_links),
                clicked_article_titles=[
                    link.article.title_he or link.article.title for link in clicked_article_links
                ],
                preferences_clicked=preferences_link is not None
                and preferences_link.clicked_at is not None,
            )
        )
    return results
