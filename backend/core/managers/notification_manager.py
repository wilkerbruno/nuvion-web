# backend/core/managers/notification_manager.py
"""
Facade de notificações para o backend web.
Versão sem PyQt6 — sem signals, sem QObject.
"""
from utils.logger import LOGGER


class NotificationManager:

    def get_user_notifications(
        self, user_id: str, include_read: bool = False, limit: int = 50
    ):
        try:
            from crud.crud_manager import crud_system
            notifs = crud_system.notifications.get_user_notifications(
                user_id, include_read=include_read, limit=limit
            )
            return [n.to_dict() for n in notifs]
        except Exception as e:
            LOGGER.error(f"get_user_notifications: {e}")
            return []

    def get_unread_count(self, user_id: str) -> int:
        try:
            from crud.crud_manager import crud_system
            return crud_system.notifications.count_unread(user_id)
        except Exception as e:
            LOGGER.error(f"get_unread_count: {e}")
            return 0

    def mark_as_read(self, notif_id: str, user_id: str) -> bool:
        try:
            from crud.crud_manager import crud_system
            return crud_system.notifications.mark_as_read(notif_id, user_id)
        except Exception as e:
            LOGGER.error(f"mark_as_read: {e}")
            return False

    def mark_all_as_read(self, user_id: str) -> int:
        try:
            from crud.crud_manager import crud_system
            return crud_system.notifications.mark_all_as_read(user_id)
        except Exception as e:
            LOGGER.error(f"mark_all_as_read: {e}")
            return 0

    def broadcast_notification(
        self,
        admin_id: str,
        title: str,
        message: str,
        priority: str = "normal",
        icon: str = "📢",
    ):
        try:
            from crud.crud_manager import crud_system
            notif = crud_system.notifications.create_global_notification(
                admin_id=admin_id,
                type="admin_broadcast",
                priority=priority,
                title=title,
                message=message,
                icon=icon,
            )
            return notif.id if notif else None
        except Exception as e:
            LOGGER.error(f"broadcast_notification: {e}")
            return None

    def create_personal_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        type: str = "sistema",
        priority: str = "normal",
        icon: str = "🔔",
        extra_data: dict = None,
    ):
        try:
            from crud.crud_manager import crud_system
            notif = crud_system.notifications.create_personal_notification(
                user_id=user_id,
                type=type,
                priority=priority,
                title=title,
                message=message,
                icon=icon,
                extra_data=extra_data or {},
            )
            return notif.id if notif else None
        except Exception as e:
            LOGGER.error(f"create_personal_notification: {e}")
            return None


notification_manager = NotificationManager()