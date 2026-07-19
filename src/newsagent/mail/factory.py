"""Sender selection — swapping providers is a one-line config change
(NEWSAGENT_EMAIL_SENDER)."""

from pathlib import Path

from newsagent.config import settings
from newsagent.mail.base import EmailSender
from newsagent.mail.console import ConsoleEmailSender


def get_email_sender() -> EmailSender:
    if settings.email_sender == "console":
        outbox = Path(settings.email_outbox_dir) if settings.email_outbox_dir else None
        return ConsoleEmailSender(outbox_dir=outbox)
    raise ValueError(f"Unknown email sender {settings.email_sender!r} (known: console)")
