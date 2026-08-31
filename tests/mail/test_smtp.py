import base64
import smtplib
from email import message_from_string

import pytest

from newsagent.mail.base import EmailSendError
from newsagent.mail.smtp import SmtpEmailSender

HEBREW_HTML = "<html dir='rtl'><body>שלום עולם</body></html>"

# A real (tiny, 1x1) PNG - the sender base64-decodes it, so garbage bytes
# would fail rather than exercise the actual path.
_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
HTML_WITH_INLINE_LOGO = (
    f'<html><body><img src="data:image/png;base64,{_TINY_PNG_B64}"></body></html>'
)


class _FakeSMTP:
    instances: list["_FakeSMTP"] = []

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host = host
        self.port = port
        self.started_tls = False
        self.login_args: tuple[str, str] | None = None
        self.sent: tuple[str, list[str], str] | None = None
        _FakeSMTP.instances.append(self)

    def __enter__(self) -> "_FakeSMTP":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def sendmail(self, from_addr: str, to_addrs: list[str], message: str) -> None:
        self.sent = (from_addr, to_addrs, message)


@pytest.fixture(autouse=True)
def _reset_fake_smtp() -> None:
    _FakeSMTP.instances = []


def _sender(**overrides: object) -> SmtpEmailSender:
    kwargs: dict = dict(
        host="smtp.example.com",
        port=587,
        username="user@example.com",
        password="secret",
        from_address="digest@example.com",
        use_tls=True,
    )
    kwargs.update(overrides)
    return SmtpEmailSender(**kwargs)


def test_send_logs_in_and_delivers(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    _sender().send("reader@example.com", "Daily digest", HEBREW_HTML)

    smtp = _FakeSMTP.instances[0]
    assert (smtp.host, smtp.port) == ("smtp.example.com", 587)
    assert smtp.started_tls is True
    assert smtp.login_args == ("user@example.com", "secret")
    from_addr, to_addrs, message = smtp.sent
    assert from_addr == "digest@example.com"
    assert to_addrs == ["reader@example.com"]
    assert "Daily digest" in message
    # Hebrew body is base64-encoded (non-ASCII, MIMEText's default transfer
    # encoding) - decode before checking content, not a raw substring match.
    parsed = message_from_string(message)
    body = parsed.get_payload(decode=True).decode("utf-8")
    assert "שלום עולם" in body


def test_from_header_carries_product_display_name(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    _sender().send("reader@example.com", "Daily digest", HEBREW_HTML)

    _, _, message = _FakeSMTP.instances[0].sent
    parsed = message_from_string(message)
    assert parsed["From"] == "NewsAgent <digest@example.com>"


def test_inline_data_uri_image_becomes_a_cid_attachment(monkeypatch: pytest.MonkeyPatch):
    # Gmail (and other clients) commonly refuse to render a raw data: URI in
    # an actual received email even though it renders fine in a browser -
    # confirmed live, 2026-08-31. Content-ID is the universally-supported way
    # to embed an image in an email, so the sender rewrites it right before
    # the wire send.
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    _sender().send("reader@example.com", "Subject", HTML_WITH_INLINE_LOGO)

    _, _, message = _FakeSMTP.instances[0].sent
    parsed = message_from_string(message)
    assert parsed.is_multipart()

    html_part = next(p for p in parsed.walk() if p.get_content_type() == "text/html")
    html_body = html_part.get_payload(decode=True).decode("utf-8")
    assert "data:image/png" not in html_body
    assert 'src="cid:inline-image-0"' in html_body

    image_part = next(p for p in parsed.walk() if p.get_content_maintype() == "image")
    assert image_part["Content-ID"] == "<inline-image-0>"
    assert image_part["Content-Disposition"] == "inline"
    assert image_part.get_payload(decode=True) == base64.b64decode(_TINY_PNG_B64)


def test_html_without_a_data_uri_image_stays_a_plain_message(monkeypatch: pytest.MonkeyPatch):
    # No embedded image to convert - stays the simple single-part message it
    # always was, rather than always paying for multipart/related.
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    _sender().send("reader@example.com", "Subject", HEBREW_HTML)

    _, _, message = _FakeSMTP.instances[0].sent
    assert message_from_string(message).is_multipart() is False


def test_use_tls_false_skips_starttls(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    _sender(use_tls=False).send("reader@example.com", "Daily digest", HEBREW_HTML)
    assert _FakeSMTP.instances[0].started_tls is False


def test_smtp_failure_raises_email_send_error(monkeypatch: pytest.MonkeyPatch):
    class _FailingSMTP(_FakeSMTP):
        def login(self, username: str, password: str) -> None:
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    monkeypatch.setattr(smtplib, "SMTP", _FailingSMTP)
    with pytest.raises(EmailSendError):
        _sender().send("reader@example.com", "Daily digest", HEBREW_HTML)
