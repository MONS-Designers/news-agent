"""Domain service for the self-registration waitlist (FR11) — captures a
brand-new email that arrived after the registration cap was full, so a
capacity-full sign-in attempt leaves a real trace instead of nothing.
"""

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from newsagent.models import Waitlist


def capture_to_waitlist(db: Session, email: str, name: str | None) -> Waitlist:
    """Add (or refresh) a waitlist entry for `email` — one atomic upsert, not
    a select-then-branch (the TOCTOU pattern already flagged elsewhere in
    this codebase for get-or-create helpers). A repeat attempt for the same
    email updates `name`/`captured_at` in place rather than creating a
    duplicate row (AC3).
    """
    normalized = email.strip().lower()
    stmt = sqlite_insert(Waitlist).values(email=normalized, name=name)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Waitlist.email],
        set_={"name": stmt.excluded.name, "captured_at": func.now()},
    )
    db.execute(stmt)
    db.commit()
    entry = db.scalar(select(Waitlist).where(Waitlist.email == normalized))
    assert entry is not None  # just upserted — must exist
    return entry
