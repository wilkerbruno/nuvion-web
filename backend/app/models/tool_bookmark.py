"""Favoritos de página dentro de uma ferramenta de IA (Fase 5 — extensão).

Diferente de `UserFavorite` (favoritar a FERRAMENTA inteira, pro catálogo
`/ai-tools`), este aqui favorita uma PÁGINA específica dentro do uso de uma
ferramenta pela extensão — ex.: uma conversa específica de um chat de IA.

Nasceu de uma limitação real do Chrome: não existe como isolar os
favoritos NATIVOS do navegador por janela/ferramenta/perfil-anônimo — são
sempre uma lista única por perfil, ponto final, mesmo em modo anônimo. A
extensão contorna isso injetando um botão próprio ("★ Favoritar") dentro da
janela da ferramenta, que salva aqui via `POST /tool-bookmarks` em vez de
usar `chrome.bookmarks` — assim cada usuário tem sua própria lista, ligada
à conta dele (não ao navegador/computador), sem se misturar com os
favoritos normais do Chrome.
"""
from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.models.base import BaseModel


class ToolBookmark(Base, BaseModel):
    """Uma página salva pelo usuário enquanto usava uma ferramenta de IA."""

    __tablename__ = "tool_bookmarks"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    ai_tool_id = Column(String(36), ForeignKey("ai_tools.id"), nullable=False, index=True)

    url = Column(Text, nullable=False)
    title = Column(String(255), nullable=True)

    user = relationship("User", back_populates="tool_bookmarks")
    ai_tool = relationship("AITool", back_populates="tool_bookmarks")
