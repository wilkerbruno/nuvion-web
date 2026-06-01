# backend/workers/chrome_worker.py
"""
Worker de automação — roda como processo separado no VPS.
Consome jobs da fila Redis (via Celery) e executa abertura do Chrome.

Iniciar:
  celery -A workers.chrome_worker worker --concurrency=4 --loglevel=info
"""
import json
import os
import sys
import uuid

import redis
from celery import Celery

# Adicionar o projeto desktop ao path
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
    worker_prefetch_multiplier=1,          # Um job por vez por worker
    task_acks_late=True,                   # Confirmar só após concluir
    task_reject_on_worker_lost=True,
)

_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)


def _publish(job_id: str, event_type: str, data: dict = None):
    """Publica evento no canal Redis do job (consumido pelo WebSocket)."""
    msg = json.dumps({"type": event_type, "data": data or {}})
    _redis.publish(f"job:{job_id}", msg)
    # Salvar resultado final para polling HTTP
    if event_type in ("opened", "error", "done"):
        _redis.setex(f"job_result:{job_id}", 3600, msg)


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
            _publish(job_id, "error", {"message": "Ferramenta não encontrada"})
            return

        _publish(job_id, "starting", {"message": f"Abrindo {tool.name}..."})

        # Reutiliza CookieBrowserManager do projeto desktop
        manager = CookieBrowserManager()
        driver = manager.open_url_by_id(tool_id)

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
        raise self.retry(exc=exc, countdown=5) if self.request.retries < 1 else exc


# ── Client helper (usado pelas rotas FastAPI) ─────────────────────────────────

class WorkerClient:
    def enqueue_open_tool(self, user_id: str, tool_id: str) -> str:
        job_id = str(uuid.uuid4())
        open_tool_task.apply_async(
            kwargs={"job_id": job_id, "user_id": user_id, "tool_id": tool_id},
            task_id=job_id,
        )
        return job_id


worker_client = WorkerClient()
