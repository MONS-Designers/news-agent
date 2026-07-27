from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from newsagent.api.auth import require_admin
from newsagent.api.deps import get_db
from newsagent.api.schemas import PendingTaxonomySuggestionOut
from newsagent.services import taxonomy

# Own file, not an extension of admin.py: source approval and taxonomy approval
# are two independent review concerns that merely share a shape (AD-10).
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/taxonomy", response_model=list[PendingTaxonomySuggestionOut])
def list_pending_taxonomy_suggestions(
    db: Session = Depends(get_db),
) -> list[taxonomy.PendingSuggestionView]:
    return taxonomy.list_pending_suggestions(db)
