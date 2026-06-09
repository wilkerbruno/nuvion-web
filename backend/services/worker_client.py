# backend/services/worker_client.py
"""
Envia jobs para:
1. Extensão Chrome do usuário (se conectada) — abre janela local, sem VNC
2. Worker HTTP (container com Chrome headless + VNC) — fallback
"""
import logging
import uuid
from typing import Optional

import requests

LOGGER = logging.getLogger("NuvionBrowser")

WORKER_URL = None

def _get_worker_url():
    global WORKER_URL
    if WORKER_URL is None:
        try:
            from core.config import settings
            WORKER_URL = getattr(settings, "WORKER_URL", "http://nuvion_worker:8001")
        except Exception:
            WORKER_URL = "http://nuvion_worker:8001"
    return WORKER_URL


def _build_job_data(tool_id: str, user_id: str, job_id: str, tool=None, 
                     creds=None, cookies=None, proxy=None) -> dict:
    """Monta o payload do job com todas as informações necessárias."""
    data = {
        "job_id": job_id,
        "tool_id": tool_id,
        "user_id": user_id,
        "url": getattr(tool, "url", ""),
        "login_method": "manual",
        "email": None,
        "password": None,
        "cookies": None,
        "proxy": None,
    }

    if tool and hasattr(tool, "get_active_login_method"):
        data["login_method"] = tool.get_active_login_method()

    if creds:
        data["email"] = getattr(creds, "username", None)
        data["password"] = getattr(creds, "password", None)

    if cookies:
        data["cookies"] = cookies

    if proxy:
        data["proxy"] = {
            "host": getattr(proxy, "host", ""),
            "port": getattr(proxy, "port", 1080),
            "type": getattr(proxy, "proxy_type", "socks5").lower(),
            "username": getattr(proxy, "username", "") or "",
            "password": getattr(proxy, "password", "") or "",
        }

    return data


async def send_job_to_extension(user_id: str, job_data: dict) -> bool:
    """Tenta enviar job para a extensão Chrome do usuário."""
    try:
        from api.routes.extension import send_open_tool, is_extension_connected
        if not is_extension_connected(user_id):
            return False
        return await send_open_tool(user_id, job_data)
    except Exception as e:
        LOGGER.warning(f"[WorkerClient] Extensão indisponível: {e}")
        return False


def send_job_to_worker(job_id: str, user_id: str, tool_id: str) -> bool:
    """Envia job para o worker HTTP (VNC fallback)."""
    url = _get_worker_url()
    try:
        resp = requests.post(
            f"{url}/open-tool",
            json={"job_id": job_id, "user_id": user_id, "tool_id": tool_id},
            timeout=10,
        )
        if resp.status_code == 200:
            LOGGER.info(f"[WorkerClient] Job enviado ao worker HTTP: {job_id}")
            return True
    except Exception as e:
        LOGGER.warning(f"[WorkerClient] Falha no worker HTTP: {e}")
    return False


async def dispatch_job(tool_id: str, user_id: str, tool=None,
                        creds=None, cookies=None, proxy=None) -> dict:
    """
    Despacha job para extensão (preferencial) ou worker VNC (fallback).
    Retorna {"job_id": str, "method": "extension"|"worker"|"unavailable"}.
    """
    job_id = str(uuid.uuid4())

    # Tentar extensão primeiro
    try:
        job_data = _build_job_data(tool_id, user_id, job_id, tool, creds, cookies, proxy)
        sent = await send_job_to_extension(user_id, job_data)
        if sent:
            LOGGER.info(f"[WorkerClient] Job {job_id} → extensão Chrome")
            return {"job_id": job_id, "method": "extension"}
    except Exception as e:
        LOGGER.warning(f"[WorkerClient] Extensão falhou: {e}")

    # Fallback: worker VNC
    sent = send_job_to_worker(job_id, user_id, tool_id)
    if sent:
        return {"job_id": job_id, "method": "worker"}

    LOGGER.error(f"[WorkerClient] Nenhum destino disponível para job {job_id}")
    return {"job_id": job_id, "method": "unavailable"}