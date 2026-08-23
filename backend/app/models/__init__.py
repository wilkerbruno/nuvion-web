"""Agrega todos os modelos (portado de database/models/__init__.py).

Importar este módulo garante que todas as tabelas fiquem registradas em
`Base.metadata` — usado tanto pelo Alembic (autogenerate) quanto por
`Base.metadata.create_all()` em testes locais.
"""
from app.db.base_class import Base
from app.models import relationships  # noqa: F401 — só para registrar os relationships
from app.models.ai_direct_credentials import AIDirectCredentials
from app.models.ai_session import AISession
from app.models.ai_session_cookies import AISessionCookies
from app.models.ai_tool import AITool
from app.models.base import BaseModel
from app.models.browser_settings import BrowserSettings
from app.models.device_data import DeviceData
from app.models.download import Download
from app.models.expense import Expense
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.payment_config import PaymentConfig
from app.models.proxy import Proxy
from app.models.reward import Reward
from app.models.user import User
from app.models.user_favorite import UserFavorite
from app.models.user_session import UserSession

__all__ = [
    "Base",
    "BaseModel",
    "User",
    "AITool",
    "AIDirectCredentials",
    "AISession",
    "AISessionCookies",
    "UserFavorite",
    "Payment",
    "PaymentConfig",
    "BrowserSettings",
    "UserSession",
    "Download",
    "Proxy",
    "DeviceData",
    "Notification",
    "Expense",
    "Reward",
]
