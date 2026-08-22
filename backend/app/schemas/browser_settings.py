"""Schemas de configurações de navegação (anti-detecção) — consumidos pela
extensão (Fase 2) para decidir como mascarar fingerprint em cada sessão.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict


class BrowserSettingsPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    anti_detection_settings: dict
    cache_settings: dict
    language: str
    theme: str
    privacy_settings: dict


class BrowserSettingsUpdate(BaseModel):
    anti_detection_settings: Optional[dict] = None
    cache_settings: Optional[dict] = None
    language: Optional[str] = None
    theme: Optional[str] = None
    privacy_settings: Optional[dict] = None
