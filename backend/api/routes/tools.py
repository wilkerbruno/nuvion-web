# backend/api/routes/tools.py
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from core.security import get_current_user_id, require_admin

router = APIRouter()


class ToolCreate(BaseModel):
    name: str
    url: str
    description: str = ""
    category: str = "conversacao"
    tags: List[str] = []
    observations: str = ""
    login_method: str = "manual"
    proxy_id: Optional[str] = None
    block_extensions: bool = False
    is_featured: bool = False


class ToolUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    observations: Optional[str] = None
    login_method: Optional[str] = None
    proxy_id: Optional[str] = None
    block_extensions: Optional[bool] = None
    is_featured: Optional[bool] = None


def _tool_to_dict(tool, favorite_ids: set = None) -> dict:
    return {
        "id":           tool.id,
        "name":         tool.name,
        "url":          tool.url,
        "description":  tool.description or "",
        "category":     tool.category or "conversacao",
        "tags":         tool.tags or [],
        "observations": tool.observations or "",
        "login_method": tool.login_method or "manual",
        "proxy_id":     tool.proxy_id,
        "block_extensions": bool(tool.block_extensions),
        "is_featured":  bool(tool.is_featured),
        "rating":       float(tool.rating or 0),
        "is_favorite":  (tool.id in favorite_ids) if favorite_ids is not None else False,
        "created_at":   tool.created_at.isoformat() if tool.created_at else None,
    }


@router.get("")
def list_tools(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    user_id: str = Depends(get_current_user_id),
):
    from crud.crud_manager import crud_system

    tools = crud_system.ai_tools.get_all(limit=limit, offset=offset)

    # Filtrar por categoria
    if category and category != "todas":
        if category == "favoritos":
            fav_ids = set(crud_system.user_favorites.get_user_favorite_ids(user_id))
            tools = [t for t in tools if t.id in fav_ids]
        else:
            tools = [t for t in tools if t.category == category]

    # Busca
    if search:
        q = search.lower()
        tools = [
            t for t in tools
            if q in (t.name or "").lower()
            or q in (t.url or "").lower()
            or any(q in tag.lower() for tag in (t.tags or []))
        ]

    # Favoritos do usuário
    fav_ids = set(crud_system.user_favorites.get_user_favorite_ids(user_id))

    return [_tool_to_dict(t, fav_ids) for t in tools]


@router.get("/{tool_id}")
def get_tool(tool_id: str, user_id: str = Depends(get_current_user_id)):
    from crud.crud_manager import crud_system

    tool = crud_system.ai_tools.get_by_id(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Ferramenta não encontrada")

    fav_ids = set(crud_system.user_favorites.get_user_favorite_ids(user_id))
    return _tool_to_dict(tool, fav_ids)


@router.post("", status_code=201)
def create_tool(body: ToolCreate, admin=Depends(require_admin)):
    from crud.crud_manager import crud_system

    success, result = crud_system.ai_tools.add_tool(
        name=body.name,
        url=body.url,
        description=body.description,
        category=body.category,
        tags=body.tags,
        observations=body.observations,
        login_method=body.login_method,
        proxy_id=body.proxy_id,
        block_extensions=body.block_extensions,
        is_featured=body.is_featured,
    )
    if not success:
        raise HTTPException(status_code=400, detail=result)

    return {"id": result, "message": "Ferramenta criada com sucesso"}


@router.patch("/{tool_id}")
def update_tool(tool_id: str, body: ToolUpdate, admin=Depends(require_admin)):
    from crud.crud_manager import crud_system

    ok = crud_system.ai_tools.update_tool(
        tool_id=tool_id,
        **{k: v for k, v in body.dict().items() if v is not None},
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Ferramenta não encontrada")
    return {"message": "Ferramenta atualizada"}


@router.delete("/{tool_id}")
def delete_tool(tool_id: str, admin=Depends(require_admin)):
    from crud.crud_manager import crud_system

    ok = crud_system.ai_tools.delete(tool_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Ferramenta não encontrada")
    return {"message": "Ferramenta removida"}



@router.post("/{tool_id}/open")
async def open_tool(tool_id: str, user_id: str = Depends(get_current_user_id)):
    from services.worker_client import dispatch_job
    result = await dispatch_job(tool_id=tool_id, user_id=user_id)
    return {"job_id": result["job_id"], "method": result["method"], "status": "queued"}