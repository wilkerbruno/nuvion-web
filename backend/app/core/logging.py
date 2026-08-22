"""Logging central do backend.

Equivalente web de utils/logger.py no projeto desktop. Lá o logger também
gravava em arquivo local; aqui só logamos para stdout/stderr, que é o padrão
esperado por qualquer plataforma de deploy (Docker, Railway, etc. coletam
os logs do processo diretamente).
"""
import logging
import sys

from app.core.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def _configure_root_logger() -> None:
    root = logging.getLogger()
    if root.handlers:
        # Já configurado (ex.: reload do uvicorn) — evita handlers duplicados
        return

    root.setLevel(settings.LOG_LEVEL)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(handler)


_configure_root_logger()

LOGGER = logging.getLogger("nuvion")
