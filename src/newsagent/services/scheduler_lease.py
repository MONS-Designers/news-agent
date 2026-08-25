"""Mutual exclusion for the delivery loop.

One conditional UPDATE decides it. The database applies `UPDATE ... WHERE` as
a single atomic statement, so when two processes race, exactly one sees
rowcount 1 and the other sees 0 - no read-then-write window for them to both
pass through.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsagent.models.scheduler_lease import LEASE_ID, SchedulerLease

logger = logging.getLogger(__name__)

# Generously longer than any realistic tick, because expiry is what lets a
# rival take over: if a tick ever outlasts the lease, a second process could
# start delivering while the first is still mid-send - exactly the duplicate
# this module exists to prevent. Renewed at the start of every tick, so the
# only way to reach expiry is for the holder to actually stop.
LEASE_SECONDS = 600


def acquire(db: Session, holder: str, ttl_seconds: int = LEASE_SECONDS) -> bool:
    """Claim or renew the delivery lease. True means this process may deliver.

    Succeeds when the lease is unclaimed, expired, or already held by
    `holder`; fails when a different live process holds it.
    """
    now = datetime.now()
    expires_at = now + timedelta(seconds=ttl_seconds)

    claimed = db.execute(
        update(SchedulerLease)
        .where(
            SchedulerLease.id == LEASE_ID,
            or_(SchedulerLease.holder == holder, SchedulerLease.expires_at <= now),
        )
        .values(holder=holder, expires_at=expires_at)
    ).rowcount

    if claimed:
        db.commit()
        return True

    # rowcount 0 is ambiguous: either a rival holds a live lease, or the row
    # has never been created. Try to create it - the primary key makes this
    # safe under a race, and the loser simply reports "not acquired".
    db.rollback()
    try:
        db.add(SchedulerLease(id=LEASE_ID, holder=holder, expires_at=expires_at))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def release(db: Session, holder: str) -> None:
    """Expire this process's lease on a clean shutdown, so a replacement can
    start immediately instead of waiting out the full TTL. Best-effort: if it
    fails, the lease still expires on its own."""
    db.execute(
        update(SchedulerLease)
        .where(SchedulerLease.id == LEASE_ID, SchedulerLease.holder == holder)
        .values(expires_at=datetime.now())
    )
    db.commit()
