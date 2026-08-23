"""Schemas dos favoritos de página por ferramenta (Fase 5) — ver
app/models/tool_bookmark.py."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ToolBookmarkCreate(BaseModel):
    ai_tool_id: str
    url: str = Field(min_length=1, max_length=4000)
    title: Optional[str] = Field(default=None, max_length=255)


class ToolBookmarkPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ai_tool_id: str
    url: str
    title: Optional[str] = None
    created_at: datetime
