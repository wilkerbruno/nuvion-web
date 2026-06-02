# crud/sqlalchemy_payment_config_manager.py
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from crud.base_manager import BaseManager
from database.models.payment_config import PaymentConfig
from utils.logger import LOGGER


class SQLAlchemyPaymentConfigManager(BaseManager[PaymentConfig]):
    """Manager para configurações de pagamento usando SQLAlchemy"""

    def __init__(self):
        super().__init__(PaymentConfig)
        LOGGER.info("PaymentConfigManager inicializado")

    def get_config_by_key(
        self, config_key: str = "mercadopago_main"
    ) -> Optional[PaymentConfig]:
        """Busca configuração por chave"""
        session = self.get_session()
        try:
            config = (
                session.query(PaymentConfig)
                .filter(PaymentConfig.config_key == config_key)
                .first()
            )
            if config:
                LOGGER.info(f"Configuração encontrada: {config_key}")
            else:
                LOGGER.warning(f"Configuração não encontrada: {config_key}")
            return config
        except Exception as e:
            LOGGER.error(f"Erro ao buscar configuração {config_key}: {e}")
            return None
        finally:
            session.close()

    def create_or_update_config(
        self, config_key: str, config_data: Dict
    ) -> Optional[PaymentConfig]:
        """Cria ou atualiza configuração"""
        session = self.get_session()
        try:
            # Buscar configuração existente
            existing_config = (
                session.query(PaymentConfig)
                .filter(PaymentConfig.config_key == config_key)
                .first()
            )

            if existing_config:
                # Atualizar configuração existente
                existing_config.update_from_dict(config_data)
                session.commit()
                session.refresh(existing_config)
                LOGGER.info(f"Configuração atualizada: {config_key}")
                return existing_config
            else:
                # Criar nova configuração
                new_config = PaymentConfig(config_key=config_key, **config_data)
                session.add(new_config)
                session.commit()
                session.refresh(new_config)
                LOGGER.info(f"Nova configuração criada: {config_key}")
                return new_config

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao salvar configuração {config_key}: {e}")
            return None
        finally:
            session.close()

    def get_active_config(self) -> Optional[PaymentConfig]:
        """Busca primeira configuração ativa"""
        session = self.get_session()
        try:
            return (
                session.query(PaymentConfig)
                .filter(PaymentConfig.is_active == True)
                .first()
            )
        except Exception as e:
            LOGGER.error(f"Erro ao buscar configuração ativa: {e}")
            return None
        finally:
            session.close()

    def test_config_connection(self, config_key: str = "mercadopago_main") -> bool:
        """Testa conexão da configuração"""
        config = self.get_config_by_key(config_key)
        if not config:
            return False

        # Testar conexão
        is_valid = config.test_connection()

        # Salvar resultado do teste
        if is_valid:
            session = self.get_session()
            try:
                session.merge(config)  # Atualiza last_tested_at
                session.commit()
            except Exception as e:
                LOGGER.error(f"Erro ao salvar teste de conexão: {e}")
            finally:
                session.close()

        return is_valid

    def get_all_configs(self) -> List[PaymentConfig]:
        """Lista todas as configurações"""
        session = self.get_session()
        try:
            return (
                session.query(PaymentConfig)
                .order_by(PaymentConfig.created_at.desc())
                .all()
            )
        except Exception as e:
            LOGGER.error(f"Erro ao listar configurações: {e}")
            return []
        finally:
            session.close()

    def delete_config(self, config_key: str) -> bool:
        """Remove configuração"""
        session = self.get_session()
        try:
            config = (
                session.query(PaymentConfig)
                .filter(PaymentConfig.config_key == config_key)
                .first()
            )

            if config:
                session.delete(config)
                session.commit()
                LOGGER.info(f"Configuração removida: {config_key}")
                return True
            else:
                LOGGER.warning(
                    f"Configuração não encontrada para remoção: {config_key}"
                )
                return False

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao remover configuração {config_key}: {e}")
            return False
        finally:
            session.close()
