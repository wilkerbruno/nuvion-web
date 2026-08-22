"""Payloads de autenticação — novo nesta versão web (o app desktop não tinha
uma camada de API/schema, a UI falava direto com crud/sqlalchemy_user_manager.py)."""
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=20)
    cpf: Optional[str] = Field(default=None, max_length=20)
    # Igual ao desktop: cadastro exige indicação de um usuário existente.
    # Para criar o primeiro usuário do sistema, ver scripts/create_admin.py.
    referral_code: str = Field(min_length=1, max_length=10)


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
