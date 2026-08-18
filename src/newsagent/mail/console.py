"""Local-dev sender: prints a compact summary to stdout and, when an outbox
directory is configured, writes the full HTML body to a file so Hebrew/RTL
rendering can be checked in a browser. No API key, no network."""

import re
from datetime import datetime
from pathlib import Path

from newsagent.mail.base import EmailSender


class ConsoleEmailSender(EmailSender):
    def __init__(self, outbox_dir: Path | None = None) -> None:
        self._outbox_dir = outbox_dir

    def send(self, to: str, subject: str, html_body: str) -> None:
        print(f"[email] to={to} subject={subject!r} ({len(html_body)} chars html)")
        if self._outbox_dir is not None:
            self._outbox_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            safe_to = re.sub(r"[^\w.@-]", "_", to)
            path = self._outbox_dir / f"{stamp}-{safe_to}.html"
            path.write_text(html_body, encoding="utf-8")
            print(f"[email] written to {path}")
