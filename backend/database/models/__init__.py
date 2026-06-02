from database.models.ai_session_cookies import AISessionCookies
from database.models.ai_tool import AITool
from database.models.base import BaseModel
from database.models.browser_settings import BrowserSettings
from database.models.device_data import DeviceData
from database.models.download import Download
from database.models.payment import Payment
from database.models.payment_config import PaymentConfig
from database.models.proxy import Proxy
from database.models.relationships import *
from database.models.user import User
from database.models.user_favorite import UserFavorite
from database.models.user_session import UserSession
from database.models.ai_direct_credentials import AIDirectCredentials
from database.models.notification import Notification  # ← NOVO IMPORT
from database.sqlalchemy_config import Base
from database.models.expense import Expense

from . import relationships
from .ai_session import AISession

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
]
