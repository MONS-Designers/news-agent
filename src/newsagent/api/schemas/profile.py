from pydantic import BaseModel, ConfigDict


class ProfileUpdateIn(BaseModel):
    field_name: str
    is_other: bool = False


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field_name: str | None
