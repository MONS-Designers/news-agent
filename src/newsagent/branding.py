"""The Hebrew noun the product calls its weekly email.

Centralized because it is still an open product decision and it appears in the
subject line, the masthead, and the email body. The frontend carries its own
copy in frontend/src/branding.ts - change both together.
"""

from pathlib import Path

# Placeholder until the naming decision lands - deliberately still the original
# word, so nothing ships under a name nobody approved.
DIGEST_NOUN = "הדייג'סט"
DIGEST_NOUN_WEEKLY = "הדייג'סט השבועי"

# The subject line leads with the product, not the product's noun for its own
# email - the reader recognizes the sender before they parse the wording.
PRODUCT_NAME = "NewsAgent"

# Inlined as a data URI rather than referencing the frontend's deployed
# /logo-mark.png: a browser/email client fetches images from wherever the
# markup points, and that URL depends on the frontend's deployed domain
# matching settings.frontend_url exactly - the same class of drift that broke
# OAuth login when frontend/backend moved to split subdomains (see CLAUDE.md,
# "Cross-repo integration"). Shipping the bytes with the backend package
# removes the dependency entirely. Shared by the digest template and the
# tracking router's feedback-thanks page.
LOGO_DATA_URI = "data:image/png;base64," + (
    Path(__file__).resolve().parent / "templates" / "assets" / "logo-mark.b64"
).read_text().strip()
