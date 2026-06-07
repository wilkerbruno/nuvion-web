# backend/services/worker_client.py
"""
Cliente do worker Chrome.

Estrategia:
  1. Tenta Celery + Redis (producao com Redis configurado)
  2. Fallback: thread direta usando ChromeBrowserManager do projeto desktop
"""
import logging
import os
import sys
import threading
import uuid

LOGGER = logging.getLogger("NuvionBrowser")

_redis_ok: bool | None = None


def _ensure_desktop_path():
    """Garante que o projeto desktop esta no sys.path."""
    desktop = os.environ.get("DESKTOP_PROJECT_PATH", "/opt/nuvion-desktop")
    if desktop not in sys.path:
        sys.path.insert(0, desktop)
    return desktop


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
    """
    Executa abertura do Chrome em thread separada.
    Usa ChromeBrowserManager do projeto desktop diretamente,
    sem depender de PyQt6 (que nao existe no container da API).
    """
    LOGGER.info(f"[Thread] Iniciando job {job_id} | tool={tool_id} | user={user_id}")

    desktop = _ensure_desktop_path()
    LOGGER.info(f"[Thread] DESKTOP_PROJECT_PATH={desktop}")

    try:
        from crud.crud_manager import crud_system

        # Buscar dados da ferramenta
        ia = crud_system.ai_tools.get_by_id_with_relationships(
            tool_id, "direct_credentials", "proxy"
        )
        if not ia:
            LOGGER.error(f"[Thread] Ferramenta {tool_id} nao encontrada")
            return

        LOGGER.info(f"[Thread] Ferramenta: {ia.name} | URL: {ia.url}")

        # Detectar metodo de login
        login_method = (
            ia.get_active_login_method()
            if hasattr(ia, "get_active_login_method")
            else "manual"
        )
        LOGGER.info(f"[Thread] Login method: {login_method}")

        email = None
        password = None
        cookies_data = None

        if login_method in ("google", "direct"):
            try:
                creds = crud_system.direct_credentials.get_direct_credentials(tool_id)
                if creds:
                    email = creds.username
                    password = creds.password
                    LOGGER.info(f"[Thread] Credenciais: {email}")
            except Exception as e:
                LOGGER.warning(f"[Thread] Erro ao buscar credenciais: {e}")

        elif login_method == "cookies":
            try:
                session = crud_system.cookie_sessions.get_active_cookie_session(tool_id)
                if session:
                    cookies_data = session.cookies_data
                    LOGGER.info(f"[Thread] {len(cookies_data or [])} cookies encontrados")
            except Exception as e:
                LOGGER.warning(f"[Thread] Erro ao buscar cookies: {e}")

        # Proxy
        proxy_url = None
        proxy_obj = getattr(ia, "proxy", None)
        if proxy_obj and getattr(proxy_obj, "id", None):
            try:
                scheme = getattr(proxy_obj, "proxy_type", "http").lower()
                host = proxy_obj.host
                port = proxy_obj.port
                user = getattr(proxy_obj, "username", "") or ""
                pwd  = getattr(proxy_obj, "password", "") or ""
                proxy_url = (
                    f"{scheme}://{user}:{pwd}@{host}:{port}"
                    if (user and pwd)
                    else f"{scheme}://{host}:{port}"
                )
                LOGGER.info(f"[Thread] Proxy: {host}:{port}")
            except Exception as e:
                LOGGER.warning(f"[Thread] Erro ao montar proxy: {e}")

        # Abrir Chrome via ChromeBrowserManager (sem PyQt6)
        from core.managers.chrome_browser_manager import chrome_browser_manager

        LOGGER.info(f"[Thread] Abrindo Chrome para {ia.name}...")
        driver = chrome_browser_manager.open_chrome_for_tool(
            ai_tool_id=tool_id,
            target_url=ia.url,
            email=email,
            password=password,
            block_extensions=bool(getattr(ia, "block_extensions", False)),
            cookies_data=cookies_data,
            proxy_url=proxy_url,
        )

        if driver:
            LOGGER.info(f"[Thread] {ia.name} aberto com sucesso!")
        else:
            LOGGER.error(f"[Thread] Falha ao abrir {ia.name}")

    except Exception as e:
        import traceback
        LOGGER.error(
            f"[Thread] Erro no job {job_id}: {e}\n{traceback.format_exc()}"
        )


class WorkerClient:

    def enqueue_open_tool(self, user_id: str, tool_id: str) -> str:
        job_id = str(uuid.uuid4())

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
                LOGGER.warning(f"Celery falhou ({e}), usando thread direta")

        # Fallback: thread direta
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