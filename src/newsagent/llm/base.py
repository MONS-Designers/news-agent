"""Abstract LLM provider contract.

Template-method design: public methods own the uniform behavior every adapter
must share (hybrid retry: transient errors retried internally with backoff,
then a typed error surfaces). Adapters implement the raw `_score_relevance` /
`_summarize` operations only.

Purity is a contract property: the same input may legally return the same
output, which is what makes caching adapters valid implementations.
"""

import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import TypeVar

from newsagent.llm.errors import LLMError
from newsagent.llm.types import ArticleInput, DigestVoice, Refusal, RelevanceScore, SummaryResult

T = TypeVar("T")


class LLMProvider(ABC):
    def __init__(
        self,
        *,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep

    # -- public contract -----------------------------------------------------

    def score_relevance(
        self,
        article: ArticleInput,
        topic: str,
        *,
        preference_history: Sequence[str] | None = None,
    ) -> RelevanceScore | Refusal:
        return self._run(lambda: self._score_relevance(article, topic, preference_history))

    def summarize(self, article: ArticleInput) -> SummaryResult | Refusal:
        return self._run(lambda: self._summarize(article))

    def compose_digest_voice(self, headlines: Sequence[str]) -> DigestVoice | Refusal:
        return self._run(lambda: self._compose_digest_voice(headlines))

    def score_relevance_many(
        self,
        articles: Sequence[ArticleInput],
        topic: str,
        *,
        preference_history: Sequence[str] | None = None,
    ) -> list[RelevanceScore | Refusal]:
        """Default loop; adapters may override to use a real batch API."""
        return [
            self.score_relevance(article, topic, preference_history=preference_history)
            for article in articles
        ]

    # -- adapter surface -----------------------------------------------------

    @abstractmethod
    def _score_relevance(
        self,
        article: ArticleInput,
        topic: str,
        preference_history: Sequence[str] | None,
    ) -> RelevanceScore | Refusal: ...

    @abstractmethod
    def _summarize(self, article: ArticleInput) -> SummaryResult | Refusal: ...

    @abstractmethod
    def _compose_digest_voice(self, headlines: Sequence[str]) -> DigestVoice | Refusal: ...

    # -- shared retry mechanics ----------------------------------------------

    def _run(self, operation: Callable[[], T]) -> T:
        attempt = 1
        while True:
            try:
                return operation()
            except LLMError as error:
                if not error.transient or attempt >= self._max_attempts:
                    raise
                self._sleep(self._backoff_seconds * 2 ** (attempt - 1))
                attempt += 1
