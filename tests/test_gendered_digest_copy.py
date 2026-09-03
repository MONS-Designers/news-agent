"""Regression guard for GH #61 (gendered Hebrew copy) on the digest email
template. Mirrors frontend/src/__tests__/gendered-copy.spec.ts, scoped to
digest.html.j2 per that issue's DoD #4. See CLAUDE.md's "Gender-neutral
Hebrew copy" section for the house style this guards against regressing.

Targeted scan, not a parser - see the frontend counterpart's docstring for
the same caveats (word-initial imperative detection only, small deliberately
non-exhaustive denylist, "אשר" excluded for its legitimate "which/that" use).
"""

import re
from pathlib import Path

_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent / "src" / "newsagent" / "templates" / "digest.html.j2"
)

_HEBREW_LETTER = "א-ת"

# Unambiguous wherever they appear.
_ANYWHERE_OFFENDERS = ["אתה", "תוכל"]

# Same denylist as the frontend guard - bare masculine imperatives as they
# tend to actually show up: a standalone label, or the first word of a
# sentence.
_SENTENCE_START_OFFENDERS = [
    "בחר", "הקש", "בטל", "התחבר", "פנה", "דחה", "קדם", "רענן",
    "חזור", "בוא", "לחץ", "מחק", "שמור", "טען", "נסה", "בדוק",
]


def _find_anywhere_offenders(text: str) -> list[str]:
    hits = []
    for word in _ANYWHERE_OFFENDERS:
        pattern = rf"(?<![{_HEBREW_LETTER}]){word}(?![{_HEBREW_LETTER}])"
        if re.search(pattern, text):
            hits.append(word)
    return hits


def _find_sentence_start_offenders(text: str) -> list[str]:
    hits = []
    for word in _SENTENCE_START_OFFENDERS:
        pattern = rf"[\"'>]\s*{word}(?=[\s\"'<])"
        if re.search(pattern, text):
            hits.append(word)
    return hits


def test_digest_template_has_no_gendered_copy():
    text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    anywhere = [f'"{w}" (pronoun/modal)' for w in _find_anywhere_offenders(text)]
    sentence_start = [f'"{w}" (bare imperative)' for w in _find_sentence_start_offenders(text)]
    assert anywhere + sentence_start == []
