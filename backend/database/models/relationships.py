from sqlalchemy.orm import relationship

from database.models.ai_direct_credentials import AIDirectCredentials
from database.models.ai_tool import AITool
from database.models.proxy import Proxy
from database.models.user import User
from database.models.ai_session import AISession
from database.models.browser_settings import BrowserSettings
from database.models.device_data import DeviceData
from database.models.download import Download
from database.models.payment import Payment
from database.models.notification import Notification
from database.models.user_favorite import UserFavorite
from database.models.user_session import UserSession


# Adicionar relacionamentos ao User
User.favorites = relationship(
    "UserFavorite", back_populates="user", cascade="all, delete-orphan"
)

User.payments = relationship(
    "Payment", back_populates="user", cascade="all, delete-orphan"
)

User.browser_settings = relationship(
    "BrowserSettings",
    back_populates="user",
    uselist=False,
    cascade="all, delete-orphan",
)

User.sessions = relationship(
    "UserSession", back_populates="user", cascade="all, delete-orphan"
)

User.downloads = relationship(
    "Download", back_populates="user", cascade="all, delete-orphan"
)

# NOVO RELACIONAMENTO PARA AI_SESSIONS
User.ai_sessions = relationship(
    "AISession", back_populates="user", cascade="all, delete-orphan"
)

# Adicionar relacionamentos ao AITool
AITool.favorites = relationship(
    "UserFavorite", back_populates="ai_tool", cascade="all, delete-orphan"
)

# NOVO RELACIONAMENTO PARA AI_SESSIONS
AITool.ai_sessions = relationship(
    "AISession", back_populates="ai_tool", cascade="all, delete-orphan"
)

# *** RELACIONAMENTOS IA-PROXY CORRIGIDOS ***
AITool.proxy = relationship("Proxy", back_populates="assigned_ais")

# Adicionar relacionamentos ao Proxy
Proxy.assigned_ais = relationship("AITool", back_populates="proxy")

AITool.cookie_sessions = relationship(
    "AISessionCookies", back_populates="ai_tool", cascade="all, delete, delete-orphan"
)

User.device_data = relationship(
    "DeviceData", 
    foreign_keys="DeviceData.user_id",
    back_populates="user", 
    cascade="all, delete-orphan"
)

# Direct - CASCADE DELETE  
AITool.direct_credentials = relationship(
    "AIDirectCredentials", 
    back_populates="ai_tool", 
    uselist=False,
    cascade="all, delete, delete-orphan"
)

AIDirectCredentials.ai_tool = relationship(
    "AITool", 
    back_populates="direct_credentials"
)

# Relacionamento User -> Notificações (notificações recebidas)
User.notifications = relationship(
    "Notification",
    foreign_keys="[Notification.user_id]",
    back_populates="user",
    cascade="all, delete-orphan"
)

# Relacionamento User -> Notificações Criadas (para admins)
User.created_notifications = relationship(
    "Notification",
    foreign_keys="[Notification.created_by_admin_id]",
    back_populates="created_by"
)