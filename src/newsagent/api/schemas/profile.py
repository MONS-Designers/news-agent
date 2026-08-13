from pydantic import BaseModel, ConfigDict


class ProfileUpdateIn(BaseModel):
    field_name: str | None = None
    field_is_other: bool = False
    role_name: str | None = None
    role_is_other: bool = False
    experience_bucket: str | None = None
    interest_free_text: str | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field_name: str | None
    role_name: str | None
    experience_bucket: str | None
    interest_free_text: str | None


class TopicSuggestionsOut(BaseModel):
    """GET /me/topic-suggestions - the only read path for suggestion state
    (AD-7). Deliberately not merged into ProfileOut."""

    model_config = ConfigDict(from_attributes=True)

    suggestion_status: str
    suggested_topic_ids: list[int] | None
    suggested_new_topic_names: list[str] | None
