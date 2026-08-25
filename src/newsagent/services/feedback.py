"""Domain service for reader feedback.

One write path for all three entry points (email thumb, email footer note,
in-app button) so they can never drift apart in what they record. Recording is
append-only and never rejects a duplicate - see models/feedback.py.
"""

from sqlalchemy.orm import Session

from newsagent.models import Feedback

# An in-app note is the only unbounded input here; the email paths carry no free
# text. Mirrors the cap style used in services/profile.py.
MAX_TEXT_LENGTH = 2000


def record(
    db: Session,
    *,
    source: str,
    user_id: int | None = None,
    digest_id: int | None = None,
    article_id: int | None = None,
    sentiment: str | None = None,
    text: str | None = None,
) -> Feedback:
    """Persist one piece of feedback. Over-long text is truncated rather than
    rejected: losing the tail of a long note is a better outcome than throwing
    away the whole thing and showing the reader an error."""
    cleaned = text.strip()[:MAX_TEXT_LENGTH] if text else None
    entry = Feedback(
        user_id=user_id,
        digest_id=digest_id,
        article_id=article_id,
        source=source,
        sentiment=sentiment,
        text=cleaned or None,
    )
    db.add(entry)
    db.commit()
    return entry
