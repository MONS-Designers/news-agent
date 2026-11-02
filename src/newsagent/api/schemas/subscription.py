from pydantic import BaseModel


class SubscriptionOut(BaseModel):
    unsubscribed: bool
    # date.weekday() numbers (Monday=0), Sunday first.
    digest_weekdays: list[int]


class SubscriptionUpdateIn(BaseModel):
    # Both optional: a request changes only the fields it carries.
    unsubscribed: bool | None = None
    digest_weekdays: list[int] | None = None
