"""Digest builder stage: for each user, gather summarized articles
in their subscribed topics that were never delivered to them before, and build
(or extend) the Digest for `for_date` - the weekly send date.

Selection is "not yet sent", not "articles from this week": a DigestArticle row
is itself the record of delivery, so nothing repeats across runs and nothing is
lost if a week is skipped. One digest per user per date (unique constraint);
re-running the same date appends only newly arrived articles; no empty digests.

Cadence note: fetch/filter/summarize run daily so nothing scrolls off an RSS
feed unseen, while this stage and `send` run weekly - so a week's worth of
summarized candidates competes for `digest_max_articles` slots here.
"""

import logging
import time
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent import telemetry
from newsagent.config import settings
from newsagent.llm.base import LLMProvider
from newsagent.llm.errors import LLMError
from newsagent.llm.types import Refusal
from newsagent.models import Article, Digest, DigestArticle, Source, User, UserTopicPreference
from newsagent.pipeline.ranking import select_top
from newsagent.pipeline.summarize import SUMMARY_DONE

logger = logging.getLogger(__name__)

# How far back to look for an already-composed editorial voice covering the
# same articles. Bounded rather than unlimited because the voice is written
# about a moment in the news - borrowing one from last month would open a
# digest with a stale framing of stories that have since moved on.
VOICE_REUSE_DAYS = 3


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


def _reuse_recent_voice(db: Session, digest: Digest) -> bool:
    """Copy the editorial voice from a recent digest built on the exact same
    articles, instead of paying another LLM call to describe the same news.
    Returns whether a match was found.

    Matched on the article set, not on topics: the voice is generated *from*
    the headlines, so borrowing it across different article sets would open a
    reader's digest by referring to stories that are not in it.

    This is aimed squarely at new signups. `topic_affinity` gives a reader with
    no sent-and-opened history a neutral score for every topic, so two people
    who just picked the same topics get ranked identically and land on the same
    top-N - which is exactly when the LLM would be asked to write the same
    intro twice.
    """
    article_ids = {entry.article_id for entry in digest.articles}
    if not article_ids:
        return False

    cutoff = digest.date - timedelta(days=VOICE_REUSE_DAYS)
    recent = db.scalars(
        select(Digest).where(
            Digest.id != digest.id,
            Digest.date >= cutoff,
            Digest.date <= digest.date,
            Digest.intro_he.is_not(None),
        )
    )
    for candidate in recent:
        if {entry.article_id for entry in candidate.articles} == article_ids:
            digest.intro_he = candidate.intro_he
            digest.dad_joke_he = candidate.dad_joke_he
            logger.info("Digest %s reused the voice from digest %s", digest.id, candidate.id)
            return True
    return False


def _compose_voice(provider: LLMProvider, digest: Digest) -> str | None:
    """Fill the digest's editorial voice from its article headlines. Best-effort:
    a refusal or provider error leaves the voice empty (template renders without
    it) rather than failing the build.

    Returns `'succeeded'` / `'refused'` / `'error'` reflecting the provider's
    actual outcome, for the caller to pass on as this run's real
    `outbound_runs` counts (AD-13 - never a hardcoded placeholder) - or
    `None` if there were no headlines to compose from at all, i.e. nothing
    was attempted."""
    headlines = [entry.article.title_he or entry.article.title for entry in digest.articles]
    if not headlines:
        return None
    try:
        voice = provider.compose_digest_voice(headlines)
    except LLMError as error:
        logger.warning("Voice composition failed for digest %s: %s", digest.id, error)
        return "error"
    if isinstance(voice, Refusal):
        return "refused"
    digest.intro_he = voice.intro_he
    digest.dad_joke_he = voice.dad_joke_he
    return "succeeded"


def build_digests(
    db: Session,
    provider: LLMProvider,
    for_date: date | None = None,
    *,
    user_ids: Collection[int] | None = None,
) -> DigestReport:
    """Build digests for every eligible user, or only for `user_ids`.

    The caller decides *who* - this stage has no opinion about cadence or
    onboarding. That split is what makes the scheduler's short tick affordable:
    building a digest costs an LLM call for the editorial voice, so the loop
    passes the handful of users who are actually due (see services/cadence.py)
    and this does no LLM work at all on the ticks where nobody is. An empty
    collection means nobody, which is different from `None` (everybody).
    """
    if for_date is None:
        for_date = date.today()
    report = DigestReport()

    if user_ids is not None and not user_ids:
        return report

    # Unsubscribed users (GH #46) are skipped entirely - no digest is even
    # built for them, not just held back at send time.
    candidates = select(User).where(User.unsubscribed_at.is_(None))
    if user_ids is not None:
        candidates = candidates.where(User.id.in_(user_ids))

    for user in db.scalars(candidates):
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
        # Refresh the voice against the digest's now-final article set, unless
        # a recent digest already covers exactly these articles - then the LLM
        # would only be rewriting a description of the same news. One run per
        # user (AD-11/AD-14: digest_build is per-user, unlike filter/summarize).
        with telemetry.open_run(
            telemetry.KIND_DIGEST_BUILD,
            user_id=user.id,
            intent_summary=f"digest voice · {for_date}",
        ) as run:
            outcome: str | None = None
            try:
                with telemetry.attribute_call(telemetry.PURPOSE_DIGEST_VOICE):
                    voice_check_start = time.monotonic()
                    reused = _reuse_recent_voice(db, digest)
                    if reused:
                        # AD-15: the transport never ran, so the caller reports
                        # the cache lookup itself - real duration, zero cost. A
                        # reused voice is as usable as a freshly composed one.
                        telemetry.report_avoided(
                            duration_ms=int((time.monotonic() - voice_check_start) * 1000)
                        )
                        outcome = "succeeded"
                    else:
                        outcome = _compose_voice(provider, digest)
            except BaseException:
                # Only LLMError ever reaches _compose_voice's own try - an
                # unmapped exception must still count as an error here, or
                # run.close() below never runs at all and the run silently
                # closes as 0/0/0, indistinguishable from a no-op (round 2
                # review finding).
                outcome = "error"
                raise
            finally:
                # Real outcome, not a placeholder (AD-13): "no headlines"
                # (outcome is None) means nothing was attempted, so it counts
                # toward none of the three - same as an article a filter run
                # never scored.
                run.close(
                    succeeded=1 if outcome == "succeeded" else 0,
                    refused=1 if outcome == "refused" else 0,
                    errors=1 if outcome == "error" else 0,
                )
        db.commit()
        logger.info("Digest for %s (%s): +%d articles", user.email, for_date, len(selected))

    return report
