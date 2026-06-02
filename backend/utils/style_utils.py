# utils/style_utils.py
"""
Utilitários para carregar estilos CSS
"""
from utils.platform_utils import path_resolver
from utils.logger import LOGGER

_stylesheet_cache = {}

def load_stylesheet(css_filename: str) -> str:
    """
    Carrega arquivo CSS
    
    Args:
        css_filename: Nome do arquivo CSS (ex: 'login.css')
    
    Returns:
        Conteúdo do CSS como string
    """
    if css_filename in _stylesheet_cache:
        return _stylesheet_cache[css_filename]
    
    try:
        content = path_resolver.read_text(f'assets/css/{css_filename}')
        _stylesheet_cache[css_filename] = content
        LOGGER.info(f"Stylesheet carregado: {css_filename}")
        return content
    except FileNotFoundError:
        LOGGER.error(f"Stylesheet não encontrado: {css_filename}")
        return ""
    except Exception as e:
        LOGGER.error(f"Erro ao carregar stylesheet {css_filename}: {e}")
        return ""

def preload_common_stylesheets():
    """Pré-carrega stylesheets comuns"""
    common_styles = [
        'login.css',
        'styles.css', 
        'dashboard.css',
        'settings.css',
    ]
    
    for style in common_styles:
        try:
            load_stylesheet(style)
        except:
            pass
