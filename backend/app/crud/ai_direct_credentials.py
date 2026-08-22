"""CRUD de credenciais diretas de login de IA (portado de
crud/sqlalchemy_direct_credentials_manager.py).

Melhoria de segurança consciente em relação ao original: lá, `password`
era salvo em texto plano no banco ("SEM criptografia para testes", segundo
o próprio comentário do código-fonte). Aqui é cifrado em repouso com Fernet
(`settings.ENCRYPTION_KEY`, sem default — ver app/core/config.py) e nunca
retornado em texto puro por nenhuma rota (ver app/schemas/ai_tool_secrets.py
— só um `configured: bool`).
"""
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import LOGGER
from app.models.ai_direct_credentials import AIDirectCredentials


def _fernet() -> Fernet:
    return Fernet(settings.ENCRYPTION_KEY.encode())


def _encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def _decrypt(value: str) -> Optional[str]:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError) as e:
        LOGGER.error(f"Falha ao descriptografar credencial: {e}")
        return None


def get_by_ai_tool(db: Session, ai_tool_id: str) -> Optional[AIDirectCredentials]:
    return (
        db.query(AIDirectCredentials)
        .filter(AIDirectCredentials.ai_tool_id == ai_tool_id)
        .first()
    )


def create_or_update(
    db: Session,
    *,
    ai_tool_id: str,
    username: str,
    password: str,
    login_url: Optional[str] = None,
    username_selector: Optional[str] = None,
    password_selector: Optional[str] = None,
    submit_selector: Optional[str] = None,
) -> AIDirectCredentials:
    existing = get_by_ai_tool(db, ai_tool_id)
    encrypted_password = _encrypt(password)

    if existing:
        existing.username = username
        existing.password = encrypted_password
        if login_url is not None:
            existing.login_url = login_url
        if username_selector is not None:
            existing.username_selector = username_selector
        if password_selector is not None:
            existing.password_selector = password_selector
        if submit_selector is not None:
            existing.submit_selector = submit_selector
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    credentials = AIDirectCredentials(
        ai_tool_id=ai_tool_id,
        username=username,
        password=encrypted_password,
        login_url=login_url,
        is_active=True,
        **{
            k: v
            for k, v in {
                "username_selector": username_selector,
                "password_selector": password_selector,
                "submit_selector": submit_selector,
            }.items()
            if v is not None
        },
    )
    db.add(credentials)
    db.commit()
    db.refresh(credentials)
    return credentials


def get_decrypted_password(credentials: AIDirectCredentials) -> Optional[str]:
    """Só para uso interno (futura automação de login via extensão) — nunca
    expor o retorno desta função em uma resposta de API."""
    return _decrypt(credentials.password)


def delete(db: Session, credentials: AIDirectCredentials) -> None:
    db.delete(credentials)
    db.commit()


def summary(credentials: Optional[AIDirectCredentials]) -> dict:
    if credentials is None:
        return {"configured": False}
    return {
        "configured": True,
        "username": credentials.username,
        "login_url": credentials.login_url,
        "is_active": credentials.is_active,
        "login_status": credentials.login_status,
        "failed_attempts": credentials.failed_attempts,
        "max_attempts": credentials.max_attempts,
    }
