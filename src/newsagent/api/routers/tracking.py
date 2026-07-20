"""Public, unauthenticated open-tracking pixel for digest emails.

No auth: the token itself is the credential (unguessable, unique per digest).
Always returns the same pixel regardless of whether the token is valid, so the
endpoint can't be used to enumerate which tokens exist.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.api.deps import get_db
from newsagent.models import Digest

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
