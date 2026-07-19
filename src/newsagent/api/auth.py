"""Session-based auth: identity resolution and route-guard dependencies.

The session cookie (signed by SessionMiddleware) stores the authenticated
Google email plus what it maps to in our DB: admin, user, or both. OAuth only
authenticates — it never creates rows.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.api.deps import get_db
from newsagent.models import Admin, User

SESSION_KEY = "identity"


@dataclass
class Identity:
    email: str
    is_admin: bool
    user_id: int | None


def resolve_identity(db: Session, email: str) -> Identity | None:
    """Map a verified Google email to our seeded Admin/User rows.

    Returns None when the email matches neither — the caller rejects the login.
    """
    admin = db.scalar(select(Admin).where(Admin.email == email))
    user = db.scalar(select(User).where(User.email == email))
    if admin is None and user is None:
        return None
    return Identity(email=email, is_admin=admin is not None, user_id=user.id if user else None)


def load_identity(request: Request) -> Identity | None:
    data = request.session.get(SESSION_KEY)
    if data is None:
        return None
    return Identity(**data)


def save_identity(request: Request, identity: Identity) -> None:
    request.session[SESSION_KEY] = {
        "email": identity.email,
        "is_admin": identity.is_admin,
        "user_id": identity.user_id,
    }


def clear_identity(request: Request) -> None:
    request.session.pop(SESSION_KEY, None)


def require_identity(request: Request) -> Identity:
    identity = load_identity(request)
    if identity is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")
    return identity


def require_admin(identity: Identity = Depends(require_identity)) -> Identity:
    if not identity.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return identity


def require_user(
    identity: Identity = Depends(require_identity),
    db: Session = Depends(get_db),
) -> User:
    if identity.user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No user account")
    user = db.get(User, identity.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User no longer exists")
    return user
