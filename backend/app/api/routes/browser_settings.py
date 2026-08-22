"""Rotas de configurações de navegação — consumidas pelo painel e pela
extensão (Fase 2).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.crud import browser_settings as browser_settings_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.browser_settings import BrowserSettingsPublic, BrowserSettingsUpdate

router = APIRouter(prefix="/browser-settings", tags=["browser-settings"])


@router.get("/me", response_model=BrowserSettingsPublic)
def my_browser_settings(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return browser_settings_crud.get_or_create(db, current_user.id)


@router.patch("/me", response_model=BrowserSettingsPublic)
def update_my_browser_settings(
    payload: BrowserSettingsUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    settings = browser_settings_crud.get_or_create(db, current_user.id)
    return browser_settings_crud.update(db, settings, **payload.model_dump(exclude_unset=True))
