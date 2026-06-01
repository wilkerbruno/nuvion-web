# backend/api/routes/notifications.py
from fastapi import APIRouter, Depends
from core.security import get_current_user_id

router = APIRouter()


@router.get("")
def list_notifications(
    include_read: bool = False,
    limit: int = 50,
    user_id: str = Depends(get_current_user_id),
):
    from crud.crud_manager import crud_system
    from core.managers.notification_manager import notification_manager
    return notification_manager.get_user_notifications(
        user_id, include_read=include_read, limit=limit
    )


@router.post("/{notif_id}/read")
def mark_read(notif_id: str, user_id: str = Depends(get_current_user_id)):
    from core.managers.notification_manager import notification_manager
    notification_manager.mark_as_read(notif_id, user_id)
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(user_id: str = Depends(get_current_user_id)):
    from core.managers.notification_manager import notification_manager
    notification_manager.mark_all_as_read(user_id)
    return {"ok": True}


@router.get("/unread-count")
def unread_count(user_id: str = Depends(get_current_user_id)):
    from core.managers.notification_manager import notification_manager
    count = notification_manager.get_unread_count(user_id)
    return {"count": count}
