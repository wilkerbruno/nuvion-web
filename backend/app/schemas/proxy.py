"""Schemas de proxy — usados pelo painel web e pela extensão (Fase 2).

Diferente de `UserPublic`, aqui a senha do proxy É retornada ao dono: não é
uma credencial de conta, é uma configuração que o próprio usuário cadastrou
e pode precisar conferir depois (ex.: para usar o mesmo proxy em outro
lugar). Nunca é retornada para ninguém além do dono — ver
`app/api/routes/proxies.py`, que sempre filtra por `user_id`.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProxyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(gt=0, le=65535)
    proxy_type: str = Field(pattern="^(HTTP|HTTPS|SOCKS4|SOCKS5)$")
    username: Optional[str] = Field(default=None, max_length=100)
    password: Optional[str] = None


class ProxyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    host: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, gt=0, le=65535)
    proxy_type: Optional[str] = Field(default=None, pattern="^(HTTP|HTTPS|SOCKS4|SOCKS5)$")
    username: Optional[str] = Field(default=None, max_length=100)
    password: Optional[str] = None
    is_active: Optional[bool] = None


class ProxyPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    host: str
    port: int
    proxy_type: str
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: bool
    is_selected: bool
    status: str
    response_time: Optional[int] = None
