"""Rotas de notificações (Fase 4 — equivalente web de notifications_widget.py
+ notification_manager.py).

O plano de migração (seção 6) cogitava WebSocket para push em tempo real;
aqui optamos por polling curto no painel (`GET /notifications/me/unread-count`
a cada N segundos) — mesma escolha pragmática já feita para status de
pagamento na Fase 3 (`/payments/{id}`), evitando abrir uma segunda
tecnologia de transporte (WebSocket) só para este recurso. Fica documentado
como possível otimização futura, não uma lacuna silenciosa.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_admin
from app.crud import notification as notification_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import (
    BroadcastRequest,
    DeleteExpiredResponse,
    MarkAllReadResponse,
    NotificationPublic,
    NotificationStats,
    UnreadCount,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])
admin_router = APIRouter(prefix="/admin/notifications", tags=["notifications-admin"])


def _to_public(notification, user_id: str) -> NotificationPublic:
    public = NotificationPublic.model_validate(notification)
    public.is_read = notification.is_read_by_user(user_id)
    return public


@router.get("/me", response_model=List[NotificationPublic])
def my_notifications(
    include_read: bool = False,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    notifications = notification_crud.list_for_user(
        db, current_user.id, include_read=include_read, limit=limit
    )
    return [_to_public(n, current_user.id) for n in notifications]


@router.get("/me/unread-count", response_model=UnreadCount)
def unread_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return UnreadCount(unread_count=notification_crud.count_unread(db, current_user.id))


@router.post("/me/read-all", response_model=MarkAllReadResponse)
def read_all(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    count = notification_crud.mark_all_as_read(db, current_user.id)
    return MarkAllReadResponse(marked_count=count)


@router.post("/{notification_id}/read", response_model=NotificationPublic)
def read_one(
    notification_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    notification = notification_crud.get_by_id(db, notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notificação não encontrada")
    notification_crud.mark_as_read(db, notification, current_user.id)
    return _to_public(notification, current_user.id)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_one(
    notification_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    notification = notification_crud.get_by_id(db, notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notificação não encontrada")

    is_owner = (not notification.is_global) and notification.user_id == current_user.id
    is_admin = current_user.account_type == "Admin"
    if not (is_owner or (notification.is_global and is_admin)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissão")

    notification_crud.delete_notification(db, notification)


@admin_router.post("/broadcast", response_model=NotificationPublic, status_code=status.HTTP_201_CREATED)
def broadcast(
    payload: BroadcastRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    notification = notification_crud.create_global(db, admin_id=admin.id, **payload.model_dump())
    return _to_public(notification, admin.id)


@admin_router.get("/stats", response_model=List[NotificationStats])
def stats(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return notification_crud.global_stats(db)


@admin_router.delete("/expired", response_model=DeleteExpiredResponse)
def delete_expired(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    count = notification_crud.delete_expired(db)
    return DeleteExpiredResponse(deleted_count=count)
