from fastapi import APIRouter

from newsagent.api.schemas import TopicPreferenceOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/preferences", response_model=list[TopicPreferenceOut])
def list_my_preferences() -> list[TopicPreferenceOut]:
    # Stub — real lookup lands with the preferences page issue.
    return []
