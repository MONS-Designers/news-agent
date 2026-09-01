"""Digest HTML rendering (issue #13): Hebrew, RTL, inline-styled premium-
newspaper email. Renders the digest's already-selected articles in order;
every field rendered here was persisted by #11/#12/#25, so nothing is
recomputed or re-selected.

Keyword emphasis is applied safely: paragraph text is HTML-escaped first, then
``**markdown**`` markers become ``<strong>`` - provider output can never inject
markup.
"""

import html
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.branding import DIGEST_NOUN_WEEKLY, LOGO_DATA_URI, PRODUCT_NAME
from newsagent.config import settings
from newsagent.models import Article, Digest, User
from newsagent.models.digest_link import (
    KIND_ARTICLE,
    KIND_FEEDBACK_DOWN,
    KIND_FEEDBACK_UP,
    KIND_PREFERENCES,
    KIND_UNSUBSCRIBE,
    DigestLink,
)
from newsagent.models.user import first_name

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "j2"]),
)

_HEBREW_MONTHS = [
    "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
    "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
]

# Per-topic accent color for the category tag; unknown topics fall back. The
# tag's text is Topic.name itself - Hebrew since migration d7f3a4b91e28 - so
# there is no separate label map to keep in sync.
# Colors chosen (and verified) to clear WCAG AA 4.5:1 against the #0b1020 email
# background - see DESIGN.md.Colors in the ux-news-agent-2026-07-20 spine.
_TOPIC_COLORS = {"בינה מלאכותית": "#4ade80", "סייבר": "#f87171", "חלל": "#818cf8"}
_DEFAULT_TOPIC_COLOR = "#94a3b8"

# Punchline legibility cap (DESIGN.md: Gveret Levin is a connected handwriting
# face - keep it short so it stays charming instead of straining to read).
_MAX_PUNCHLINE_CHARS = 60

_BOLD = re.compile(r"\*\*(.+?)\*\*")
# Embedded LTR runs inside Hebrew copy (brand names, "GPT-4", "40%") - wrapped in
# <bdi> so mixed-direction text doesn't reorder unpredictably next to Hebrew
# punctuation/numerals.
_LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9%$.,'\-]*|\d+%")


def _hebrew_date(value) -> str:
    return f"{value.day} ב{_HEBREW_MONTHS[value.month - 1]} {value.year}"


def _wrap_bidi_runs(text: str) -> str:
    """Escape text to HTML, wrapping embedded Latin runs in <bdi> for bidi
    safety. Splits and escapes each segment separately on the RAW text first -
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
    provider output - escaping always happens before any tag is inserted, so
    nothing the provider writes can inject markup."""
    bidi_safe = _wrap_bidi_runs(text)
    return Markup(_BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", bidi_safe))


def _truncate_punchline(text: str) -> str:
    if len(text) <= _MAX_PUNCHLINE_CHARS:
        return text
    return text[: _MAX_PUNCHLINE_CHARS - 1].rsplit(" ", 1)[0] + "…"


# Inbox apps show the subject and the preheader side by side, so the preheader
# must say something the subject doesn't - send.py's _subject() already leads
# with the top article's headline, so repeating it here would read as a stutter.
_MAX_PREHEADER_CHARS = 90


def _truncate_preheader(text: str) -> str:
    text = text.strip()
    if len(text) <= _MAX_PREHEADER_CHARS:
        return text
    return text[: _MAX_PREHEADER_CHARS - 1].rsplit(" ", 1)[0] + "…"


@dataclass
class ArticleView:
    title_he: Markup
    paragraphs: list[Markup]
    reading_time_minutes: int
    url: str
    source_name: str
    topic_label: str
    topic_color: str
    feedback_up_url: str
    feedback_down_url: str


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
    paragraphs = article.paragraphs_he or ([article.summary_he] if article.summary_he else [])
    title = article.title_he or article.title
    link = _get_or_create_link(db, digest, KIND_ARTICLE, article.url, article=article)
    thanks_url = f"{settings.frontend_url}/?feedback=thanks"
    return ArticleView(
        title_he=_emphasize(title),
        paragraphs=[_emphasize(p) for p in paragraphs],
        reading_time_minutes=article.reading_time_minutes or 1,
        url=_click_url(link),
        source_name=article.source.name,
        topic_label=topic_name,
        topic_color=_TOPIC_COLORS.get(topic_name, _DEFAULT_TOPIC_COLOR),
        feedback_up_url=_click_url(
            _get_or_create_link(db, digest, KIND_FEEDBACK_UP, thanks_url, article=article)
        ),
        feedback_down_url=_click_url(
            _get_or_create_link(db, digest, KIND_FEEDBACK_DOWN, thanks_url, article=article)
        ),
    )


@dataclass
class WelcomeView:
    """The one-time beta welcome block. Composed here rather than in the
    template because which sentences apply depends on whether we know the
    reader's name and Field, and whether there is any content to show."""

    greeting: Markup | None
    lines: list[Markup]


def _welcome_view(user: User, *, has_articles: bool) -> WelcomeView:
    # Deliberately no fallback address: a bare "שלום," or "שלום, משתמש" reads
    # worse than opening straight into the message.
    #
    # The name is whatever Google gave us, verbatim - never transliterated.
    # Most Israeli accounts carry a Latin name, so "שלום Nomi," is a mixed-
    # direction line: without the <bdi> that _emphasize adds, bidi resolution
    # can drag the comma to the wrong side of the name. Same treatment the
    # article text already gets, applied here too rather than assumed unneeded.
    name = first_name(user)
    greeting = _emphasize(f"שלום {name},") if name else None

    # Every sentence stays free of second-person present tense, which Hebrew
    # cannot write without picking a gender. Past tense ("הצטרפת", "סיפרת",
    # "בחרת") and "אליך" are spelled identically for both, so the warm,
    # personal voice costs nobody a wrong assumption.
    lines = [
        "שמח שהצטרפת.",
        "ההזמנה הזו לא נשלחה לרשימת תפוצה. היא יצאה לקבוצה קטנה של אנשים "
        "שנבחרו בשם, וההזמנה הגיעה אליך.",
    ]
    chose = f"הרגע סיפרת לי שבחרת ב{user.field_name}, ומה מעניין אותך שם." if user.field_name else "הרגע סיפרת לי מה מעניין אותך."
    if has_articles:
        lines.append(f"{chose} הלכתי לקרוא, וזה מה שמצאתי. זו הריצה הראשונה שלי - מכאן אני מגיע פעם בשבוע.")
        lines.append(
            "אם משהו כאן פספס, כדאי לי לדעת. אני עוד לומד, ומה שיגיע ממך עכשיו "
            "יעצב את מה שיישלח בשבוע הבא."
        )
    else:
        lines.append(
            f"{chose} חלק מהנושאים שבחרת חדשים לגמרי אצלי, ואני עוד מחפש להם "
            "מקורות טובים - עדיף לי לחכות יום מאשר לשלוח רעש."
        )
        lines.append("הדייג'סט הראשון יגיע בימים הקרובים. משם, פעם בשבוע.")
    # Field names reach these lines from the database too, and can be Latin
    # ("DevOps"), so every line gets the same bidi treatment as the greeting.
    return WelcomeView(greeting=greeting, lines=[_emphasize(line) for line in lines])


def render_welcome_html(user: User) -> str:
    """The beta-only welcome, for a reader whose topics produced no articles
    yet (so `build_digests` created no Digest for them at all).

    Renders the same template with an empty article list. Every tracked link
    is absent by necessity - DigestLink and the open pixel both hang off a
    Digest row, and there is none here - so the links point straight at the
    app instead of through /c/.
    """
    template = _env.get_template("digest.html.j2")
    return template.render(
        digest_noun_weekly=DIGEST_NOUN_WEEKLY,
        digest_date=_hebrew_date(date.today()),
        welcome=_welcome_view(user, has_articles=False),
        articles=[],
        total_reading_time=0,
        preferences_url=f"{settings.frontend_url}/preferences",
        unsubscribe_url=f"{settings.frontend_url}/preferences",
        feedback_note_url=f"{settings.frontend_url}/?feedback=open",
        tracking_pixel_url=None,
        logo_url=LOGO_DATA_URI,
        home_url=settings.frontend_url,
        preheader_text=f"{PRODUCT_NAME} - ההזמנה שלך מוכנה",
    )


def render_digest_html(digest: Digest, db: Session) -> str:
    template = _env.get_template("digest.html.j2")

    articles = [entry.article for entry in digest.articles]
    views = [_to_view(db, digest, a) for a in articles]
    total_reading_time = sum(v.reading_time_minutes for v in views)

    # Distinct from the subject line on purpose - see _truncate_preheader.
    # The digest's own voice intro is a natural second line; if it isn't
    # there yet, the top article's opening line stands in (still different
    # text from the headline the subject already used).
    if digest.intro_he:
        preheader_text = _truncate_preheader(digest.intro_he)
    elif articles:
        top = articles[0]
        lead_paragraph = (top.paragraphs_he or [None])[0] or top.summary_he
        preheader_text = (
            # **markdown** stripped to plain text rather than run through
            # _emphasize: a preview snippet has no <strong> to render into.
            _truncate_preheader(_BOLD.sub(lambda m: m.group(1), lead_paragraph))
            if lead_paragraph
            else f"{DIGEST_NOUN_WEEKLY} שלך מוכן"
        )
    else:
        preheader_text = f"{PRODUCT_NAME} - {DIGEST_NOUN_WEEKLY} שלך"

    dad_joke_he = _truncate_punchline(digest.dad_joke_he) if digest.dad_joke_he else None

    preferences_link = _get_or_create_link(
        db, digest, KIND_PREFERENCES, f"{settings.frontend_url}/preferences"
    )
    unsubscribe_link = _get_or_create_link(
        db, digest, KIND_UNSUBSCRIBE, f"{settings.frontend_url}/preferences"
    )
    # Digest-level pair (article_id null): "how was this week's edition?", as
    # opposed to the per-article thumbs above.
    thanks_url = f"{settings.frontend_url}/?feedback=thanks"
    digest_up_link = _get_or_create_link(db, digest, KIND_FEEDBACK_UP, thanks_url)
    digest_down_link = _get_or_create_link(db, digest, KIND_FEEDBACK_DOWN, thanks_url)

    return template.render(
        digest_noun_weekly=DIGEST_NOUN_WEEKLY,
        digest_date=_hebrew_date(digest.date),
        # Only until the welcome has actually been delivered - send.py stamps
        # welcomed_at on success, so a failed send re-renders it next run.
        welcome=(
            _welcome_view(digest.user, has_articles=bool(articles))
            if digest.user.welcomed_at is None
            else None
        ),
        intro_he=digest.intro_he,
        dad_joke_he=dad_joke_he,
        joke_corner_title="קינוח",
        articles=views,
        total_reading_time=total_reading_time,
        preferences_url=_click_url(preferences_link),
        unsubscribe_url=_click_url(unsubscribe_link),
        digest_feedback_up_url=_click_url(digest_up_link),
        digest_feedback_down_url=_click_url(digest_down_link),
        feedback_note_url=f"{settings.frontend_url}/?feedback=open",
        tracking_pixel_url=f"{settings.backend_base_url}/t/{digest.tracking_token}.gif",
        logo_url=LOGO_DATA_URI,
        home_url=settings.frontend_url,
        preheader_text=preheader_text,
    )
