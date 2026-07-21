from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from newsagent.api.auth import require_user
from newsagent.api.deps import get_db
from newsagent.api.schemas import PreferenceUpdateIn, TopicPreferenceOut
from newsagent.models import User
from newsagent.services import preferences

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/preferences", response_model=list[TopicPreferenceOut])
def list_my_preferences(
    user: User = Depends(require_user), db: Session = Depends(get_db)
) -> list[preferences.TopicChoice]:
    return preferences.list_topic_choices(db, user)


@router.put("/preferences", response_model=list[TopicPreferenceOut])
def update_my_preferences(
    body: PreferenceUpdateIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[preferences.TopicChoice]:
    try:
        return preferences.set_preferences(db, user, body.topic_ids)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
