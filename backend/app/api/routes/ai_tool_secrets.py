"""Rotas de credenciais diretas e cookies de sessão por ferramenta de IA
(Fase 4). Login automático de verdade (o `auto_login_engine.py` do desktop,
que dirigia o QtWebEngine embutido) não foi portado — não existe equivalente
direto na arquitetura web (a extensão só injeta script na página, não
comanda navegação como o QtWebEngine embutido fazia); fica documentado como
trabalho futuro em backend/README.md. Por ora estas rotas só armazenam e
mostram o status ("configurado" ou não) das credenciais/cookies — quem as
usaria de fato (login automático) ainda não existe nesta fase.

Escrita restrita a admin (são segredos compartilhados da plataforma, não
dados de um usuário específico — mesma modelagem do app desktop, onde
`AIDirectCredentials`/`AISessionCookies` são 1:1 com a ferramenta de IA, não
com o usuário). Leitura (resumo sem segredo) liberada a qualquer usuário
autenticado.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_admin
from app.crud import ai_direct_credentials as credentials_crud
from app.crud import ai_session_cookies as cookies_crud
from app.crud.ai_tool import get_by_id as get_tool_by_id
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai_tool_secrets import (
    CookieSessionSet,
    CookieSessionSummary,
    DirectCredentialsSet,
    DirectCredentialsSummary,
)

router = APIRouter(prefix="/ai-tools/{tool_id}", tags=["ai-tools-secrets"])


def _get_tool_or_404(db: Session, tool_id: str):
    tool = get_tool_by_id(db, tool_id)
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ferramenta não encontrada")
    return tool


@router.get("/credentials", response_model=DirectCredentialsSummary)
def get_credentials(
    tool_id: str,
    _user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _get_tool_or_404(db, tool_id)
    return credentials_crud.summary(credentials_crud.get_by_ai_tool(db, tool_id))


@router.put("/credentials", response_model=DirectCredentialsSummary)
def set_credentials(
    tool_id: str,
    payload: DirectCredentialsSet,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_tool_or_404(db, tool_id)
    credentials = credentials_crud.create_or_update(db, ai_tool_id=tool_id, **payload.model_dump())
    return credentials_crud.summary(credentials)


@router.delete("/credentials", status_code=status.HTTP_204_NO_CONTENT)
def delete_credentials(
    tool_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_tool_or_404(db, tool_id)
    credentials = credentials_crud.get_by_ai_tool(db, tool_id)
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credenciais não configuradas")
    credentials_crud.delete(db, credentials)


@router.get("/cookies", response_model=CookieSessionSummary)
def get_cookies(
    tool_id: str,
    _user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _get_tool_or_404(db, tool_id)
    return cookies_crud.summary(cookies_crud.get_by_ai_tool(db, tool_id))


@router.put("/cookies", response_model=CookieSessionSummary)
def set_cookies(
    tool_id: str,
    payload: CookieSessionSet,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_tool_or_404(db, tool_id)
    if not payload.cookies_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lista de cookies vazia")
    cookie_session = cookies_crud.create_or_update(
        db, ai_tool_id=tool_id, cookies_data=payload.cookies_data
    )
    return cookies_crud.summary(cookie_session)


@router.delete("/cookies", status_code=status.HTTP_204_NO_CONTENT)
def delete_cookies(
    tool_id: str,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_tool_or_404(db, tool_id)
    cookie_session = cookies_crud.get_by_ai_tool(db, tool_id)
    if cookie_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cookies não configurados")
    cookies_crud.delete(db, cookie_session)
