# worker/main.py
import logging
import os
import sys
import threading
import socket
import time
import struct

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


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class Socks5HttpBridge:
    """
    Proxy HTTP local simples que encaminha conexões para SOCKS5 com autenticação.
    O Chrome conecta via HTTP CONNECT → bridge conecta ao SOCKS5 com auth.
    """

    def __init__(self, socks5_host, socks5_port, socks5_user, socks5_pass):
        self.socks5_host = socks5_host
        self.socks5_port = socks5_port
        self.socks5_user = socks5_user
        self.socks5_pass = socks5_pass
        self.local_port = _find_free_port()
        self._server = None
        self._thread = None

    def _socks5_connect(self, target_host: str, target_port: int) -> socket.socket:
        import socks
        s = socks.socksocket()
        s.set_proxy(
            socks.SOCKS5,
            self.socks5_host,
            self.socks5_port,
            username=self.socks5_user,
            password=self.socks5_pass,
        )
        s.settimeout(30)
        s.connect((target_host, target_port))
        return s

    def _handle_client(self, client_sock: socket.socket):
        try:
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = client_sock.recv(4096)
                if not chunk:
                    return
                data += chunk

            first_line = data.split(b"\r\n")[0].decode("utf-8", errors="replace")
            parts = first_line.split()
            if len(parts) < 2:
                return

            method = parts[0]
            if method == "CONNECT":
                # HTTPS
                host_port = parts[1]
                host, port = host_port.rsplit(":", 1)
                port = int(port)
            else:
                # HTTP direto
                url = parts[1]
                if url.startswith("http://"):
                    url = url[7:]
                host_port = url.split("/")[0]
                if ":" in host_port:
                    host, port = host_port.rsplit(":", 1)
                    port = int(port)
                else:
                    host, port = host_port, 80

            remote = self._socks5_connect(host, port)

            if method == "CONNECT":
                client_sock.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            else:
                remote.sendall(data)

            def relay(src, dst):
                try:
                    while True:
                        d = src.recv(8192)
                        if not d:
                            break
                        dst.sendall(d)
                except Exception:
                    pass
                finally:
                    try:
                        src.close()
                    except Exception:
                        pass
                    try:
                        dst.close()
                    except Exception:
                        pass

            t1 = threading.Thread(target=relay, args=(client_sock, remote), daemon=True)
            t2 = threading.Thread(target=relay, args=(remote, client_sock), daemon=True)
            t1.start()
            t2.start()

        except Exception as e:
            LOGGER.debug(f"[Bridge] Erro: {e}")
            try:
                client_sock.close()
            except Exception:
                pass

    def _serve(self):
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", self.local_port))
        self._server.listen(50)
        self._server.settimeout(1)
        LOGGER.info(f"[Bridge] HTTP proxy local na porta {self.local_port} → SOCKS5 {self.socks5_host}:{self.socks5_port}")
        while True:
            try:
                client, _ = self._server.accept()
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception:
                break

    def start(self):
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        time.sleep(0.5)
        return f"http://127.0.0.1:{self.local_port}"

    def stop(self):
        if self._server:
            try:
                self._server.close()
            except Exception:
                pass


# Registry de bridges ativos (por job_id)
_bridges: dict[str, Socks5HttpBridge] = {}


def _open_chrome(tool_id: str, url: str, email=None, password=None,
                 cookies_data=None, proxy_url=None, block_extensions=False):
    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--display={os.environ.get('DISPLAY', ':99')}")

    bridge = None
    if proxy_url:
        # Parsear proxy_url: socks5://user:pass@host:port
        effective_proxy = proxy_url
        if proxy_url.startswith("socks5://") and "@" in proxy_url:
            try:
                rest = proxy_url[9:]  # remove socks5://
                auth, hostport = rest.rsplit("@", 1)
                socks5_user, socks5_pass = auth.split(":", 1)
                socks5_host, socks5_port = hostport.rsplit(":", 1)
                bridge = Socks5HttpBridge(socks5_host, int(socks5_port), socks5_user, socks5_pass)
                effective_proxy = bridge.start()
                LOGGER.info(f"[Worker] Bridge HTTP→SOCKS5: {effective_proxy} → {socks5_host}:{socks5_port}")
            except Exception as e:
                LOGGER.warning(f"[Worker] Falha ao criar bridge: {e} — usando proxy direto")
                effective_proxy = proxy_url

        options.add_argument(f"--proxy-server={effective_proxy}")
        LOGGER.info(f"[Worker] Chrome proxy: {effective_proxy}")

    driver = uc.Chrome(options=options, headless=False)
    driver.get(url)

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
    return driver, bridge


def _open_tool_background(job_id: str, user_id: str, tool_id: str):
    LOGGER.info(f"[Worker] Iniciando job {job_id} | tool={tool_id}")
    bridge = None
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
                LOGGER.info(f"[Worker] Proxy: {host}:{port} ({scheme}) user={bool(u)}")
            except Exception as e:
                LOGGER.warning(f"[Worker] Proxy erro: {e}")

        driver, bridge = _open_chrome(
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
        if bridge:
            bridge.stop()


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