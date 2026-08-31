from pydantic import BaseModel


class FeedbackIn(BaseModel):
    """In-app feedback. Both fields are optional but at least one must be
    present - a star alone, a note alone, or both are all valid. Over-long
    text is truncated by the service rather than rejected here."""

    rating: int | None = None
    text: str | None = None
