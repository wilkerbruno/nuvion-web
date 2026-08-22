"""Autenticação — implementação real (Fase 1 do roadmap).

Equivalente web de core/login_window.py: lá a UI chamava
crud/sqlalchemy_user_manager.py direto; aqui a mesma lógica (agora em
app/crud/user.py) fica atrás de endpoints HTTP que emitem JWT em vez de
manter o usuário "logado" na memória do processo.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.crud import user as user_crud
from app.db.session import get_db
from app.schemas.auth import AccessToken, LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from app.schemas.user import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    ok, result = user_crud.register_user(
        db,
        username=payload.username,
        password=payload.password,
        email=payload.email,
        name=payload.name,
        phone=payload.phone,
        cpf=payload.cpf,
        referral_code=payload.referral_code,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

    user = user_crud.get_by_id(db, result)
    return user


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    ok, result = user_crud.verify_login(db, payload.username_or_email, payload.password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=result)

    user_id = result
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/refresh", response_model=AccessToken)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    token_data = decode_token(payload.refresh_token)
    if token_data is None or token_data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")

    user_id = token_data.get("sub")
    user = user_crud.get_by_id(db, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado")

    return AccessToken(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserPublic)
def me(current_user=Depends(get_current_user)):
    return current_user
