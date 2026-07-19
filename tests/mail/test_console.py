from pathlib import Path

import pytest

from newsagent.mail.console import ConsoleEmailSender

HEBREW_HTML = "<html dir='rtl'><body>שלום עולם</body></html>"


def test_send_prints_summary(capsys: pytest.CaptureFixture[str]):
    ConsoleEmailSender().send("user@example.com", "Daily digest", HEBREW_HTML)
    output = capsys.readouterr().out
    assert "user@example.com" in output
    assert "Daily digest" in output


def test_send_writes_html_to_outbox(tmp_path: Path):
    sender = ConsoleEmailSender(outbox_dir=tmp_path / "outbox")
    sender.send("user@example.com", "Daily digest", HEBREW_HTML)
    files = list((tmp_path / "outbox").glob("*.html"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == HEBREW_HTML
    assert "user@example.com" in files[0].name


def test_no_outbox_writes_no_files(tmp_path: Path):
    ConsoleEmailSender().send("user@example.com", "Daily digest", HEBREW_HTML)
    assert list(tmp_path.iterdir()) == []
