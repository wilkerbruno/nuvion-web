# database/models/ai_session_cookies.py (CORRIGIDO)
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import (JSON, Boolean, Column, DateTime, ForeignKey, Integer,
                        String, Text)
from sqlalchemy.orm import relationship

from database.models.base import BaseModel
from database.sqlalchemy_config import Base
from utils.logger import LOGGER


class AISessionCookies(Base, BaseModel):
    """
    Modelo SIMPLIFICADO para armazenar apenas cookies das IAs
    Focado no sistema de upload manual de cookies
    """

    __tablename__ = "ai_sessions_cookies"

    # Chaves estrangeiras
    ai_tool_id = Column(String(36), ForeignKey("ai_tools.id"), nullable=False)

    # Dados essenciais para cookies
    cookies_data = Column(JSON, nullable=False)  # Lista de cookies normalizados
    imported_from = Column(
        String(20), default="manual"
    )  # "manual", "extension", "file"
    source_file = Column(String(255), nullable=True)  # Nome do arquivo original

    # Status e controle
    is_active = Column(Boolean, default=True)
    is_enabled = Column(Boolean, default=True)  # Se deve aplicar cookies
    status = Column(String(20), default="active")  # active, expired, invalid

    # Metadados
    expires_at = Column(DateTime, nullable=True)  # Quando os cookies expiram
    cookies_count = Column(Integer, default=0)  # Quantos cookies tem
    domain_extracted = Column(String(255), nullable=True)  # Domínio extraído

    # Relacionamento
    ai_tool = relationship("AITool", back_populates="cookie_sessions")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Auto-configurar metadados se cookies_data fornecido
        if self.cookies_data and isinstance(self.cookies_data, list):
            self._update_metadata()

    def _update_metadata(self):
        """Atualiza metadados baseado nos cookies"""
        try:
            from core.utils.cookie_parser import CookieParser

            if not self.cookies_data:
                return

            # Contar cookies
            self.cookies_count = len(self.cookies_data)

            # Extrair domínio
            self.domain_extracted = CookieParser.extract_domain_from_cookies(
                self.cookies_data
            )

            # Calcular expiração baseada nos cookies
            self._calculate_expiration()

            LOGGER.info(
                f"Metadados atualizados: {self.cookies_count} cookies, domínio: {self.domain_extracted}"
            )

        except Exception as e:
            LOGGER.error(f"Erro ao atualizar metadados: {e}")

    def _calculate_expiration(self):
        """Calcula data de expiração baseada nos cookies"""
        try:
            if not self.cookies_data:
                return

            # Encontrar a menor data de expiração dos cookies
            min_expiration = None

            for cookie in self.cookies_data:
                exp_date = cookie.get("expirationDate")
                if exp_date:
                    if min_expiration is None or exp_date < min_expiration:
                        min_expiration = exp_date

            if min_expiration:
                # Converter timestamp para datetime UTC
                self.expires_at = datetime.fromtimestamp(
                    min_expiration, tz=timezone.utc
                )
            else:
                # Se não há expiração definida, definir para 30 dias
                self.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        except Exception as e:
            LOGGER.error(f"Erro ao calcular expiração: {e}")
            # Fallback: 30 dias
            self.expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    def is_valid(self) -> bool:
        """Verifica se os cookies ainda são válidos - VERSÃO CORRIGIDA"""
        try:
            if not self.is_active or not self.is_enabled:
                return False

            if self.status != "active":
                return False

            if self.expires_at:
                expires_at = self.expires_at

                # *** CORREÇÃO DE TIMEZONE ***
                # Garantir timezone UTC
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                now_utc = datetime.now(timezone.utc)

                if expires_at < now_utc:
                    return False

            return True

        except Exception as e:
            LOGGER.error(f"Erro ao verificar validade: {e}")
            return False

    def get_cookies_for_domain(self, domain: str) -> List[Dict]:
        """Retorna cookies filtrados por domínio"""
        try:
            if not self.cookies_data:
                return []

            filtered = []
            for cookie in self.cookies_data:
                cookie_domain = cookie.get("domain", "")

                # Remover ponto inicial se existir
                if cookie_domain.startswith("."):
                    cookie_domain = cookie_domain[1:]

                # Verificar se domínio bate
                if domain.endswith(cookie_domain) or cookie_domain.endswith(domain):
                    filtered.append(cookie)

            return filtered

        except Exception as e:
            LOGGER.error(f"Erro ao filtrar cookies por domínio: {e}")
            return []

    def get_auth_cookies(self) -> List[Dict]:
        """Retorna apenas cookies de autenticação importantes"""
        try:
            if not self.cookies_data:
                return []

            auth_indicators = ["session", "auth", "token", "key", "login", "sid"]
            auth_cookies = []

            for cookie in self.cookies_data:
                name = cookie.get("name", "").lower()
                if any(indicator in name for indicator in auth_indicators):
                    auth_cookies.append(cookie)

            return auth_cookies

        except Exception as e:
            LOGGER.error(f"Erro ao obter cookies de auth: {e}")
            return []

    def update_cookies(self, new_cookies: List[Dict], source_file: str = None):
        """Atualiza cookies existentes"""
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
        """Marca cookies como expirados"""
        self.status = "expired"
        self.is_active = False
        self.updated_at = datetime.now(timezone.utc)

    def mark_as_invalid(self):
        """Marca cookies como inválidos"""
        self.status = "invalid"
        self.is_active = False
        self.updated_at = datetime.now(timezone.utc)

    def to_dict_summary(self) -> Dict:
        """Retorna resumo dos dados em formato dict"""
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
