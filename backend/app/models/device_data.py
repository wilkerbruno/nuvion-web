"""Dados de dispositivo (portado de database/models/device_data.py).

`device_id` passa a identificar navegador+extensão instalada (não mais uma
máquina com o app desktop instalado) — ver plano de migração, seção 4.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.models.base import BaseModel
from app.utils.datetime_utils import safe_datetime_diff


class DeviceData(Base, BaseModel):
    """Dados específicos de dispositivo/navegador do usuário."""

    __tablename__ = "device_data"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    device_id = Column(String(36), unique=True, nullable=False, index=True)

    device_name = Column(String(100), nullable=False)
    device_type = Column(String(50))

    ip_address = Column(String(45), nullable=False)
    mac_address = Column(String(17), nullable=False)

    os_name = Column(String(50))
    os_version = Column(String(100))

    last_login = Column(DateTime, nullable=False)
    last_logout = Column(DateTime)
    online_time = Column(Integer, default=0)

    cpu_info = Column(Text)
    memory_total = Column(String(20))
    resolution = Column(String(20))

    is_active = Column(String(10), default="Offline")

    is_authorized = Column(Boolean, default=False, nullable=False)
    authorization_status = Column(String(20), default="pending", nullable=False, index=True)
    authorized_by_admin_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    authorization_date = Column(DateTime, nullable=True)
    first_seen_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", foreign_keys=[user_id], back_populates="device_data")
    authorized_by = relationship(
        "User", foreign_keys=[authorized_by_admin_id], backref="authorized_devices"
    )

    def calculate_online_time(self):
        if not self.last_login:
            return 0
        end_time = self.last_logout or datetime.now(timezone.utc)
        return safe_datetime_diff(self.last_login, end_time)

    def format_online_time(self):
        total_seconds = self.online_time or self.calculate_online_time()
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

    def get_short_mac(self):
        if self.mac_address and len(self.mac_address) >= 12:
            return f"...{self.mac_address[-8:]}"
        return self.mac_address or "N/A"

    def is_authorized_device(self) -> bool:
        return self.is_authorized and self.authorization_status == "authorized"

    def can_login(self) -> bool:
        return self.is_authorized_device() and self.authorization_status != "rejected"

    def authorize(self, admin_user_id: str) -> None:
        self.is_authorized = True
        self.authorization_status = "authorized"
        self.authorized_by_admin_id = admin_user_id
        self.authorization_date = datetime.now(timezone.utc)

    def reject(self) -> None:
        self.is_authorized = False
        self.authorization_status = "rejected"
        self.authorization_date = datetime.now(timezone.utc)

    def revoke_authorization(self) -> None:
        self.is_authorized = False
        self.authorization_status = "pending"
        self.authorized_by_admin_id = None
        self.authorization_date = None

    def update_last_seen(self) -> None:
        self.last_seen_at = datetime.now(timezone.utc)
