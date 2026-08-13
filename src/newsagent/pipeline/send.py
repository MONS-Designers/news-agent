"""Digest delivery stage (issue #13): render + send every digest not yet
sent, mark sent_at on success. A failed send leaves sent_at NULL — the next
run retries it, mirroring the retry pattern used across the pipeline.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.mail.base import EmailSendError, EmailSender
from newsagent.models import Digest
from newsagent.pipeline.render import render_digest_html

logger = logging.getLogger(__name__)


@dataclass
class SendReport:
    sent: int = 0
    failed: int = 0


def send_pending_digests(db: Session, sender: EmailSender) -> SendReport:
    report = SendReport()

    digests = db.scalars(select(Digest).where(Digest.sent_at.is_(None))).all()
    for digest in digests:
        html = render_digest_html(digest, db)
        subject = f"הדייג'סט השבועי שלך — {digest.date.isoformat()}"
        try:
            sender.send(digest.user.email, subject, html)
        except EmailSendError as error:
            report.failed += 1
            logger.warning("Send failed for digest %s: %s", digest.id, error)
            continue
        digest.sent_at = datetime.now()
        report.sent += 1
        db.commit()

    return report
