"""Schemas de histórico de downloads (Fase 4)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DownloadCreate(BaseModel):
    file_name: str
    file_path: Optional[str] = None
    url: Optional[str] = None
    status: str = "in_progress"


class DownloadUpdate(BaseModel):
    status: str = Field(pattern="^(in_progress|completed|failed|cancelled)$")


class DownloadPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    file_name: str
    file_path: Optional[str] = None
    url: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = None
    created_at: datetime
