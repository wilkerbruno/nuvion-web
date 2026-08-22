"""Favoritos do usuário (portado de database/models/user_favorite.py)."""
from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.models.base import BaseModel


class UserFavorite(Base, BaseModel):
    """Modelo de favoritos do usuário."""

    __tablename__ = "user_favorites"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    ai_tool_id = Column(String(36), ForeignKey("ai_tools.id"), nullable=False)

    user = relationship("User", back_populates="favorites")
    ai_tool = relationship("AITool", back_populates="favorites")

    __table_args__ = (UniqueConstraint("user_id", "ai_tool_id", name="_user_tool_uc"),)
