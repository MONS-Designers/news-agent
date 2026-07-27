from pydantic import BaseModel, ConfigDict


class ProfileUpdateIn(BaseModel):
    field_name: str
    field_is_other: bool = False
    role_name: str | None = None
    role_is_other: bool = False


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field_name: str | None
    role_name: str | None
