from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from newsagent.api.auth import require_user
from newsagent.api.deps import get_db
from newsagent.api.schemas import FieldOut, PreferenceUpdateIn, ProfileOut, ProfileUpdateIn, TopicPreferenceOut
from newsagent.models import Field, User
from newsagent.services import preferences, taxonomy

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


@router.get("/fields", response_model=list[FieldOut])
def list_my_fields(user: User = Depends(require_user), db: Session = Depends(get_db)) -> list[Field]:
    return taxonomy.list_fields(db)


@router.put("/profile", response_model=ProfileOut)
def update_my_profile(
    body: ProfileUpdateIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> User:
    return taxonomy.record_field_selection(
        db, user, field_name=body.field_name, is_other=body.is_other
    )
