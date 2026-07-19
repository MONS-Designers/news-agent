from fastapi import APIRouter, Depends

from newsagent.api.auth import require_user
from newsagent.api.schemas import TopicPreferenceOut
from newsagent.models import User

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/preferences", response_model=list[TopicPreferenceOut])
def list_my_preferences(user: User = Depends(require_user)) -> list[TopicPreferenceOut]:
    # Stub — real lookup lands with the preferences page issue.
    return []
