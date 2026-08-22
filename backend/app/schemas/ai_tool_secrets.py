"""Schemas de credenciais diretas e cookies de sessão por ferramenta de IA
(Fase 4) — nunca incluem segredo em texto puro, só status "configurado"."""
from typing import List, Optional

from pydantic import BaseModel


class DirectCredentialsSet(BaseModel):
    username: str
    password: str
    login_url: Optional[str] = None
    username_selector: Optional[str] = None
    password_selector: Optional[str] = None
    submit_selector: Optional[str] = None


class DirectCredentialsSummary(BaseModel):
    configured: bool
    username: Optional[str] = None
    login_url: Optional[str] = None
    is_active: Optional[bool] = None
    login_status: Optional[str] = None
    failed_attempts: Optional[int] = None
    max_attempts: Optional[int] = None


class CookieSessionSet(BaseModel):
    cookies_data: List[dict]


class CookieSessionSummary(BaseModel):
    configured: bool
    id: Optional[str] = None
    domain: Optional[str] = None
    cookies_count: Optional[int] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    is_enabled: Optional[bool] = None
    expires_at: Optional[str] = None
    created_at: Optional[str] = None
    source_file: Optional[str] = None
