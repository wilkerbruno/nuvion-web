# worker/main.py
import logging
import os
import sys
import threading
import socket as _socket_module
import socketserver
import struct
import time
from typing import Optional
from urllib.parse import urlparse as _urlparse

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


# ── Bridge SOCKS5 (portada do desktop, sem PyQt6) ────────────────────────────

class _ChromeSOCKS5Bridge:
    def __init__(self, proxy_host, proxy_port, proxy_user="", proxy_pass=""):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.proxy_user = proxy_user
        self.proxy_pass = proxy_pass
        self.server = None
        self.local_port = 0

    def start(self) -> int:
        try:
            bridge = self

            class _Handler(socketserver.StreamRequestHandler):
                def handle(self):
                    try:
                        first_line = self.rfile.readline().decode("utf-8", errors="ignore").strip()
                        while True:
                            line = self.rfile.readline().decode("utf-8", errors="ignore").strip()
                            if not line:
                                break
                        if not first_line.upper().startswith("CONNECT"):
                            self.wfile.write(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                            return
                        target = first_line.split()[1]
                        host, port_str = target.rsplit(":", 1)
                        port = int(port_str)
                        upstream = bridge._connect_upstream(host, port)
                        if not upstream:
                            self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                            self.wfile.flush()
                            return
                        self.wfile.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
                        self.wfile.flush()
                        bridge._relay(self.connection, upstream)
                    except Exception:
                        pass

            class _Server(socketserver.ThreadingTCPServer):
                allow_reuse_address = True
                daemon_threads = True

            self.server = _Server(("127.0.0.1", 0), _Handler)
            self.local_port = self.server.server_address[1]
            t = threading.Thread(target=self.server.serve_forever, daemon=True)
            t.start()
            LOGGER.info(f"Bridge SOCKS5: 127.0.0.1:{self.local_port} → {self.proxy_host}:{self.proxy_port}")
            return self.local_port
        except Exception as e:
            LOGGER.error(f"Erro ao iniciar bridge SOCKS5: {e}")
            return 0

    @staticmethod
    def _recv_exact(sock, n):
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError(f"Conexao encerrada antes de {n} bytes")
            buf += chunk
        return buf

    def _connect_upstream(self, target_host, target_port):
        sock = _socket_module.socket(_socket_module.AF_INET, _socket_module.SOCK_STREAM)
        sock.settimeout(15)
        try:
            sock.connect((self.proxy_host, self.proxy_port))
            if self.proxy_user and self.proxy_pass:
                sock.send(b"\x05\x02\x00\x02")
            else:
                sock.send(b"\x05\x01\x00")
            auth_resp = self._recv_exact(sock, 2)
            if auth_resp[0] != 5:
                sock.close(); return None
            chosen = auth_resp[1]
            if chosen == 0xFF:
                sock.close(); return None
            if chosen == 0x02:
                user_b = self.proxy_user.encode()
                pass_b = self.proxy_pass.encode()
                sock.send(bytes([0x01, len(user_b)]) + user_b + bytes([len(pass_b)]) + pass_b)
                ar = self._recv_exact(sock, 2)
                if ar[1] != 0x00:
                    sock.close(); return None
            try:
                host_ip = _socket_module.inet_aton(target_host)
                addr_part = b"\x01" + host_ip
            except OSError:
                host_b = target_host.encode()
                addr_part = b"\x03" + bytes([len(host_b)]) + host_b
            sock.send(b"\x05\x01\x00" + addr_part + struct.pack(">H", target_port))
            header = self._recv_exact(sock, 4)
            if header[1] != 0x00:
                sock.close(); return None
            atyp = header[3]
            if atyp == 0x01:
                self._recv_exact(sock, 6)
            elif atyp == 0x03:
                dlen = self._recv_exact(sock, 1)[0]
                self._recv_exact(sock, dlen + 2)
            elif atyp == 0x04:
                self._recv_exact(sock, 18)
            else:
                sock.close(); return None
            sock.settimeout(None)
            return sock
        except Exception as e:
            LOGGER.error(f"Bridge upstream erro: {e}")
            sock.close(); return None

    @staticmethod
    def _relay(client, upstream):
        def _forward(src, dst):
            try:
                while True:
                    data = src.recv(65536)
                    if not data: break
                    dst.sendall(data)
            except Exception:
                pass
            finally:
                try: dst.shutdown(_socket_module.SHUT_WR)
                except Exception: pass
        t = threading.Thread(target=_forward, args=(upstream, client), daemon=True)
        t.start()
        _forward(client, upstream)
        t.join(timeout=120)

    def stop(self):
        try:
            if self.server:
                self.server.shutdown()
                self.server = None
        except Exception: pass


def _start_socks5_bridge(proxy_url: str) -> Optional[str]:
    parsed = _urlparse(proxy_url)
    if parsed.scheme.lower() not in ("socks5", "socks4", "socks"):
        return proxy_url
    bridge = _ChromeSOCKS5Bridge(
        parsed.hostname, parsed.port or 1080,
        parsed.username or "", parsed.password or ""
    )
    port = bridge.start()
    if port:
        return f"http://127.0.0.1:{port}", bridge
    return None, None


# ── Login automático (portado do desktop) ─────────────────────────────────────

def _wait_for_cloudflare(driver, timeout=20):
    from selenium.common.exceptions import NoSuchWindowException, WebDriverException
    indicators = ['just a moment', 'um momento', 'checking your browser',
                  'cf-browser-verification', 'turnstile', 'challenge-running']
    for _ in range(timeout):
        time.sleep(1)
        try:
            src = driver.page_source.lower()
            if not any(i in src for i in indicators):
                return True
        except (NoSuchWindowException, WebDriverException):
            return False
    return False


def _google_oauth_login(driver, email, password):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    try:
        LOGGER.info("Executando Google OAuth login...")
        email_field = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@type='email']"))
        )
        email_field.click()
        email_field.clear()
        for c in email:
            email_field.send_keys(c)
            time.sleep(0.05)
        email_field.send_keys(Keys.RETURN)
        time.sleep(1.5)
        pwd_field = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@type='password']"))
        )
        pwd_field.click()
        time.sleep(0.2)
        pwd_field.clear()
        for c in password:
            pwd_field.send_keys(c)
            time.sleep(0.05)
        pwd_field.send_keys(Keys.RETURN)
        time.sleep(3)
        LOGGER.info("Google OAuth login executado")
        return True
    except Exception as e:
        LOGGER.error(f"Erro no Google OAuth login: {e}")
        return False


def _auto_login(driver, target_url, email, password):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    try:
        current_url = driver.current_url
        LOGGER.info(f"Login automático — URL atual: {current_url}")

        if "accounts.google.com" in current_url:
            return _google_oauth_login(driver, email, password)

        # Procurar botão de login
        login_selectors = [
            "//a[contains(text(), 'Login') or contains(text(), 'Sign in') or contains(text(), 'Entrar')]",
            "//button[contains(text(), 'Login') or contains(text(), 'Sign in') or contains(text(), 'Entrar')]",
            "//a[contains(@href, 'login') or contains(@href, 'signin')]",
        ]
        for sel in login_selectors:
            try:
                btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, sel)))
                btn.click()
                time.sleep(2)
                break
            except Exception:
                continue

        time.sleep(2)
        if "accounts.google.com" in driver.current_url:
            return _google_oauth_login(driver, email, password)

        # Login direto
        from selenium.webdriver.common.keys import Keys
        time.sleep(4)
        email_field = None
        for sel in ["//input[@type='email']", "//input[@name='email']", "//input[@id='email']"]:
            try:
                email_field = WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.XPATH, sel)))
                break
            except Exception:
                continue
        if not email_field:
            LOGGER.warning("Campo email não encontrado")
            return False
        email_field.clear()
        for c in email:
            email_field.send_keys(c)
            time.sleep(0.05)

        pwd_field = None
        for sel in ["//input[@type='password']", "//input[@name='password']"]:
            try:
                pwd_field = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, sel)))
                break
            except Exception:
                continue
        if not pwd_field:
            LOGGER.warning("Campo senha não encontrado")
            return False
        pwd_field.clear()
        for c in password:
            pwd_field.send_keys(c)
            time.sleep(0.05)
        pwd_field.send_keys(Keys.RETURN)
        time.sleep(3)
        return True
    except Exception as e:
        LOGGER.error(f"Erro no login automático: {e}")
        return False


# ── Abertura do Chrome ────────────────────────────────────────────────────────

def _open_tool_background(job_id: str, user_id: str, tool_id: str):
    LOGGER.info(f"[Worker] Iniciando job {job_id} | tool={tool_id}")
    bridge = None
    try:
        import undetected_chromedriver as uc
        from crud.crud_manager import crud_system

        ia = crud_system.ai_tools.get_by_id_with_relationships(
            tool_id, "direct_credentials", "proxy"
        )
        if not ia:
            LOGGER.error(f"[Worker] Ferramenta {tool_id} não encontrada")
            return

        LOGGER.info(f"[Worker] Abrindo: {ia.name} | {ia.url}")

        login_method = ia.get_active_login_method() if hasattr(ia, "get_active_login_method") else "manual"
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
                    LOGGER.info(f"[Worker] {len(cookies_data or [])} cookies")
            except Exception as e:
                LOGGER.warning(f"[Worker] Cookies erro: {e}")

        # Proxy
        proxy_obj = getattr(ia, "proxy", None)
        effective_proxy = None
        if proxy_obj and getattr(proxy_obj, "id", None):
            try:
                scheme = getattr(proxy_obj, "proxy_type", "http").lower()
                host, port = proxy_obj.host, proxy_obj.port
                u = getattr(proxy_obj, "username", "") or ""
                p = getattr(proxy_obj, "password", "") or ""
                proxy_url = f"{scheme}://{u}:{p}@{host}:{port}" if (u and p) else f"{scheme}://{host}:{port}"
                LOGGER.info(f"[Worker] Proxy: {host}:{port} ({scheme}) auth={bool(u)}")

                if scheme in ("socks5", "socks4", "socks"):
                    effective_proxy, bridge = _start_socks5_bridge(proxy_url)
                    if effective_proxy:
                        LOGGER.info(f"[Worker] Bridge ativa: {effective_proxy}")
                    else:
                        LOGGER.warning("[Worker] Bridge falhou — abrindo sem proxy")
                else:
                    effective_proxy = proxy_url
            except Exception as e:
                LOGGER.warning(f"[Worker] Proxy erro: {e}")

        # Opções Chrome
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--lang=pt-BR")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument(f"--display={os.environ.get('DISPLAY', ':99')}")

        # Perfil isolado por tool_id
        import tempfile
        profile_dir = os.path.join(tempfile.gettempdir(), f"nuvion_uc_{tool_id}")
        os.makedirs(profile_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir}")

        if effective_proxy:
            options.add_argument(f"--proxy-server={effective_proxy}")
            options.add_argument("--ignore-certificate-errors")
            LOGGER.info(f"[Worker] Chrome proxy: {effective_proxy}")

        driver = uc.Chrome(options=options, headless=False)
        driver.get(ia.url)

        _wait_for_cloudflare(driver)

        if cookies_data:
            LOGGER.info("[Worker] Injetando cookies...")
            driver.delete_all_cookies()
            for cookie in (cookies_data if isinstance(cookies_data, list) else []):
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    pass
            driver.get(ia.url)

        elif email and password:
            LOGGER.info("[Worker] Executando login automático...")
            _auto_login(driver, ia.url, email, password)

        LOGGER.info(f"[Worker] ✅ CLAUDE DIVISIONS {ia.name} aberto com sucesso!")

    except Exception as e:
        import traceback
        LOGGER.error(f"[Worker] Erro no job {job_id}: {e}\n{traceback.format_exc()}")


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