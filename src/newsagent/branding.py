"""The Hebrew noun the product calls its weekly email.

Centralized because it is still an open product decision and it appears in the
subject line, the masthead, and the email body. The frontend carries its own
copy in frontend/src/branding.ts - change both together.
"""

# Placeholder until the naming decision lands - deliberately still the original
# word, so nothing ships under a name nobody approved.
DIGEST_NOUN = "הדייג'סט"
DIGEST_NOUN_WEEKLY = "הדייג'סט השבועי"

# The subject line leads with the product, not the product's noun for its own
# email - the reader recognizes the sender before they parse the wording.
PRODUCT_NAME = "NewsAgent"
