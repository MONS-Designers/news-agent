"""Who is due for a digest right now.

The single place that turns a reader's chosen frequency into a yes/no for
today. Kept apart from pipeline/digest.py on purpose: the build stage decides
*what* goes in a digest, this decides *whether* one is owed at all, and the
scheduler is the only thing that needs both.

Cadence is expressed as a minimum number of days between sends rather than
fixed weekdays. That keeps "twice a week" an approximation - every third day,
not a standing Sunday/Wednesday slot. Exact weekdays would need a real
schedule model (which days, in whose timezone); if that is ever wanted, this
is the module to grow, and nothing outside it should learn about days.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from newsagent.models import Digest, User
from newsagent.models.user import (
    FREQUENCY_DAILY,
    FREQUENCY_TWICE_WEEKLY,
    FREQUENCY_WEEKLY,
)

INTERVAL_DAYS: dict[str, int] = {
    FREQUENCY_DAILY: 1,
    FREQUENCY_TWICE_WEEKLY: 3,
    FREQUENCY_WEEKLY: 7,
}

DEFAULT_FREQUENCY = FREQUENCY_WEEKLY


def interval_days(frequency: str | None) -> int:
    """Days between sends for `frequency`, falling back to the default for an
    unknown value - a row written by an older or newer version of the app must
    not stop that reader's mail."""
    return INTERVAL_DAYS.get(frequency or "", INTERVAL_DAYS[DEFAULT_FREQUENCY])


def due_user_ids(db: Session, today: date | None = None) -> list[int]:
    """Ids of subscribed users whose next digest is owed on or before `today`.

    A user who has never been sent one is due immediately. Measured from the
    last *sent* digest's date, not the last built one: a digest that was built
    but never delivered has not started the reader's clock.

    Cheap by design - one grouped query, no per-user work - because the
    scheduler calls this on every tick and the answer is usually "nobody".
    """
    if today is None:
        today = date.today()

    last_sent = (
        select(Digest.user_id, func.max(Digest.date).label("last_date"))
        .where(Digest.sent_at.is_not(None))
        .group_by(Digest.user_id)
        .subquery()
    )
    rows = db.execute(
        select(User.id, User.digest_frequency, last_sent.c.last_date)
        .outerjoin(last_sent, last_sent.c.user_id == User.id)
        .where(User.unsubscribed_at.is_(None))
    ).all()

    return [
        user_id
        for user_id, frequency, last_date in rows
        if last_date is None or (today - last_date).days >= interval_days(frequency)
    ]
