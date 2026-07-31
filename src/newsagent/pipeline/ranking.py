"""Weighted digest ranking + top-N selection (issue #25): score each user's
undelivered candidates and keep only the best `digest_max_articles`, so
`build_digests` attaches a real ranked shortlist instead of everything it
finds. Unselected candidates get no DigestArticle row and stay undelivered,
eligible again on a future run.

`final_score = relevance_weight*relevance + recency_weight*recency +
interest_weight*interest`, where `interest` blends the LLM's interestingness
score with a per-topic personalization affinity derived from which of the
user's past digests they actually opened — issue #25 is the first real
consumer of #13's open-tracking data.
"""

import math
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.models import Article, Digest, User

_NEUTRAL_AFFINITY = 0.5


def topic_affinity(db: Session, user: User, before_date: date) -> dict[int, float]:
    """Per-topic personalization signal: among the user's past **sent** digests
    (excluding the one being built for `before_date`) that contained at least
    one article of a given topic, the fraction that were opened. A topic with
    no such history — including when the user has no past sent digests at
    all — defaults to neutral (0.5)."""
    past_digests = db.scalars(
        select(Digest).where(
            Digest.user_id == user.id,
            Digest.sent_at.is_not(None),
            Digest.date != before_date,
        )
    ).all()

    seen: dict[int, int] = {}
    opened: dict[int, int] = {}
    for digest in past_digests:
        topic_ids = {entry.article.source.topic_id for entry in digest.articles}
        for topic_id in topic_ids:
            seen[topic_id] = seen.get(topic_id, 0) + 1
            if digest.opened_at is not None:
                opened[topic_id] = opened.get(topic_id, 0) + 1

    return {topic_id: opened.get(topic_id, 0) / count for topic_id, count in seen.items()}


def score_article(
    article: Article, *, now: datetime, topic_affinities: dict[int, float]
) -> float:
    """Weighted final score for one candidate. `topic_affinities` is the
    (user, before_date) affinity map from `topic_affinity`, computed once per
    selection run and shared across candidates."""
    reference = article.published_at or article.scraped_at
    hours_since = (now - reference).total_seconds() / 3600
    recency = math.exp(-math.log(2) * hours_since / settings.recency_half_life_hours)

    llm_interestingness = (
        article.interestingness if article.interestingness is not None else _NEUTRAL_AFFINITY
    )
    personalization_affinity = topic_affinities.get(article.source.topic_id, _NEUTRAL_AFFINITY)
    interest = (
        settings.interestingness_weight * llm_interestingness
        + settings.personalization_weight * personalization_affinity
    )

    return (
        settings.relevance_weight * article.relevance_score
        + settings.recency_weight * recency
        + settings.interest_weight * interest
    )


def select_top(
    db: Session, user: User, candidates: list[Article], for_date: date, limit: int | None = None
) -> list[Article]:
    """Rank `candidates` by `final_score` descending and keep the top `limit`
    (default `digest_max_articles`). Callers pass a smaller `limit` when a
    same-day rerun has already attached some of today's digest, so the total
    per digest never exceeds `digest_max_articles`. Callers are responsible
    for leaving the rest unattached (no DigestArticle row) so they remain
    undelivered."""
    if limit is None:
        limit = settings.digest_max_articles
    if not candidates or limit <= 0:
        return []
    affinities = topic_affinity(db, user, for_date)
    # published_at/scraped_at are naive UTC (feedparser's parsed struct_time,
    # SQLite's server-side now()) — compare against UTC "now", not local time.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ranked = sorted(
        candidates,
        key=lambda article: score_article(article, now=now, topic_affinities=affinities),
        reverse=True,
    )
    return ranked[:limit]
