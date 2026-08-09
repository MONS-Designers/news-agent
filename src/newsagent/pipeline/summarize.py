"""Summarize + translate stage (issue #11): produce Hebrew summaries for
relevant articles through the LLM provider.

Twin of the relevance stage: same state machine shape (pending/error enter;
summarized/refused terminal), same per-article commit, same usage aggregation.
Gated on relevance_status == relevant — summarizing anything else is waste.
All four SummaryResult fields are persisted onto Article so digest rendering
(#13) never recomputes anything.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.llm.base import LLMProvider
from newsagent.llm.errors import LLMError
from newsagent.llm.types import ArticleInput, Refusal
from newsagent.pipeline.relevance import STATUS_RELEVANT
from newsagent.models import Article

logger = logging.getLogger(__name__)

SUMMARY_PENDING = "pending"
SUMMARY_DONE = "summarized"
SUMMARY_REFUSED = "refused"
SUMMARY_ERROR = "error"

_SUMMARIZABLE = (SUMMARY_PENDING, SUMMARY_ERROR)


@dataclass
class SummarizeReport:
    summarized: int = 0
    refused: int = 0
    errors: int = 0
    usage_input_units: int = 0
    usage_output_units: int = 0


def _accumulate_usage(report: SummarizeReport, provider: LLMProvider) -> None:
    """Drain whatever the provider billed for the article just processed —
    success or failure — so a malformed-output error doesn't read as free."""
    for usage in provider.drain_usage():
        report.usage_input_units += usage.input_units
        report.usage_output_units += usage.output_units


def summarize_relevant_articles(db: Session, provider: LLMProvider) -> SummarizeReport:
    report = SummarizeReport()

    articles = db.scalars(
        select(Article).where(
            Article.relevance_status == STATUS_RELEVANT,
            Article.summary_status.in_(_SUMMARIZABLE),
        )
    ).all()

    for article in articles:
        article_input = ArticleInput(
            title=article.title,
            text=article.full_text or article.rss_summary or article.title,
        )
        try:
            result = provider.summarize(article_input)
        except LLMError as error:
            article.summary_status = SUMMARY_ERROR
            report.errors += 1
            logger.warning("Summarize failed for article %s: %s", article.id, error)
            _accumulate_usage(report, provider)
            db.commit()
            continue

        if isinstance(result, Refusal):
            article.summary_status = SUMMARY_REFUSED
            report.refused += 1
        elif not result.summary_he.strip():
            # An empty summary without a Refusal is a provider bug, not a value.
            article.summary_status = SUMMARY_ERROR
            report.errors += 1
            logger.warning("Empty summary for article %s — treating as error", article.id)
        else:
            article.summary_he = result.summary_he
            article.title_he = result.title_he
            article.source_language = result.source_language
            article.reading_time_minutes = result.reading_time_minutes
            article.bullets_he = list(result.bullets_he)
            article.interestingness = result.interestingness
            article.summary_status = SUMMARY_DONE
            report.summarized += 1
        _accumulate_usage(report, provider)
        db.commit()

    return report
