"""Schemas de usuário/perfil — expostos pela API (nunca expor password_hash)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserPublic(BaseModel):
    """Representação segura do usuário para respostas da API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    name: str
    phone: str
    cpf: Optional[str] = None
    avatar_url: Optional[str] = None
    referral_code: str
    account_type: str
    status: str
    category: str
    last_login: Optional[datetime] = None
    payment_due_date: Optional[datetime] = None
    created_at: datetime


class AdminUserUpdate(BaseModel):
    """Campos que um Admin pode alterar de qualquer usuário — ver
    app/api/routes/admin_users.py. Propositalmente não inclui `account_type`
    (promover/rebaixar Admin) nesta primeira versão — troca de plano e
    bloqueio de conta são os dois casos pedidos; mexer em quem é Admin fica
    de fora até ter uma tela própria com mais salvaguardas."""

    category: Optional[str] = Field(default=None, pattern="^(Standard|Premium|VIP)$")
    status: Optional[str] = Field(default=None, pattern="^(Ativo|Inativo|Cancelado|Bloqueado)$")


class ProfileUpdateRequest(BaseModel):
    """Campos que o próprio usuário pode alterar no perfil."""

    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    avatar_url: Optional[str] = None
    profile_settings: Optional[dict] = None


class DashboardSummary(BaseModel):
    """Equivalente web de core/widgets/dashboard_widget.py — visão geral da conta."""

    user: UserPublic
    payment_status: dict
    is_blocked: bool
    block_message: Optional[str] = None
