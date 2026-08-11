import smtplib
from email import message_from_string

import pytest

from newsagent.mail.base import EmailSendError
from newsagent.mail.smtp import SmtpEmailSender

HEBREW_HTML = "<html dir='rtl'><body>שלום עולם</body></html>"


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
    # encoding) — decode before checking content, not a raw substring match.
    parsed = message_from_string(message)
    body = parsed.get_payload(decode=True).decode("utf-8")
    assert "שלום עולם" in body


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
