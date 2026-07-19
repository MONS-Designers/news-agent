from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from newsagent.api import auth
from newsagent.api.deps import get_db
from newsagent.api.schemas import IdentityOut
from newsagent.config import settings

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

    identity = auth.resolve_identity(db, email)
    if identity is None:
        # Authenticated with Google but not seeded as admin or user — reject.
        return RedirectResponse(f"{settings.frontend_url}/?error=unauthorized")

    auth.save_identity(request, identity)
    destination = "/admin" if identity.is_admin else "/preferences"
    return RedirectResponse(f"{settings.frontend_url}{destination}")


@router.get("/me", response_model=IdentityOut)
def me(identity: auth.Identity = Depends(auth.require_identity)) -> auth.Identity:
    return identity


@router.post("/logout")
def logout(request: Request) -> dict[str, str]:
    auth.clear_identity(request)
    return {"status": "signed_out"}
