"""Rotas do catálogo de ferramentas de IA + favoritos (Fase 4).

Leitura (`GET`) é liberada para qualquer usuário autenticado; escrita do
catálogo (`POST`/`PATCH`/`DELETE`) é restrita a admin — mesmo padrão de
`admin_payment_config.py` (Fase 3). Credenciais diretas e cookies de sessão
de cada ferramenta ficam em `app/api/routes/ai_tool_secrets.py`.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_admin
from app.crud import ai_direct_credentials as credentials_crud
from app.crud import ai_session_cookies as cookies_crud
from app.crud import ai_tool as ai_tool_crud
from app.crud import user_favorite as favorite_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai_tool import (
    AIToolCreate,
    AIToolPublic,
    AIToolUpdate,
    FavoriteToggleResponse,
)
from app.schemas.ai_tool_launch import AIToolLaunchResponse, LaunchCredentials, LaunchProxyInfo

router = APIRouter(prefix="/ai-tools", tags=["ai-tools"])


def _to_public(tool, favorite_ids: set) -> AIToolPublic:
    public = AIToolPublic.model_validate(tool)
    public.is_favorite = tool.id in favorite_ids
    return public


@router.get("", response_model=List[AIToolPublic])
def list_tools(
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    tools = ai_tool_crud.list_all(db, category=category, search=search)
    favorite_ids = set(favorite_crud.list_favorite_ids(db, current_user.id))
    return [_to_public(tool, favorite_ids) for tool in tools]


@router.get("/favorites", response_model=List[AIToolPublic])
def list_favorites(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    tools = favorite_crud.list_favorite_tools(db, current_user.id)
    favorite_ids = {tool.id for tool in tools}
    return [_to_public(tool, favorite_ids) for tool in tools]


def _get_or_404(db: Session, tool_id: str):
    tool = ai_tool_crud.get_by_id(db, tool_id)
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ferramenta não encontrada")
    return tool


@router.get("/{tool_id}", response_model=AIToolPublic)
def get_tool(
    tool_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    tool = _get_or_404(db, tool_id)
    favorite_ids = set(favorite_crud.list_favorite_ids(db, current_user.id))
    return _to_public(tool, favorite_ids)


@router.get("/{tool_id}/launch", response_model=AIToolLaunchResponse)
def launch_tool(
    tool_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Reúne tudo que a extensão precisa para abrir a ferramenta já logada
    e já roteada pelo proxy configurado pelo admin: URL, método de login,
    dados de conexão do proxy (se atribuído) e credenciais/cookies (se
    configurados) — nessa ordem de preferência (cookies primeiro, já que é
    o método principal combinado com o usuário; credenciais como reforço).

    Liberado para qualquer usuário autenticado (não só admin) — é o próprio
    usuário abrindo a ferramenta para uso normal, mesma lógica de `GET
    /ai-tools` (leitura do catálogo é pública para quem está logado).
    """
    tool = _get_or_404(db, tool_id)

    proxy_info = None
    if tool.proxy is not None and tool.proxy.is_active:
        proxy_info = LaunchProxyInfo(
            host=tool.proxy.host,
            port=tool.proxy.port,
            proxy_type=tool.proxy.proxy_type,
            username=tool.proxy.username,
            password=tool.proxy.password,
        )

    cookies = None
    cookie_session = cookies_crud.get_by_ai_tool(db, tool_id)
    if cookie_session is not None and cookie_session.is_valid():
        cookies = cookie_session.cookies_data

    credentials = None
    direct_credentials = credentials_crud.get_by_ai_tool(db, tool_id)
    if direct_credentials is not None and direct_credentials.is_active:
        decrypted = credentials_crud.get_decrypted_password(direct_credentials)
        if decrypted is not None:
            credentials = LaunchCredentials(
                username=direct_credentials.username,
                password=decrypted,
                login_url=direct_credentials.login_url,
                username_selector=direct_credentials.username_selector,
                password_selector=direct_credentials.password_selector,
                submit_selector=direct_credentials.submit_selector,
            )

    return AIToolLaunchResponse(
        ai_tool_id=tool.id,
        name=tool.name,
        url=tool.url,
        login_method=tool.get_active_login_method(),
        proxy=proxy_info,
        credentials=credentials,
        cookies=cookies,
    )


@router.post("", response_model=AIToolPublic, status_code=status.HTTP_201_CREATED)
def create_tool(
    payload: AIToolCreate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if ai_tool_crud.get_by_name(db, payload.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Ferramenta com este nome já existe"
        )
    tool = ai_tool_crud.create(db, **payload.model_dump())
    return _to_public(tool, set())


@router.patch("/{tool_id}", response_model=AIToolPublic)
def update_tool(
    tool_id: str,
    payload: AIToolUpdate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tool = _get_or_404(db, tool_id)
    tool = ai_tool_crud.update(db, tool, **payload.model_dump(exclude_unset=True))
    return _to_public(tool, set())


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tool(
    tool_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tool = _get_or_404(db, tool_id)
    ai_tool_crud.delete(db, tool)


@router.post("/{tool_id}/favorite", response_model=FavoriteToggleResponse)
def toggle_favorite(
    tool_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _get_or_404(db, tool_id)
    ok, is_fav = favorite_crud.toggle_favorite(db, current_user.id, tool_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Falha ao alternar favorito")
    return FavoriteToggleResponse(ai_tool_id=tool_id, is_favorite=is_fav)
