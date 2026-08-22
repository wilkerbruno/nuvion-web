"""Cookies de sessão de IA (portado de database/models/ai_session_cookies.py).

Guarda cookies de sessão de terceiros para login automático — dado sensível
que passa a trafegar por um backend central em vez de ficar só no disco do
usuário. Ver plano de migração, seção 11 (riscos/LGPD) sobre isso.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.logging import LOGGER
from app.db.base_class import Base
from app.models.base import BaseModel


class AISessionCookies(Base, BaseModel):
    """Armazena cookies das IAs (upload manual ou, futuramente, via extensão)."""

    __tablename__ = "ai_sessions_cookies"

    ai_tool_id = Column(String(36), ForeignKey("ai_tools.id"), nullable=False)

    cookies_data = Column(JSON, nullable=False)
    imported_from = Column(String(20), default="manual")  # "manual", "extension", "file"
    source_file = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True)
    is_enabled = Column(Boolean, default=True)
    status = Column(String(20), default="active")  # active, expired, invalid

    expires_at = Column(DateTime, nullable=True)
    cookies_count = Column(Integer, default=0)
    domain_extracted = Column(String(255), nullable=True)

    ai_tool = relationship("AITool", back_populates="cookie_sessions")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.cookies_data and isinstance(self.cookies_data, list):
            self._update_metadata()

    def _update_metadata(self):
        try:
            from app.services.cookie_parser import CookieParser  # Fase 4 — ver app/services/cookie_parser.py

            if not self.cookies_data:
                return

            self.cookies_count = len(self.cookies_data)
            self.domain_extracted = CookieParser.extract_domain_from_cookies(self.cookies_data)
            self._calculate_expiration()

            LOGGER.info(
                f"Metadados atualizados: {self.cookies_count} cookies, domínio: {self.domain_extracted}"
            )
        except Exception as e:
            LOGGER.error(f"Erro ao atualizar metadados: {e}")

    def _calculate_expiration(self):
        try:
            if not self.cookies_data:
                return

            min_expiration = None
            for cookie in self.cookies_data:
                exp_date = cookie.get("expirationDate")
                if exp_date and (min_expiration is None or exp_date < min_expiration):
                    min_expiration = exp_date

            if min_expiration:
                self.expires_at = datetime.fromtimestamp(min_expiration, tz=timezone.utc)
            else:
                self.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        except Exception as e:
            LOGGER.error(f"Erro ao calcular expiração: {e}")
            self.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    def is_valid(self) -> bool:
        try:
            if not self.is_active or not self.is_enabled:
                return False
            if self.status != "active":
                return False
            if self.expires_at:
                expires_at = self.expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at < datetime.now(timezone.utc):
                    return False
            return True
        except Exception as e:
            LOGGER.error(f"Erro ao verificar validade: {e}")
            return False

    def get_cookies_for_domain(self, domain: str) -> List[Dict]:
        try:
            if not self.cookies_data:
                return []
            filtered = []
            for cookie in self.cookies_data:
                cookie_domain = cookie.get("domain", "")
                if cookie_domain.startswith("."):
                    cookie_domain = cookie_domain[1:]
                if domain.endswith(cookie_domain) or cookie_domain.endswith(domain):
                    filtered.append(cookie)
            return filtered
        except Exception as e:
            LOGGER.error(f"Erro ao filtrar cookies por domínio: {e}")
            return []

    def get_auth_cookies(self) -> List[Dict]:
        try:
            if not self.cookies_data:
                return []
            auth_indicators = ["session", "auth", "token", "key", "login", "sid"]
            return [
                cookie
                for cookie in self.cookies_data
                if any(ind in cookie.get("name", "").lower() for ind in auth_indicators)
            ]
        except Exception as e:
            LOGGER.error(f"Erro ao obter cookies de auth: {e}")
            return []

    def update_cookies(self, new_cookies: List[Dict], source_file: str = None):
        try:
            self.cookies_data = new_cookies
            if source_file:
                self.source_file = source_file
            self._update_metadata()
            self.updated_at = datetime.now(timezone.utc)
            LOGGER.info(f"Cookies atualizados para IA {self.ai_tool_id}")
        except Exception as e:
            LOGGER.error(f"Erro ao atualizar cookies: {e}")

    def mark_as_expired(self):
        self.status = "expired"
        self.is_active = False
        self.updated_at = datetime.now(timezone.utc)

    def mark_as_invalid(self):
        self.status = "invalid"
        self.is_active = False
        self.updated_at = datetime.now(timezone.utc)

    def to_dict_summary(self) -> Dict:
        return {
            "id": self.id,
            "ai_tool_id": self.ai_tool_id,
            "domain": self.domain_extracted,
            "cookies_count": self.cookies_count,
            "status": self.status,
            "is_active": self.is_active,
            "is_enabled": self.is_enabled,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "source_file": self.source_file,
        }
