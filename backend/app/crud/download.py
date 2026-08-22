"""CRUD do histórico de downloads (Fase 4).

Não existia um manager dedicado no app desktop para isto (o download em si
rodava dentro do processo QtWebEngine); o histórico aqui é alimentado pela
extensão via `chrome.downloads` (ver extension/src/background/service-worker.js)
— o backend só guarda status para exibir no painel.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.download import Download


def create(
    db: Session,
    *,
    user_id: str,
    file_name: str,
    file_path: Optional[str] = None,
    url: Optional[str] = None,
    status: str = "in_progress",
) -> Download:
    download = Download(
        user_id=user_id,
        file_name=file_name,
        file_path=file_path,
        url=url,
        status=status,
        start_time=datetime.now(timezone.utc),
    )
    db.add(download)
    db.commit()
    db.refresh(download)
    return download


def list_for_user(db: Session, user_id: str, limit: int = 100) -> List[Download]:
    return (
        db.query(Download)
        .filter(Download.user_id == user_id)
        .order_by(Download.created_at.desc())
        .limit(limit)
        .all()
    )


def get_owned(db: Session, user_id: str, download_id: str) -> Optional[Download]:
    return (
        db.query(Download)
        .filter(Download.id == download_id, Download.user_id == user_id)
        .first()
    )


def update_status(db: Session, download: Download, *, status: str, end_time=None) -> Download:
    download.status = status
    if end_time is not None:
        download.end_time = end_time
    db.commit()
    db.refresh(download)
    return download
