# backend/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.config import settings

bearer_scheme = HTTPBearer()


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {"sub": user_id, "username": username, "exp": expire, "type": "access"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "refresh"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Dependencies ──────────────────────────────────────────────────────────────

def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Token inválido")
    return payload["sub"]


def get_current_user(
    user_id: str = Depends(get_current_user_id),
):
    """Retorna dicionário com dados básicos do usuário do token."""
    return {"id": user_id}


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """Bloqueia se o usuário não for Admin."""
    from crud.crud_manager import crud_system

    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    user = crud_system.users.get_by_id(user_id)
    if not user or user.account_type != "Admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return {"id": user_id, "account_type": "Admin"}


# ── Password ──────────────────────────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False
