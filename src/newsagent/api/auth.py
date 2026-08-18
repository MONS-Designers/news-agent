"""Session-based auth: identity resolution and route-guard dependencies.

The session cookie (signed by SessionMiddleware) stores the authenticated
Google email plus what it maps to in our DB: admin, user, or both.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.api.deps import get_db
from newsagent.models import Admin, User
from newsagent.services.identity import register_user_if_capacity

SESSION_KEY = "identity"


@dataclass
class Identity:
    email: str
    is_admin: bool
    user_id: int | None


def resolve_identity(db: Session, email: str, name: str | None = None, cap: int = 10) -> Identity | None:
    """Map a verified Google email to our seeded Admin/User rows - or, for a
    brand-new email with room under the registration cap, create one (FR1).

    An Admin with no User row is also a self-registration candidate: it goes
    through the same capacity-gated creation as anyone else, so an admin who
    wants to subscribe to their own digest counts against the same cap as
    everyone else - no special exemption. The one thing that never changes is
    that an Admin always signs in: if the cap is full, they just keep
    `user_id=None` instead of being turned away.

    Returns None only when the email has no Admin row either *and* the cap is
    already full - the caller then routes to the waitlist (FR11) instead of
    signing anyone in. This is the only place a User row is created from an
    unauthenticated-until-this-point request; reached only after Google's
    OAuth callback has already verified the email.
    """
    admin = db.scalar(select(Admin).where(Admin.email == email))
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        return Identity(email=email, is_admin=admin is not None, user_id=user.id)

    created = register_user_if_capacity(db, email, name, cap)
    if created is not None:
        return Identity(email=email, is_admin=admin is not None, user_id=created.id)
    if admin is not None:
        return Identity(email=email, is_admin=True, user_id=None)
    return None


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
