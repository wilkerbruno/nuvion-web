# backend/api/routes/worker.py
"""
Rotas do worker Chrome.
- GET  /api/worker/status/{job_id}  — polling HTTP
- WS   /api/worker/ws/{job_id}      — WebSocket em tempo real

O chrome_worker.py publica eventos neste formato:
  {"type": "starting"|"opened"|"error"|"done", "data": {...}}

armazenados em:
  Redis pub/sub canal : job:{job_id}
  Redis key resultado : job_result:{job_id}
"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

LOGGER = logging.getLogger("NuvionBrowser")
router = APIRouter()

TERMINAL_TYPES = {"opened", "error", "done"}


# ---------------------------------------------------------------------------
# Helper Redis
# ---------------------------------------------------------------------------

def _redis_client():
    """Retorna cliente Redis ou None se indisponivel."""
    try:
        import redis
        from core.config import settings
        r = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        r.ping()
        return r
    except Exception as e:
        LOGGER.debug(f"Redis indisponivel: {e}")
        return None


def _get_saved_result(job_id: str) -> Optional[dict]:
    """Busca resultado salvo (para jobs ja concluidos)."""
    r = _redis_client()
    if not r:
        return None
    try:
        raw = r.get(f"job_result:{job_id}")
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# HTTP polling (fallback)
# ---------------------------------------------------------------------------

@router.get("/status/{job_id}")
def get_job_status(job_id: str):
    saved = _get_saved_result(job_id)
    if saved:
        return saved

    r = _redis_client()
    if not r:
        return {
            "type": "error",
            "data": {
                "message": (
                    "Redis nao disponivel. Configure a variavel REDIS_URL "
                    "e adicione o servico Redis no Easypanel."
                )
            },
        }
    return {"type": "pending", "data": {"message": "Aguardando worker..."}}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@router.websocket("/ws/{job_id}")
async def job_websocket(
    websocket: WebSocket,
    job_id: str,
    token: str = Query(...),
):
    """
    WebSocket que retransmite eventos do chrome_worker em tempo real.

    Formato dos eventos (espelhado do chrome_worker._publish):
      {"type": "starting"|"opened"|"error"|"done", "data": {...}}
    """
    await websocket.accept()

    # -- Validar JWT -------------------------------------------------------
    try:
        from core.security import decode_token
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            await websocket.send_json(
                {"type": "error", "data": {"message": "Token invalido"}}
            )
            await websocket.close(code=4001)
            return
    except Exception as e:
        await websocket.send_json({"type": "error", "data": {"message": str(e)}})
        await websocket.close(code=4001)
        return

    # -- Verificar Redis ---------------------------------------------------
    r = _redis_client()
    if r is None:
        await websocket.send_json({
            "type": "error",
            "data": {
                "message": (
                    "Redis nao disponivel. "
                    "Adicione o servico Redis no Easypanel e configure "
                    "REDIS_URL nos containers da API e do worker."
                )
            },
        })
        await websocket.close()
        return

    # -- Resultado ja salvo? (job concluido antes do WS conectar) ----------
    saved = _get_saved_result(job_id)
    if saved and saved.get("type") in TERMINAL_TYPES:
        await websocket.send_json(saved)
        await websocket.close()
        return

    # -- Subscribe e retransmitir eventos ----------------------------------
    await websocket.send_json({
        "type": "queued",
        "data": {"message": "Job enfileirado, aguardando worker..."},
    })

    timeout = 120  # segundos maximos de espera
    elapsed = 0

    try:
        pubsub = r.pubsub()
        pubsub.subscribe(f"job:{job_id}")

        while elapsed < timeout:
            # Checar mensagem (nao bloqueante, timeout=1s)
            msg = pubsub.get_message(timeout=1.0)
            if msg and msg["type"] == "message":
                try:
                    data = json.loads(msg["data"])
                    await websocket.send_json(data)
                    # Fechar ao receber evento terminal
                    if data.get("type") in TERMINAL_TYPES:
                        break
                except Exception:
                    pass

            await asyncio.sleep(0.1)
            elapsed += 1

            # Heartbeat a cada 15s para manter conexao viva
            if elapsed % 15 == 0:
                try:
                    await websocket.send_json(
                        {"type": "waiting", "data": {"elapsed": elapsed}}
                    )
                except Exception:
                    break
        else:
            # Timeout
            try:
                await websocket.send_json({
                    "type": "error",
                    "data": {
                        "message": f"Timeout de {timeout}s — worker nao respondeu.",
                    },
                })
            except Exception:
                pass

        pubsub.unsubscribe(f"job:{job_id}")
        pubsub.close()

    except WebSocketDisconnect:
        LOGGER.info(f"WS desconectado pelo cliente: {job_id}")
    except Exception as e:
        LOGGER.error(f"Erro no WS {job_id}: {e}")
        try:
            await websocket.send_json({"type": "error", "data": {"message": str(e)}})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass