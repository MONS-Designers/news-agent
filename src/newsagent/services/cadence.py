"""Who is due for a digest right now.

The single place that turns a reader's chosen weekdays into a yes/no for
today. Kept apart from pipeline/digest.py on purpose: the build stage decides
*what* goes in a digest, this decides *whether* one is owed at all, and the
scheduler is the only thing that needs both.

A reader picks fixed weekdays, Sunday to Friday - never Saturday. The frequency
is not stored: it is derived from how many days are chosen (six = daily,
two = twice weekly, one = weekly), so the two can never disagree. Days are
evaluated in Israel time, whatever timezone the server runs in.

A chosen day that passes without a send (the scheduler was down) is not made
up the next day. Nothing is lost by that: the build stage selects articles not
yet sent, so they roll into the reader's next digest.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from newsagent.models import Digest, User
from newsagent.models.user import DEFAULT_DIGEST_WEEKDAYS

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

# date.weekday() numbers, in the order of an Israeli week: Sunday first.
SEND_WEEKDAYS: tuple[int, ...] = (6, 0, 1, 2, 3, 4)

DAILY = "daily"
TWICE_WEEKLY = "twice_weekly"
WEEKLY = "weekly"

_FREQUENCY_BY_DAY_COUNT: dict[int, str] = {
    len(SEND_WEEKDAYS): DAILY,
    2: TWICE_WEEKLY,
    1: WEEKLY,
}


def local_today(now: datetime | None = None) -> date:
    """Today's date in Israel - the date a reader means by "Sunday"."""
    return (now or datetime.now(ISRAEL_TZ)).astimezone(ISRAEL_TZ).date()


def frequency_of(weekdays: object) -> str | None:
    """The frequency a day set amounts to, or None if it is not a valid one."""
    if not isinstance(weekdays, list) or any(type(day) is not int for day in weekdays):
        return None
    days = set(weekdays)
    if len(days) != len(weekdays) or not days <= set(SEND_WEEKDAYS):
        return None
    return _FREQUENCY_BY_DAY_COUNT.get(len(days))


def effective_weekdays(stored: object) -> list[int]:
    """The days a reader actually gets mail on, Sunday first. An invalid stored
    value falls back to the default - a row written by an older or newer
    version of the app must not stop that reader's mail."""
    if frequency_of(stored) is None:
        return list(DEFAULT_DIGEST_WEEKDAYS)
    return sorted(stored, key=SEND_WEEKDAYS.index)  # type: ignore[arg-type]


def due_user_ids(db: Session, today: date | None = None) -> list[int]:
    """Ids of subscribed users for whom `today` is a chosen day and who have not
    been sent a digest dated today yet.

    Only a *sent* digest counts: one that was built but never delivered is
    retried on the same day rather than skipped until the next chosen day.

    Cheap by design - one grouped query, no per-user work - because the
    scheduler calls this on every tick and the answer is usually "nobody".
    """
    if today is None:
        today = local_today()

    last_sent = (
        select(Digest.user_id, func.max(Digest.date).label("last_date"))
        .where(Digest.sent_at.is_not(None))
        .group_by(Digest.user_id)
        .subquery()
    )
    rows = db.execute(
        select(User.id, User.digest_weekdays, last_sent.c.last_date)
        .outerjoin(last_sent, last_sent.c.user_id == User.id)
        .where(User.unsubscribed_at.is_(None))
    ).all()

    return [
        user_id
        for user_id, weekdays, last_date in rows
        if today.weekday() in effective_weekdays(weekdays)
        and (last_date is None or last_date < today)
    ]
