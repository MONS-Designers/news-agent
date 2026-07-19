import pytest

from newsagent.config import settings
from newsagent.mail.console import ConsoleEmailSender
from newsagent.mail.factory import get_email_sender


def test_default_sender_is_console():
    assert isinstance(get_email_sender(), ConsoleEmailSender)


def test_unknown_sender_raises_clear_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "email_sender", "no-such-sender")
    with pytest.raises(ValueError, match="no-such-sender"):
        get_email_sender()
