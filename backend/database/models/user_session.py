from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from database.models.base import BaseModel
from database.sqlalchemy_config import Base


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

    # Relacionamento
    user = relationship("User", back_populates="sessions")
