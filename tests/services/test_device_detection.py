import pytest

from newsagent.services.device_detection import classify_device

_IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
_IPAD_UA = (
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
_WINDOWS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_GOOGLEBOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


@pytest.mark.parametrize(
    "user_agent,expected",
    [
        (_IPHONE_UA, "mobile"),
        (_IPAD_UA, "tablet"),
        (_WINDOWS_UA, "desktop"),
        (_GOOGLEBOT_UA, "bot"),
    ],
)
def test_classifies_known_user_agents(user_agent: str, expected: str) -> None:
    assert classify_device(user_agent) == expected


def test_missing_user_agent_is_unknown() -> None:
    assert classify_device(None) == "unknown"


def test_empty_user_agent_is_unknown() -> None:
    assert classify_device("") == "unknown"


def test_gibberish_user_agent_is_unknown() -> None:
    assert classify_device("not a real user agent string") == "unknown"
