"""Configuração de pagamento/Mercado Pago (portado de database/models/payment_config.py).

Os valores de `access_token`/`client_secret` guardados aqui são segredo de
servidor — nunca devem ser retornados por nenhum endpoint da API voltado ao
painel ou à extensão. Ver plano de migração, seção 7.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, String, Text
from sqlalchemy.dialects.mysql import JSON

from app.core.logging import LOGGER
from app.db.base_class import Base
from app.models.base import BaseModel


class PaymentConfig(Base, BaseModel):
    """Configurações de pagamento do sistema (Mercado Pago / PIX)."""

    __tablename__ = "payment_configs"

    config_key = Column(String(50), unique=True, nullable=False, index=True)

    access_token = Column(Text, nullable=True)
    public_key = Column(Text, nullable=True)
    client_id = Column(Text, nullable=True)
    client_secret = Column(Text, nullable=True)
    webhook_url = Column(Text, nullable=True)

    pix_key = Column(String(200), nullable=True)
    pix_name = Column(String(100), nullable=True)

    environment = Column(Enum("sandbox", "production"), default="sandbox", nullable=False)
    currency = Column(String(3), default="BRL", nullable=False)
    min_amount = Column(String(10), default="1.00", nullable=True)

    standard_amount = Column(String(10), default="97.00", nullable=False)
    premium_amount = Column(String(10), default="70.00", nullable=False)
    vip_amount = Column(String(10), default="0.00", nullable=False)

    # --- USDT (rede TRC20) — self-custodial, sem provedor terceiro. A
    # carteira e os preços em USDT são configurados aqui, do mesmo jeito
    # que os valores em BRL acima — não há conversão automática BRL→USDT
    # por câmbio ao vivo (decisão consciente: evita depender de mais uma
    # API externa só pra cotação; o admin define o preço em USDT
    # diretamente, como já fazia com o preço em BRL). Ver
    # docs/PAGAMENTOS_CRIPTO.md.
    usdt_wallet_address = Column(String(64), nullable=True)
    usdt_network = Column(String(20), default="TRC20", nullable=False)
    standard_amount_usdt = Column(String(10), nullable=True)
    premium_amount_usdt = Column(String(10), nullable=True)
    vip_amount_usdt = Column(String(10), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    last_tested_at = Column(DateTime, nullable=True)

    additional_config = Column(JSON, default=dict)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.config_key:
            self.config_key = "mercadopago_main"

    def test_connection(self) -> bool:
        if not self.access_token:
            LOGGER.warning("Access token não configurado")
            return False
        # TODO: chamada real à API do Mercado Pago (Fase 3 do roadmap)
        self.last_tested_at = datetime.now(timezone.utc)
        return len(self.access_token) > 10

    def get_config_dict(self) -> dict:
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
            "standard_amount": self.standard_amount or "97.00",
            "premium_amount": self.premium_amount or "70.00",
            "vip_amount": self.vip_amount or "0.00",
            "usdt_wallet_address": self.usdt_wallet_address or "",
            "usdt_network": self.usdt_network or "TRC20",
            "standard_amount_usdt": self.standard_amount_usdt or "",
            "premium_amount_usdt": self.premium_amount_usdt or "",
            "vip_amount_usdt": self.vip_amount_usdt or "",
            "is_active": self.is_active,
            "last_tested_at": self.last_tested_at.isoformat() if self.last_tested_at else None,
        }

    def update_from_dict(self, config_data: dict):
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
            "standard_amount": "standard_amount",
            "premium_amount": "premium_amount",
            "vip_amount": "vip_amount",
            "usdt_wallet_address": "usdt_wallet_address",
            "usdt_network": "usdt_network",
            "standard_amount_usdt": "standard_amount_usdt",
            "premium_amount_usdt": "premium_amount_usdt",
            "vip_amount_usdt": "vip_amount_usdt",
            "is_active": "is_active",
        }

        for form_field, model_field in field_mapping.items():
            if form_field in config_data:
                value = config_data[form_field]
                if model_field == "environment":
                    value = "production" if value == "Produção" else "sandbox"
                if value == "" and model_field != "is_active":
                    value = None
                setattr(self, model_field, value)

        self.updated_at = datetime.now(timezone.utc)
        LOGGER.info(f"Configuração atualizada via update_from_dict: {self.config_key}")

    def __repr__(self):
        return f"<PaymentConfig(key={self.config_key}, env={self.environment}, active={self.is_active})>"
