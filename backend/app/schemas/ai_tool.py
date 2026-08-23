"""Schemas do catálogo de ferramentas de IA (Fase 4)."""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class AIToolCreate(BaseModel):
    name: str
    url: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []
    observations: Optional[str] = None
    proxy_id: Optional[str] = None
    login_method: str = "manual"
    is_featured: bool = False
    block_extensions: bool = False


class AIToolUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    observations: Optional[str] = None
    proxy_id: Optional[str] = None
    login_method: Optional[str] = None
    is_featured: Optional[bool] = None
    block_extensions: Optional[bool] = None


class AIToolPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    url: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []
    observations: Optional[str] = None
    proxy_id: Optional[str] = None
    block_extensions: bool = False
    is_featured: bool
    login_method: str
    is_favorite: bool = False


class FavoriteToggleResponse(BaseModel):
    ai_tool_id: str
    is_favorite: bool
