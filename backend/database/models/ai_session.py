# database/models/ai_session.py (CORRIGIDO)
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, Column, DateTime, ForeignKey, String,
                        Text)
from sqlalchemy.orm import relationship

from database.models.base import BaseModel
from database.sqlalchemy_config import Base
from utils.logger import LOGGER


class AISession(Base, BaseModel):
    """Modelo para armazenar sessões das IAs com login automático"""

    __tablename__ = "ai_sessions"

    # Chaves estrangeiras
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    ai_tool_id = Column(String(36), ForeignKey("ai_tools.id"), nullable=False)

    # Dados da sessão
    session_data = Column(JSON, nullable=True)  # Cookies, tokens, etc
    session_token = Column(Text, nullable=True)  # Token de sessão específico
    login_cookies = Column(JSON, nullable=True)  # Cookies de login
    auth_headers = Column(JSON, nullable=True)  # Headers de autenticação

    # Dados do navegador
    user_agent = Column(Text, nullable=True)
    viewport_size = Column(String(20), nullable=True)  # "1920x1080"
    browser_profile = Column(Text, nullable=True)  # Caminho do perfil

    # Status e controle
    is_active = Column(Boolean, default=True)
    auto_login_enabled = Column(Boolean, default=True)
    last_login_attempt = Column(DateTime, nullable=True)
    last_successful_login = Column(DateTime, nullable=True)
    login_status = Column(
        String(20), default="pending"
    )  # pending, success, failed, expired

    # Configurações de login
    login_url = Column(Text, nullable=True)  # URL específica de login
    login_method = Column(String(20), default="automatic")  # automatic, manual
    login_script = Column(Text, nullable=True)  # Script JS customizado para login

    # Metadados
    expires_at = Column(DateTime, nullable=True)

    # RELACIONAMENTOS CORRIGIDOS - usar back_populates
    user = relationship("User", back_populates="ai_sessions")
    ai_tool = relationship("AITool", back_populates="ai_sessions")

    def is_session_valid(self) -> bool:
        """Verifica se a sessão ainda é válida - VERSÃO CORRIGIDA TIMEZONE"""
        try:
            if not self.is_active:
                return False

            if self.login_status != "success":
                return False

            # *** CORREÇÃO DE TIMEZONE ***
            if self.expires_at:
                expires_at = self.expires_at

                # Se expires_at é naive (sem timezone), assumir UTC
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                # Comparar com agora em UTC
                now_utc = datetime.now(timezone.utc)

                if expires_at < now_utc:
                    LOGGER.info(f"Sessão expirada para IA {self.ai_tool_id}")
                    return False

            return True

        except Exception as e:
            LOGGER.error(f"Erro ao verificar validade da sessão: {e}")
            return False

    def mark_login_success(self):
        """Marca login como bem-sucedido"""
        self.login_status = "success"
        self.last_successful_login = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        LOGGER.info(f"Login marcado como sucesso para IA {self.ai_tool_id}")

    def mark_login_failed(self):
        """Marca login como falhado"""
        self.login_status = "failed"
        self.last_login_attempt = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        LOGGER.error(f"Login marcado como falha para IA {self.ai_tool_id}")

    def update_session_data(
        self, cookies: dict = None, tokens: dict = None, headers: dict = None
    ):
        """Atualiza dados da sessão"""
        if cookies:
            self.login_cookies = cookies
            LOGGER.info(f"Cookies atualizados para IA {self.ai_tool_id}")

        if tokens:
            self.session_data = tokens
            LOGGER.info(f"Tokens atualizados para IA {self.ai_tool_id}")

        if headers:
            self.auth_headers = headers
            LOGGER.info(f"Headers atualizados para IA {self.ai_tool_id}")

        self.updated_at = datetime.now(timezone.utc)
