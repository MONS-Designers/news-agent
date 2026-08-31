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
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.api.deps import get_db
from newsagent.branding import LOGO_DATA_URI
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

# Answers "does the click work without a login" by construction: this page
# needs nothing from the frontend SPA, so it renders identically whether or
# not the reader is signed in on this device. Previously the click redirected
# into the SPA at /?feedback=thanks, whose confirmation toast only mounts
# when a session is active (frontend/src/App.vue: `<FeedbackWidget v-if="me">`)
# - a signed-out click was recorded but looked like nothing happened.
_THANKS_HTML = """<!doctype html>
<html dir="rtl" lang="he">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>תודה</title>
</head>
<body style="margin:0; padding:0; background-color:#1c2333; direction:rtl; font-family:'Segoe UI',Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="min-height:100vh; background-color:#1c2333;">
<tr><td align="center" style="padding:48px 24px;">
<table role="presentation" width="360" cellpadding="0" cellspacing="0" style="max-width:360px; width:100%; background-color:#0b1020; border-radius:16px; border:1px solid rgba(240,180,41,.22);">
<tr><td style="padding:36px 28px; text-align:center;">
<a href="__HOME_URL__" style="text-decoration:none;">
<img src="__LOGO__" width="32" height="32" alt="NewsAgent" style="display:block; margin:0 auto 18px; border-radius:8px;">
</a>
<div style="font-size:36px; margin-bottom:14px;">__EMOJI__</div>
<div style="font-size:18px; font-weight:700; color:#ffffff; margin-bottom:8px;">תודה!</div>
<div style="font-size:14px; color:#a3adc4; line-height:1.6;">זה יעזור לי לשלוח לך כתבות רלוונטיות בדייג'סט הבא.</div>
</td></tr>
</table>
</td></tr>
</table>
<script>
  // Best-effort: browsers only honor window.close() on a tab the page's own
  // script opened, so a tab reached via a normal link click (the email tap
  // that lands here) is commonly left open by design - a silent no-op, not
  // an error. Clicking the logo before the timer fires navigates away first,
  // which cancels this naturally.
  setTimeout(function () { window.close(); }, 2000);
</script>
</body>
</html>"""


def _thanks_page(sentiment: str) -> HTMLResponse:
    emoji = "👍" if sentiment == "up" else "👎"
    html = (
        _THANKS_HTML.replace("__EMOJI__", emoji)
        .replace("__LOGO__", LOGO_DATA_URI)
        .replace("__HOME_URL__", settings.frontend_url)
    )
    return HTMLResponse(html)


@router.get("/t/{token}.gif")
def track_open(token: str, request: Request, db: Session = Depends(get_db)) -> Response:
    digest = db.scalar(select(Digest).where(Digest.tracking_token == token))
    if digest is not None and digest.opened_at is None:
        digest.opened_at = datetime.now()
        digest.opened_device_type = classify_device(request.headers.get("user-agent"))
        db.commit()
    return Response(content=_PIXEL, media_type="image/gif")


@router.get("/c/{token}")
def track_click(token: str, request: Request, db: Session = Depends(get_db)) -> Response:
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
        sentiment = FEEDBACK_KINDS[link.kind]
        # Recorded per click, not once per link: a reader who taps 👍 today and
        # 👎 next week on the same article has told us two different things.
        feedback.record(
            db,
            source=SOURCE_ARTICLE if link.article_id is not None else SOURCE_DIGEST,
            user_id=link.digest.user_id,
            digest_id=link.digest_id,
            article_id=link.article_id,
            sentiment=sentiment,
        )
        # Confirmed right here instead of redirecting into the frontend SPA:
        # that redirect's confirmation toast only mounts for a signed-in
        # session (App.vue: `<FeedbackWidget v-if="me">`), so a reader who
        # isn't logged in on this device had their feedback recorded but saw
        # no confirmation at all. This also drops the SPA's boot time from
        # what used to be the tap's only visible feedback.
        return _thanks_page(sentiment)
    return RedirectResponse(url=link.target_url)
