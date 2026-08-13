from pydantic import BaseModel


class SubscriptionOut(BaseModel):
    unsubscribed: bool


class SubscriptionUpdateIn(BaseModel):
    unsubscribed: bool
