"""Deterministic mock provider — deliberately boring.

Same input always yields the same output; no API key, no network. Scoring is
topic-token overlap; "translation" is a marker prefix. The `fail_*` knobs exist
only so the contract tests can exercise the shared retry mechanics — by default
the mock never fails.
"""

import re
from collections.abc import Sequence

from newsagent.llm.base import LLMProvider
from newsagent.llm.errors import LLMProviderError, LLMTransportError
from newsagent.llm.types import ArticleInput, Refusal, RelevanceScore, SummaryResult, Usage

_MIN_TEXT_LENGTH = 40
_WORDS_PER_MINUTE = 200
_HEBREW_CHARS = re.compile(r"[֐-׿]")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w']+", text.lower())


class MockLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        fail_transient: int = 0,
        fail_permanent: bool = False,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._fail_transient = fail_transient
        self._fail_permanent = fail_permanent

    def _maybe_fail(self) -> None:
        if self._fail_permanent:
            raise LLMProviderError("injected permanent failure")
        if self._fail_transient > 0:
            self._fail_transient -= 1
            raise LLMTransportError("injected transient failure")

    def _refuse_if_junk(self, article: ArticleInput) -> Refusal | None:
        if len(article.text.strip()) < _MIN_TEXT_LENGTH:
            return Refusal(reason="article text too short to process")
        return None

    def _score_relevance(
        self,
        article: ArticleInput,
        topic: str,
        preference_history: Sequence[str] | None,
    ) -> RelevanceScore | Refusal:
        self._maybe_fail()
        refusal = self._refuse_if_junk(article)
        if refusal is not None:
            return refusal

        topic_tokens = set(_tokens(topic))
        if not topic_tokens:
            return Refusal(reason="empty topic")
        text_tokens = set(_tokens(f"{article.title} {article.text}"))
        score = len(topic_tokens & text_tokens) / len(topic_tokens)
        return RelevanceScore(
            score=score,
            usage=Usage(input_units=len(_tokens(article.text)), output_units=1),
        )

    def _summarize(self, article: ArticleInput) -> SummaryResult | Refusal:
        self._maybe_fail()
        refusal = self._refuse_if_junk(article)
        if refusal is not None:
            return refusal

        words = article.text.split()
        snippet = " ".join(words[:40])
        summary_he = f"[תרגום דמה] {snippet}"
        source_language = "he" if _HEBREW_CHARS.search(article.text) else "en"
        return SummaryResult(
            summary_he=summary_he,
            title_he=f"[תרגום דמה] {article.title}",
            source_language=source_language,
            reading_time_minutes=max(1, round(len(words) / _WORDS_PER_MINUTE)),
            usage=Usage(input_units=len(words), output_units=len(summary_he.split())),
        )
