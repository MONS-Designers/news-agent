"""Domain services for managing who may sign in: admins and users.

Kept in the domain layer (no FastAPI imports) so both the CLI and any future
API endpoint can reuse the same logic.
"""

from sqlalchemy import select
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
