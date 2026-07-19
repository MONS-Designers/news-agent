"""Email sender contract — same swappable-adapter pattern as newsagent.llm.

The pipeline sends only through this interface; a real provider (Resend, SES,
SMTP) is added later as another adapter with no pipeline changes.
"""

from abc import ABC, abstractmethod


class EmailSendError(Exception):
    """Sending failed. Adapters translate vendor errors into this."""


class EmailSender(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, html_body: str) -> None:
        """Deliver one HTML email. Raises EmailSendError on failure."""
