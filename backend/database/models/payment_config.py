# database/models/payment_config.py
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, String, Text
from sqlalchemy.dialects.mysql import JSON

from database.models.base import BaseModel
from database.sqlalchemy_config import Base
from utils.logger import LOGGER


class PaymentConfig(Base, BaseModel):
    """Modelo para configurações de pagamento do sistema"""

    __tablename__ = "payment_configs"

    # Chave única para identificar o tipo de configuração
    config_key = Column(String(50), unique=True, nullable=False, index=True)

    # Credenciais Mercado Pago
    access_token = Column(Text, nullable=True)
    public_key = Column(Text, nullable=True)
    client_id = Column(Text, nullable=True)
    client_secret = Column(Text, nullable=True)
    webhook_url = Column(Text, nullable=True)

    # Configurações PIX
    pix_key = Column(String(200), nullable=True)
    pix_name = Column(String(100), nullable=True)

    # Configurações gerais
    environment = Column(
        Enum("sandbox", "production"), default="sandbox", nullable=False
    )
    currency = Column(String(3), default="BRL", nullable=False)
    min_amount = Column(String(10), default="1.00", nullable=True)

    # Valores por categoria
    standard_amount = Column(String(10), default="97.00", nullable=False)
    premium_amount = Column(String(10), default="70.00", nullable=False)
    vip_amount = Column(String(10), default="0.00", nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_tested_at = Column(DateTime, nullable=True)

    # Dados adicionais em JSON
    additional_config = Column(JSON, default=dict)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.config_key:
            self.config_key = "mercadopago_main"

    def test_connection(self) -> bool:
        """Testa se as credenciais estão válidas"""
        if not self.access_token:
            LOGGER.warning("Access token não configurado")
            return False

        # TODO: Implementar teste real da API do Mercado Pago
        # Por enquanto, apenas verifica se o token existe
        self.last_tested_at = datetime.now(timezone.utc)
        return len(self.access_token) > 10

    def get_config_dict(self) -> dict:
        """Retorna configurações como dicionário"""
        return {
            "access_token": self.access_token or "",
            "public_key": self.public_key or "",
            "client_id": self.client_id or "",
            "client_secret": self.client_secret or "",
            "webhook_url": self.webhook_url or "",
            "pix_key": self.pix_key or "",
            "pix_name": self.pix_name or "Sua Empresa",
            "environment": self.environment or "sandbox",
            "currency": self.currency or "BRL",
            "min_amount": self.min_amount or "1.00",
            # CAMPOS DE VALORES POR CATEGORIA (CRÍTICO!)
            "standard_amount": self.standard_amount or "97.00",
            "premium_amount": self.premium_amount or "70.00",
            "vip_amount": self.vip_amount or "0.00",
            "is_active": self.is_active,
            "last_tested_at": (
                self.last_tested_at.isoformat() if self.last_tested_at else None
            ),
        }

    def update_from_dict(self, config_data: dict):
        """Atualiza configuração a partir de dicionário"""
        # Mapear campos do dicionário para campos do modelo
        field_mapping = {
            "access_token": "access_token",
            "public_key": "public_key",
            "client_id": "client_id",
            "client_secret": "client_secret",
            "webhook_url": "webhook_url",
            "environment": "environment",
            "pix_key": "pix_key",
            "pix_name": "pix_name",
            "currency": "currency",
            "min_amount": "min_amount",
            # ADICIONAR CAMPOS DE VALORES
            "standard_amount": "standard_amount",
            "premium_amount": "premium_amount",
            "vip_amount": "vip_amount",
            "is_active": "is_active",
        }

        # Atualizar campos
        for form_field, model_field in field_mapping.items():
            if form_field in config_data:
                value = config_data[form_field]

                # Conversão de tipo para environment
                if model_field == "environment":
                    # Converter "Produção" para "production" e "Sandbox" para "sandbox"
                    value = "production" if value == "Produção" else "sandbox"

                # Converter valores vazios para None (exceto is_active)
                if value == "" and model_field != "is_active":
                    value = None

                setattr(self, model_field, value)

        # Atualizar timestamp
        from datetime import datetime, timezone

        self.updated_at = datetime.now(timezone.utc)

        LOGGER.info(f"Configuração atualizada via update_from_dict: {self.config_key}")

    def __repr__(self):
        return f"<PaymentConfig(key={self.config_key}, env={self.environment}, active={self.is_active})>"
