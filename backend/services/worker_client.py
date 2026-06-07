# backend/services/worker_client.py
"""
Cliente do worker — importa WorkerClient diretamente do chrome_worker.
Se Redis nao estiver disponivel, retorna job_id sem travar a requisicao.
"""
import logging
import uuid

LOGGER = logging.getLogger("NuvionBrowser")


class WorkerClient:
    """
    Wrapper seguro em torno do WorkerClient do chrome_worker.
    Nao importa nada no nivel de modulo — so importa quando chamado,
    evitando que a API trave ao subir sem Redis disponivel.
    """

    def enqueue_open_tool(self, user_id: str, tool_id: str) -> str:
        job_id = str(uuid.uuid4())

        try:
            from workers.chrome_worker import open_tool_task
            open_tool_task.apply_async(
                kwargs={"job_id": job_id, "user_id": user_id, "tool_id": tool_id},
                task_id=job_id,
            )
            LOGGER.info(f"Job enfileirado: {job_id} | tool={tool_id} | user={user_id}")
        except Exception as e:
            LOGGER.warning(f"Falha ao enfileirar job {job_id}: {e}")

        return job_id


worker_client = WorkerClient()