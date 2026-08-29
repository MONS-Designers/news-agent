"""Relevance filtering stage (issue #10): score pending articles against their
source's topic through the LLM provider, persist score + verdict.

Score is the provider's fact; the verdict is pipeline policy (threshold from
config) - both are stored, so a threshold change can re-verdict without paying
for re-scoring. Scored exactly once: only pending/error articles enter, and the
DB row is the cache. Per-article commit so progress survives crashes.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from newsagent import telemetry
from newsagent.config import settings
from newsagent.llm.base import LLMProvider
from newsagent.llm.errors import LLMError
from newsagent.llm.types import ArticleInput, Refusal
from newsagent.models import Article, Source, User, UserTopicPreference
from newsagent.models.source import STATUS_APPROVED

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_RELEVANT = "relevant"
STATUS_IRRELEVANT = "irrelevant"
STATUS_REFUSED = "refused"
STATUS_ERROR = "error"

# Articles in these states enter a filter run (error is retryable, not terminal).
_FILTERABLE = (STATUS_PENDING, STATUS_ERROR)


@dataclass
class FilterReport:
    relevant: int = 0
    irrelevant: int = 0
    refused: int = 0
    errors: int = 0
    scores: list[float] = field(default_factory=list)
    # Set once telemetry.open_run() creates the run - None if telemetry
    # itself failed to open one (swallowed; see telemetry/sink.py). Read by
    # cli.py to correlate this run's log_entries afterward.
    run_id: int | None = None

    @property
    def scored(self) -> int:
        return self.relevant + self.irrelevant

    @property
    def borderline(self) -> int:
        """Scores between the contract anchors (0.3–0.7) - worth watching."""
        return sum(1 for s in self.scores if 0.3 < s < 0.7)


def active_subscriber_count(db: Session, topic_ids: set[int]) -> int:
    """Distinct users *actively* subscribed (`User.unsubscribed_at IS NULL`)
    to any of `topic_ids` - AD-13/AD-14's `subscriber_count` definition.
    Shared between this module and `summarize.py`, the two shared-stage
    (not per-user) callers - an unsubscribed user must not inflate either
    stage's "cost per subscriber" denominator."""
    if not topic_ids:
        return 0
    return (
        db.scalar(
            select(func.count(func.distinct(UserTopicPreference.user_id)))
            .join(User, User.id == UserTopicPreference.user_id)
            .where(
                UserTopicPreference.topic_id.in_(topic_ids),
                User.unsubscribed_at.is_(None),
            )
        )
        or 0
    )


def filter_pending_articles(
    db: Session,
    provider: LLMProvider,
    threshold: float | None = None,
) -> FilterReport:
    if threshold is None:
        threshold = settings.relevance_threshold
    report = FilterReport()

    # Skip articles whose source's topic nobody is subscribed to (GH #45) - a
    # topic that lost its last subscriber simply stops advancing here rather
    # than needing separate cleanup; nothing scores it, so nothing downstream
    # ever sees it.
    subscribed_topic_ids = select(UserTopicPreference.topic_id)
    articles = db.scalars(
        select(Article)
        .join(Source)
        .where(
            Article.relevance_status.in_(_FILTERABLE),
            Source.status == STATUS_APPROVED,
            Source.topic_id.in_(subscribed_topic_ids),
        )
    ).all()

    # AD-14: filtering is a shared stage, not per-user - subscriber_count is
    # the number of distinct active users subscribed to a topic this run
    # touched, not a per-article or per-user cost split.
    topic_ids = {article.source.topic_id for article in articles}
    subscriber_count = active_subscriber_count(db, topic_ids)

    with telemetry.open_run(
        telemetry.KIND_FILTER,
        subscriber_count=subscriber_count,
        intent_summary=f"filter · {len(articles)} articles",
    ) as run:
        report.run_id = run.run_id
        try:
            for article in articles:
                article_input = ArticleInput(
                    title=article.title,
                    text=article.rss_summary or article.title,
                )
                topic_name = article.source.topic.name
                with telemetry.attribute_call(telemetry.PURPOSE_FILTERING, article_id=article.id):
                    try:
                        result = provider.score_relevance(article_input, topic_name)
                    except LLMError as error:
                        article.relevance_status = STATUS_ERROR
                        report.errors += 1
                        logger.warning("Scoring failed for article %s: %s", article.id, error)
                        db.commit()
                        continue

                    if isinstance(result, Refusal):
                        article.relevance_status = STATUS_REFUSED
                        report.refused += 1
                    else:
                        article.relevance_score = result.score
                        article.relevance_status = (
                            STATUS_RELEVANT if result.score >= threshold else STATUS_IRRELEVANT
                        )
                        report.scores.append(result.score)
                        if result.score >= threshold:
                            report.relevant += 1
                        else:
                            report.irrelevant += 1
                    db.commit()
        finally:
            # Only LLMError is caught per-article above - anything else (a DB
            # commit failure, say) must still close the run with whatever
            # this loop already accumulated, not discard it as 0/0/0: earlier
            # articles in the same loop already had their status committed
            # and their outbound_calls rows written (round 2 review finding).
            run.close(succeeded=report.scored, refused=report.refused, errors=report.errors)

    if report.scores:
        logger.info(
            "Filter run: %d scored (min=%.2f avg=%.2f max=%.2f, %d borderline)",
            len(report.scores),
            min(report.scores),
            sum(report.scores) / len(report.scores),
            max(report.scores),
            report.borderline,
        )
    return report
