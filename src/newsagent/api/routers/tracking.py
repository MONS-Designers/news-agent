"""Public, unauthenticated open- and click-tracking endpoints for digest
emails (FR12, FR13).

No auth on either endpoint: the token itself is the credential (unguessable,
unique per digest / per link). The open pixel always returns the same image
regardless of whether the token is valid, so it can't be used to enumerate
which tokens exist. The click redirect can't offer that same guarantee - it
has to know the real destination to redirect to - but the token is still
unguessable, matching FR12's "same shape as the existing pixel" design.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.api.deps import get_db
from newsagent.config import settings
from newsagent.models import Digest, DigestLink
from newsagent.models.digest_link import KIND_UNSUBSCRIBE
from newsagent.services import subscription

router = APIRouter(tags=["tracking"])

# 1x1 transparent GIF
_PIXEL = bytes.fromhex(
    "47494638396101000100800000ffffff00000021f90401000000002c00000000010001000002024401003b"
)


@router.get("/t/{token}.gif")
def track_open(token: str, db: Session = Depends(get_db)) -> Response:
    digest = db.scalar(select(Digest).where(Digest.tracking_token == token))
    if digest is not None and digest.opened_at is None:
        digest.opened_at = datetime.now()
        db.commit()
    return Response(content=_PIXEL, media_type="image/gif")


@router.get("/c/{token}")
def track_click(token: str, db: Session = Depends(get_db)) -> RedirectResponse:
    link = db.scalar(select(DigestLink).where(DigestLink.token == token))
    if link is None:
        # Unknown/stale token: nowhere real to send them, so fall back to the
        # app itself rather than erroring.
        return RedirectResponse(url=settings.frontend_url)
    if link.clicked_at is None:
        link.clicked_at = datetime.now()
    # A click proves the digest was opened even if the tracking pixel's image
    # never loaded (image-blocking is the common case, not the exception).
    if link.digest.opened_at is None:
        link.digest.opened_at = datetime.now()
    db.commit()
    if link.kind == KIND_UNSUBSCRIBE:
        subscription.set_unsubscribed(db, link.digest.user, True)
    return RedirectResponse(url=link.target_url)
