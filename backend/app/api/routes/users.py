"""Perfil do usuário — equivalente web de core/widgets/settings/profile_section.py."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import ProfileUpdateRequest, UserPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
def get_my_profile(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.patch("/me", response_model=UserPublic)
def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    updated = user_crud.update_profile(
        db,
        current_user,
        name=payload.name,
        avatar_url=payload.avatar_url,
        profile_settings=payload.profile_settings,
    )
    return updated
