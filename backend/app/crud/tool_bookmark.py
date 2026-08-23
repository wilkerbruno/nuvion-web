"""CRUD dos favoritos de página por ferramenta (Fase 5) — ver
app/models/tool_bookmark.py. Sempre escopado por `user_id`: um usuário
nunca lista, edita nem apaga favorito de outro."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.tool_bookmark import ToolBookmark


def create(
    db: Session, *, user_id: str, ai_tool_id: str, url: str, title: Optional[str] = None
) -> ToolBookmark:
    bookmark = ToolBookmark(user_id=user_id, ai_tool_id=ai_tool_id, url=url, title=title)
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return bookmark


def list_for_user(db: Session, user_id: str, ai_tool_id: Optional[str] = None) -> List[ToolBookmark]:
    query = db.query(ToolBookmark).filter(ToolBookmark.user_id == user_id)
    if ai_tool_id:
        query = query.filter(ToolBookmark.ai_tool_id == ai_tool_id)
    return query.order_by(ToolBookmark.created_at.desc()).all()


def get_owned(db: Session, user_id: str, bookmark_id: str) -> Optional[ToolBookmark]:
    return (
        db.query(ToolBookmark)
        .filter(ToolBookmark.id == bookmark_id, ToolBookmark.user_id == user_id)
        .first()
    )


def delete(db: Session, bookmark: ToolBookmark) -> None:
    db.delete(bookmark)
    db.commit()
