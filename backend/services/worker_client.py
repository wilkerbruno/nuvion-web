# backend/services/worker_client.py
"""
Cliente do worker Chrome.

Estrategia (em ordem de prioridade):
  1. Celery + Redis  — producao ideal
  2. HTTP para o container worker — fallback quando Redis nao existe
     O container worker expoe POST http://worker:8001/open-tool
"""
import logging
import os
import uuid

LOGGER = logging.getLogger("NuvionBrowser")

# URL interna do container worker no Easypanel
# Configuravel via env var WORKER_URL
WORKER_HTTP_URL = os.getenv("WORKER_URL", "http://worker:8001")

_redis_ok: bool | None = None


def _redis_available() -> bool:
    global _redis_ok
    if _redis_ok is not None:
        return _redis_ok
    try:
        import redis
        from core.config import settings
        r = redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        r.ping()
        _redis_ok = True
        LOGGER.info("Redis disponivel — usando Celery")
    except Exception as e:
        _redis_ok = False
        LOGGER.warning(f"Redis indisponivel ({e}) — usando HTTP para worker")
    return _redis_ok


def _call_worker_http(job_id: str, user_id: str, tool_id: str) -> bool:
    """
    Chama o endpoint HTTP do container worker.
    O worker precisa estar rodando worker/main.py (FastAPI na porta 8001).
    """
    try:
        import requests
        url = f"{WORKER_HTTP_URL}/open-tool"
        resp = requests.post(
            url,
            json={"job_id": job_id, "user_id": user_id, "tool_id": tool_id},
            timeout=5,
        )
        if resp.status_code == 200:
            LOGGER.info(f"Job enviado ao worker via HTTP: {job_id}")
            return True
        LOGGER.warning(f"Worker HTTP retornou {resp.status_code}: {resp.text}")
        return False
    except Exception as e:
        LOGGER.warning(f"Falha ao chamar worker via HTTP ({e})")
        return False


class WorkerClient:

    def enqueue_open_tool(self, user_id: str, tool_id: str) -> str:
        job_id = str(uuid.uuid4())

        # Caminho 1: Celery + Redis
        if _redis_available():
            try:
                from workers.chrome_worker import open_tool_task
                open_tool_task.apply_async(
                    kwargs={
                        "job_id": job_id,
                        "user_id": user_id,
                        "tool_id": tool_id,
                    },
                    task_id=job_id,
                )
                LOGGER.info(f"Job enfileirado via Celery: {job_id}")
                return job_id
            except Exception as e:
                LOGGER.warning(f"Celery falhou ({e}), tentando HTTP")

        # Caminho 2: HTTP para container worker
        if _call_worker_http(job_id, user_id, tool_id):
            return job_id

        # Sem worker disponivel — retornar job_id mesmo assim
        # O WebSocket vai informar ao frontend que o worker nao esta disponivel
        LOGGER.error(
            f"Nenhum worker disponivel para job {job_id}. "
            f"Configure Redis ou WORKER_URL no Easypanel."
        )
        return job_id


worker_client = WorkerClient()