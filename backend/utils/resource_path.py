# utils/resource_path.py
"""
Sistema de paths que funciona tanto em desenvolvimento quanto como executável
"""
import os
import sys
from pathlib import Path

def get_base_path():
    """
    Retorna o diretório base do projeto
    Funciona tanto em desenvolvimento quanto empacotado
    """
    if getattr(sys, 'frozen', False):
        # Rodando como executável (PyInstaller)
        # sys._MEIPASS é o diretório temporário onde PyInstaller extrai os arquivos
        return Path(sys._MEIPASS)
    else:
        # Rodando em desenvolvimento
        # Subir dois níveis de utils/resource_path.py para chegar na raiz
        return Path(__file__).parent.parent

def get_asset_path(relative_path):
    """
    Retorna o path completo para um asset
    
    Args:
        relative_path: Path relativo a partir da raiz do projeto
                      Ex: 'assets/js/smart_selector_engine.js'
    
    Returns:
        Path absoluto para o arquivo
    """
    base = get_base_path()
    full_path = base / relative_path
    
    if not full_path.exists():
        raise FileNotFoundError(
            f"Asset não encontrado: {relative_path}\n"
            f"Path completo: {full_path}\n"
            f"Base path: {base}"
        )
    
    return full_path

def read_asset_file(relative_path, encoding='utf-8'):
    """
    Lê um arquivo de asset
    
    Args:
        relative_path: Path relativo ao diretório do projeto
        encoding: Encoding do arquivo (default: utf-8)
    
    Returns:
        Conteúdo do arquivo como string
    """
    file_path = get_asset_path(relative_path)
    with open(file_path, 'r', encoding=encoding) as f:
        return f.read()

def get_config_path(filename):
    """Retorna path para arquivo de configuração"""
    return get_asset_path(f'config/{filename}')

def get_css_path(filename):
    """Retorna path para arquivo CSS"""
    return get_asset_path(f'assets/css/{filename}')

def get_js_path(filename):
    """Retorna path para arquivo JavaScript"""
    return get_asset_path(f'assets/js/{filename}')

def get_icon_path(filename):
    """Retorna path para ícone"""
    return get_asset_path(f'icons/{filename}')

def get_image_path(filename):
    """Retorna path para imagem"""
    return get_asset_path(f'assets/img/{filename}')

# Para debug
if __name__ == '__main__':
    print(f"Base path: {get_base_path()}")
    print(f"Executável? {getattr(sys, 'frozen', False)}")