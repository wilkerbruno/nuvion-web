# worker/main.py
"""
Servidor HTTP do container worker Chrome.
Recebe jobs da API via POST /open-tool e executa Chrome UC.

Iniciar (via Dockerfile ou Easypanel):
  uvicorn main:app --host 0.0.0.0 --port 8001
"""
import logging
import os
import sys
import threading

from fastapi import FastAPI
from pydantic import BaseModel

# Adicionar projeto desktop ao path
DESKTOP_PATH = os.environ.get("DESKTOP_PROJECT_PATH", "/opt/nuvion-desktop")
if DESKTOP_PATH not in sys.path:
    sys.path.insert(0, DESKTOP_PATH)

LOGGER = logging.getLogger("NuvionWorker")

app = FastAPI(title="Nuvion Chrome Worker", version="1.0.0")


class OpenToolRequest(BaseModel):
    job_id: str
    user_id: str
    tool_id: str


def _open_tool_background(job_id: str, user_id: str, tool_id: str):
    """Executa abertura do Chrome em thread separada."""
    LOGGER.info(f"[Worker] Iniciando job {job_id} | tool={tool_id}")
    try:
        from crud.crud_manager import crud_system
        from core.managers.chrome_browser_manager import chrome_browser_manager

        ia = crud_system.ai_tools.get_by_id_with_relationships(
            tool_id, "direct_credentials", "proxy"
        )
        if not ia:
            LOGGER.error(f"[Worker] Ferramenta {tool_id} nao encontrada")
            return

        LOGGER.info(f"[Worker] Abrindo: {ia.name} | {ia.url}")

        login_method = (
            ia.get_active_login_method()
            if hasattr(ia, "get_active_login_method")
            else "manual"
        )

        email = password = cookies_data = proxy_url = None

        if login_method in ("google", "direct"):
            try:
                creds = crud_system.direct_credentials.get_direct_credentials(tool_id)
                if creds:
                    email = creds.username
                    password = creds.password
            except Exception as e:
                LOGGER.warning(f"[Worker] Credenciais: {e}")

        elif login_method == "cookies":
            try:
                session = crud_system.cookie_sessions.get_active_cookie_session(tool_id)
                if session:
                    cookies_data = session.cookies_data
            except Exception as e:
                LOGGER.warning(f"[Worker] Cookies: {e}")

        proxy_obj = getattr(ia, "proxy", None)
        if proxy_obj and getattr(proxy_obj, "id", None):
            try:
                scheme = getattr(proxy_obj, "proxy_type", "http").lower()
                host, port = proxy_obj.host, proxy_obj.port
                u = getattr(proxy_obj, "username", "") or ""
                p = getattr(proxy_obj, "password", "") or ""
                proxy_url = (
                    f"{scheme}://{u}:{p}@{host}:{port}"
                    if (u and p)
                    else f"{scheme}://{host}:{port}"
                )
            except Exception as e:
                LOGGER.warning(f"[Worker] Proxy: {e}")

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
            LOGGER.info(f"[Worker] {ia.name} aberto com sucesso!")
        else:
            LOGGER.error(f"[Worker] Falha ao abrir {ia.name}")

    except Exception as e:
        import traceback
        LOGGER.error(f"[Worker] Erro no job {job_id}: {e}\n{traceback.format_exc()}")


@app.get("/health")
def health():
    return {"status": "ok", "service": "chrome-worker"}


@app.post("/open-tool")
def open_tool(req: OpenToolRequest):
    """
    Recebe job da API e executa Chrome em thread separada.
    Retorna imediatamente sem bloquear.
    """
    LOGGER.info(
        f"[Worker] Job recebido: {req.job_id} | tool={req.tool_id} | user={req.user_id}"
    )

    t = threading.Thread(
        target=_open_tool_background,
        args=(req.job_id, req.user_id, req.tool_id),
        daemon=True,
        name=f"chrome-{req.job_id[:8]}",
    )
    t.start()

    return {"job_id": req.job_id, "status": "started"}