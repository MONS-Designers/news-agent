"""Digest HTML rendering (issue #13): Hebrew, RTL, inline-styled premium-
newspaper email. Renders the digest's already-selected articles in order;
every field rendered here was persisted by #11/#12/#25, so nothing is
recomputed or re-selected.

Keyword emphasis is applied safely: bullet text is HTML-escaped first, then
``**markdown**`` markers become ``<strong>`` — provider output can never inject
markup.
"""

import html
import re
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.config import settings
from newsagent.models import Article, Digest
from newsagent.models.digest_link import KIND_ARTICLE, KIND_PREFERENCES, KIND_UNSUBSCRIBE, DigestLink

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "j2"]),
)

_HEBREW_MONTHS = [
    "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
    "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
]

# Per-topic category tag: Hebrew label + accent color. Unknown topics fall back.
# Colors chosen (and verified) to clear WCAG AA 4.5:1 against the #0b1020 email
# background — see DESIGN.md.Colors in the ux-news-agent-2026-07-20 spine.
_TOPIC_LABELS = {"AI": "בינה מלאכותית", "Cybersecurity": "סייבר", "Space": "חלל"}
_TOPIC_COLORS = {"AI": "#4ade80", "Cybersecurity": "#f87171", "Space": "#818cf8"}
_DEFAULT_TOPIC_COLOR = "#94a3b8"

# Punchline legibility cap (DESIGN.md: Gveret Levin is a connected handwriting
# face — keep it short so it stays charming instead of straining to read).
_MAX_PUNCHLINE_CHARS = 60

_BOLD = re.compile(r"\*\*(.+?)\*\*")
# Embedded LTR runs inside Hebrew copy (brand names, "GPT-4", "40%") — wrapped in
# <bdi> so mixed-direction text doesn't reorder unpredictably next to Hebrew
# punctuation/numerals.
_LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9%$.,'\-]*|\d+%")


def _hebrew_date(value) -> str:
    return f"{value.day} ב{_HEBREW_MONTHS[value.month - 1]} {value.year}"


def _wrap_bidi_runs(text: str) -> str:
    """Escape text to HTML, wrapping embedded Latin runs in <bdi> for bidi
    safety. Splits and escapes each segment separately on the RAW text first —
    running the Latin regex on already-escaped text would match letters inside
    entity references (e.g. "lt" in "&lt;") and corrupt them."""
    parts = []
    pos = 0
    for match in _LATIN_RUN.finditer(text):
        parts.append(html.escape(text[pos : match.start()]))
        parts.append(f"<bdi>{html.escape(match.group(0))}</bdi>")
        pos = match.end()
    parts.append(html.escape(text[pos:]))
    return "".join(parts)


def _emphasize(text: str) -> Markup:
    """Escape + bidi-wrap, then turn **markdown** into <strong>. Safe for
    provider output — escaping always happens before any tag is inserted, so
    nothing the provider writes can inject markup."""
    bidi_safe = _wrap_bidi_runs(text)
    return Markup(_BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", bidi_safe))


def _truncate_punchline(text: str) -> str:
    if len(text) <= _MAX_PUNCHLINE_CHARS:
        return text
    return text[: _MAX_PUNCHLINE_CHARS - 1].rsplit(" ", 1)[0] + "…"


@dataclass
class ArticleView:
    title_he: Markup
    bullets: list[Markup]
    reading_time_minutes: int
    url: str
    source_name: str
    topic_label: str
    topic_color: str
    image_url: str | None
    # Plain-text title for the image alt attribute: what a reader with images
    # blocked sees instead of the picture (issue #24). Kept separate from
    # title_he, which carries <bdi>/<strong> markup that can't live in an attr.
    alt_text: str


def _get_or_create_link(
    db: Session, digest: Digest, kind: str, target_url: str, article: Article | None = None
) -> DigestLink:
    """Get-or-create a click-trackable link for this digest (FR12). Same
    get-or-create idempotency as services/sources.py: a retried send re-renders
    the same digest and must reuse the same token, not mint a new one."""
    article_id = article.id if article is not None else None
    existing = db.scalar(
        select(DigestLink).where(
            DigestLink.digest_id == digest.id,
            DigestLink.kind == kind,
            DigestLink.article_id == article_id,
        )
    )
    if existing is not None:
        return existing
    link = DigestLink(digest_id=digest.id, kind=kind, article_id=article_id, target_url=target_url)
    db.add(link)
    db.commit()
    return link


def _click_url(link: DigestLink) -> str:
    return f"{settings.backend_base_url}/c/{link.token}"


def _to_view(db: Session, digest: Digest, article: Article) -> ArticleView:
    topic_name = article.source.topic.name
    bullets = article.bullets_he or ([article.summary_he] if article.summary_he else [])
    title = article.title_he or article.title
    link = _get_or_create_link(db, digest, KIND_ARTICLE, article.url, article=article)
    return ArticleView(
        title_he=_emphasize(title),
        bullets=[_emphasize(b) for b in bullets],
        reading_time_minutes=article.reading_time_minutes or 1,
        url=_click_url(link),
        source_name=article.source.name,
        topic_label=_TOPIC_LABELS.get(topic_name, topic_name),
        topic_color=_TOPIC_COLORS.get(topic_name, _DEFAULT_TOPIC_COLOR),
        image_url=article.image_url,
        alt_text=title,
    )


def render_digest_html(digest: Digest, db: Session) -> str:
    template = _env.get_template("digest.html.j2")

    articles = [entry.article for entry in digest.articles]
    views = [_to_view(db, digest, a) for a in articles]
    total_reading_time = sum(v.reading_time_minutes for v in views)

    dad_joke_he = _truncate_punchline(digest.dad_joke_he) if digest.dad_joke_he else None

    preferences_link = _get_or_create_link(
        db, digest, KIND_PREFERENCES, f"{settings.frontend_url}/preferences"
    )
    unsubscribe_link = _get_or_create_link(
        db, digest, KIND_UNSUBSCRIBE, f"{settings.frontend_url}/preferences"
    )

    return template.render(
        digest_date=_hebrew_date(digest.date),
        intro_he=digest.intro_he,
        dad_joke_he=dad_joke_he,
        joke_corner_title="קינוח",
        articles=views,
        total_reading_time=total_reading_time,
        preferences_url=_click_url(preferences_link),
        unsubscribe_url=_click_url(unsubscribe_link),
        tracking_pixel_url=f"{settings.backend_base_url}/t/{digest.tracking_token}.gif",
    )
