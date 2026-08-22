"""Modelo de downloads (portado de database/models/download.py).

No desktop, o download acontecia dentro do processo do app. Na web, quem
baixa o arquivo é o navegador do usuário (via extensão) — este modelo
continua servindo para o histórico/status exibido no painel.
"""
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.models.base import BaseModel


class Download(Base, BaseModel):
    __tablename__ = "downloads"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(2048))
    url = Column(String(2048))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    status = Column(String(50))

    user = relationship("User", back_populates="downloads")
