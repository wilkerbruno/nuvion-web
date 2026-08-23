"""Rotas de diamantes/recompensas (Fase 4 — equivalente web de rewards_widget.py).

Diamantes são ganhos por indicação (`app/crud/user.py::register_user`
chama `reward_service.process_referral_rewards` no cadastro) e trocados por
recompensas do catálogo, gerido por admin via `/admin/rewards` (tabela
`rewards` — ver app/models/reward.py; deixou de ser um JSON estático).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.reward import ClaimRewardResponse, RewardBalance, RewardCatalogItem
from app.services import reward_service

router = APIRouter(prefix="/rewards", tags=["rewards"])


@router.get("/me", response_model=RewardBalance)
def my_rewards(current_user: User = Depends(get_current_active_user)):
    return RewardBalance(
        diamonds=reward_service.get_diamonds(current_user),
        diamond_rate=reward_service.get_diamond_rate(),
        transactions=list(reversed(reward_service.get_transactions(current_user))),
        claimed_rewards=reward_service.get_claimed_rewards(current_user),
        referral_code=current_user.referral_code,
        referral_reward=reward_service.get_referral_reward_amount(),
    )


@router.get("/catalog", response_model=list[RewardCatalogItem])
def catalog(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    claimed = set(reward_service.get_claimed_rewards(current_user))
    return [
        RewardCatalogItem(**reward, already_claimed=reward["id"] in claimed)
        for reward in reward_service.get_rewards_catalog(db)
    ]


@router.post("/claim/{reward_id}", response_model=ClaimRewardResponse)
def claim(
    reward_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ok, message = reward_service.claim_reward(db, current_user, reward_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return ClaimRewardResponse(
        success=True, message=message, diamonds=reward_service.get_diamonds(current_user)
    )
