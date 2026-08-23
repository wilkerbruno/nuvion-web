"""Schema da resposta de "abrir ferramenta" pela extensão (Fase 5).

Esta é a única rota da plataforma que devolve uma senha de login de
ferramenta em texto puro — decisão consciente, não um descuido. O
destinatário é sempre o próprio usuário autenticado que está abrindo a
ferramenta pela extensão instalada no navegador dele (nunca um terceiro);
é o mesmo nível de confiança que já existe em `GET /proxies`, que devolve
`password` em texto puro ao dono do proxy pessoal (ver app/schemas/proxy.py).
Sem isso a extensão não teria como preencher o formulário de login sozinha.

`app/crud/ai_direct_credentials.get_decrypted_password()` já documentava
essa exceção futura ("uso interno — futura automação de login via
extensão") desde a Fase 4; esta é essa automação chegando.
"""
from typing import List, Optional

from pydantic import BaseModel


class LaunchProxyInfo(BaseModel):
    host: str
    port: int
    proxy_type: str
    username: Optional[str] = None
    password: Optional[str] = None


class LaunchCredentials(BaseModel):
    username: str
    password: str
    login_url: Optional[str] = None
    username_selector: Optional[str] = None
    password_selector: Optional[str] = None
    submit_selector: Optional[str] = None


class AIToolLaunchResponse(BaseModel):
    ai_tool_id: str
    name: str
    url: str
    login_method: str
    proxy: Optional[LaunchProxyInfo] = None
    credentials: Optional[LaunchCredentials] = None
    cookies: Optional[List[dict]] = None
