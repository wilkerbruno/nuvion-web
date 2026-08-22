"""Sessões de login do usuário (portado de database/models/user_session.py).

No desktop isso registrava sessões locais do app. Na web, passa a registrar
sessões de login no painel/extensão (IP, navegador, dispositivo) — a mesma
tabela, com o mesmo propósito de auditoria.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.models.base import BaseModel


class UserSession(Base, BaseModel):
    __tablename__ = "user_sessions"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    login_time = Column(DateTime)
    logout_time = Column(DateTime)
    ip_address = Column(String(45))
    os = Column(String(50))
    browser = Column(String(50))
    device = Column(String(100))
    last_activity_time = Column(DateTime)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="sessions")
