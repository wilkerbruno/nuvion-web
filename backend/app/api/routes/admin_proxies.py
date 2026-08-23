"""Rotas de admin para proxies globais/compartilhados (`user_id IS NULL`).

Diferente de `/proxies` (app/api/routes/proxies.py, onde cada usuário
cadastra e escolhe seus próprios proxies pessoais para a extensão), estas
rotas gerenciam os proxies que um admin cadastra e associa a uma ferramenta
de IA específica via `AITool.proxy_id` — mesmo modelo do app desktop
original (proxy por IA, gerido só pelo admin). Usados pela extensão para
rotear cada ferramenta pelo proxy que o admin escolheu para ela (ver
extension/src/background — PAC por domínio da ferramenta).
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.crud import proxy as proxy_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.proxy import ProxyCreate, ProxyPublic, ProxyUpdate

router = APIRouter(prefix="/admin/proxies", tags=["admin-proxies"])


@router.get("", response_model=List[ProxyPublic])
def list_global_proxies(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return proxy_crud.list_global(db)


@router.post("", response_model=ProxyPublic, status_code=status.HTTP_201_CREATED)
def create_global_proxy(
    payload: ProxyCreate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return proxy_crud.create(db, user_id=None, **payload.model_dump())


def _get_or_404(db: Session, proxy_id: str):
    proxy = proxy_crud.get_global(db, proxy_id)
    if proxy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy não encontrado")
    return proxy


@router.patch("/{proxy_id}", response_model=ProxyPublic)
def update_global_proxy(
    proxy_id: str,
    payload: ProxyUpdate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    proxy = _get_or_404(db, proxy_id)
    return proxy_crud.update(db, proxy, **payload.model_dump(exclude_unset=True))


@router.delete("/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_global_proxy(
    proxy_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    proxy = _get_or_404(db, proxy_id)
    proxy_crud.delete(db, proxy)
