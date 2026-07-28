"""Non-LLM popularity-based fallback adapter (FR-9).

MVP default and the only always-available path: no API key, no network, no DB
access of its own. `suggest_roles`/`suggest_prompts` have nothing to generate
without a connected LLM-backed source, so they return empty (FR-2/FR-5
assumptions) — only `suggest_topics` is real.
"""

from collections.abc import Sequence

from newsagent.suggestions.base import SuggestionSource
from newsagent.suggestions.types import PromptText, RoleOption, TopicPopularity, TopicSuggestion


class PopularitySuggestionSource(SuggestionSource):
    def _suggest_roles(
        self, field_name: str, *, existing_roles: Sequence[str] = ()
    ) -> list[RoleOption]:
        return []

    def _suggest_prompts(
        self,
        *,
        field_name: str | None = None,
        role_name: str | None = None,
        experience_bucket: str | None = None,
    ) -> list[PromptText]:
        return []

    def _suggest_topics(
        self,
        *,
        field_name: str | None,
        role_name: str | None,
        interest_free_text: str | None,
        popularity: Sequence[TopicPopularity],
    ) -> list[TopicSuggestion]:
        # Deliberately ignores field_name/role_name/interest_free_text — a
        # popularity ranking that doesn't key off the user's profile is what
        # makes this the fallback, not a targeted suggestion. Stable sort so a
        # deterministic input ordering (as the calling service would produce
        # from a real query) yields a deterministic result.
        ranked = sorted(popularity, key=lambda p: p.selection_count, reverse=True)
        return [TopicSuggestion(topic_id=p.topic_id) for p in ranked]
