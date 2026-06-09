# worker/main.py
import logging
import os
import sys
import threading
import subprocess
import socket
import time

from fastapi import FastAPI
from pydantic import BaseModel

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


def _find_free_port():
    """Encontra uma porta livre no sistema."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _start_local_proxy(proxy_url: str) -> tuple[str, subprocess.Popen | None]:
    """
    Se proxy é SOCKS5 com auth, inicia um tunnel local via pproxy.
    Retorna (proxy_url_para_chrome, processo_ou_None).
    """
    if not proxy_url:
        return proxy_url, None

    # Detectar SOCKS5 com autenticação
    if proxy_url.startswith("socks5://") and "@" in proxy_url:
        try:
            local_port = _find_free_port()
            # pproxy: tunnel local HTTP → SOCKS5 com auth
            cmd = [
                "pproxy", "-l", f"http://:{local_port}",
                "-r", proxy_url,
                "--daemon"
            ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1.5)  # aguarda pproxy iniciar
            local_proxy = f"http://127.0.0.1:{local_port}"
            LOGGER.info(f"[Worker] Tunnel local: {local_proxy} → {proxy_url.split('@')[1]}")
            return local_proxy, proc
        except Exception as e:
            LOGGER.warning(f"[Worker] Falha ao iniciar tunnel pproxy: {e} — usando proxy direto")
            return proxy_url, None

    return proxy_url, None


def _open_chrome(tool_id: str, url: str, email=None, password=None,
                 cookies_data=None, proxy_url=None, block_extensions=False):
    """Abre Chrome UC com suporte a SOCKS5 autenticado via tunnel local."""
    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--display={os.environ.get('DISPLAY', ':99')}")

    proxy_proc = None
    if proxy_url:
        effective_proxy, proxy_proc = _start_local_proxy(proxy_url)
        options.add_argument(f"--proxy-server={effective_proxy}")
        LOGGER.info(f"[Worker] Chrome usando proxy: {effective_proxy}")

    driver = uc.Chrome(options=options, headless=False)
    driver.get(url)

    # Injetar cookies se existirem
    if cookies_data:
        try:
            driver.delete_all_cookies()
            for cookie in (cookies_data if isinstance(cookies_data, list) else []):
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    pass
            driver.refresh()
        except Exception as e:
            LOGGER.warning(f"[Worker] Erro ao injetar cookies: {e}")

    LOGGER.info(f"[Worker] Chrome aberto em: {url}")
    return driver, proxy_proc


def _open_tool_background(job_id: str, user_id: str, tool_id: str):
    LOGGER.info(f"[Worker] Iniciando job {job_id} | tool={tool_id}")
    proxy_proc = None
    try:
        from crud.crud_manager import crud_system

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
                LOGGER.info(f"[Worker] Proxy: {host}:{port} ({scheme})")
            except Exception as e:
                LOGGER.warning(f"[Worker] Proxy erro: {e}")

        driver, proxy_proc = _open_chrome(
            tool_id=tool_id,
            url=ia.url,
            email=email,
            password=password,
            cookies_data=cookies_data,
            proxy_url=proxy_url,
            block_extensions=bool(getattr(ia, "block_extensions", False)),
        )

        if driver:
            LOGGER.info(f"[Worker] ✅ CLAUDE DIVISIONS {ia.name} aberto com sucesso!")
        else:
            LOGGER.error(f"[Worker] ❌ Falha ao abrir {ia.name}")

    except Exception as e:
        import traceback
        LOGGER.error(f"[Worker] Erro no job {job_id}: {e}\n{traceback.format_exc()}")
    finally:
        # Manter proxy_proc vivo enquanto o Chrome estiver aberto
        # (o processo daemon encerra com o worker)
        pass


@app.get("/health")
def health():
    return {"status": "ok", "service": "chrome-worker"}


@app.post("/open-tool")
def open_tool(req: OpenToolRequest):
    LOGGER.info(f"[Worker] Job recebido: {req.job_id} | tool={req.tool_id}")
    t = threading.Thread(
        target=_open_tool_background,
        args=(req.job_id, req.user_id, req.tool_id),
        daemon=True,
        name=f"chrome-{req.job_id[:8]}",
    )
    t.start()
    return {"job_id": req.job_id, "status": "started"}