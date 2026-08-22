"""Endpoint de healthcheck — usado por Docker/monitoramento para saber se a
API subiu e se consegue falar com o banco."""
from fastapi import APIRouter

from app.db.session import check_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    db_ok = check_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
    }
