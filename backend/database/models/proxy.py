from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from database.models.base import BaseModel
from database.sqlalchemy_config import Base
from utils.logger import LOGGER


class Proxy(Base, BaseModel):
    """Modelo de proxy para navegação anônima"""

    __tablename__ = "proxy"

    # Informações básicas do proxy
    name = Column(String(100), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    proxy_type = Column(String(20), nullable=False)  # HTTP, HTTPS, SOCKS4, SOCKS5

    # Credenciais de autenticação (opcionais)
    username = Column(String(100), nullable=True)
    password = Column(Text, nullable=True)

    # Status e controle
    is_active = Column(Boolean, default=True)
    status = Column(String(20), default="unknown")
    current_ai = Column(String(100), nullable=True)

    # Métricas de performance
    response_time = Column(Integer, nullable=True)
    last_tested = Column(DateTime, nullable=True)

    # Relacionamento
    assigned_ais = relationship("AITool", back_populates="proxy")

    @property
    def ias_count(self):
        """Retorna quantas IAs estão usando este proxy - VERSÃO SEGURA"""
        try:
            if (
                hasattr(self, "_sa_instance_state")
                and self._sa_instance_state.session is None
            ):
                # Se não há sessão, retornar 0 para evitar erro
                return 0
            else:
                return len(self.assigned_ias) if self.assigned_ias else 0
        except Exception:
            return 0

    @property
    def status_display(self):
        """Retorna status formatado para exibição - VERSÃO CORRIGIDA"""
        try:
            # Verificar se assigned_ias está carregado para evitar lazy loading
            if (
                hasattr(self, "_sa_instance_state")
                and self._sa_instance_state.session is None
            ):
                # Se não há sessão, usar contagem básica sem relacionamento
                ias_count = 0
            else:
                # Se há sessão, pode acessar o relacionamento
                ias_count = len(self.assigned_ias) if self.assigned_ias else 0

            if self.status == "available":
                return (
                    f"✅ Disponível ({ias_count} IAs)"
                    if ias_count > 0
                    else "✅ Disponível"
                )
            elif self.status == "in_use":
                return f"🔄 Em uso ({ias_count} IAs)" if ias_count > 0 else "🔄 Em uso"
            elif self.status == "offline":
                return "❌ Offline"
            else:
                return (
                    f"❓ Desconhecido ({ias_count} IAs)"
                    if ias_count > 0
                    else "❓ Desconhecido"
                )

        except Exception as e:
            # Em caso de erro, retornar status simples
            LOGGER.error(f"Erro em status_display: {e}")
            return f"{self.status.title()}" if self.status else "Desconhecido"

    @property
    def connection_string(self):
        """Retorna string de conexão do proxy"""
        if self.username and self.password:
            return f"{self.proxy_type.lower()}://{self.username}:{self.password}@{self.host}:{self.port}"
        else:
            return f"{self.proxy_type.lower()}://{self.host}:{self.port}"

    @property
    def display_name(self):
        """Nome para exibição em listas"""
        return f"{self.name} ({self.host}:{self.port})"

    def __repr__(self):
        return f"<Proxy(name='{self.name}', host='{self.host}:{self.port}', status='{self.status}', ias={self.ias_count})>"
