# backend/api/routes/proxy.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.security import get_current_user_id, require_admin

router = APIRouter()


class ProxyCreate(BaseModel):
    name: str
    host: str
    port: int
    proxy_type: str = "http"
    username: Optional[str] = None
    password: Optional[str] = None


@router.get("")
def list_proxies(admin=Depends(require_admin)):
    from crud.crud_manager import crud_system
    proxies = crud_system.proxies.get_all() if hasattr(crud_system, "proxies") else []
    return [
        {
            "id":         p.id,
            "name":       p.name,
            "host":       p.host,
            "port":       p.port,
            "proxy_type": p.proxy_type,
            "is_active":  getattr(p, "is_active", True),
        }
        for p in proxies
    ]


@router.post("", status_code=201)
def create_proxy(body: ProxyCreate, admin=Depends(require_admin)):
    from crud.crud_manager import crud_system
    proxy = crud_system.proxies.create(**body.dict())
    if not proxy:
        raise HTTPException(status_code=400, detail="Falha ao criar proxy")
    return {"id": proxy.id}


@router.delete("/{proxy_id}")
def delete_proxy(proxy_id: str, admin=Depends(require_admin)):
    from crud.crud_manager import crud_system
    ok = crud_system.proxies.delete(proxy_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Proxy não encontrado")
    return {"message": "Proxy removido"}
