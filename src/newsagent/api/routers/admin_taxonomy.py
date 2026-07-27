from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from newsagent.api.auth import require_admin
from newsagent.api.deps import get_db
from newsagent.api.schemas import PendingTaxonomySuggestionOut, TaxonomySuggestionDecision
from newsagent.services import taxonomy

# Own file, not an extension of admin.py: source approval and taxonomy approval
# are two independent review concerns that merely share a shape (AD-10).
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/taxonomy", response_model=list[PendingTaxonomySuggestionOut])
def list_pending_taxonomy_suggestions(
    db: Session = Depends(get_db),
) -> list[taxonomy.PendingSuggestionView]:
    return taxonomy.list_pending_suggestions(db)


@router.patch("/taxonomy/{suggestion_id}", response_model=PendingTaxonomySuggestionOut)
def decide_taxonomy_suggestion(
    suggestion_id: int,
    body: TaxonomySuggestionDecision,
    db: Session = Depends(get_db),
) -> taxonomy.PendingSuggestionView:
    try:
        decided = taxonomy.decide_pending_suggestion(
            db, suggestion_id, status=body.status, name=body.name
        )
    # Both subclasses come before the generic ValueError so their structured
    # detail survives instead of being flattened to a string.
    except taxonomy.SuggestionNotPendingError as error:
        raise HTTPException(status_code=400, detail=error.detail) from error
    except taxonomy.RoleHasNoFieldError as error:
        raise HTTPException(status_code=400, detail=error.detail) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if decided is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")
    return decided
