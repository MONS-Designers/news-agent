"""One-shot delivery pass for readers whose cadence is due.

The daily content pipeline invokes this module after fetch, filtering,
extraction, and summarization. Cadence still controls whether a reader gets a
digest; the daily invocation does not turn the weekly product into a daily one.

The first email is triggered by the final preferences save. The scheduled pass
also retries any welcome or digest that could not be delivered at that time.
"""

import logging
import socket
import time
import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

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


@dataclass
class TickReport:
    digests_sent: int = 0
    welcomes_sent: int = 0
    digests_failed: int = 0
    welcomes_failed: int = 0


def _unwelcomed_user_ids(
    db: Session, user_ids: Collection[int] | None = None
) -> list[int]:
    if user_ids is not None and not user_ids:
        return []

    pending = select(User.id).where(
        User.welcomed_at.is_(None), User.unsubscribed_at.is_(None)
    )
    if user_ids is not None:
        pending = pending.where(User.id.in_(user_ids))
    return list(db.scalars(pending))


def tick(
    db: Session,
    provider: LLMProvider,
    sender: EmailSender,
    today: date | None = None,
    *,
    user_ids: Collection[int] | None = None,
    welcome_only: bool = False,
) -> TickReport:
    """Build and send due digests, or a single new reader's first email.

    The scheduled pass processes all unwelcomed users and users due by cadence.
    The profile-save event passes one user ID with ``welcome_only=True`` so an
    unrelated signup cannot trigger another reader's regular digest.
    """
    unwelcomed_ids = _unwelcomed_user_ids(db, user_ids)
    digest_stage.build_digests(db, provider, today, user_ids=unwelcomed_ids)

    if not welcome_only:
        due_ids = cadence.due_user_ids(db, today)
        if user_ids is not None:
            allowed_ids = set(user_ids)
            due_ids = [user_id for user_id in due_ids if user_id in allowed_ids]
        digest_stage.build_digests(db, provider, today, user_ids=due_ids)

    digest_report = send_stage.send_pending_digests(db, sender, user_ids=user_ids)
    welcome_report = send_stage.send_pending_welcomes(db, sender, user_ids=user_ids)
    return TickReport(
        digests_sent=digest_report.sent,
        welcomes_sent=welcome_report.sent,
        digests_failed=digest_report.failed,
        welcomes_failed=welcome_report.failed,
    )


def run_once(
    *, user_ids: Collection[int] | None = None, welcome_only: bool = False
) -> TickReport | None:
    """Run one leased delivery pass and exit; ``None`` means another run owns it."""
    provider = get_llm_provider()
    sender = get_email_sender()
    holder = f"{socket.gethostname()}:{socket.getpid()}:{uuid.uuid4().hex[:8]}"

    with SessionLocal() as db:
        if not scheduler_lease.acquire(db, holder):
            logger.info("Another delivery run holds the lease; skipping this run")
            return None

        started = time.monotonic()
        try:
            report = tick(db, provider, sender, user_ids=user_ids, welcome_only=welcome_only)
        finally:
            try:
                scheduler_lease.release(db, holder)
            except Exception:
                logger.warning("Could not release the delivery lease; it will expire", exc_info=True)

        elapsed = time.monotonic() - started
        if elapsed > scheduler_lease.LEASE_SECONDS / 2:
            logger.warning(
                "Delivery pass took %.0fs, over half the %ds lease",
                elapsed,
                scheduler_lease.LEASE_SECONDS,
            )
        logger.info(
            "Delivery pass: %d digests, %d welcome-only, %d failed",
            report.digests_sent,
            report.welcomes_sent,
            report.digests_failed + report.welcomes_failed,
        )
        return report


def deliver_first_email_for_user(user_id: int) -> None:
    """Background task for the final profile/preferences save."""
    try:
        report = run_once(user_ids=[user_id], welcome_only=True)
        if report is None:
            logger.info(
                "First-email delivery for user %s deferred to the next scheduled pass",
                user_id,
            )
    except Exception:
        # The daily pass retries unwelcomed readers, so a transient provider or
        # database failure here must not fail the already-saved preferences.
        logger.exception("First-email delivery failed for user %s", user_id)


def main() -> int:
    """Command entry point used once after the daily content pipeline."""
    configure_logging()
    try:
        report = run_once()
    except Exception:
        logger.exception("Scheduled delivery pass failed")
        return 1

    if report is None:
        return 0
    if report.digests_failed or report.welcomes_failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
