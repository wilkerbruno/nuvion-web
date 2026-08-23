"""Serviço de diamantes/recompensas (portado de core/services/reward_service.py).

Diferenças em relação ao original:

- O original chamava `crud.database_adapter.crud_system.users` (import
  tardio, sessão própria por chamada). Aqui a sessão vem injetada por
  parâmetro, igual ao resto do backend (ver app/crud/user.py).
- O catálogo de recompensas e as taxas (`diamond_rate`, `min_payment`,
  `referral_reward`) vinham do arquivo `diamond_platform_config.json` na
  raiz do projeto desktop — junto com o `access_token`/`app_id` do Mercado
  Pago em texto puro. Aqui o catálogo foi portado para
  `app/data/diamond_platform_config.json` SEM as credenciais do MP, que já
  são geridas por `PaymentConfig` no banco (Fase 3) — ver o comentário no
  próprio arquivo JSON.
- O catálogo de recompensas em si (os itens, não as taxas) DEIXOU de vir
  desse JSON — agora mora na tabela `rewards` (app/models/reward.py),
  editável por admin via `/admin/rewards`. O JSON continua sendo a fonte
  de `diamond_rate`/`min_payment`/`referral_reward`/`signup_bonus` (taxas
  da plataforma como um todo, não recompensas individuais) e também a
  semente inicial do catálogo — ver `seed_default_rewards` abaixo.

Os diamantes continuam persistidos em `User.profile_settings` (JSON), sob
as mesmas chaves do app desktop: "diamonds", "transactions",
"claimed_rewards". Isso evita uma migração de schema para este dado e
mantém compatibilidade se algum dia os dados do desktop forem importados
(Fase 5 do roadmap).
"""
import json
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import LOGGER
from app.models.user import User

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "diamond_platform_config.json"


@lru_cache
def _load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _reward_to_dict(reward) -> dict:
    return {
        "id": reward.id,
        "icon": reward.icon,
        "title": reward.title,
        "description": reward.description,
        "points": reward.points,
        "available": reward.available,
    }


def get_rewards_catalog(db: Session) -> List[dict]:
    """Retorna o catálogo de recompensas resgatáveis por diamantes (tabela
    `rewards` — não vem mais do JSON, ver docstring do módulo)."""
    from app.crud import reward as reward_crud

    return [_reward_to_dict(r) for r in reward_crud.list_all(db)]


def get_reward_by_id(db: Session, reward_id: str) -> Optional[dict]:
    from app.crud import reward as reward_crud

    reward = reward_crud.get(db, reward_id)
    return _reward_to_dict(reward) if reward is not None else None


def seed_default_rewards(db: Session) -> int:
    """Semeia a tabela `rewards` com os itens que estavam no catálogo antigo
    (JSON) — só insere algo se a tabela estiver vazia, então nunca
    sobrescreve nem ressuscita recompensas que um admin já criou/editou/
    removeu depois. Chamado só em dois lugares, logo depois de a tabela
    `rewards` ser criada: `scripts/sync_schema_live.py` (produção/deploy) e
    `tests/conftest.py` (suíte de testes, banco SQLite novo por teste).
    Retorna quantas recompensas foram inseridas."""
    from app.crud import reward as reward_crud

    if reward_crud.list_all(db):
        return 0

    seeded = 0
    for item in _load_config().get("rewards", []):
        reward_crud.create(
            db,
            icon=item.get("icon", "🎁"),
            title=item["title"],
            description=item.get("description", ""),
            points=int(item.get("points", 0)),
            available=bool(item.get("available", True)),
        )
        seeded += 1
    return seeded


def get_referral_reward_amount() -> int:
    return int(_load_config().get("referral_reward", 50))


def get_signup_bonus_amount() -> int:
    return int(_load_config().get("signup_bonus", 20))


def get_diamond_rate() -> float:
    """Quantos diamantes equivalem a R$1 (usado só para exibição no painel)."""
    return float(_load_config().get("diamond_rate", 10))


# ------------------------------------------------------------------ #
# Leitura de dados do usuário                                          #
# ------------------------------------------------------------------ #


def get_diamonds(user: User) -> int:
    settings = user.profile_settings or {}
    return int(settings.get("diamonds", 0))


def get_transactions(user: User) -> List[dict]:
    settings = user.profile_settings or {}
    return list(settings.get("transactions", []))


def get_claimed_rewards(user: User) -> List[str]:
    settings = user.profile_settings or {}
    return list(settings.get("claimed_rewards", []))


# ------------------------------------------------------------------ #
# Operações de crédito e débito                                        #
# ------------------------------------------------------------------ #


def add_diamonds(
    db: Session,
    user: User,
    amount: int,
    transaction_type: str,
    description: str,
    reference_id: Optional[str] = None,
) -> bool:
    """Credita diamantes ao usuário e registra a transação."""
    if amount <= 0:
        LOGGER.warning(f"RewardService.add_diamonds: amount inválido {amount}")
        return False

    settings = dict(user.profile_settings) if user.profile_settings else {}
    current_balance = int(settings.get("diamonds", 0))
    new_balance = current_balance + amount

    transaction = {
        "id": str(uuid.uuid4()),
        "type": transaction_type,
        "diamonds": amount,
        "balance_after": new_balance,
        "description": description,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if reference_id:
        transaction["reference_id"] = reference_id

    transactions = list(settings.get("transactions", []))
    transactions.append(transaction)

    settings["diamonds"] = new_balance
    settings["transactions"] = transactions
    user.profile_settings = settings

    db.commit()
    db.refresh(user)

    LOGGER.info(
        f"Diamantes creditados: usuario={user.id} | +{amount} | "
        f"saldo={new_balance} | tipo={transaction_type}"
    )
    return True


def deduct_diamonds(
    db: Session,
    user: User,
    amount: int,
    transaction_type: str,
    description: str,
    reference_id: Optional[str] = None,
) -> bool:
    """Debita diamantes do usuário. Retorna False se saldo insuficiente."""
    if amount <= 0:
        LOGGER.warning(f"RewardService.deduct_diamonds: amount inválido {amount}")
        return False

    settings = dict(user.profile_settings) if user.profile_settings else {}
    current_balance = int(settings.get("diamonds", 0))

    if current_balance < amount:
        LOGGER.warning(
            f"RewardService.deduct_diamonds: saldo insuficiente usuario={user.id} | "
            f"saldo={current_balance} | requerido={amount}"
        )
        return False

    new_balance = current_balance - amount

    transaction = {
        "id": str(uuid.uuid4()),
        "type": transaction_type,
        "diamonds": -amount,
        "balance_after": new_balance,
        "description": description,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if reference_id:
        transaction["reference_id"] = reference_id

    transactions = list(settings.get("transactions", []))
    transactions.append(transaction)

    settings["diamonds"] = new_balance
    settings["transactions"] = transactions
    user.profile_settings = settings

    db.commit()
    db.refresh(user)

    LOGGER.info(
        f"Diamantes debitados: usuario={user.id} | -{amount} | "
        f"saldo={new_balance} | tipo={transaction_type}"
    )
    return True


def mark_reward_claimed(db: Session, user: User, reward_id: str) -> None:
    settings = dict(user.profile_settings) if user.profile_settings else {}
    claimed = list(settings.get("claimed_rewards", []))
    if reward_id not in claimed:
        claimed.append(reward_id)
        settings["claimed_rewards"] = claimed
        user.profile_settings = settings
        db.commit()
        db.refresh(user)


def claim_reward(db: Session, user: User, reward_id: str) -> Tuple[bool, str]:
    """Resgata uma recompensa do catálogo, debitando os diamantes necessários.

    Retorna (sucesso, mensagem).
    """
    reward = get_reward_by_id(db, reward_id)
    if reward is None:
        return False, "Recompensa não encontrada"
    if not reward.get("available", True):
        return False, "Recompensa indisponível no momento"
    if reward_id in get_claimed_rewards(user):
        return False, "Recompensa já resgatada"

    points = int(reward.get("points", 0))
    ok = deduct_diamonds(
        db,
        user,
        amount=points,
        transaction_type="reward_claim",
        description=f"Resgate: {reward.get('title', reward_id)}",
        reference_id=reward_id,
    )
    if not ok:
        return False, "Saldo de diamantes insuficiente"

    mark_reward_claimed(db, user, reward_id)
    return True, "Recompensa resgatada com sucesso"


# ------------------------------------------------------------------ #
# Lógica de indicação                                                  #
# ------------------------------------------------------------------ #


def process_referral_rewards(db: Session, new_user: User, referrer: User) -> None:
    """Processa os bônus de indicação para ambos os lados após cadastro.

    Chamado por app/crud/user.py::register_user logo após o commit do novo
    usuário. Falhas aqui não devem impedir o cadastro — por isso não
    lançam exceção (mesma postura defensiva do original).
    """
    try:
        signup_bonus = get_signup_bonus_amount()
        referral_reward = get_referral_reward_amount()

        add_diamonds(
            db,
            new_user,
            amount=signup_bonus,
            transaction_type="signup_bonus",
            description="Bônus de boas-vindas por usar código de indicação",
            reference_id=referrer.id,
        )
        add_diamonds(
            db,
            referrer,
            amount=referral_reward,
            transaction_type="referral_bonus",
            description="Recompensa por indicação — novo usuário cadastrado",
            reference_id=new_user.id,
        )
        LOGGER.info(
            f"Recompensas de indicação processadas: novo={new_user.id} | "
            f"indicador={referrer.id}"
        )
    except Exception as e:  # noqa: BLE001 — nunca deve derrubar o cadastro
        LOGGER.error(f"RewardService.process_referral_rewards erro: {e}")
