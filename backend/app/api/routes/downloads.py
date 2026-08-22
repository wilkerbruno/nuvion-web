"""Rotas de histórico de downloads (Fase 4).

`POST /downloads` é chamada pela extensão quando `chrome.downloads` dispara
um evento (ver extension/src/background/service-worker.js) — o download em
si já aconteceu no navegador do usuário antes deste registro existir; isto
é só espelho de status para o painel, como já estava documentado no plano
de migração (seção 6).
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.crud import download as download_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.download import DownloadCreate, DownloadPublic, DownloadUpdate

router = APIRouter(prefix="/downloads", tags=["downloads"])


@router.get("/me", response_model=List[DownloadPublic])
def my_downloads(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return download_crud.list_for_user(db, current_user.id)


@router.post("", response_model=DownloadPublic, status_code=status.HTTP_201_CREATED)
def register_download(
    payload: DownloadCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return download_crud.create(db, user_id=current_user.id, **payload.model_dump())


@router.patch("/{download_id}", response_model=DownloadPublic)
def update_download(
    download_id: str,
    payload: DownloadUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    download = download_crud.get_owned(db, current_user.id, download_id)
    if download is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Download não encontrado")

    end_time = datetime.now(timezone.utc) if payload.status in ("completed", "failed", "cancelled") else None
    return download_crud.update_status(db, download, status=payload.status, end_time=end_time)
