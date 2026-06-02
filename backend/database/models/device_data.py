# database/models/device_data.py
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.models.base import BaseModel
from database.sqlalchemy_config import Base
from utils.datetime_utils import safe_datetime_diff


class DeviceData(Base, BaseModel):
    """Modelo para armazenar dados específicos de dispositivo do usuário"""

    __tablename__ = "device_data"

    # Relacionamento com usuário
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Device Token
    device_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID do dispositivo
    
    # Dados básicos do dispositivo
    device_name = Column(String(100), nullable=False)  # Nome do computador
    device_type = Column(String(50))  # Desktop, Laptop, etc.

    # Dados de rede
    ip_address = Column(String(45), nullable=False)  # IPv4 ou IPv6
    mac_address = Column(String(17), nullable=False)  # Format: AA:BB:CC:DD:EE:FF

    # Dados do sistema operacional
    os_name = Column(String(50))  # Windows, Linux, macOS
    os_version = Column(String(100))  # Versão específica do SO

    # Dados de sessão
    last_login = Column(DateTime, nullable=False)
    last_logout = Column(DateTime)
    online_time = Column(Integer, default=0)  # Tempo online em segundos

    # Dados adicionais do dispositivo
    cpu_info = Column(Text)  # Informações do processador
    memory_total = Column(String(20))  # Memória RAM total
    resolution = Column(String(20))  # Resolução da tela

    # Status atual
    is_active = Column(String(10), default="Offline")  # Online/Offline/Away

    # Sistema de Autorização de Dispositivos
    is_authorized = Column(Boolean, default=False, nullable=False)  # Se dispositivo foi autorizado
    authorization_status = Column(
        String(20), 
        default="pending", 
        nullable=False,
        index=True
    )  # pending, authorized, rejected
    authorized_by_admin_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # Admin que autorizou
    authorization_date = Column(DateTime, nullable=True)  # Quando foi autorizado
    first_seen_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))  # Primeira vez visto
    last_seen_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))  # Última vez visto

    # Relacionamentos
    user = relationship(
        "User", 
        foreign_keys=[user_id],
        back_populates="device_data"
    )
    
    authorized_by = relationship(
        "User", 
        foreign_keys=[authorized_by_admin_id],
        backref="authorized_devices"
    )

    def calculate_online_time(self):
        """Calcula tempo online baseado no last_login e last_logout - VERSÃO CORRIGIDA"""
        if not self.last_login:
            return 0

        end_time = self.last_logout or datetime.now(timezone.utc)
        return safe_datetime_diff(self.last_login, end_time)

    def format_online_time(self):
        """Formata tempo online para exibição (ex: 2h 30m)"""
        total_seconds = self.online_time or self.calculate_online_time()

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def get_short_mac(self):
        """Retorna MAC address formatado"""
        if self.mac_address and len(self.mac_address) >= 12:
            # Mostrar apenas os últimos 6 caracteres
            return f"...{self.mac_address[-8:]}"
        return self.mac_address or "N/A"

    def is_authorized_device(self) -> bool:
        """
        Verifica se dispositivo está autorizado para login
        
        Returns:
            bool: True se autorizado
        """
        return self.is_authorized and self.authorization_status == "authorized"

    def can_login(self) -> bool:
        """
        Verifica se pode fazer login neste dispositivo
        
        Returns:
            bool: True se pode logar
        """
        return (
            self.is_authorized_device() 
            and self.authorization_status != "rejected"
        )

    def authorize(self, admin_user_id: str) -> None:
        """
        Autoriza o dispositivo
        
        Args:
            admin_user_id: ID do admin que está autorizando
        """
        self.is_authorized = True
        self.authorization_status = "authorized"
        self.authorized_by_admin_id = admin_user_id
        self.authorization_date = datetime.now(timezone.utc)

    def reject(self) -> None:
        """Rejeita o dispositivo"""
        self.is_authorized = False
        self.authorization_status = "rejected"
        self.authorization_date = datetime.now(timezone.utc)

    def revoke_authorization(self) -> None:
        """Revoga autorização do dispositivo"""
        self.is_authorized = False
        self.authorization_status = "pending"
        self.authorized_by_admin_id = None
        self.authorization_date = None

    def update_last_seen(self) -> None:
        """Atualiza timestamp de última vez visto"""
        self.last_seen_at = datetime.now(timezone.utc)
