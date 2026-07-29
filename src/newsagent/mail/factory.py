"""Sender selection — swapping providers is a one-line config change
(NEWSAGENT_EMAIL_SENDER)."""

from pathlib import Path

from newsagent.config import settings
from newsagent.mail.base import EmailSender
from newsagent.mail.console import ConsoleEmailSender
from newsagent.mail.smtp import SmtpEmailSender


def get_email_sender() -> EmailSender:
    if settings.email_sender == "console":
        outbox = Path(settings.email_outbox_dir) if settings.email_outbox_dir else None
        return ConsoleEmailSender(outbox_dir=outbox)
    if settings.email_sender == "smtp":
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            from_address=settings.smtp_from_address,
            use_tls=settings.smtp_use_tls,
        )
    raise ValueError(f"Unknown email sender {settings.email_sender!r} (known: console, smtp)")
