from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from database.models.base import BaseModel
from database.sqlalchemy_config import Base


class Download(Base, BaseModel):
    __tablename__ = "downloads"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(2048))
    url = Column(String(2048))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    status = Column(String(50))

    # Relacionamento
    user = relationship("User", back_populates="downloads")
