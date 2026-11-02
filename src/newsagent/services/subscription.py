"""Digest delivery settings - the opt-out switch (GH #46) and which weekdays
the digest arrives on (GH #59, #63), independent of *which* topics a user
picks (that's services/preferences.py).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from newsagent.models import User
from newsagent.services import cadence


def set_unsubscribed(db: Session, user: User, unsubscribed: bool) -> User:
    if unsubscribed and user.unsubscribed_at is None:
        user.unsubscribed_at = datetime.now()
        db.commit()
    elif not unsubscribed and user.unsubscribed_at is not None:
        user.unsubscribed_at = None
        db.commit()
    return user


def frequency_allowed(user: User, frequency: str) -> bool:
    """Whether this reader may use `frequency`. Every frequency is free today;
    each will carry its own price later, and that entitlement check belongs
    here - the one server-side gate - never only in the UI."""
    return True


def set_digest_weekdays(db: Session, user: User, weekdays: list[int]) -> User:
    """Raises ValueError for a day set that is not a valid frequency, or one this
    reader is not allowed; nothing is stored in either case."""
    frequency = cadence.frequency_of(weekdays)
    if frequency is None:
        raise ValueError("Choose one day, two days, or every day from Sunday to Friday")
    if not frequency_allowed(user, frequency):
        raise ValueError(f"Frequency not available: {frequency}")
    user.digest_weekdays = cadence.effective_weekdays(weekdays)
    db.commit()
    return user
