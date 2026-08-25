"""Digest delivery stage (issue #13): render + send every digest not yet
sent, mark sent_at on success. A failed send leaves sent_at NULL - the next
run retries it, mirroring the retry pattern used across the pipeline.

Known and accepted: sending happens before the `sent_at` commit, so a process
killed between the two re-sends an email the reader already received. SMTP and
the database share no transaction, so the window cannot be closed, only
pointed the other way (at-most-once, which risks losing a digest instead).
This ordering deliberately favours a rare duplicate over a silent loss - see
`_bmad-output/implementation-artifacts/deferred-work.md` (2026-08-24) for the
alternatives that were weighed. The scheduler lease does not help here: it
prevents concurrent delivery, not crash recovery.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.branding import DIGEST_NOUN_WEEKLY, PRODUCT_NAME
from newsagent.mail.base import EmailSendError, EmailSender
from newsagent.models import Digest, User
from newsagent.pipeline.render import render_digest_html, render_welcome_html

logger = logging.getLogger(__name__)

# Gmail on mobile shows roughly this much of a subject line. The headline is
# trimmed to fit rather than truncated mid-sentence, so the hook survives the
# preview instead of trailing off.
_MAX_SUBJECT_HEADLINE_CHARS = 52


@dataclass
class SendReport:
    sent: int = 0
    failed: int = 0


def _first_name(user: User) -> str | None:
    return user.name.split()[0] if user.name and user.name.strip() else None


def _welcome_subject(user: User) -> str:
    """The first email's climax is getting in, not any one headline."""
    name = _first_name(user)
    opening = f"{name}, ה" if name else "ה"
    return f"{opening}דייג'סט הראשון שלך מוכן."


def _subject(digest: Digest) -> str:
    """Lead with the digest's top-ranked headline, not the date - the subject
    line is the only thing competing for the open, and a date never earned one.
    `digest.articles` is in the order build_digests attached them, which is
    ranked order, so the first entry is the strongest story."""
    if digest.user.welcomed_at is None:
        return _welcome_subject(digest.user)
    if not digest.articles:
        return f"{PRODUCT_NAME} · {DIGEST_NOUN_WEEKLY} שלך"
    top = digest.articles[0].article
    headline = (top.title_he or top.title).strip()
    if len(headline) > _MAX_SUBJECT_HEADLINE_CHARS:
        headline = headline[:_MAX_SUBJECT_HEADLINE_CHARS].rsplit(" ", 1)[0] + "…"
    return f"{PRODUCT_NAME} · {headline}"


def send_pending_digests(db: Session, sender: EmailSender) -> SendReport:
    report = SendReport()

    # A user who unsubscribed (GH #46) after their digest was already built
    # but before it was sent must not receive it - build_digests skips them
    # going forward, but this catches the same-run race.
    digests = db.scalars(
        select(Digest)
        .join(User)
        .where(Digest.sent_at.is_(None), User.unsubscribed_at.is_(None))
    ).all()
    for digest in digests:
        html = render_digest_html(digest, db)
        try:
            sender.send(digest.user.email, _subject(digest), html)
        except EmailSendError as error:
            report.failed += 1
            logger.warning("Send failed for digest %s: %s", digest.id, error)
            continue
        digest.sent_at = datetime.now()
        # Stamped only after a successful send, in the same commit: a failed
        # send leaves both null, so the retry still carries the welcome rather
        # than silently downgrading the reader's first email to a plain digest.
        if digest.user.welcomed_at is None:
            digest.user.welcomed_at = datetime.now()
        report.sent += 1
        db.commit()

    return report


def send_pending_welcomes(db: Session, sender: EmailSender) -> SendReport:
    """The beta-only welcome, for a reader who finished setup but whose topics
    produced nothing to send yet - `build_digests` creates no Digest at all in
    that case, so `send_pending_digests` above would never reach them and the
    promised "email in a few minutes" would just be silence.

    Scoped to users who have actually completed a profile: a signed-in visitor
    who never picked anything has not asked for mail.
    """
    report = SendReport()
    users = db.scalars(
        select(User).where(
            User.welcomed_at.is_(None),
            User.unsubscribed_at.is_(None),
            User.field_name.is_not(None),
            ~User.digests.any(),
        )
    ).all()
    for user in users:
        html = render_welcome_html(user)
        try:
            sender.send(user.email, _welcome_subject(user), html)
        except EmailSendError as error:
            report.failed += 1
            logger.warning("Welcome send failed for user %s: %s", user.id, error)
            continue
        user.welcomed_at = datetime.now()
        report.sent += 1
        db.commit()

    return report
