from pydantic import BaseModel, ConfigDict


class FieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str

class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class PendingTaxonomySuggestionOut(BaseModel):
    """One row of the admin Taxonomy Curation Queue (FR-6)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    field_name: str | None
    text: str
    submission_count: int
