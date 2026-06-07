# backend/workers/chrome_worker.py
"""
Worker de automacao — roda como processo separado no VPS.
Consome jobs da fila Redis (via Celery) e executa abertura do Chrome.

Iniciar:
  celery -A workers.chrome_worker worker --concurrency=4 --loglevel=info
"""
import json
import logging
import os
import sys
import uuid

from celery import Celery

sys.path.insert(0, os.environ.get("DESKTOP_PROJECT_PATH", "/opt/nuvion-desktop"))

from core.config import settings

celery_app = Celery(
    "nuvion_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # ── Falhar rapido se Redis cair (evita 20s de retry na API) ──────────
    broker_transport_options={
        "socket_connect_timeout": 3,
        "socket_timeout": 3,
        "retry_on_timeout": False,
        "max_retries": 0,
    },
    result_backend_transport_options={
        "socket_connect_timeout": 3,
        "socket_timeout": 3,
        "retry_on_timeout": False,
        "max_retries": 0,
    },
    broker_connection_retry=False,       # nao tentar reconectar automaticamente
    broker_connection_max_retries=0,
)

# ---------------------------------------------------------------------------
# Redis lazy — so conecta quando a task roda, nao no import pela API
# ---------------------------------------------------------------------------
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis as redis_lib
        _redis_client = redis_lib.from_url(
            settings.REDIS_URL, decode_responses=True
        )
    return _redis_client


def _publish(job_id: str, event_type: str, data: dict = None):
    """
    Publica evento no canal Redis do job.
    Formato: {"type": "...", "data": {...}}
    """
    try:
        r = _get_redis()
        msg = json.dumps({"type": event_type, "data": data or {}})
        r.publish(f"job:{job_id}", msg)
        if event_type in ("opened", "error", "done"):
            r.setex(f"job_result:{job_id}", 3600, msg)
    except Exception as e:
        logging.getLogger("NuvionBrowser").warning(
            f"Nao foi possivel publicar evento {event_type} para job {job_id}: {e}"
        )


# ---------------------------------------------------------------------------
# Task principal
# ---------------------------------------------------------------------------

@celery_app.task(name="open_tool", bind=True, max_retries=1, soft_time_limit=90)
def open_tool_task(self, job_id: str, user_id: str, tool_id: str):
    """
    Abre a ferramenta de IA no Chrome UC.
    Publica eventos de progresso no Redis para o WebSocket.
    """
    _publish(job_id, "starting", {"message": "Iniciando Chrome..."})

    try:
        from crud.crud_manager import crud_system
        from core.managers.cookie_browser_manager import CookieBrowserManager

        tool = crud_system.ai_tools.get_by_id(tool_id)
        if not tool:
            _publish(job_id, "error", {"message": "Ferramenta nao encontrada"})
            return

        _publish(job_id, "starting", {"message": f"Abrindo {tool.name}..."})

        manager = CookieBrowserManager()
        driver = manager.open_tool_by_id(tool_id)

        if driver:
            _publish(job_id, "opened", {
                "message": f"{tool.name} aberto com sucesso",
                "tool_id": tool_id,
                "tool_name": tool.name,
                "url": tool.url,
            })
        else:
            _publish(job_id, "error", {"message": f"Falha ao abrir {tool.name}"})

    except Exception as exc:
        _publish(job_id, "error", {"message": str(exc)})
        if self.request.retries < 1:
            raise self.retry(exc=exc, countdown=5)
        raise exc