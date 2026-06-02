import uuid
from datetime import datetime, timezone  # ← Adicionar timezone

from sqlalchemy import Column, DateTime, String
from sqlalchemy.ext.declarative import declared_attr


class BaseModel:
    """Classe base para todos os modelos com campos comuns"""

    @declared_attr
    def __tablename__(cls):
        """Gera nome da tabela automaticamente"""
        return cls.__name__.lower() + "s"

    # ID padrão UUID para todos os modelos
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Timestamps - CORREÇÃO AQUI
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"
