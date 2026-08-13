"""Digest delivery opt-out (GH #46) - a self-service on/off switch,
independent of *which* topics a user picks (that's services/preferences.py).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from newsagent.models import User


def set_unsubscribed(db: Session, user: User, unsubscribed: bool) -> User:
    if unsubscribed and user.unsubscribed_at is None:
        user.unsubscribed_at = datetime.now()
        db.commit()
    elif not unsubscribed and user.unsubscribed_at is not None:
        user.unsubscribed_at = None
        db.commit()
    return user
