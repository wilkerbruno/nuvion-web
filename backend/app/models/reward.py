"""Modelo do catálogo de recompensas trocáveis por diamantes.

Antes disto, o catálogo inteiro vivia só em `app/data/diamond_platform_config.json`
(arquivo estático, editado à mão, exigindo redeploy a cada mudança) — ver o
comentário em app/services/reward_service.py sobre a origem desse arquivo.
Este modelo passa o catálogo para o banco, editável por admin via
`/admin/rewards` (app/api/routes/admin_rewards.py), sem precisar de deploy
novo a cada recompensa criada/editada/removida.

As taxas globais da plataforma (`diamond_rate`, `min_payment`,
`referral_reward`, `signup_bonus`) NÃO migram para cá — não são
"recompensas" individuais, continuam em `diamond_platform_config.json`.

Compatibilidade com o catálogo antigo: na primeira vez que esta tabela é
criada (banco novo, ou primeiro deploy depois desta mudança), ela é
semeada com os itens que estavam no JSON — ver
`reward_service.seed_default_rewards`, chamado por
`scripts/sync_schema_live.py` (produção) e `tests/conftest.py` (testes).
Isso nunca roda de novo depois de a tabela já ter pelo menos uma linha —
não sobrescreve nem ressuscita recompensas que um admin já editou/removeu.
"""
from sqlalchemy import Boolean, Column, Integer, String, Text

from app.db.base_class import Base
from app.models.base import BaseModel


class Reward(Base, BaseModel):
    """Item do catálogo de recompensas resgatáveis por diamantes."""

    __tablename__ = "rewards"

    icon = Column(String(16), nullable=False, default="🎁")
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=False, default="")
    points = Column(Integer, nullable=False)
    available = Column(Boolean, nullable=False, default=True)
