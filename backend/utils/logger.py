# utils/logger.py
import logging
import os
import sys
from pathlib import Path


def get_logs_directory():
    """Retorna diretorio seguro para gravar logs."""
    logs_dir = Path.home() / ".nuvion_browser" / "logs"
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir
    except Exception:
        return None


def _make_console_handler() -> logging.StreamHandler:
    """
    Cria um StreamHandler para stdout com encoding UTF-8 forcado.

    No Windows com console cp1252, emojis nos logs causam UnicodeEncodeError
    que derruba o handler inteiro e propaga excecao para o chamador do LOGGER.
    Forcar UTF-8 e definir errors='replace' garante que qualquer caractere
    fora do cp1252 seja exibido como '?' em vez de lancar excecao.
    """
    try:
        # Reabrir sys.stdout com UTF-8 se possivel
        # (funciona em Python 3.7+ com io.TextIOWrapper)
        import io
        utf8_stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding="utf-8",
            errors="replace",
            line_buffering=True,
        )
        handler = logging.StreamHandler(utf8_stdout)
    except (AttributeError, Exception):
        # sys.stdout pode nao ter .buffer em alguns ambientes (ex: pytest,
        # windowed PyInstaller com sys.stdout=devnull do nosso rthook)
        # Nesse caso usar o StreamHandler padrao com errors='replace'
        handler = logging.StreamHandler(sys.stdout)
        # Substituir o metodo emit para ignorar erros de encoding
        original_emit = handler.emit

        def safe_emit(record):
            try:
                original_emit(record)
            except (UnicodeEncodeError, UnicodeDecodeError):
                try:
                    # Tentar de novo com a mensagem sanitizada
                    record.msg = record.msg.encode(
                        "ascii", errors="replace"
                    ).decode("ascii")
                    record.args = ()
                    original_emit(record)
                except Exception:
                    pass

        handler.emit = safe_emit

    return handler


def setup_logger():
    """Configura o logger raiz do Nuvion Browser."""
    handlers = [_make_console_handler()]

    logs_dir = get_logs_directory()
    if logs_dir:
        try:
            file_handler = logging.FileHandler(
                logs_dir / "browser.log",
                encoding="utf-8",   # Arquivo sempre UTF-8
            )
            handlers.append(file_handler)
        except Exception:
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s].[%(levelname)s].%(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


setup_logger()
LOGGER = logging.getLogger("NuvionBrowser")

try:
    from utils.auto_login_logger import AUTO_LOGIN_LOGGER
    from utils.debug_system import DEBUG_SYSTEM
except ImportError:
    AUTO_LOGIN_LOGGER = LOGGER
    DEBUG_SYSTEM = None