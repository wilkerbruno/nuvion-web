# worker/main.py
"""
Servidor HTTP do container worker.
A API chama POST /open-tool → este servidor abre o Chrome UC em thread separada.
"""
import logging
import os
import sys
import threading

from fastapi import FastAPI
from pydantic import BaseModel

# Path do projeto desktop (onde estão crud/, database/, core/, etc)
DESKTOP_PATH = os.environ.get("DESKTOP_PROJECT_PATH", "/app")
if DESKTOP_PATH not in sys.path:
    sys.path.insert(0, DESKTOP_PATH)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s].[%(levelname)s].%(message)s",
    datefmt="%H:%M:%S",
)
LOGGER = logging.getLogger("NuvionWorker")

app = FastAPI(title="Nuvion Chrome Worker", version="1.0.0")


class OpenToolRequest(BaseModel):
    job_id: str
    user_id: str
    tool_id: str


def _open_tool_background(job_id: str, user_id: str, tool_id: str):
    """Abre Chrome UC em thread separada — não bloqueia o uvicorn."""
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
        LOGGER.info(f"[Worker] Login method: {login_method}")

        email = password = cookies_data = proxy_url = None

        if login_method in ("google", "direct"):
            try:
                creds = crud_system.direct_credentials.get_direct_credentials(tool_id)
                if creds:
                    email = creds.username
                    password = creds.password
                    LOGGER.info(f"[Worker] Credenciais: {email}")
            except Exception as e:
                LOGGER.warning(f"[Worker] Credenciais erro: {e}")

        elif login_method == "cookies":
            try:
                session = crud_system.cookie_sessions.get_active_cookie_session(tool_id)
                if session:
                    cookies_data = session.cookies_data
                    LOGGER.info(f"[Worker] {len(cookies_data or [])} cookies carregados")
            except Exception as e:
                LOGGER.warning(f"[Worker] Cookies erro: {e}")

        # Proxy
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
                LOGGER.info(f"[Worker] Proxy: {host}:{port}")
            except Exception as e:
                LOGGER.warning(f"[Worker] Proxy erro: {e}")

        # Abrir Chrome
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
            LOGGER.info(f"[Worker] ✅ {ia.name} aberto com sucesso!")
        else:
            LOGGER.error(f"[Worker] ❌ Falha ao abrir {ia.name}")

    except Exception as e:
        import traceback
        LOGGER.error(
            f"[Worker] Erro no job {job_id}: {e}\n{traceback.format_exc()}"
        )


@app.get("/health")
def health():
    return {"status": "ok", "service": "chrome-worker"}


@app.post("/open-tool")
def open_tool(req: OpenToolRequest):
    """
    Recebe job da API e abre Chrome em thread separada.
    Retorna imediatamente — o Chrome abre em background.
    """
    LOGGER.info(f"[Worker] Job recebido: {req.job_id} | tool={req.tool_id}")
    t = threading.Thread(
        target=_open_tool_background,
        args=(req.job_id, req.user_id, req.tool_id),
        daemon=True,
        name=f"chrome-{req.job_id[:8]}",
    )
    t.start()
    return {"job_id": req.job_id, "status": "started"}