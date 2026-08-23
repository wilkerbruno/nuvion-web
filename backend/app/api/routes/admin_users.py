"""Rotas de admin para gestão de usuários — definir o plano (categoria) de
uma conta e bloquear/desbloquear (via `status`). Mesma trava de acesso das
outras rotas administrativas (`require_admin`, ver app/api/deps.py).

Por que só `category`/`status` e não outros campos (senha, email, tipo de
conta): esta tela nasceu de um pedido específico — "definir qual o plano do
usuário, bloquear caso necessário" — e trocar quem é Admin/Equipe é uma ação
mais sensível (escalonamento de privilégio) que merece uma tela própria com
mais salvaguardas, não um campo a mais neste PATCH genérico.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import AdminUserUpdate, UserPublic

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("", response_model=List[UserPublic])
def list_users(
    search: Optional[str] = None,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return user_crud.list_users(db, search=search)


def _get_or_404(db: Session, user_id: str) -> User:
    user = user_crud.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    return user


@router.get("/{user_id}", response_model=UserPublic)
def get_user(
    user_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _get_or_404(db, user_id)


@router.patch("/{user_id}", response_model=UserPublic)
def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = _get_or_404(db, user_id)

    # Trava de segurança: um admin não pode bloquear/cancelar a própria
    # conta por aqui — evita um autobloqueio acidental que tira o acesso de
    # quem estava usando a tela (ainda dá pra fazer isso direto no banco,
    # se for mesmo intencional).
    if user.id == admin.id and payload.status in ("Bloqueado", "Cancelado"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode bloquear/cancelar a própria conta por aqui",
        )

    updated = user_crud.update_admin_fields(db, user, **payload.model_dump(exclude_unset=True))
    return updated
