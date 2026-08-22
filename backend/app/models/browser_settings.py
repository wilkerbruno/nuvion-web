"""Configurações de navegação por usuário (portado de database/models/browser_settings.py).

`anti_detection_settings` passa a ser lido pela extensão (via API) para
decidir como mascarar fingerprint em cada sessão de navegação.
"""
from sqlalchemy import JSON, Column, ForeignKey, String
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.models.base import BaseModel


class BrowserSettings(Base, BaseModel):
    __tablename__ = "browser_settings"

    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    anti_detection_settings = Column(JSON, default=dict)
    cache_settings = Column(JSON, default=dict)
    language = Column(String(10), default="pt_BR")
    theme = Column(String(20), default="dark")
    privacy_settings = Column(JSON, default=dict)

    user = relationship("User", back_populates="browser_settings", uselist=False)
