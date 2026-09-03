from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from newsagent.models.base import Base

if TYPE_CHECKING:
    from newsagent.models.article import Article
    from newsagent.models.digest import Digest
    from newsagent.models.user import User

SENTIMENT_UP = "up"
SENTIMENT_DOWN = "down"

# The in-app widget (SOURCE_APP) asks a different question than the email
# thumbs - "how's the product overall?" vs. "was this one article good?" - so
# it collects a 1-5 star rating instead of up/down. Stored in the same
# `sentiment` column as its string digit ("1".."5") rather than a new column:
# the column is already a free-form nullable string with no DB-level
# constraint, and SOURCE_APP is the only source that ever writes a rating, so
# there's no ambiguity reading it back.
RATING_CHOICES = (1, 2, 3, 4, 5)

# Where the reader was when they told us. Not derivable from the nullable FKs:
# a digest-level thumb and a footer note both carry digest_id and no article_id.
SOURCE_ARTICLE = "article"
SOURCE_DIGEST = "digest"
SOURCE_APP = "app"


class Feedback(Base):
    """One thing a reader told us, from any of the three entry points (email
    thumb, email footer note, in-app button).

    Deliberately append-only and permissive: no unique constraint, both
    `sentiment` and `text` nullable, and `user_id` nullable. A beta reader
    tapping 👍 twice leaves two rows, which is honest data - deduplicating
    would silently discard a second, later opinion. The point of this table is
    that leaving feedback never fails.
    """

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable: an email thumb is authenticated by the DigestLink token, not by
    # a session, and the digest may outlive the user row.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    digest_id: Mapped[int | None] = mapped_column(ForeignKey("digests.id"), nullable=True)
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), nullable=True)
    source: Mapped[str] = mapped_column(String)
    sentiment: Mapped[str | None] = mapped_column(String, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User | None"] = relationship()
    digest: Mapped["Digest | None"] = relationship()
    article: Mapped["Article | None"] = relationship()
