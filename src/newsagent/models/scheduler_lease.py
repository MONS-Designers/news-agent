from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from newsagent.models.base import Base

# The lease is a single, fixed row - there is one delivery loop, so there is
# one thing to hold. Using a constant id (rather than one row per holder) is
# what makes claiming it a single conditional UPDATE, which the database
# executes atomically.
LEASE_ID = 1


class SchedulerLease(Base):
    """Which scheduler process is currently allowed to deliver.

    Exists because sending is not idempotent across processes: two loops both
    reading `Digest.sent_at IS NULL` would each render and send the same
    digest. `welcomed_at` protects the one-time welcome, but nothing protected
    an ordinary digest.

    Time-based rather than a held database lock: a scheduler that is killed
    (a container stop, an OOM) never gets to release anything, so a lock that
    depends on an orderly release would block delivery until someone noticed.
    An expiring lease recovers on its own once `expires_at` passes.
    """

    __tablename__ = "scheduler_lease"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Opaque per-process identity, so a holder can tell its own lease from a
    # rival's and renew it instead of waiting for its own expiry.
    holder: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
