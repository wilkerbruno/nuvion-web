"""Rotas de admin para o catálogo de recompensas (tabela `rewards` — ver
app/models/reward.py). Antes disto o catálogo só existia como arquivo JSON
estático, editável à mão e exigindo redeploy; estas rotas são o CRUD real,
mesma trava de acesso das outras rotas de escrita administrativa do projeto
(`require_admin`, ver app/api/deps.py e app/api/routes/ai_tools.py).
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.crud import reward as reward_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.reward import RewardAdminPublic, RewardCreate, RewardUpdate

router = APIRouter(prefix="/admin/rewards", tags=["admin-rewards"])


@router.get("", response_model=List[RewardAdminPublic])
def list_rewards(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return reward_crud.list_all(db)


@router.post("", response_model=RewardAdminPublic, status_code=status.HTTP_201_CREATED)
def create_reward(
    payload: RewardCreate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return reward_crud.create(db, **payload.model_dump())


def _get_or_404(db: Session, reward_id: str):
    reward = reward_crud.get(db, reward_id)
    if reward is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recompensa não encontrada")
    return reward


@router.patch("/{reward_id}", response_model=RewardAdminPublic)
def update_reward(
    reward_id: str,
    payload: RewardUpdate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reward = _get_or_404(db, reward_id)
    return reward_crud.update(db, reward, **payload.model_dump(exclude_unset=True))


@router.delete("/{reward_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reward(
    reward_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reward = _get_or_404(db, reward_id)
    reward_crud.delete(db, reward)
