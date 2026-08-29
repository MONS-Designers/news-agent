"""Summarize + translate stage (issue #11): produce Hebrew summaries for
relevant articles through the LLM provider.

Twin of the relevance stage: same state machine shape (pending/error enter;
summarized/refused terminal), same per-article commit, same usage aggregation.
Gated on relevance_status == relevant - summarizing anything else is waste.
All four SummaryResult fields are persisted onto Article so digest rendering
(#13) never recomputes anything.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent import telemetry
from newsagent.config import settings
from newsagent.llm.base import LLMProvider
from newsagent.llm.errors import LLMError
from newsagent.llm.types import ArticleInput, Refusal
from newsagent.pipeline.relevance import STATUS_RELEVANT, active_subscriber_count
from newsagent.models import Article, Source, UserTopicPreference

logger = logging.getLogger(__name__)

SUMMARY_PENDING = "pending"
SUMMARY_DONE = "summarized"
SUMMARY_REFUSED = "refused"
SUMMARY_ERROR = "error"
# Terminal like refused - reached once summarize_attempts hits the configured
# max (Epic C, Story C.1). Deliberately excluded from _SUMMARIZABLE below.
SUMMARY_FAILED = "failed"

_SUMMARIZABLE = (SUMMARY_PENDING, SUMMARY_ERROR)


@dataclass
class SummarizeReport:
    summarized: int = 0
    refused: int = 0
    errors: int = 0
    # Set once telemetry.open_run() creates the run - None if telemetry
    # itself failed to open one (swallowed; see telemetry/sink.py). Read by
    # cli.py to correlate this run's log_entries afterward.
    run_id: int | None = None


def _record_failure(article: Article, report: SummarizeReport) -> None:
    """Increment the bounded-retry counter for a failed attempt (LLMError, or
    the empty-summary-without-refusal provider bug below - both are "the call
    didn't produce a usable result"). Once the counter reaches the configured
    max, the article's status becomes the terminal "failed" instead of
    "error" so _SUMMARIZABLE stops selecting it - never retried, never billed
    for again."""
    article.summarize_attempts += 1
    if article.summarize_attempts >= settings.max_summarize_attempts:
        article.summary_status = SUMMARY_FAILED
    else:
        article.summary_status = SUMMARY_ERROR
    report.errors += 1


def summarize_relevant_articles(db: Session, provider: LLMProvider) -> SummarizeReport:
    report = SummarizeReport()

    # Skip articles whose source's topic nobody is subscribed to (GH #45) -
    # this is the paid LLM stage, so it's the most expensive place this
    # waste could otherwise happen.
    subscribed_topic_ids = select(UserTopicPreference.topic_id)
    articles = db.scalars(
        select(Article)
        .join(Source)
        .where(
            Article.relevance_status == STATUS_RELEVANT,
            Article.summary_status.in_(_SUMMARIZABLE),
            Source.topic_id.in_(subscribed_topic_ids),
        )
    ).all()

    # AD-14: summarizing is a shared stage, not per-user - subscriber_count is
    # the number of distinct active users subscribed to a topic this run
    # touched.
    topic_ids = {article.source.topic_id for article in articles}
    subscriber_count = active_subscriber_count(db, topic_ids)

    with telemetry.open_run(
        telemetry.KIND_SUMMARIZE,
        subscriber_count=subscriber_count,
        intent_summary=f"summarize · {len(articles)} articles",
    ) as run:
        report.run_id = run.run_id
        try:
            for article in articles:
                article_input = ArticleInput(
                    title=article.title,
                    text=article.full_text or article.rss_summary or article.title,
                )
                with telemetry.attribute_call(telemetry.PURPOSE_SUMMARIZING, article_id=article.id):
                    try:
                        result = provider.summarize(article_input)
                    except LLMError as error:
                        _record_failure(article, report)
                        logger.warning("Summarize failed for article %s: %s", article.id, error)
                        db.commit()
                        continue

                    if isinstance(result, Refusal):
                        article.summary_status = SUMMARY_REFUSED
                        report.refused += 1
                    elif not result.summary_he.strip():
                        # An empty summary without a Refusal is a provider bug, not a value.
                        _record_failure(article, report)
                        logger.warning("Empty summary for article %s - treating as error", article.id)
                    else:
                        article.summary_he = result.summary_he
                        article.title_he = result.title_he
                        article.source_language = result.source_language
                        article.reading_time_minutes = result.reading_time_minutes
                        article.paragraphs_he = list(result.paragraphs_he)
                        article.interestingness = result.interestingness
                        article.summary_status = SUMMARY_DONE
                        report.summarized += 1
                    db.commit()
        finally:
            # Only LLMError is caught per-article above - anything else (a DB
            # commit failure, say) must still close the run with whatever
            # this loop already accumulated, not discard it as 0/0/0: earlier
            # articles in the same loop already had their status committed
            # and their outbound_calls rows written (round 2 review finding).
            run.close(succeeded=report.summarized, refused=report.refused, errors=report.errors)

    return report
