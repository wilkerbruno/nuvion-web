"""Favoritos de página dentro de uma ferramenta de IA (Fase 5) — salvos pela
extensão via um botão próprio injetado na janela da ferramenta, já que os
favoritos nativos do Chrome não têm como ser isolados por ferramenta/janela
(ver app/models/tool_bookmark.py). Sempre escopado ao próprio usuário
autenticado — ninguém vê, cria ou apaga favorito de outra pessoa, nem
Admin; não existe rota de admin aqui."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.crud import ai_tool as ai_tool_crud
from app.crud import tool_bookmark as bookmark_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.tool_bookmark import ToolBookmarkCreate, ToolBookmarkPublic

router = APIRouter(prefix="/tool-bookmarks", tags=["tool-bookmarks"])


@router.get("", response_model=List[ToolBookmarkPublic])
def list_bookmarks(
    ai_tool_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return bookmark_crud.list_for_user(db, current_user.id, ai_tool_id=ai_tool_id)


@router.post("", response_model=ToolBookmarkPublic, status_code=status.HTTP_201_CREATED)
def create_bookmark(
    payload: ToolBookmarkCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if ai_tool_crud.get_by_id(db, payload.ai_tool_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ferramenta não encontrada")
    return bookmark_crud.create(db, user_id=current_user.id, **payload.model_dump())


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(
    bookmark_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    bookmark = bookmark_crud.get_owned(db, current_user.id, bookmark_id)
    if bookmark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorito não encontrado")
    bookmark_crud.delete(db, bookmark)
