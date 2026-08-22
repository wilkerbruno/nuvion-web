"""Dashboard inicial — equivalente web de core/widgets/dashboard_widget.py
e core/widgets/settings/dashboard_section.py.

Nesta fase é só um resumo de conta (perfil + status de pagamento). As
próximas fases adicionam proxies, IA, diamantes etc. ao mesmo painel.
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_active_user
from app.models.user import User
from app.schemas.user import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/me", response_model=DashboardSummary)
def my_dashboard(current_user: User = Depends(get_current_active_user)):
    return DashboardSummary(
        user=current_user,
        payment_status=current_user.get_payment_status_info(),
        is_blocked=current_user.is_blocked(),
        block_message=current_user.get_block_message() if current_user.is_blocked() else None,
    )
