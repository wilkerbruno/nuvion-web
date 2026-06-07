# backend/services/worker_client.py
"""
Cliente do worker Chrome.

Estrategia com fallback:
  1. Tenta usar Celery + Redis (ideal para producao)
  2. Se Redis indisponivel: executa em thread separada diretamente
     (funciona sem Redis, porem sem status em tempo real via WebSocket)
"""
import logging
import threading
import uuid

LOGGER = logging.getLogger("NuvionBrowser")

# Cache de disponibilidade — testado uma vez, nao a cada chamada
_redis_ok: bool | None = None  # None = nao testado


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
        LOGGER.warning(f"Redis indisponivel ({e}) — usando thread direta")
    return _redis_ok


def _run_in_thread(job_id: str, user_id: str, tool_id: str):
    """Executa abertura do Chrome em thread separada (sem Redis)."""
    LOGGER.info(f"[Thread] Iniciando job {job_id} | tool={tool_id} | user={user_id}")
    try:
        import sys, os
        desktop = os.environ.get("DESKTOP_PROJECT_PATH", "/opt/nuvion-desktop")
        if desktop not in sys.path:
            sys.path.insert(0, desktop)

        from crud.crud_manager import crud_system
        from core.managers.cookie_browser_manager import CookieBrowserManager

        tool = crud_system.ai_tools.get_by_id(tool_id)
        if not tool:
            LOGGER.error(f"[Thread] Ferramenta {tool_id} nao encontrada")
            return

        LOGGER.info(f"[Thread] Abrindo {tool.name}...")
        manager = CookieBrowserManager()
        driver = manager.open_tool_by_id(tool_id)

        if driver:
            LOGGER.info(f"[Thread] {tool.name} aberto com sucesso")
        else:
            LOGGER.error(f"[Thread] Falha ao abrir {tool.name}")

    except Exception as e:
        import traceback
        LOGGER.error(f"[Thread] Erro no job {job_id}: {e}\n{traceback.format_exc()}")


class WorkerClient:

    def enqueue_open_tool(self, user_id: str, tool_id: str) -> str:
        job_id = str(uuid.uuid4())

        if _redis_available():
            # ── Caminho 1: Celery + Redis ──────────────────────────────────
            try:
                from workers.chrome_worker import open_tool_task
                open_tool_task.apply_async(
                    kwargs={"job_id": job_id, "user_id": user_id, "tool_id": tool_id},
                    task_id=job_id,
                )
                LOGGER.info(f"Job enfileirado via Celery: {job_id}")
                return job_id
            except Exception as e:
                LOGGER.warning(f"Celery falhou ({e}), usando thread direta")

        # ── Caminho 2: Thread direta (sem Redis) ──────────────────────────
        t = threading.Thread(
            target=_run_in_thread,
            args=(job_id, user_id, tool_id),
            daemon=True,
            name=f"chrome-{job_id[:8]}",
        )
        t.start()
        LOGGER.info(f"Job iniciado em thread direta: {job_id}")
        return job_id


worker_client = WorkerClient()