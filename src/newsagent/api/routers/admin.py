from fastapi import APIRouter

from newsagent.api.schemas import SourceOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/sources", response_model=list[SourceOut])
def list_pending_sources() -> list[SourceOut]:
    # Stub — source approval logic lands with the admin panel issue.
    return []
