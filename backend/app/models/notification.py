"""Notificações (portado de database/models/notification.py)."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import relationship

from app.core.logging import LOGGER
from app.db.base_class import Base
from app.models.base import BaseModel


class Notification(Base, BaseModel):
    """Notificações pessoais (um usuário) ou globais (todos os usuários)."""

    __tablename__ = "notifications"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    is_global = Column(Boolean, default=False, nullable=False, index=True)
    created_by_admin_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    type = Column(String(50), nullable=False, default="sistema")
    priority = Column(String(20), nullable=False, default="normal")

    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    icon = Column(String(50), default="🔔")

    extra_data = Column(JSON, default=dict)

    is_read = Column(Boolean, default=False, nullable=False)
    read_by = Column(JSON, default=list)

    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id], back_populates="notifications")
    created_by = relationship(
        "User", foreign_keys=[created_by_admin_id], back_populates="created_notifications"
    )

    __table_args__ = (
        Index("idx_user_unread", "user_id", "is_read"),
        Index("idx_global_active", "is_global", "created_at"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.read_by:
            self.read_by = []
        if not self.extra_data:
            self.extra_data = {}

    def is_read_by_user(self, user_id: str) -> bool:
        if self.is_global:
            return user_id in (self.read_by or [])
        return self.is_read

    def mark_read_by_user(self, user_id: str) -> None:
        if self.is_global:
            if not self.read_by:
                self.read_by = []
            if user_id not in self.read_by:
                self.read_by.append(user_id)
                LOGGER.info(f"Notificação global {self.id} marcada como lida por usuário {user_id}")
        else:
            if not self.is_read:
                self.is_read = True
                LOGGER.info(f"Notificação pessoal {self.id} marcada como lida")

    def check_if_all_users_read(self, total_active_users: int) -> bool:
        if not self.is_global:
            return False
        read_count = len(self.read_by or [])
        return read_count >= total_active_users

    def mark_fully_read(self) -> None:
        if not self.is_read:
            self.is_read = True
            LOGGER.info(f"Notificação global {self.id} marcada como completamente lida")

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def get_read_count(self) -> int:
        if not self.is_global:
            return 1 if self.is_read else 0
        return len(self.read_by or [])

    def to_dict(self) -> dict:
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
