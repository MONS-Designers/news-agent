"""The delivery loop - the scheduler lives in this codebase, not in infra cron.

Run as a long-lived process alongside the API:

    python -m newsagent.scheduler

Each tick does two independent passes:

  1. First email - anyone who finished setup and has not been welcomed yet.
     Ungated by cadence: their clock has not started, and the promise made at
     signup is "in a few minutes", so this is what makes the tick interval
     matter at all.
  2. Regular cadence - whoever services/cadence.py says is due today, at
     whatever frequency each of them chose.

Both passes are bounded by a query that usually returns nobody, so an idle
tick costs two SELECTs and no LLM call. That, not the interval, is what makes
a two-minute loop affordable.

Fetching, filtering and summarizing are NOT here - they stay in the daily
pipeline run. This loop only selects from already-summarized articles and
delivers, which is why it is cheap enough to run continuously.

Two kinds of overlap could cause duplicate mail, and both are handled:

  * Within this process there is none by construction - the loop is
    sequential and sleeps *after* the tick returns, so a slow tick delays the
    next one instead of running alongside it. The interval is a minimum gap,
    not a wall-clock schedule. (A real cron would not give this for free.)
  * Across processes, a lease row (services/scheduler_lease.py) lets exactly
    one instance deliver at a time; the rest skip their tick. Extra replicas
    are therefore harmless, and a killed holder's lease expires so delivery
    resumes without anyone intervening.
"""

import logging
import os
import signal
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import date
from types import FrameType

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.db import SessionLocal
from newsagent.llm import get_llm_provider
from newsagent.llm.base import LLMProvider
from newsagent.logging_setup import configure_logging
from newsagent.mail import get_email_sender
from newsagent.mail.base import EmailSender
from newsagent.models import User
from newsagent.pipeline import digest as digest_stage
from newsagent.pipeline import send as send_stage
from newsagent.services import cadence, scheduler_lease

logger = logging.getLogger(__name__)

TICK_SECONDS = 120


@dataclass
class TickReport:
    digests_sent: int = 0
    welcomes_sent: int = 0


def _unwelcomed_user_ids(db: Session) -> list[int]:
    return list(
        db.scalars(
            select(User.id).where(
                User.welcomed_at.is_(None), User.unsubscribed_at.is_(None)
            )
        )
    )


def tick(
    db: Session, provider: LLMProvider, sender: EmailSender, today: date | None = None
) -> TickReport:
    """One pass. Safe to call repeatedly - every write it drives is guarded by
    `welcomed_at` or `sent_at`, so a tick that follows a completed one does
    nothing.

    Both build passes run before the single send pass: `send_pending_digests`
    delivers whatever is unsent regardless of which pass created it, so
    sending between the two builds would only split one mailing in half.
    """
    digest_stage.build_digests(db, provider, today, user_ids=_unwelcomed_user_ids(db))
    digest_stage.build_digests(db, provider, today, user_ids=cadence.due_user_ids(db, today))

    return TickReport(
        digests_sent=send_stage.send_pending_digests(db, sender).sent,
        welcomes_sent=send_stage.send_pending_welcomes(db, sender).sent,
    )


_stopping = False


def _request_stop(signum: int, frame: FrameType | None) -> None:
    """Finish the tick in flight, then exit - a container stop must not kill
    the process between rendering an email and marking it sent."""
    global _stopping
    logger.info("Signal %s received; stopping after this tick", signum)
    _stopping = True


def run() -> None:
    configure_logging()
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    provider = get_llm_provider()
    sender = get_email_sender()
    holder = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    logger.info("Scheduler started (tick every %ss, holder %s)", TICK_SECONDS, holder)

    while not _stopping:
        try:
            with SessionLocal() as db:
                if not scheduler_lease.acquire(db, holder):
                    logger.debug("Another scheduler holds the lease; skipping tick")
                else:
                    started = time.monotonic()
                    report = tick(db, provider, sender)
                    elapsed = time.monotonic() - started

                    # Overrunning the lease is the one way a second process
                    # could start delivering while this one is still working,
                    # so surface it well before it becomes possible.
                    if elapsed > scheduler_lease.LEASE_SECONDS / 2:
                        logger.warning(
                            "Tick took %.0fs, over half the %ds lease - raise "
                            "LEASE_SECONDS before it can be stolen mid-send",
                            elapsed,
                            scheduler_lease.LEASE_SECONDS,
                        )
                    if report.digests_sent or report.welcomes_sent:
                        logger.info(
                            "Tick: %d digests, %d welcome-only",
                            report.digests_sent,
                            report.welcomes_sent,
                        )
        except Exception:
            # One bad tick (a dropped DB connection, a provider outage) must
            # not end the loop - the next tick retries everything, since no
            # work is marked done until it succeeds.
            logger.exception("Tick failed; continuing")

        for _ in range(TICK_SECONDS):
            if _stopping:
                break
            time.sleep(1)

    # Hand the lease back so a replacement container can start delivering at
    # once instead of idling until the TTL runs out.
    try:
        with SessionLocal() as db:
            scheduler_lease.release(db, holder)
    except Exception:
        logger.warning("Could not release the lease; it will expire", exc_info=True)

    logger.info("Scheduler stopped")


if __name__ == "__main__":
    run()
