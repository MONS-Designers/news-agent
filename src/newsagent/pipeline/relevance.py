"""Relevance filtering stage (issue #10): score pending articles against their
source's topic through the LLM provider, persist score + verdict.

Score is the provider's fact; the verdict is pipeline policy (threshold from
config) - both are stored, so a threshold change can re-verdict without paying
for re-scoring. Scored exactly once: only pending/error articles enter, and the
DB row is the cache. Per-article commit so progress survives crashes.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.llm.base import LLMProvider
from newsagent.llm.errors import LLMError
from newsagent.llm.types import ArticleInput, Refusal
from newsagent.models import Article, Source, UserTopicPreference
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
    usage_input_units: int = 0
    usage_output_units: int = 0
    scores: list[float] = field(default_factory=list)

    @property
    def scored(self) -> int:
        return self.relevant + self.irrelevant

    @property
    def borderline(self) -> int:
        """Scores between the contract anchors (0.3–0.7) - worth watching."""
        return sum(1 for s in self.scores if 0.3 < s < 0.7)


def _accumulate_usage(report: FilterReport, provider: LLMProvider) -> None:
    """Drain whatever the provider billed for the article just processed -
    success or failure - so a malformed-output error doesn't read as free."""
    for usage in provider.drain_usage():
        report.usage_input_units += usage.input_units
        report.usage_output_units += usage.output_units


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

    for article in articles:
        article_input = ArticleInput(
            title=article.title,
            text=article.rss_summary or article.title,
        )
        topic_name = article.source.topic.name
        try:
            result = provider.score_relevance(article_input, topic_name)
        except LLMError as error:
            article.relevance_status = STATUS_ERROR
            report.errors += 1
            logger.warning("Scoring failed for article %s: %s", article.id, error)
            _accumulate_usage(report, provider)
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
        _accumulate_usage(report, provider)
        db.commit()

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
