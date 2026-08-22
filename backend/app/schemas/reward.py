"""Schemas de diamantes/recompensas (Fase 4)."""
from typing import List, Optional

from pydantic import BaseModel


class RewardTransaction(BaseModel):
    id: str
    type: str
    diamonds: int
    balance_after: int
    description: str
    timestamp: str
    reference_id: Optional[str] = None


class RewardBalance(BaseModel):
    diamonds: int
    diamond_rate: float
    transactions: List[RewardTransaction]
    claimed_rewards: List[str]
    referral_code: str
    referral_reward: int


class RewardCatalogItem(BaseModel):
    id: str
    icon: str
    title: str
    description: str
    points: int
    available: bool
    already_claimed: bool = False


class ClaimRewardResponse(BaseModel):
    success: bool
    message: str
    diamonds: int
