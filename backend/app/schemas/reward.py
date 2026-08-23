"""Schemas de diamantes/recompensas (Fase 4; CRUD de admin adicionado depois
— ver app/models/reward.py e app/api/routes/admin_rewards.py)."""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


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


# --- Administração do catálogo (só admin — ver app/api/deps.py::require_admin) ---


class RewardCreate(BaseModel):
    icon: str = Field(default="🎁", max_length=16)
    title: str = Field(min_length=1, max_length=150)
    description: str = ""
    points: int = Field(gt=0)
    available: bool = True


class RewardUpdate(BaseModel):
    icon: Optional[str] = Field(default=None, max_length=16)
    title: Optional[str] = Field(default=None, min_length=1, max_length=150)
    description: Optional[str] = None
    points: Optional[int] = Field(default=None, gt=0)
    available: Optional[bool] = None


class RewardAdminPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    icon: str
    title: str
    description: str
    points: int
    available: bool
