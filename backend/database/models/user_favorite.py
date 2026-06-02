from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from database.models.base import BaseModel
from database.sqlalchemy_config import Base


class UserFavorite(Base, BaseModel):
    """Modelo de favoritos do usuário"""

    __tablename__ = "user_favorites"

    # Chaves estrangeiras
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    ai_tool_id = Column(String(36), ForeignKey("ai_tools.id"), nullable=False)

    # Relacionamentos
    user = relationship("User", back_populates="favorites")
    ai_tool = relationship("AITool", back_populates="favorites")

    # Constraint única para evitar duplicatas
    __table_args__ = (UniqueConstraint("user_id", "ai_tool_id", name="_user_tool_uc"),)
