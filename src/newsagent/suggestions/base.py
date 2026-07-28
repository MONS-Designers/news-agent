"""Abstract Suggestion Source provider contract.

Sibling to `newsagent.llm.base` (AD-3) — same template-method shape (hybrid
retry: transient errors retried internally with backoff, then a typed error
surfaces), deliberately not importing from or importing into `newsagent.llm`.
Adapters implement the raw `_suggest_*` operations only.
"""

import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import TypeVar

from newsagent.suggestions.errors import SuggestionError
from newsagent.suggestions.types import PromptText, RoleOption, TopicPopularity, TopicSuggestion

T = TypeVar("T")


class SuggestionSource(ABC):
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

    def suggest_roles(
        self, field_name: str, *, existing_roles: Sequence[str] = ()
    ) -> list[RoleOption]:
        return self._run(lambda: self._suggest_roles(field_name, existing_roles=existing_roles))

    def suggest_prompts(
        self,
        *,
        field_name: str | None = None,
        role_name: str | None = None,
        experience_bucket: str | None = None,
    ) -> list[PromptText]:
        return self._run(
            lambda: self._suggest_prompts(
                field_name=field_name,
                role_name=role_name,
                experience_bucket=experience_bucket,
            )
        )

    def suggest_topics(
        self,
        *,
        field_name: str | None,
        role_name: str | None,
        interest_free_text: str | None,
        popularity: Sequence[TopicPopularity],
    ) -> list[TopicSuggestion]:
        return self._run(
            lambda: self._suggest_topics(
                field_name=field_name,
                role_name=role_name,
                interest_free_text=interest_free_text,
                popularity=popularity,
            )
        )

    # -- adapter surface -----------------------------------------------------

    @abstractmethod
    def _suggest_roles(
        self, field_name: str, *, existing_roles: Sequence[str] = ()
    ) -> list[RoleOption]: ...

    @abstractmethod
    def _suggest_prompts(
        self,
        *,
        field_name: str | None = None,
        role_name: str | None = None,
        experience_bucket: str | None = None,
    ) -> list[PromptText]: ...

    @abstractmethod
    def _suggest_topics(
        self,
        *,
        field_name: str | None,
        role_name: str | None,
        interest_free_text: str | None,
        popularity: Sequence[TopicPopularity],
    ) -> list[TopicSuggestion]: ...

    # -- shared retry mechanics ----------------------------------------------

    def _run(self, operation: Callable[[], T]) -> T:
        attempt = 1
        while True:
            try:
                return operation()
            except SuggestionError as error:
                if not error.transient or attempt >= self._max_attempts:
                    raise
                self._sleep(self._backoff_seconds * 2 ** (attempt - 1))
                attempt += 1
