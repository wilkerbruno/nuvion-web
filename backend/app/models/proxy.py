"""Modelo de proxy (portado de database/models/proxy.py, sem mudanças de schema).

O gerenciamento de proxy em si (roteamento, teste, SOCKS5) migra para o
Proxy Gateway do backend — ver plano de migração, seção 6. Este modelo
continua sendo a fonte de verdade dos proxies cadastrados por usuário/IA.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.logging import LOGGER
from app.db.base_class import Base
from app.models.base import BaseModel


class Proxy(Base, BaseModel):
    """Modelo de proxy para navegação anônima.

    `user_id` e `is_selected` são novos na versão web (Fase 2, plano seção
    6): no desktop original o proxy era só admin-gerenciado e associado por
    IA (`assigned_ais`); aqui cada usuário pode cadastrar seus próprios
    proxies para a extensão usar. `user_id` fica nullable para não quebrar
    o caso de proxy admin/compartilhado, sem dono de um usuário específico.
    """

    __tablename__ = "proxy"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)

    name = Column(String(100), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    proxy_type = Column(String(20), nullable=False)  # HTTP, HTTPS, SOCKS4, SOCKS5

    username = Column(String(100), nullable=True)
    password = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    is_selected = Column(
        Boolean, default=False, nullable=False,
        comment="Proxy ativo escolhido pelo usuário para a extensão usar agora",
    )
    status = Column(String(20), default="unknown")
    current_ai = Column(String(100), nullable=True)

    response_time = Column(Integer, nullable=True)
    last_tested = Column(DateTime, nullable=True)

    assigned_ais = relationship("AITool", back_populates="proxy")
    owner = relationship("User", back_populates="proxies")

    @property
    def ias_count(self):
        try:
            if hasattr(self, "_sa_instance_state") and self._sa_instance_state.session is None:
                return 0
            return len(self.assigned_ais) if self.assigned_ais else 0
        except Exception:
            return 0

    @property
    def status_display(self):
        try:
            if hasattr(self, "_sa_instance_state") and self._sa_instance_state.session is None:
                ias_count = 0
            else:
                ias_count = len(self.assigned_ais) if self.assigned_ais else 0

            if self.status == "available":
                return f"✅ Disponível ({ias_count} IAs)" if ias_count > 0 else "✅ Disponível"
            elif self.status == "in_use":
                return f"🔄 Em uso ({ias_count} IAs)" if ias_count > 0 else "🔄 Em uso"
            elif self.status == "offline":
                return "❌ Offline"
            else:
                return f"❓ Desconhecido ({ias_count} IAs)" if ias_count > 0 else "❓ Desconhecido"
        except Exception as e:
            LOGGER.error(f"Erro em status_display: {e}")
            return f"{self.status.title()}" if self.status else "Desconhecido"

    @property
    def connection_string(self):
        if self.username and self.password:
            return f"{self.proxy_type.lower()}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.proxy_type.lower()}://{self.host}:{self.port}"

    @property
    def display_name(self):
        return f"{self.name} ({self.host}:{self.port})"

    def __repr__(self):
        return (
            f"<Proxy(name='{self.name}', host='{self.host}:{self.port}', "
            f"status='{self.status}', ias={self.ias_count})>"
        )
