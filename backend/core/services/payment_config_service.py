# backend/core/services/payment_config_service.py
"""
Serviço de configuração de pagamentos — lê do banco via crud_system.
"""
from utils.logger import LOGGER


class PaymentConfigService:

    @staticmethod
    def get_mercadopago_config() -> dict:
        """Retorna configuração ativa do Mercado Pago."""
        try:
            from crud.crud_manager import crud_system
            config = crud_system.payment_configs.get_active_config()
            if config:
                return config.get_config_dict()
        except Exception as e:
            LOGGER.error(f"get_mercadopago_config: {e}")
        return {}

    @staticmethod
    def get_amount_by_category(category: str) -> float:
        """Retorna valor de assinatura pela categoria."""
        defaults = {"Standard": 97.00, "Premium": 70.00, "VIP": 0.00}
        try:
            from crud.crud_manager import crud_system
            config = crud_system.payment_configs.get_active_config()
            if config:
                mapping = {
                    "Standard": float(config.standard_amount or 97),
                    "Premium":  float(config.premium_amount  or 70),
                    "VIP":      float(config.vip_amount      or 0),
                }
                return mapping.get(category, defaults.get(category, 97.00))
        except Exception as e:
            LOGGER.error(f"get_amount_by_category: {e}")
        return defaults.get(category, 97.00)