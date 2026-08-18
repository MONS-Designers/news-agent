from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from newsagent.api.auth import require_admin
from newsagent.api.deps import get_db
from newsagent.api.schemas import SourceOut, SourceStatusUpdate
from newsagent.models import Source
from newsagent.models.source import STATUS_PENDING
from newsagent.services.sources import set_source_status

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/sources", response_model=list[SourceOut])
def list_pending_sources(db: Session = Depends(get_db)) -> list[Source]:
    return list(db.scalars(select(Source).where(Source.status == STATUS_PENDING)).all())


@router.patch("/sources/{source_id}", response_model=SourceOut)
def update_source_status(
    source_id: int, body: SourceStatusUpdate, db: Session = Depends(get_db)
) -> Source:
    source = set_source_status(db, source_id, body.status)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return source
