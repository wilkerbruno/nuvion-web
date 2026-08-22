"""CRUD do catálogo de ferramentas de IA (portado de
crud/sqlalchemy_ai_tools_manager.py).

No app desktop o catálogo era gerido por um admin local; aqui vira um
catálogo compartilhado por todos os usuários da plataforma via API —
leitura pública (autenticada), escrita restrita a admin (`require_admin`,
ver app/api/deps.py).
"""
from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.ai_tool import AITool


def list_all(db: Session, category: Optional[str] = None, search: Optional[str] = None) -> List[AITool]:
    query = db.query(AITool)
    if category:
        query = query.filter(AITool.category == category)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(AITool.name.ilike(like), AITool.description.ilike(like)))
    return query.order_by(AITool.is_featured.desc(), AITool.name.asc()).all()


def get_by_id(db: Session, tool_id: str) -> Optional[AITool]:
    return db.query(AITool).filter(AITool.id == tool_id).first()


def get_by_name(db: Session, name: str) -> Optional[AITool]:
    return db.query(AITool).filter(AITool.name == name).first()


def create(
    db: Session,
    *,
    name: str,
    url: str,
    description: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[list] = None,
    observations: Optional[str] = None,
    proxy_id: Optional[str] = None,
    login_method: str = "manual",
    is_featured: bool = False,
    block_extensions: bool = False,
) -> AITool:
    tool = AITool(
        name=name,
        url=url,
        description=description,
        category=category,
        tags=tags or [],
        observations=observations,
        proxy_id=proxy_id,
        login_method=login_method,
        is_featured=is_featured,
        block_extensions=block_extensions,
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return tool


def update(db: Session, tool: AITool, **fields) -> AITool:
    for key, value in fields.items():
        if value is not None and hasattr(tool, key):
            setattr(tool, key, value)
    db.commit()
    db.refresh(tool)
    return tool


def delete(db: Session, tool: AITool) -> None:
    db.delete(tool)
    db.commit()
