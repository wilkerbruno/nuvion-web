"""Mixin base para todos os modelos (portado 1:1 de database/models/base.py)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String
from sqlalchemy.ext.declarative import declared_attr


class BaseModel:
    """Classe base para todos os modelos com campos comuns."""

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower() + "s"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"
