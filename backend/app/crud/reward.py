"""CRUD do catálogo de recompensas (tabela `rewards` — ver app/models/reward.py).

Mesmo padrão de app/crud/ai_tool.py e app/crud/proxy.py: `update` só aplica
campos explicitamente enviados (o schema `RewardUpdate` já filtra com
`exclude_unset=True` antes de chamar isto, então `None` aqui normalmente
significa "não veio no payload", não "limpar o campo").
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.reward import Reward


def list_all(db: Session) -> List[Reward]:
    return db.query(Reward).order_by(Reward.created_at.asc()).all()


def get(db: Session, reward_id: str) -> Optional[Reward]:
    return db.query(Reward).filter(Reward.id == reward_id).first()


def create(
    db: Session,
    *,
    title: str,
    points: int,
    icon: str = "🎁",
    description: str = "",
    available: bool = True,
) -> Reward:
    reward = Reward(
        icon=icon,
        title=title,
        description=description,
        points=points,
        available=available,
    )
    db.add(reward)
    db.commit()
    db.refresh(reward)
    return reward


def update(db: Session, reward: Reward, **fields) -> Reward:
    for key, value in fields.items():
        if value is not None and hasattr(reward, key):
            setattr(reward, key, value)
    db.commit()
    db.refresh(reward)
    return reward


def delete(db: Session, reward: Reward) -> None:
    db.delete(reward)
    db.commit()
