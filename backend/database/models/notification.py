from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, Text, Index
from sqlalchemy.orm import relationship

from database.models.base import BaseModel
from database.sqlalchemy_config import Base
from utils.logger import LOGGER


class Notification(Base, BaseModel):
    """
    Modelo de notificações do sistema
    Suporta notificações pessoais (para um usuário) e globais (para todos)
    """

    __tablename__ = "notifications"

    # Relacionamento com usuário (NULL para notificações globais)
    user_id = Column(
        String(36), 
        ForeignKey("users.id"), 
        nullable=True,
        index=True
    )

    # Identificação do tipo de notificação
    is_global = Column(Boolean, default=False, nullable=False, index=True)

    # Admin que criou a notificação (para notificações globais)
    created_by_admin_id = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=True
    )

    # Tipo de notificação
    type = Column(
        String(50), 
        nullable=False, 
        default="sistema"
    )  # Valores: "sistema", "download", "atualizacao", "admin_broadcast", "pagamento"

    # Prioridade
    priority = Column(
        String(20), 
        nullable=False, 
        default="normal"
    )  # Valores: "normal", "importante", "critica"

    # Conteúdo da notificação
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    icon = Column(String(50), default="🔔")

    # Metadados extras em JSON (paths de arquivos, URLs, etc)
    # ALTERADO: metadata → extra_data para evitar conflito com SQLAlchemy
    extra_data = Column(JSON, default=dict)

    # Status de leitura para notificações pessoais
    is_read = Column(Boolean, default=False, nullable=False)

    # Array de user_ids que já leram (para notificações globais)
    read_by = Column(JSON, default=list)

    # Data de expiração (opcional)
    expires_at = Column(DateTime, nullable=True)

    # Relacionamentos
    user = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="notifications"
    )

    created_by = relationship(
        "User",
        foreign_keys=[created_by_admin_id],
        back_populates="created_notifications"
    )

    # Índices compostos para otimização de queries
    __table_args__ = (
        Index('idx_user_unread', 'user_id', 'is_read'),
        Index('idx_global_active', 'is_global', 'created_at'),
    )

    def __init__(self, **kwargs):
        """Inicializa notificação com valores padrão"""
        super().__init__(**kwargs)
        
        # Garantir que read_by seja lista vazia se não especificado
        if not self.read_by:
            self.read_by = []
        
        # Garantir que extra_data seja dict vazio se não especificado
        if not self.extra_data:
            self.extra_data = {}

    def is_read_by_user(self, user_id: str) -> bool:
        """
        Verifica se usuário específico já leu a notificação
        
        Args:
            user_id: ID do usuário a verificar
            
        Returns:
            True se usuário já leu, False caso contrário
        """
        if self.is_global:
            # Para notificações globais, verificar array read_by
            return user_id in (self.read_by or [])
        else:
            # Para notificações pessoais, verificar campo is_read
            return self.is_read

    def mark_read_by_user(self, user_id: str) -> None:
        """
        Marca notificação como lida para usuário específico
        
        Args:
            user_id: ID do usuário que leu a notificação
        """
        if self.is_global:
            # Para notificações globais, adicionar ao array read_by
            if not self.read_by:
                self.read_by = []
            
            if user_id not in self.read_by:
                self.read_by.append(user_id)
                LOGGER.info(
                    f"Notificação global {self.id} marcada como lida por usuário {user_id}"
                )
        else:
            # Para notificações pessoais, marcar is_read como True
            if not self.is_read:
                self.is_read = True
                LOGGER.info(
                    f"Notificacao pessoal {self.id} marcada como lida"
                )

    def check_if_all_users_read(self, total_active_users: int) -> bool:
        """
        Verifica se todos os usuarios ativos do sistema ja leram a notificacao global
        
        Args:
            total_active_users: Numero total de usuarios ativos no sistema
            
        Returns:
            True se todos os usuarios leram, False caso contrario
        """
        if not self.is_global:
            # Notificacoes pessoais nao usam essa verificacao
            return False
        
        read_count = len(self.read_by or [])
        
        LOGGER.debug(
            f"Notificacao {self.id}: {read_count}/{total_active_users} usuarios leram"
        )
        
        return read_count >= total_active_users

    def mark_fully_read(self) -> None:
        """
        Marca notificacao como completamente lida (is_read=True)
        Usado quando todos os usuarios ja visualizaram uma notificacao global
        """
        if not self.is_read:
            self.is_read = True
            LOGGER.info(
                f"Notificacao global {self.id} marcada como completamente lida (todos usuarios visualizaram)"
            )

    def is_expired(self) -> bool:
        """
        Verifica se notificação está expirada
        
        Returns:
            True se expirada, False caso contrário
        """
        if not self.expires_at:
            return False
        
        return datetime.now(timezone.utc) > self.expires_at

    def get_read_count(self) -> int:
        """
        Retorna quantos usuários leram a notificação (apenas para globais)
        
        Returns:
            Número de usuários que leram
        """
        if not self.is_global:
            return 1 if self.is_read else 0
        
        return len(self.read_by or [])

    def to_dict(self) -> dict:
        """
        Converte notificação para dicionário
        
        Returns:
            Dicionário com dados da notificação
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "is_global": self.is_global,
            "created_by_admin_id": self.created_by_admin_id,
            "type": self.type,
            "priority": self.priority,
            "title": self.title,
            "message": self.message,
            "icon": self.icon,
            "extra_data": self.extra_data,
            "is_read": self.is_read,
            "read_by": self.read_by,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        type_label = "Global" if self.is_global else "Pessoal"
        return f"<Notification(id={self.id}, type={self.type}, {type_label}, title='{self.title}')>"
