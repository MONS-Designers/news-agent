from pydantic import BaseModel, ConfigDict


class TopicPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
