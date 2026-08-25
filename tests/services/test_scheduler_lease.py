from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsagent.models import SchedulerLease
from newsagent.models.base import Base
from newsagent.models.scheduler_lease import LEASE_ID
from newsagent.services.scheduler_lease import acquire, release


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_first_process_acquires_the_lease(db: Session):
    assert acquire(db, "alice") is True


def test_second_process_is_locked_out(db: Session):
    """The whole point: two schedulers, only one delivers."""
    acquire(db, "alice")

    assert acquire(db, "bob") is False


def test_holder_can_renew_its_own_lease(db: Session):
    """Renewal on every tick is what keeps a working holder from expiring
    out from under itself."""
    acquire(db, "alice")

    assert acquire(db, "alice") is True


def test_renewal_pushes_the_expiry_forward(db: Session):
    acquire(db, "alice", ttl_seconds=60)
    first = db.scalar(select(SchedulerLease.expires_at))

    acquire(db, "alice", ttl_seconds=600)
    second = db.scalar(select(SchedulerLease.expires_at))

    assert second > first


def test_an_expired_lease_is_taken_over(db: Session):
    """A scheduler that was killed never releases anything - delivery must
    resume on its own rather than waiting for a human."""
    acquire(db, "alice")
    lease = db.get(SchedulerLease, LEASE_ID)
    lease.expires_at = datetime.now() - timedelta(seconds=1)
    db.commit()

    assert acquire(db, "bob") is True
    assert db.get(SchedulerLease, LEASE_ID).holder == "bob"


def test_a_live_lease_is_not_stolen_by_the_takeover_path(db: Session):
    acquire(db, "alice", ttl_seconds=600)

    assert acquire(db, "bob") is False
    assert db.get(SchedulerLease, LEASE_ID).holder == "alice"


def test_release_lets_a_replacement_start_at_once(db: Session):
    acquire(db, "alice")

    release(db, "alice")

    assert acquire(db, "bob") is True


def test_release_by_a_non_holder_does_nothing(db: Session):
    """A departing straggler must not free the lease of whoever replaced it."""
    acquire(db, "alice")

    release(db, "bob")

    assert acquire(db, "bob") is False
