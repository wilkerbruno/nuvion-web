# backend/api/routes/admin.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.security import require_admin

router = APIRouter()


class BroadcastRequest(BaseModel):
    title: str
    message: str
    priority: str = "normal"
    icon: str = "📢"


class UserUpdateRequest(BaseModel):
    status: Optional[str] = None
    account_type: Optional[str] = None
    category: Optional[str] = None


@router.get("/users")
def list_users(limit: int = 200, admin=Depends(require_admin)):
    from crud.crud_manager import crud_system
    users = crud_system.users.get_all(limit=limit)
    return [
        {
            "id":           u.id,
            "username":     u.username,
            "name":         u.name,
            "email":        u.email,
            "phone":        u.phone or "",
            "account_type": u.account_type,
            "status":       u.status,
            "referral_code": u.referral_code or "",
            "created_at":   u.created_at.isoformat() if u.created_at else None,
            "last_login":   u.last_login.isoformat() if u.last_login else None,
        }
        for u in users
    ]


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UserUpdateRequest, admin=Depends(require_admin)):
    from crud.crud_manager import crud_system
    data = {k: v for k, v in body.dict().items() if v is not None}
    ok = crud_system.users.update(user_id, **data)
    if not ok:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return {"message": "Usuário atualizado"}


@router.post("/broadcast")
def broadcast(body: BroadcastRequest, admin=Depends(require_admin)):
    from core.managers.notification_manager import notification_manager
    notif_id = notification_manager.broadcast_notification(
        admin_id=admin["id"],
        title=body.title,
        message=body.message,
        priority=body.priority,
        icon=body.icon,
    )
    if not notif_id:
        raise HTTPException(status_code=500, detail="Falha ao enviar notificação")
    return {"id": notif_id, "message": "Notificação enviada"}


@router.get("/payments")
def admin_payments(limit: int = 200, admin=Depends(require_admin)):
    from crud.crud_manager import crud_system
    payments = crud_system.payments.get_all(limit=limit)
    return [
        {
            "id":          p.id,
            "user_id":     p.user_id,
            "amount":      float(p.amount),
            "description": p.description,
            "status":      p.status,
            "due_date":    p.due_date.isoformat() if p.due_date else None,
            "payment_date": p.payment_date.isoformat() if p.payment_date else None,
        }
        for p in payments
    ]


@router.post("/diamonds/{user_id}")
def add_diamonds(user_id: str, amount: int, reason: str = "Bônus administrativo", admin=Depends(require_admin)):
    from core.services.reward_service import RewardService
    ok = RewardService.add_diamonds(
        user_id=user_id,
        amount=amount,
        transaction_type="admin_bonus",
        description=reason,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Falha ao adicionar diamantes")
    return {"diamonds_added": amount}
