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
