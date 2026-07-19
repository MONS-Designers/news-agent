from fastapi import APIRouter, Depends

from newsagent.api.auth import require_admin
from newsagent.api.schemas import SourceOut

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/sources", response_model=list[SourceOut])
def list_pending_sources() -> list[SourceOut]:
    # Stub — source approval logic lands with the admin panel issue.
    return []
