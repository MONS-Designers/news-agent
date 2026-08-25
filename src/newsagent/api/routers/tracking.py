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

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.api.deps import get_db
from newsagent.config import settings
from newsagent.models import Digest, DigestLink
from newsagent.models.digest_link import FEEDBACK_KINDS, KIND_UNSUBSCRIBE
from newsagent.models.feedback import SOURCE_ARTICLE, SOURCE_DIGEST
from newsagent.services import feedback, subscription
from newsagent.services.device_detection import classify_device

router = APIRouter(tags=["tracking"])

# 1x1 transparent GIF
_PIXEL = bytes.fromhex(
    "47494638396101000100800000ffffff00000021f90401000000002c00000000010001000002024401003b"
)


@router.get("/t/{token}.gif")
def track_open(token: str, request: Request, db: Session = Depends(get_db)) -> Response:
    digest = db.scalar(select(Digest).where(Digest.tracking_token == token))
    if digest is not None and digest.opened_at is None:
        digest.opened_at = datetime.now()
        digest.opened_device_type = classify_device(request.headers.get("user-agent"))
        db.commit()
    return Response(content=_PIXEL, media_type="image/gif")


@router.get("/c/{token}")
def track_click(token: str, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    link = db.scalar(select(DigestLink).where(DigestLink.token == token))
    if link is None:
        # Unknown/stale token: nowhere real to send them, so fall back to the
        # app itself rather than erroring.
        return RedirectResponse(url=settings.frontend_url)
    if link.clicked_at is None:
        link.clicked_at = datetime.now()
        link.device_type = classify_device(request.headers.get("user-agent"))
    # A click proves the digest was opened even if the tracking pixel's image
    # never loaded (image-blocking is the common case, not the exception).
    if link.digest.opened_at is None:
        link.digest.opened_at = datetime.now()
        link.digest.opened_device_type = classify_device(request.headers.get("user-agent"))
    db.commit()
    if link.kind == KIND_UNSUBSCRIBE:
        subscription.set_unsubscribed(db, link.digest.user, True)
    elif link.kind in FEEDBACK_KINDS:
        # Recorded per click, not once per link: a reader who taps 👍 today and
        # 👎 next week on the same article has told us two different things.
        feedback.record(
            db,
            source=SOURCE_ARTICLE if link.article_id is not None else SOURCE_DIGEST,
            user_id=link.digest.user_id,
            digest_id=link.digest_id,
            article_id=link.article_id,
            sentiment=FEEDBACK_KINDS[link.kind],
        )
    return RedirectResponse(url=link.target_url)
