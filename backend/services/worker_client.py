# backend/services/worker_client.py
"""
Cliente do worker Celery para o backend web.
Enfileira jobs de abertura de ferramentas no Chrome.
"""
import uuid
from utils.logger import LOGGER


class WorkerClient:
    """Enfileira jobs no worker Chrome via Celery."""

    def enqueue_open_tool(self, user_id: str, tool_id: str) -> str:
        """
        Enfileira a abertura de uma ferramenta no Chrome worker.

        Returns:
            job_id (UUID) para acompanhar via WebSocket.
        """
        job_id = str(uuid.uuid4())
        try:
            from core.config import settings
            from workers.chrome_worker import open_tool_task

            open_tool_task.apply_async(
                kwargs={
                    "job_id": job_id,
                    "user_id": user_id,
                    "tool_id": tool_id,
                },
                task_id=job_id,
            )
            LOGGER.info(f"Job enfileirado: {job_id} | tool={tool_id} | user={user_id}")
        except Exception as e:
            # Worker pode não estar disponível (ex: dev local sem Redis).
            # Retorna o job_id mesmo assim; o frontend receberá timeout no WS.
            LOGGER.warning(f"Falha ao enfileirar job {job_id}: {e}")

        return job_id


worker_client = WorkerClient()