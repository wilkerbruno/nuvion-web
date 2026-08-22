"""Configuração de pagamento (Mercado Pago) — porta de
crud/sqlalchemy_payment_config_manager.py e da parte de leitura de
core/services/payment_config_service.py que ainda faz sentido aqui (o resto
daquele serviço — cálculo de comissão de afiliados — não foi portado; ver
backend/README.md).

Nota sobre `pix_key`/`pix_name`: no app desktop esses campos alimentavam uma
implementação SIMULADA de PIX (core/services/pix_generator.py construía o
código copia-e-cola manualmente a partir da chave). A versão web usa a API
real do Mercado Pago (`app/services/mercadopago_client.py`), que já devolve
o QR Code pronto — `pix_key`/`pix_name` viram só informativos para exibição
no painel, não são mais necessários para gerar cobrança.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.payment_config import PaymentConfig

DEFAULT_CONFIG_KEY = "mercadopago_main"

_DEFAULT_AMOUNTS = {
    "Standard": 97.00,
    "Premium": 70.00,
    "VIP": 0.00,
}


def get_by_key(db: Session, config_key: str = DEFAULT_CONFIG_KEY) -> Optional[PaymentConfig]:
    return db.query(PaymentConfig).filter(PaymentConfig.config_key == config_key).first()


def get_active_config(db: Session) -> Optional[PaymentConfig]:
    return db.query(PaymentConfig).filter(PaymentConfig.is_active.is_(True)).first()


def create_or_update(db: Session, config_key: str, data: dict) -> PaymentConfig:
    config = get_by_key(db, config_key)
    if config is not None:
        config.update_from_dict(data)
    else:
        config = PaymentConfig(config_key=config_key)
        config.update_from_dict(data)
        db.add(config)
    db.commit()
    db.refresh(config)
    return config


def is_configured(db: Session) -> bool:
    """Só exige access_token — é o único dado que a integração real via API
    precisa para gerar PIX/cobrar cartão (ver nota no topo do arquivo)."""
    config = get_active_config(db) or get_by_key(db)
    return bool(config and config.access_token and config.access_token.strip())


def get_amount_by_category(db: Session, category: str) -> float:
    config = get_active_config(db) or get_by_key(db)
    field_map = {
        "Standard": "standard_amount",
        "Premium": "premium_amount",
        "VIP": "vip_amount",
    }
    field_name = field_map.get(category, "standard_amount")

    if config is not None:
        amount_str = getattr(config, field_name, None)
        if amount_str:
            try:
                return float(amount_str)
            except (TypeError, ValueError):
                pass

    return _DEFAULT_AMOUNTS.get(category, _DEFAULT_AMOUNTS["Standard"])


def get_usdt_amount_by_category(db: Session, category: str) -> Optional[float]:
    """None quando o admin ainda não configurou preço em USDT para essa
    categoria — nesse caso o checkout em USDT não fica disponível pra ela
    (ver app/api/routes/payments.py). Não há valor default hardcoded aqui
    de propósito: diferente do BRL, não faz sentido supor um preço em USDT
    sem o admin definir explicitamente."""
    config = get_active_config(db) or get_by_key(db)
    field_map = {
        "Standard": "standard_amount_usdt",
        "Premium": "premium_amount_usdt",
        "VIP": "vip_amount_usdt",
    }
    field_name = field_map.get(category, "standard_amount_usdt")

    if config is not None:
        amount_str = getattr(config, field_name, None)
        if amount_str:
            try:
                return float(amount_str)
            except (TypeError, ValueError):
                pass
    return None


def get_usdt_wallet(db: Session) -> Optional[tuple]:
    """Retorna (endereço, rede) configurados, ou None se a carteira ainda
    não foi configurada pelo admin."""
    config = get_active_config(db) or get_by_key(db)
    if config is not None and config.usdt_wallet_address:
        return config.usdt_wallet_address, config.usdt_network or "TRC20"
    return None
