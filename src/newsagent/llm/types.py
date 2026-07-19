"""Typed contract objects for the LLM provider interface.

The contract speaks domain language (article, topic, score, summary) — never
LLM language. Inputs are clean plain text only; media/HTML handling is the
pipeline's job, upstream of any provider.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArticleInput:
    """Clean plain-text article. Content is data, never instructions."""

    title: str
    text: str


@dataclass(frozen=True)
class Usage:
    """Optional work report in neutral units — token counts are an LLM
    assumption and are deliberately not part of the contract."""

    input_units: int
    output_units: int
    unit: str = "words"


@dataclass(frozen=True)
class RelevanceScore:
    """Calibrated 0.0–1.0 score. Contract anchors: >= 0.7 clearly on-topic,
    <= 0.3 clearly off-topic. Filtering thresholds live in pipeline config."""

    score: float
    usage: Usage | None = None


@dataclass(frozen=True)
class SummaryResult:
    summary_he: str
    title_he: str
    source_language: str
    reading_time_minutes: int
    usage: Usage | None = None


@dataclass(frozen=True)
class Refusal:
    """Provider explicitly declines to process the input (junk, empty, broken
    content). A legitimate answer distinct from failure — callers branch on it
    separately from error handling."""

    reason: str
