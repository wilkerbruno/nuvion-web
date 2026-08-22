"""Schemas de notificações (Fase 4)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: Optional[str] = None
    is_global: bool
    type: str
    priority: str
    title: str
    message: str
    icon: str
    extra_data: dict
    is_read: bool
    expires_at: Optional[datetime] = None
    created_at: datetime


class UnreadCount(BaseModel):
    unread_count: int


class BroadcastRequest(BaseModel):
    title: str
    message: str
    priority: str = "normal"
    icon: str = "📢"
    extra_data: Optional[dict] = None
    expires_at: Optional[datetime] = None


class NotificationStats(BaseModel):
    id: str
    title: str
    type: str
    priority: str
    created_at: datetime
    read_count: int
    total_users: int
    read_percentage: float
    is_expired: bool


class MarkAllReadResponse(BaseModel):
    marked_count: int


class DeleteExpiredResponse(BaseModel):
    deleted_count: int
