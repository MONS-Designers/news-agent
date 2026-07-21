from pydantic import BaseModel, ConfigDict


class TopicPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    topic_id: int
    name: str
    subscribed: bool


class PreferenceUpdateIn(BaseModel):
    topic_ids: list[int]
