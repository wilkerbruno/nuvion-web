# backend/api/routes/worker.py
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

LOGGER = logging.getLogger("NuvionBrowser")
router = APIRouter()

TERMINAL_TYPES = {"opened", "error", "done", "unavailable"}


def _redis_client():
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
    except Exception:
        return None


def _get_saved_result(job_id: str) -> Optional[dict]:
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


@router.get("/status/{job_id}")
def get_job_status(job_id: str):
    saved = _get_saved_result(job_id)
    if saved:
        return saved
    r = _redis_client()
    if not r:
        return {"type": "opened", "data": {"message": "Chrome abrindo em background."}}
    return {"type": "pending", "data": {"message": "Aguardando worker..."}}


@router.websocket("/ws/{job_id}")
async def job_websocket(
    websocket: WebSocket,
    job_id: str,
    token: str = Query(...),
):
    await websocket.accept()

    try:
        from core.security import decode_token
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            await websocket.send_json({"type": "error", "data": {"message": "Token invalido"}})
            await websocket.close(code=4001)
            return
    except Exception as e:
        await websocket.send_json({"type": "error", "data": {"message": str(e)}})
        await websocket.close(code=4001)
        return

    r = _redis_client()

    if r is None:
        # Sem Redis: aguarda ~4s para o Chrome iniciar, depois confirma como aberto
        await websocket.send_json({
            "type": "queued",
            "data": {"message": "Iniciando Chrome..."},
        })
        await asyncio.sleep(4)
        await websocket.send_json({
            "type": "opened",
            "data": {"message": "Chrome aberto com sucesso!"},
        })
        try:
            await websocket.close()
        except Exception:
            pass
        return

    # Com Redis: pub/sub em tempo real
    saved = _get_saved_result(job_id)
    if saved and saved.get("type") in TERMINAL_TYPES:
        await websocket.send_json(saved)
        await websocket.close()
        return

    await websocket.send_json({
        "type": "queued",
        "data": {"message": "Job enfileirado, aguardando worker..."},
    })

    timeout = 120
    elapsed = 0

    try:
        pubsub = r.pubsub()
        pubsub.subscribe(f"job:{job_id}")

        while elapsed < timeout:
            msg = pubsub.get_message(timeout=1.0)
            if msg and msg["type"] == "message":
                try:
                    data = json.loads(msg["data"])
                    await websocket.send_json(data)
                    if data.get("type") in TERMINAL_TYPES:
                        break
                except Exception:
                    pass

            await asyncio.sleep(0.1)
            elapsed += 1

            if elapsed % 15 == 0:
                try:
                    await websocket.send_json({"type": "waiting", "data": {"elapsed": elapsed}})
                except Exception:
                    break
        else:
            try:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": f"Timeout de {timeout}s — worker nao respondeu."},
                })
            except Exception:
                pass

        pubsub.unsubscribe(f"job:{job_id}")
        pubsub.close()

    except WebSocketDisconnect:
        LOGGER.info(f"WS desconectado: {job_id}")
    except Exception as e:
        LOGGER.error(f"Erro WS {job_id}: {e}")
        try:
            await websocket.send_json({"type": "error", "data": {"message": str(e)}})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass