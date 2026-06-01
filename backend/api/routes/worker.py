# backend/api/routes/worker.py
"""
WebSocket endpoint para acompanhar status da abertura de ferramentas no Chrome.
O worker (processo separado com Selenium) publica eventos no Redis.
O WebSocket os consome e envia ao frontend em tempo real.
"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from core.security import decode_token
from core.config import settings

router = APIRouter()


@router.websocket("/ws/{job_id}")
async def job_status_ws(websocket: WebSocket, job_id: str):
    """
    Cliente conecta, recebe eventos até o job terminar ou dar timeout.
    Eventos: {"type": "queued"|"starting"|"opened"|"error"|"done", "data": {...}}
    """
    await websocket.accept()

    # Autenticar via query param token
    token = websocket.query_params.get("token")
    if not token:
        await websocket.send_json({"type": "error", "data": {"message": "Não autenticado"}})
        await websocket.close()
        return

    try:
        decode_token(token)
    except Exception:
        await websocket.send_json({"type": "error", "data": {"message": "Token inválido"}})
        await websocket.close()
        return

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"job:{job_id}")

        # Timeout de 120s
        deadline = asyncio.get_event_loop().time() + 120

        async for message in pubsub.listen():
            if asyncio.get_event_loop().time() > deadline:
                await websocket.send_json({"type": "timeout", "data": {}})
                break

            if message["type"] != "message":
                continue

            data = json.loads(message["data"])
            await websocket.send_json(data)

            # Encerrar se job finalizado
            if data.get("type") in ("opened", "error", "done"):
                break

        await pubsub.unsubscribe(f"job:{job_id}")
        await r.aclose()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "data": {"message": str(e)}})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/jobs/{job_id}")
def job_status_http(job_id: str):
    """Fallback HTTP para verificar status do job (polling)."""
    import redis
    r = redis.from_url(settings.REDIS_URL, decode_responses=True)
    raw = r.get(f"job_result:{job_id}")
    if not raw:
        return {"status": "pending"}
    return json.loads(raw)
