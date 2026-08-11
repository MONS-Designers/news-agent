from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from newsagent.api import auth
from newsagent.api.deps import get_db
from newsagent.api.schemas import IdentityOut
from newsagent.config import settings
from newsagent.models import User
from newsagent.services.waitlist import capture_to_waitlist

router = APIRouter(prefix="/auth", tags=["auth"])

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured (NEWSAGENT_GOOGLE_CLIENT_ID missing)",
        )
    redirect_uri = str(request.url_for("callback"))
    response: RedirectResponse = await oauth.google.authorize_redirect(request, redirect_uri)
    return response


def _redirect_destination(db: Session, identity: auth.Identity) -> str:
    """Where to send a just-signed-in identity. A freshly self-registered
    user (no profile yet) lands on the home page's first-run state (UX-DR6)
    rather than straight into the wizard, so they get a welcome/context beat
    first; everyone else goes to their usual landing spot.
    """
    if identity.is_admin:
        return "/admin"
    user = db.get(User, identity.user_id) if identity.user_id is not None else None
    return "/" if user is not None and user.field_name is None else "/preferences"


@router.get("/callback")
async def callback(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse(f"{settings.frontend_url}/?error=oauth_failed")

    userinfo = token.get("userinfo")
    email = userinfo.get("email") if userinfo else None
    if not email:
        return RedirectResponse(f"{settings.frontend_url}/?error=oauth_failed")
    name = userinfo.get("name") if userinfo else None

    identity = auth.resolve_identity(db, email, name=name, cap=settings.max_users)
    if identity is None:
        # Brand-new email, but the registration cap is already full — leave a
        # real trace (FR11) instead of a dead-end sign-in attempt.
        capture_to_waitlist(db, email, name)
        return RedirectResponse(f"{settings.frontend_url}/?error=capacity_full")

    auth.save_identity(request, identity)
    destination = _redirect_destination(db, identity)
    return RedirectResponse(f"{settings.frontend_url}{destination}")


@router.get("/me", response_model=IdentityOut)
def me(identity: auth.Identity = Depends(auth.require_identity)) -> auth.Identity:
    return identity


@router.post("/logout")
def logout(request: Request) -> dict[str, str]:
    auth.clear_identity(request)
    return {"status": "signed_out"}
