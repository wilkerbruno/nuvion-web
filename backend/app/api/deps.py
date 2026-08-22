"""Dependências reutilizáveis das rotas — autenticação via JWT Bearer.

Substitui a sessão local do desktop (o usuário "logado" ficava só na
memória do processo Qt). Aqui, cada request traz um access_token no header
`Authorization: Bearer <token>`, validado e resolvido para um User real.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.crud.user import get_by_id
from app.db.session import get_db
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise unauthorized

    user_id = payload.get("sub")
    user = get_by_id(db, user_id) if user_id else None
    if user is None:
        raise unauthorized

    return user


def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if user.status in ("Bloqueado", "Cancelado") or user.is_blocked():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=user.get_block_message() if user.is_blocked() else f"Conta {user.status.lower()}",
        )
    return user


def require_admin(user: User = Depends(get_current_active_user)) -> User:
    """Porta de `access_control_manager.py` do desktop, versão mínima: só
    checa `account_type == "Admin"`. Usado pelas rotas de configuração de
    pagamento (Fase 3) — quem pode ver/editar credenciais do Mercado Pago."""
    if user.account_type != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores",
        )
    return user
