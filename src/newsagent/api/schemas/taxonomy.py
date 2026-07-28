from typing import Literal

from pydantic import BaseModel, ConfigDict


class FieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str

class RoleOut(BaseModel):
    """One Role option in the Step 1 picker — curated or LLM-suggested
    (serialized from `taxonomy.RoleSuggestionView`, not a raw `Role` — an
    uncurated suggestion has no real `Role.id`, so this carries no `id` at
    all rather than a fake/optional one)."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    is_curated: bool


class PendingTaxonomySuggestionOut(BaseModel):
    """One row of the admin Taxonomy Curation Queue (FR-6)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    field_name: str | None
    text: str
    submission_count: int


class TaxonomySuggestionDecision(BaseModel):
    """Promote (`approved`) or dismiss (`rejected`) one queued suggestion.

    `name` overrides the curated Field/Role name that gets written — rows
    predating the `raw_text` column carry only casefolded text, so the admin
    corrects the spelling before it becomes a user-visible option.
    """

    status: Literal["approved", "rejected"]
    name: str | None = None
