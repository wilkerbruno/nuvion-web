# backend/api/routes/extension.py
"""
WebSocket endpoint para a extensão Chrome.
A extensão conecta aqui e recebe jobs de abertura de ferramentas.
"""
import asyncio
import json
import logging
from typing import Dict

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

LOGGER = logging.getLogger("NuvionBrowser")
router = APIRouter()

# Registry de extensões conectadas por user_id
_extensions: Dict[str, WebSocket] = {}


@router.websocket("/ws")
async def extension_ws(
    websocket: WebSocket,
    token: str = Query(...),
    client: str = Query(default="extension"),
):
    await websocket.accept()

    # Validar token
    try:
        from core.security import decode_token
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            await websocket.send_json({"type": "error", "data": {"message": "Token inválido"}})
            await websocket.close(code=4001)
            return
        user_id = payload.get("sub")
    except Exception as e:
        await websocket.send_json({"type": "error", "data": {"message": str(e)}})
        await websocket.close(code=4001)
        return

    LOGGER.info(f"[Extension] Extensão conectada: user={user_id}")
    _extensions[user_id] = websocket

    try:
        await websocket.send_json({"type": "connected", "data": {"message": "Extensão registrada"}})

        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            LOGGER.info(f"[Extension] Mensagem de {user_id}: {msg.get('type')}")

            if msg.get("type") == "pong":
                pass
            elif msg.get("type") == "extension_ready":
                LOGGER.info(f"[Extension] Extensão pronta: user={user_id}")
            elif msg.get("type") in ("opened", "error"):
                job_id = msg.get("data", {}).get("job_id")
                LOGGER.info(f"[Extension] Job {job_id}: {msg.get('type')}")

    except WebSocketDisconnect:
        LOGGER.info(f"[Extension] Extensão desconectada: user={user_id}")
    except Exception as e:
        LOGGER.error(f"[Extension] Erro: {e}")
    finally:
        _extensions.pop(user_id, None)


async def send_open_tool(user_id: str, job_data: dict) -> bool:
    """Envia job para a extensão do usuário. Retorna True se enviado."""
    ws = _extensions.get(user_id)
    if not ws:
        return False
    try:
        await ws.send_json({"type": "open_tool", "data": job_data})
        LOGGER.info(f"[Extension] Job enviado para extensão do user {user_id}")
        return True
    except Exception as e:
        LOGGER.error(f"[Extension] Erro ao enviar job: {e}")
        _extensions.pop(user_id, None)
        return False


def is_extension_connected(user_id: str) -> bool:
    return user_id in _extensions