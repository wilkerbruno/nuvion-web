"""Rotas de proxy por usuário (Fase 2 — consumidas pelo painel e pela extensão).

`GET /proxies/active` é a rota que a extensão chama para saber qual proxy
aplicar via PAC script (ver extension/src/background/service-worker.js).
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.crud import proxy as proxy_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.proxy import ProxyCreate, ProxyPublic, ProxyUpdate

router = APIRouter(prefix="/proxies", tags=["proxies"])


@router.get("", response_model=List[ProxyPublic])
def list_proxies(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return proxy_crud.list_for_user(db, current_user.id)


@router.get("/active", response_model=ProxyPublic)
def get_active_proxy(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    proxy = proxy_crud.get_active(db, current_user.id)
    if proxy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Nenhum proxy selecionado"
        )
    return proxy


@router.post("", response_model=ProxyPublic, status_code=status.HTTP_201_CREATED)
def create_proxy(
    payload: ProxyCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return proxy_crud.create(db, user_id=current_user.id, **payload.model_dump())


def _get_owned_or_404(db: Session, user_id: str, proxy_id: str):
    proxy = proxy_crud.get_owned(db, user_id, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy não encontrado")
    return proxy


@router.patch("/{proxy_id}", response_model=ProxyPublic)
def update_proxy(
    proxy_id: str,
    payload: ProxyUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    proxy = _get_owned_or_404(db, current_user.id, proxy_id)
    return proxy_crud.update(db, proxy, **payload.model_dump(exclude_unset=True))


@router.delete("/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_proxy(
    proxy_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    proxy = _get_owned_or_404(db, current_user.id, proxy_id)
    proxy_crud.delete(db, proxy)


@router.post("/{proxy_id}/select", response_model=ProxyPublic)
def select_proxy(
    proxy_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    proxy = proxy_crud.select_active(db, current_user.id, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy não encontrado")
    return proxy
