"""Modelo de ferramentas de IA (portado de database/models/ai_tool.py).

`get_login_status_summary` faz import tardio de módulos que ainda não
existem no backend (crud.database_adapter, o futuro serviço de cookies da
extensão) — igual ao original, a chamada é protegida por try/except e
simplesmente não preenche aquele campo até esses módulos serem portados
numa fase seguinte (extensão / Fase 2).
"""
from sqlalchemy import JSON, Boolean, Column, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.core.logging import LOGGER
from app.db.base_class import Base
from app.models.base import BaseModel


class AITool(Base, BaseModel):
    """Modelo de ferramentas de IA."""

    __tablename__ = "ai_tools"

    block_extensions = Column(Boolean, default=False, nullable=False)

    name = Column(String(100), nullable=False, unique=True)
    url = Column(Text, nullable=False)
    description = Column(Text)
    category = Column(String(50), index=True)

    login_cookies_raw = Column(JSON, nullable=True)
    login_method = Column(String(20), default="manual")  # "credentials", "cookies"

    observations = Column(Text)
    proxy_id = Column(String(36), ForeignKey("proxy.id"), nullable=True)
    tags = Column(JSON, default=list)
    rating = Column(Numeric(3, 2), default=0.0)
    is_featured = Column(Boolean, default=False)

    direct_credentials = relationship("AIDirectCredentials", back_populates="ai_tool")
    cookie_sessions = relationship("AISessionCookies", back_populates="ai_tool")
    proxy = relationship("Proxy", back_populates="assigned_ais")

    @property
    def proxy_info(self):
        if self.proxy:
            return f"{self.proxy.name} ({self.proxy.host}:{self.proxy.port}) - {self.proxy.proxy_type}"
        return "Sem Proxy"

    def has_cookies_configured(self) -> bool:
        return any(session.is_active for session in self.cookie_sessions)

    def get_active_cookie_session(self):
        for session in self.cookie_sessions:
            if session.is_active and session.status == "active":
                return session
        return None

    def get_cookies_status(self) -> dict:
        active_session = self.get_active_cookie_session()
        if not active_session:
            return {
                "configured": False,
                "status": "not_configured",
                "cookies_count": 0,
                "domain": None,
                "expires_at": None,
            }
        return {
            "configured": True,
            "status": active_session.status,
            "cookies_count": active_session.cookies_count,
            "domain": active_session.domain_extracted,
            "expires_at": active_session.expires_at,
            "is_valid": active_session.is_valid(),
        }

    def add_tag(self, tag: str):
        if self.tags is None:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: str):
        if self.tags and tag in self.tags:
            self.tags.remove(tag)

    def get_login_type(self) -> str:
        return self.login_method or "manual"

    def get_active_login_method(self):
        if self.login_method and self.login_method != "manual":
            LOGGER.info(f"Login method configurado no banco: {self.login_method}")
            return self.login_method

        if self.cookie_sessions:
            for cookie_session in self.cookie_sessions:
                if cookie_session.is_active:
                    LOGGER.info("Cookie ativo encontrado - usando 'cookies'")
                    return "cookies"

        LOGGER.info("Nenhum método ativo - usando 'manual'")
        return "manual"

    def has_direct_configured(self) -> bool:
        if hasattr(self, "direct_credentials") and self.direct_credentials:
            return self.direct_credentials.is_active and self.direct_credentials.is_valid()
        return False

    def get_login_status_summary(self) -> dict:
        """Resumo de status de login. Depende de módulos ainda não portados
        (crud/extensão) — falha graciosamente até essas fases estarem prontas."""
        status = {
            "ai_name": self.name,
            "ai_id": self.id,
            "login_method_db": getattr(self, "login_method", "manual"),
            "active_method": self.get_active_login_method(),
            "direct": False,
            "cookies": False,
            "details": {},
        }

        try:
            from app.crud.database_adapter import crud_system  # noqa: F401 (fase futura)

            direct_creds = crud_system.direct_credentials.get_credentials_by_ai_tool(self.id)
            if direct_creds:
                status["direct"] = bool(direct_creds.get("username") and direct_creds.get("password"))
                status["details"]["direct"] = {
                    "has_username": bool(direct_creds.get("username")),
                    "has_password": bool(direct_creds.get("password")),
                    "username": direct_creds.get("username", "N/A"),
                }
        except Exception:
            pass  # módulo ainda não existe nesta fase da migração

        try:
            from app.services.cookie_session_manager import CookieSessionManager  # noqa: F401

            cookie_data = CookieSessionManager.get_active_cookies(self.id)
            if cookie_data:
                status["cookies"] = bool(cookie_data.get("cookies_data"))
                status["details"]["cookies"] = {
                    "count": len(cookie_data.get("cookies_data", [])),
                    "source": cookie_data.get("source", "N/A"),
                }
        except Exception:
            pass  # idem — chega com a extensão (Fase 2)

        return status
