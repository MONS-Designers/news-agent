from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from newsagent.api.auth import require_user
from newsagent.api.deps import get_db
from newsagent.api.schemas import (
    FieldOut,
    PreferenceUpdateIn,
    ProfileOut,
    ProfileUpdateIn,
    RoleOut,
    TopicPreferenceOut,
    TopicSuggestionsOut,
)
from newsagent.models import Field, Role, User
from newsagent.services import preferences, profile, taxonomy

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


@router.get("/fields/{field_id}/roles", response_model=list[RoleOut])
def list_my_roles(
    field_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> list[Role]:
    return taxonomy.list_roles(db, field_id)


@router.put("/profile", response_model=ProfileOut)
def update_my_profile(
    body: ProfileUpdateIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> User:
    try:
        updated = profile.save_profile(
            db,
            user,
            field_name=body.field_name,
            field_is_other=body.field_is_other,
            role_name=body.role_name,
            role_is_other=body.role_is_other,
            experience_bucket=body.experience_bucket,
            interest_free_text=body.interest_free_text,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    # db.get_bind(), not db itself — the request-scoped session is already
    # closed by the time this BackgroundTask runs (AD-5).
    background_tasks.add_task(
        profile.run_suggestion_computation, db.get_bind(), updated.id, updated.suggestion_request_seq
    )
    return updated


@router.get("/topic-suggestions", response_model=TopicSuggestionsOut)
def get_my_topic_suggestions(user: User = Depends(require_user)) -> User:
    return user
