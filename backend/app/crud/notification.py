"""CRUD de notificações (portado de crud/notification_crud.py +
core/managers/notification_manager.py — aqui juntos num módulo só, já que
o "manager" do desktop só repassava para o CRUD e emitia sinais Qt, que não
fazem sentido numa API HTTP).
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User


def count_active_users(db: Session) -> int:
    return db.query(func.count(User.id)).filter(User.status == "Ativo").scalar() or 0


def create_personal(
    db: Session,
    *,
    user_id: str,
    type: str,
    priority: str,
    title: str,
    message: str,
    icon: str = "🔔",
    extra_data: Optional[dict] = None,
    expires_at: Optional[datetime] = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        is_global=False,
        type=type,
        priority=priority,
        title=title,
        message=message,
        icon=icon,
        extra_data=extra_data or {},
        expires_at=expires_at,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def create_global(
    db: Session,
    *,
    admin_id: str,
    type: str = "admin_broadcast",
    priority: str = "normal",
    title: str,
    message: str,
    icon: str = "📢",
    extra_data: Optional[dict] = None,
    expires_at: Optional[datetime] = None,
) -> Notification:
    notification = Notification(
        user_id=None,
        is_global=True,
        created_by_admin_id=admin_id,
        type=type,
        priority=priority,
        title=title,
        message=message,
        icon=icon,
        extra_data=extra_data or {},
        expires_at=expires_at,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def list_for_user(
    db: Session, user_id: str, include_read: bool = False, limit: int = 50, offset: int = 0
) -> List[Notification]:
    now = datetime.now(timezone.utc)
    base_filter = or_(Notification.expires_at.is_(None), Notification.expires_at > now)

    personal_query = db.query(Notification).filter(
        and_(Notification.user_id == user_id, Notification.is_global.is_(False), base_filter)
    )
    if not include_read:
        personal_query = personal_query.filter(Notification.is_read.is_(False))

    global_query = db.query(Notification).filter(and_(Notification.is_global.is_(True), base_filter))
    if not include_read:
        global_query = global_query.filter(~Notification.read_by.contains([user_id]))

    return (
        personal_query.union(global_query)
        .order_by(desc(Notification.created_at))
        .limit(limit)
        .offset(offset)
        .all()
    )


def count_unread(db: Session, user_id: str) -> int:
    now = datetime.now(timezone.utc)

    personal_count = (
        db.query(func.count(Notification.id))
        .filter(
            and_(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
                Notification.is_global.is_(False),
                or_(Notification.expires_at.is_(None), Notification.expires_at > now),
            )
        )
        .scalar()
        or 0
    )

    global_count = (
        db.query(func.count(Notification.id))
        .filter(
            and_(
                Notification.is_global.is_(True),
                ~Notification.read_by.contains([user_id]),
                or_(Notification.expires_at.is_(None), Notification.expires_at > now),
            )
        )
        .scalar()
        or 0
    )

    return personal_count + global_count


def get_by_id(db: Session, notification_id: str) -> Optional[Notification]:
    return db.query(Notification).filter(Notification.id == notification_id).first()


def mark_as_read(db: Session, notification: Notification, user_id: str) -> None:
    notification.mark_read_by_user(user_id)
    if notification.is_global and notification.check_if_all_users_read(count_active_users(db)):
        notification.mark_fully_read()
    db.commit()


def mark_all_as_read(db: Session, user_id: str) -> int:
    count = 0

    personal = (
        db.query(Notification)
        .filter(and_(Notification.user_id == user_id, Notification.is_read.is_(False)))
        .all()
    )
    for notification in personal:
        notification.is_read = True
        count += 1

    global_unread = (
        db.query(Notification)
        .filter(and_(Notification.is_global.is_(True), ~Notification.read_by.contains([user_id])))
        .all()
    )
    total_active = count_active_users(db)
    for notification in global_unread:
        if not notification.read_by:
            notification.read_by = []
        if user_id not in notification.read_by:
            notification.read_by.append(user_id)
            count += 1
            if notification.check_if_all_users_read(total_active):
                notification.mark_fully_read()

    db.commit()
    return count


def delete_notification(db: Session, notification: Notification) -> None:
    db.delete(notification)
    db.commit()


def delete_expired(db: Session) -> int:
    now = datetime.now(timezone.utc)
    expired = (
        db.query(Notification)
        .filter(and_(Notification.expires_at.isnot(None), Notification.expires_at <= now))
        .all()
    )
    count = len(expired)
    for notification in expired:
        db.delete(notification)
    db.commit()
    return count


def global_stats(db: Session, admin_id: Optional[str] = None) -> List[dict]:
    query = db.query(Notification).filter(Notification.is_global.is_(True))
    if admin_id:
        query = query.filter(Notification.created_by_admin_id == admin_id)

    notifications = query.order_by(desc(Notification.created_at)).all()
    total_users = count_active_users(db)

    stats = []
    for notification in notifications:
        read_count = len(notification.read_by or [])
        stats.append(
            {
                "id": notification.id,
                "title": notification.title,
                "type": notification.type,
                "priority": notification.priority,
                "created_at": notification.created_at,
                "read_count": read_count,
                "total_users": total_users,
                "read_percentage": (read_count / total_users * 100) if total_users > 0 else 0,
                "is_expired": notification.is_expired(),
            }
        )
    return stats
