"""Relacionamentos entre modelos (portado de database/models/relationships.py).

Mantido como módulo separado, importado por último em app/models/__init__.py
— igual ao projeto original, para evitar import circular entre os modelos.

Correção feita na migração: o arquivo original reatribuía
`AITool.proxy`, `Proxy.assigned_ais`, `AITool.cookie_sessions` e
`AITool.direct_credentials` aqui, mas essas quatro relações já são
declaradas inline nas próprias classes (app/models/ai_tool.py e
app/models/proxy.py). A dupla declaração gerava
`SADeprecationWarning: ... replacing an existing ORM-mapped attribute` no
SQLAlchemy 2.x, com aviso de virar erro em versão futura — removidas daqui,
mantendo só a declaração inline de cada uma.
"""
from sqlalchemy.orm import relationship

from app.models.ai_direct_credentials import AIDirectCredentials
from app.models.ai_tool import AITool
from app.models.user import User

# Nota: relationship() abaixo referencia outras classes (Payment, Proxy,
# UserSession etc.) só pelo nome em string — o SQLAlchemy resolve isso via
# registry no momento do mapper configure, então elas não precisam estar
# importadas aqui. O que garante que existam no registry é a ordem de
# import em app/models/__init__.py, que importa todos os modelos antes de
# importar este módulo por último.

User.favorites = relationship("UserFavorite", back_populates="user", cascade="all, delete-orphan")
User.payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
User.browser_settings = relationship(
    "BrowserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan"
)
User.sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
User.proxies = relationship("Proxy", back_populates="owner", cascade="all, delete-orphan")
User.downloads = relationship("Download", back_populates="user", cascade="all, delete-orphan")
User.ai_sessions = relationship("AISession", back_populates="user", cascade="all, delete-orphan")

AITool.favorites = relationship("UserFavorite", back_populates="ai_tool", cascade="all, delete-orphan")
AITool.ai_sessions = relationship("AISession", back_populates="ai_tool", cascade="all, delete-orphan")
# AITool.proxy / Proxy.assigned_ais / AITool.cookie_sessions / AITool.direct_credentials
# já são declaradas inline em ai_tool.py e proxy.py — ver nota acima.

User.device_data = relationship(
    "DeviceData", foreign_keys="DeviceData.user_id", back_populates="user", cascade="all, delete-orphan"
)

AIDirectCredentials.ai_tool = relationship("AITool", back_populates="direct_credentials")

User.notifications = relationship(
    "Notification", foreign_keys="[Notification.user_id]", back_populates="user",
    cascade="all, delete-orphan",
)
User.created_notifications = relationship(
    "Notification", foreign_keys="[Notification.created_by_admin_id]", back_populates="created_by"
)

User.tool_bookmarks = relationship("ToolBookmark", back_populates="user", cascade="all, delete-orphan")
AITool.tool_bookmarks = relationship("ToolBookmark", back_populates="ai_tool", cascade="all, delete-orphan")
