# backend/api/routes/auth.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user_id,
)

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: EmailStr
    name: str
    phone: str
    referral_code: str
    cpf: str | None = None

class ForgotRequest(BaseModel):
    username_or_email: str

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_to_dict(user) -> dict:
    return {
        "id":           user.id,
        "username":     user.username,
        "name":         user.name,
        "email":        user.email,
        "phone":        getattr(user, "phone", ""),
        "account_type": user.account_type,
        "status":       user.status,
        "referral_code": getattr(user, "referral_code", ""),
        "created_at":   user.created_at.isoformat() if user.created_at else None,
        "last_login":   user.last_login.isoformat() if user.last_login else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    from crud.crud_manager import crud_system

    success, result = crud_system.users.verify_login(body.username, body.password)
    if not success:
        raise HTTPException(status_code=401, detail=result or "Credenciais inválidas")

    user_id = result
    user = crud_system.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if user.status not in ("Ativo",):
        raise HTTPException(
            status_code=403,
            detail="Conta inativa. Realize o pagamento para ativar.",
        )

    return TokenResponse(
        access_token=create_access_token(user.id, user.username),
        refresh_token=create_refresh_token(user.id),
        user=_user_to_dict(user),
    )


@router.post("/register")
def register(body: RegisterRequest):
    from crud.crud_manager import crud_system

    success, result = crud_system.users.register_user(
        username=body.username,
        password=body.password,
        email=body.email,
        name=body.name,
        phone=body.phone,
        referral_code=body.referral_code,
        cpf=body.cpf,
    )
    if not success:
        raise HTTPException(status_code=400, detail=result)

    return {"message": "Conta criada com sucesso! Faça login para continuar."}


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest):
    from crud.crud_manager import crud_system

    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token inválido")

    user_id = payload["sub"]
    user = crud_system.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    return TokenResponse(
        access_token=create_access_token(user.id, user.username),
        refresh_token=create_refresh_token(user.id),
        user=_user_to_dict(user),
    )


@router.post("/forgot-password")
def forgot_password(body: ForgotRequest):
    from crud.crud_manager import crud_system
    from core.services.email_service import email_service

    user = crud_system.users.get_by_username_or_email(body.username_or_email)
    if not user:
        # Resposta genérica por segurança
        return {"message": "Se o usuário existir, um email será enviado."}

    import secrets
    token = secrets.token_urlsafe(32)
    # Salvar token de recuperação (reutiliza campo ou cria entry no banco)
    crud_system.users.set_recovery_token(user.id, token)

    try:
        email_service.send_recovery_email(user.email, user.name, token)
    except Exception:
        pass  # Não expor erros de email

    return {"message": "Se o usuário existir, um email será enviado."}


@router.get("/me")
def me(user_id: str = Depends(get_current_user_id)):
    from crud.crud_manager import crud_system

    user = crud_system.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return _user_to_dict(user)
