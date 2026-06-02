# utils/json_utils.py
"""
Utilitários para carregar arquivos JSON
"""
import json
from utils.platform_utils import path_resolver
from utils.logger import LOGGER

def load_json_file(relative_path: str) -> dict:
    """
    Carrega arquivo JSON
    
    Args:
        relative_path: Path relativo (ex: 'config/translations.json')
    
    Returns:
        Dicionário com o conteúdo do JSON
    """
    try:
        content = path_resolver.read_text(relative_path)
        data = json.loads(content)
        LOGGER.info(f"JSON carregado: {relative_path}")
        return data
    except FileNotFoundError:
        LOGGER.error(f"JSON não encontrado: {relative_path}")
        return {}
    except json.JSONDecodeError as e:
        LOGGER.error(f"Erro ao parsear JSON {relative_path}: {e}")
        return {}
    except Exception as e:
        LOGGER.error(f"Erro ao carregar JSON {relative_path}: {e}")
        return {}

def load_translations() -> dict:
    """Carrega arquivo de traduções"""
    return load_json_file('config/translations.json')

def load_language_names() -> dict:
    """Carrega nomes de idiomas"""
    return load_json_file('config/language_names.json')
