"""Domain services for managing who may sign in: admins and users.

Kept in the domain layer (no FastAPI imports) so both the CLI and any future
API endpoint can reuse the same logic.
"""

from sqlalchemy import func, insert, literal, select
from sqlalchemy.orm import Session

from newsagent.models import Admin, User


def add_admin(db: Session, email: str) -> tuple[Admin, bool]:
    """Get-or-create an Admin by email. Returns (admin, created)."""
    normalized = email.strip().lower()
    existing = db.scalar(select(Admin).where(Admin.email == normalized))
    if existing is not None:
        return existing, False
    admin = Admin(email=normalized)
    db.add(admin)
    db.commit()
    return admin, True


def add_user(db: Session, email: str, name: str | None = None) -> tuple[User, bool]:
    """Get-or-create a User by email. Returns (user, created)."""
    normalized = email.strip().lower()
    existing = db.scalar(select(User).where(User.email == normalized))
    if existing is not None:
        return existing, False
    user = User(email=normalized, name=name)
    db.add(user)
    db.commit()
    return user, True


def register_user_if_capacity(db: Session, email: str, name: str | None, cap: int) -> User | None:
    """Create a User row for a brand-new email, but only if the total User
    count is still under `cap` - and do it atomically (FR3): the count check
    and the insert are one SQL statement (INSERT...SELECT...WHERE), not a
    separate count-then-insert from the application. Two concurrent callers
    racing for the last slot can never both succeed; SQLite's single-writer
    lock is held for the whole statement, so the second caller's subquery
    only runs after the first has committed and is already reflected in it.

    Returns the created User, or None if the cap was already full. Callers
    are expected to have already ruled out an existing Admin/User match for
    this email (this function does not check for that itself).
    """
    normalized = email.strip().lower()
    stmt = insert(User).from_select(
        ["email", "name"],
        select(literal(normalized), literal(name)).where(
            select(func.count()).select_from(User).scalar_subquery() < cap
        ),
    )
    result = db.execute(stmt)
    db.commit()
    if result.rowcount != 1:  # type: ignore[attr-defined]
        return None
    return db.scalar(select(User).where(User.email == normalized))
