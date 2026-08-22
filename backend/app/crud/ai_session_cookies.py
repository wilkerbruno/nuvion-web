"""CRUD de cookies de sessão de IA (portado de
crud/sqlalchemy_cookie_session_manager.py), agora usando
app.services.cookie_parser.CookieParser em vez do import quebrado que o
modelo carregava desde a Fase 0.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.ai_session_cookies import AISessionCookies
from app.services.cookie_parser import CookieParser


def get_by_ai_tool(db: Session, ai_tool_id: str) -> Optional[AISessionCookies]:
    return (
        db.query(AISessionCookies)
        .filter(AISessionCookies.ai_tool_id == ai_tool_id)
        .first()
    )


def create_or_update(
    db: Session, *, ai_tool_id: str, cookies_data: List[dict], source_file: str = "painel_admin"
) -> AISessionCookies:
    existing = get_by_ai_tool(db, ai_tool_id)

    if existing:
        existing.update_cookies(cookies_data, source_file)
        existing.status = "active"
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing

    domain = CookieParser.extract_domain_from_cookies(cookies_data)
    expires_at = CookieParser.calculate_expiration(cookies_data)

    cookie_session = AISessionCookies(
        ai_tool_id=ai_tool_id,
        cookies_data=cookies_data,
        imported_from="direct",
        source_file=source_file,
        cookies_count=len(cookies_data),
        domain_extracted=domain,
        expires_at=expires_at,
        status="active",
        is_active=True,
        is_enabled=True,
    )
    db.add(cookie_session)
    db.commit()
    db.refresh(cookie_session)
    return cookie_session


def delete(db: Session, cookie_session: AISessionCookies) -> None:
    db.delete(cookie_session)
    db.commit()


def summary(cookie_session: Optional[AISessionCookies]) -> dict:
    if cookie_session is None:
        return {"configured": False}
    return cookie_session.to_dict_summary() | {"configured": True}
