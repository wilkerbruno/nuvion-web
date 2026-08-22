"""CRUD de favoritos (portado de crud/sqlalchemy_user_favorite_manager.py)."""
from typing import List, Tuple

from sqlalchemy.orm import Session, joinedload

from app.models.ai_tool import AITool
from app.models.user_favorite import UserFavorite


def is_favorite(db: Session, user_id: str, ai_tool_id: str) -> bool:
    return (
        db.query(UserFavorite)
        .filter(UserFavorite.user_id == user_id, UserFavorite.ai_tool_id == ai_tool_id)
        .first()
        is not None
    )


def toggle_favorite(db: Session, user_id: str, ai_tool_id: str) -> Tuple[bool, bool]:
    """Alterna o favorito. Retorna (sucesso, is_favorite_agora)."""
    existing = (
        db.query(UserFavorite)
        .filter(UserFavorite.user_id == user_id, UserFavorite.ai_tool_id == ai_tool_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        return True, False

    favorite = UserFavorite(user_id=user_id, ai_tool_id=ai_tool_id)
    db.add(favorite)
    db.commit()
    return True, True


def list_favorite_tools(db: Session, user_id: str) -> List[AITool]:
    favorites = (
        db.query(UserFavorite)
        .filter(UserFavorite.user_id == user_id)
        .options(joinedload(UserFavorite.ai_tool))
        .all()
    )
    return [fav.ai_tool for fav in favorites if fav.ai_tool]


def list_favorite_ids(db: Session, user_id: str) -> List[str]:
    rows = db.query(UserFavorite.ai_tool_id).filter(UserFavorite.user_id == user_id).all()
    return [row[0] for row in rows]
