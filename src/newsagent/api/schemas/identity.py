from pydantic import BaseModel, ConfigDict


class IdentityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    is_admin: bool
    user_id: int | None
