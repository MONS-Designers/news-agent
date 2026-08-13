from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from newsagent.api.auth import require_admin
from newsagent.api.deps import get_db
from newsagent.api.schemas import DigestEngagementOut
from newsagent.services import engagement

# Own file, not an extension of admin.py: engagement reporting is a read-only
# concern independent of source approval, matching admin_taxonomy.py's split.
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/engagement", response_model=list[DigestEngagementOut])
def list_digest_engagement(db: Session = Depends(get_db)) -> list[engagement.DigestEngagement]:
    return engagement.list_digest_engagement(db)
