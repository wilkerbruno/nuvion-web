"""Schemas de configuração de pagamento (admin-only).

Segredos (`access_token`, `public_key`, `client_secret`) nunca saem em texto
puro por nenhuma rota — só um booleano indicando se estão configurados. Ver
nota de segurança no topo de app/models/payment_config.py.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PaymentConfigPublic(BaseModel):
    config_key: str
    access_token_configured: bool
    public_key_configured: bool
    pix_key: Optional[str] = None
    pix_name: Optional[str] = None
    webhook_url: Optional[str] = None
    environment: str
    currency: str
    standard_amount: str
    premium_amount: str
    vip_amount: str
    # USDT (TRC20) — o endereço da carteira NÃO é segredo (é público por
    # natureza, ao contrário do access_token), então vai em texto puro aqui,
    # diferente de como access_token/public_key são tratados acima.
    usdt_wallet_address: Optional[str] = None
    usdt_network: str
    standard_amount_usdt: Optional[str] = None
    premium_amount_usdt: Optional[str] = None
    vip_amount_usdt: Optional[str] = None
    is_active: bool
    last_tested_at: Optional[datetime] = None

    @classmethod
    def from_model(cls, config) -> "PaymentConfigPublic":
        return cls(
            config_key=config.config_key,
            access_token_configured=bool(config.access_token),
            public_key_configured=bool(config.public_key),
            pix_key=config.pix_key,
            pix_name=config.pix_name,
            webhook_url=config.webhook_url,
            environment=config.environment,
            currency=config.currency,
            standard_amount=config.standard_amount,
            premium_amount=config.premium_amount,
            vip_amount=config.vip_amount,
            usdt_wallet_address=config.usdt_wallet_address,
            usdt_network=config.usdt_network,
            standard_amount_usdt=config.standard_amount_usdt,
            premium_amount_usdt=config.premium_amount_usdt,
            vip_amount_usdt=config.vip_amount_usdt,
            is_active=config.is_active,
            last_tested_at=config.last_tested_at,
        )


class PaymentConfigUpdate(BaseModel):
    access_token: Optional[str] = None
    public_key: Optional[str] = None
    pix_key: Optional[str] = None
    pix_name: Optional[str] = None
    webhook_url: Optional[str] = None
    environment: Optional[str] = Field(default=None, pattern="^(sandbox|production)$")
    standard_amount: Optional[str] = None
    premium_amount: Optional[str] = None
    vip_amount: Optional[str] = None
    usdt_wallet_address: Optional[str] = None
    usdt_network: Optional[str] = None
    standard_amount_usdt: Optional[str] = None
    premium_amount_usdt: Optional[str] = None
    vip_amount_usdt: Optional[str] = None
    is_active: Optional[bool] = None


class TestConnectionResult(BaseModel):
    ok: bool
    message: str
