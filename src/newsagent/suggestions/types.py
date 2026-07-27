"""Typed contract objects for the Suggestion Source interface.

The contract speaks domain language (field, role, topic) — never LLM
language, and never SQLAlchemy. Providers never query the DB (AD-3):
`TopicPopularity` is the plain aggregate data the calling service queries and
passes in.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RoleOption:
    """One generated Role option for a Field."""

    name: str


@dataclass(frozen=True)
class PromptText:
    """One Suggested Prompt shown near Interest Free-Text."""

    text: str


@dataclass(frozen=True)
class TopicPopularity:
    """Cross-user selection count for one Topic — plain aggregate data the
    calling service queries and passes in; providers never query the DB."""

    topic_id: int
    selection_count: int


@dataclass(frozen=True)
class TopicSuggestion:
    """One candidate Topic returned by `suggest_topics`."""

    topic_id: int
