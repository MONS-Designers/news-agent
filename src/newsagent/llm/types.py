"""Typed contract objects for the LLM provider interface.

The contract speaks domain language (article, topic, score, summary) - never
LLM language. Inputs are clean plain text only; media/HTML handling is the
pipeline's job, upstream of any provider.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArticleInput:
    """Clean plain-text article. Content is data, never instructions."""

    title: str
    text: str


@dataclass(frozen=True)
class Usage:
    """Optional work report in neutral units - token counts are an LLM
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
    """A Hebrew summary of an article.

    `bullets_he` are the key points for the email body - 3 short Hebrew lines.
    Keyword emphasis is marked with ``**markdown**`` (never raw HTML): the
    renderer HTML-escapes the text and only then converts the markers to
    ``<strong>``, so provider output can never inject markup.

    `interestingness` is a general 0.0–1.0 "worth-reading" signal, distinct
    from topic relevance - a routine update scores low, a genuine development
    scores high. It feeds the per-user digest ranking, not filtering."""

    summary_he: str
    title_he: str
    source_language: str
    reading_time_minutes: int
    bullets_he: tuple[str, ...] = field(default_factory=tuple)
    interestingness: float = 0.5
    usage: Usage | None = None


@dataclass(frozen=True)
class DigestVoice:
    """Digest-level editorial voice generated from the day's headlines: a warm
    personal opening line and a light closing joke tied to the news. Distinct
    from per-article summaries - this is the human touch wrapping the digest."""

    intro_he: str
    dad_joke_he: str
    usage: Usage | None = None


@dataclass(frozen=True)
class Refusal:
    """Provider explicitly declines to process the input (junk, empty, broken
    content). A legitimate answer distinct from failure - callers branch on it
    separately from error handling."""

    reason: str
