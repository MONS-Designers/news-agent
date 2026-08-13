from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DigestEngagementOut(BaseModel):
    """One row of the admin Engagement view (FR13), serialized from
    `services.engagement.DigestEngagement`."""

    model_config = ConfigDict(from_attributes=True)

    digest_id: int
    user_email: str
    date: date
    sent_at: datetime | None
    opened_at: datetime | None
    articles_total: int
    articles_clicked: int
    clicked_article_titles: list[str]
    preferences_clicked: bool
