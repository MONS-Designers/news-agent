"""Digest builder stage: for each user, gather summarized articles
in their subscribed topics that were never delivered to them before, and build
(or extend) the Digest for `for_date` — the weekly send date.

Selection is "not yet sent", not "articles from this week": a DigestArticle row
is itself the record of delivery, so nothing repeats across runs and nothing is
lost if a week is skipped. One digest per user per date (unique constraint);
re-running the same date appends only newly arrived articles; no empty digests.

Cadence note: fetch/filter/summarize run daily so nothing scrolls off an RSS
feed unseen, while this stage and `send` run weekly — so a week's worth of
summarized candidates competes for `digest_max_articles` slots here.
"""

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.llm.base import LLMProvider
from newsagent.llm.errors import LLMError
from newsagent.llm.types import Refusal
from newsagent.models import Article, Digest, DigestArticle, Source, User, UserTopicPreference
from newsagent.pipeline.ranking import select_top
from newsagent.pipeline.summarize import SUMMARY_DONE

logger = logging.getLogger(__name__)


@dataclass
class DigestReport:
    users_processed: int = 0
    digests_created: int = 0
    articles_added: int = 0


def _undelivered_articles(db: Session, user: User) -> list[Article]:
    topic_ids = select(UserTopicPreference.topic_id).where(UserTopicPreference.user_id == user.id)
    already_sent = (
        select(DigestArticle.article_id)
        .join(Digest)
        .where(Digest.user_id == user.id)
    )
    return list(
        db.scalars(
            select(Article)
            .join(Source)
            .where(
                Article.summary_status == SUMMARY_DONE,
                Source.topic_id.in_(topic_ids),
                Article.id.not_in(already_sent),
            )
        )
    )


def _compose_voice(provider: LLMProvider, digest: Digest) -> None:
    """Fill the digest's editorial voice from its article headlines. Best-effort:
    a refusal or provider error leaves the voice empty (template renders without
    it) rather than failing the build."""
    headlines = [entry.article.title_he or entry.article.title for entry in digest.articles]
    if not headlines:
        return
    try:
        voice = provider.compose_digest_voice(headlines)
    except LLMError as error:
        logger.warning("Voice composition failed for digest %s: %s", digest.id, error)
        return
    if isinstance(voice, Refusal):
        return
    digest.intro_he = voice.intro_he
    digest.dad_joke_he = voice.dad_joke_he


def build_digests(
    db: Session, provider: LLMProvider, for_date: date | None = None
) -> DigestReport:
    if for_date is None:
        for_date = date.today()
    report = DigestReport()

    # Unsubscribed users (GH #46) are skipped entirely — no digest is even
    # built for them, not just held back at send time.
    for user in db.scalars(select(User).where(User.unsubscribed_at.is_(None))):
        report.users_processed += 1
        articles = _undelivered_articles(db, user)
        if not articles:
            continue

        digest = db.scalar(
            select(Digest).where(Digest.user_id == user.id, Digest.date == for_date)
        )
        if digest is None:
            digest = Digest(user_id=user.id, date=for_date)
            db.add(digest)
            db.flush()
            report.digests_created += 1

        # Only the ranked top-N get attached this run; the rest stay
        # undelivered (no DigestArticle row) and are eligible next run (#25).
        # `limit` accounts for articles a same-day rerun already attached, so
        # the digest's total never exceeds digest_max_articles. Counted via a
        # direct query, not `digest.articles`, so accessing the count here
        # doesn't cache a stale (pre-insert) collection for `_compose_voice`.
        # Same query also gives the already-attached topics, so a rerun's
        # diversity floor (GH #37) isn't recomputed from zero.
        already_attached_topic_ids = list(
            db.scalars(
                select(Source.topic_id)
                .join(Article, Article.source_id == Source.id)
                .join(DigestArticle, DigestArticle.article_id == Article.id)
                .where(DigestArticle.digest_id == digest.id)
            )
        )
        selected = select_top(
            db,
            user,
            articles,
            for_date,
            limit=settings.digest_max_articles - len(already_attached_topic_ids),
            already_represented_topic_ids=set(already_attached_topic_ids),
        )

        for article in selected:
            db.add(DigestArticle(digest_id=digest.id, article_id=article.id))
        report.articles_added += len(selected)
        db.flush()
        # Refresh the voice against the digest's now-final article set.
        _compose_voice(provider, digest)
        db.commit()
        logger.info("Digest for %s (%s): +%d articles", user.email, for_date, len(selected))

    return report
