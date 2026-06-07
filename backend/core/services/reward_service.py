# backend/core/services/reward_service.py
"""
Serviço de recompensas — processa indicações e bônus de diamantes.
"""
from utils.logger import LOGGER


class RewardService:

    @staticmethod
    def add_diamonds(
        user_id: str,
        amount: int,
        transaction_type: str = "bonus",
        description: str = "Bônus",
    ) -> bool:
        """
        Adiciona diamantes ao usuário.
        Por ora apenas loga; expanda quando houver tabela de diamonds.
        """
        LOGGER.info(
            f"[RewardService] +{amount} diamantes para {user_id} "
            f"({transaction_type}): {description}"
        )
        return True

    @staticmethod
    def process_referral_rewards(new_user_id: str, referrer_user_id: str):
        """
        Processa recompensas de indicação.
        Chamado após registro bem-sucedido de novo usuário.
        """
        try:
            LOGGER.info(
                f"[RewardService] Indicação: novo={new_user_id} "
                f"indicador={referrer_user_id}"
            )
            RewardService.add_diamonds(
                user_id=referrer_user_id,
                amount=50,
                transaction_type="referral_bonus",
                description=f"Bônus por indicar usuário {new_user_id}",
            )
        except Exception as e:
            LOGGER.error(f"process_referral_rewards: {e}")