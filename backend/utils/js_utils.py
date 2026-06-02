# utils/js_utils.py
"""
Utilitários para carregar arquivos JavaScript
"""
from utils.platform_utils import path_resolver
from utils.logger import LOGGER

def load_javascript(filename: str) -> str:
    """
    Carrega arquivo JavaScript
    
    Args:
        filename: Nome do arquivo (ex: 'smart_selector_engine.js')
    
    Returns:
        Conteúdo do arquivo JavaScript
    """
    try:
        js_content = path_resolver.read_text(f'assets/js/{filename}')
        LOGGER.info(f"JavaScript carregado: {filename}")
        return js_content
    except FileNotFoundError as e:
        LOGGER.error(f"JavaScript não encontrado: {filename}")
        LOGGER.error(str(e))
        raise
    except Exception as e:
        LOGGER.error(f"Erro ao carregar {filename}: {e}")
        raise

def get_smart_selector_engine() -> str:
    """Carrega smart selector engine"""
    return load_javascript('smart_selector_engine.js')

def get_cookie_injector() -> str:
    """Carrega cookie injector"""
    return load_javascript('cookie_injector.js')

def get_automation_bypass() -> str:
    """Carrega automation bypass"""
    return load_javascript('automation_bypass.js')
