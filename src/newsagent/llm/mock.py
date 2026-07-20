"""Deterministic mock provider — deliberately boring.

Same input always yields the same output; no API key, no network. Scoring is
topic-token overlap; "translation" is a marker prefix. The `fail_*` knobs exist
only so the contract tests can exercise the shared retry mechanics — by default
the mock never fails.
"""

import hashlib
import re
from collections.abc import Sequence

from newsagent.llm.base import LLMProvider
from newsagent.llm.errors import LLMProviderError, LLMTransportError
from newsagent.llm.types import (
    ArticleInput,
    DigestVoice,
    Refusal,
    RelevanceScore,
    SummaryResult,
    Usage,
)

_MIN_TEXT_LENGTH = 40
_WORDS_PER_MINUTE = 200
_HEBREW_CHARS = re.compile(r"[֐-׿]")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w']+", text.lower())


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _emphasize_longest(sentence: str) -> str:
    """Wrap the single longest word in **markdown** emphasis (deterministic)."""
    words = sentence.split()
    if not words:
        return sentence
    target = max(words, key=len)
    return sentence.replace(target, f"**{target}**", 1)


# A small deterministic groaner pool — a real provider writes jokes tied to the
# actual headlines; the mock just picks one stably so tests never flake.
_DAD_JOKES = [
    "קראתי ספר על אנטי-גרביטציה — אי אפשר להניח אותו מהיד.",
    "למה האלגוריתם הלך לטיפול? היו לו יותר מדי בעיות לא פתורות.",
    "אמרתי למחשב שאני צריך הפסקה — הוא ענה: 'אין בעיה, אני כבר קורס'.",
    "איך קוראים לענן שמאחסן בדיחות? ענן גיבוי־חיוך.",
]


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

        # Deterministic bullets: first 3 sentences (or word-chunks as fallback),
        # each with its longest word emphasized via **markdown** markers.
        sentences = _split_sentences(article.text)
        if len(sentences) < 3:
            sentences = [" ".join(words[i : i + 8]) for i in range(0, len(words), 8)]
        bullets_he = tuple(
            f"[תרגום דמה] {_emphasize_longest(sentence)}" for sentence in sentences[:3]
        )

        # Deterministic interestingness in [0, 1] from a stable hash of the title.
        interestingness = (int(hashlib.sha1(article.title.encode()).hexdigest(), 16) % 1000) / 1000

        return SummaryResult(
            summary_he=summary_he,
            title_he=f"[תרגום דמה] {article.title}",
            source_language=source_language,
            reading_time_minutes=max(1, round(len(words) / _WORDS_PER_MINUTE)),
            bullets_he=bullets_he,
            interestingness=interestingness,
            usage=Usage(input_units=len(words), output_units=len(summary_he.split())),
        )

    def _compose_digest_voice(self, headlines: Sequence[str]) -> DigestVoice | Refusal:
        self._maybe_fail()
        if not headlines:
            return Refusal(reason="no headlines to compose a voice from")

        intro_he = (
            f"[דמה] בוקר טוב! ליקטתי עבורך {len(headlines)} כתבות נבחרות להיום. "
            "קריאה נעימה ☕"
        )
        # Stable joke pick from the day's headlines, so the same set → same joke.
        index = int(hashlib.sha1(" ".join(headlines).encode()).hexdigest(), 16) % len(_DAD_JOKES)
        dad_joke_he = f"[דמה] {_DAD_JOKES[index]}"
        return DigestVoice(
            intro_he=intro_he,
            dad_joke_he=dad_joke_he,
            usage=Usage(input_units=len(headlines), output_units=2),
        )
