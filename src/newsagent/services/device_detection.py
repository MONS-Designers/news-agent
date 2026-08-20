"""Classifies the device that made a request, from its User-Agent header, for
digest open/click engagement analytics (see api.routers.tracking)."""

from user_agents import parse


def classify_device(user_agent: str | None) -> str:
    """One of "mobile", "tablet", "desktop", "bot", "unknown"."""
    if not user_agent:
        return "unknown"
    parsed = parse(user_agent)
    if parsed.is_bot:
        return "bot"
    if parsed.is_tablet:
        return "tablet"
    if parsed.is_mobile:
        return "mobile"
    if parsed.is_pc:
        return "desktop"
    return "unknown"
