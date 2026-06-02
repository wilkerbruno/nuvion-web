# utils/icon_helper.py
"""
Helper para criar ícones SVG inline para a interface
"""
from PyQt6.QtCore import QByteArray, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

from utils.logger import LOGGER


def create_svg_icon(svg_content: str, size: int = 24) -> QIcon:
    """
    Cria um QIcon a partir de conteúdo SVG
    
    Args:
        svg_content: String com o conteúdo SVG
        size: Tamanho do ícone em pixels
        
    Returns:
        QIcon gerado a partir do SVG
    """
    try:
        renderer = QSvgRenderer(QByteArray(svg_content.encode()))
        pixmap = QPixmap(size, size)
        pixmap.fill(0x00000000)  # Transparente
        
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        
        return QIcon(pixmap)
    except Exception as e:
        LOGGER.error(f"Erro ao criar ícone SVG: {e}")
        return QIcon()


def get_delete_icon(color: str = "#6b7280") -> str:
    """
    Retorna SVG de ícone de exclusão (X em círculo)
    
    Args:
        color: Cor do ícone em hexadecimal
        
    Returns:
        String SVG
    """
    return f'''
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M18 6L6 18M6 6L18 18" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    '''


def get_trash_icon(color: str = "#6b7280") -> str:
    """
    Retorna SVG de ícone de lixeira
    
    Args:
        color: Cor do ícone em hexadecimal
        
    Returns:
        String SVG
    """
    return f'''
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M3 6H5H21" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M10 11V17" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M14 11V17" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    '''


def get_close_icon(color: str = "#6b7280") -> str:
    """
    Retorna SVG de ícone de fechar (X simples e profissional)
    
    Args:
        color: Cor do ícone em hexadecimal
        
    Returns:
        String SVG
    """
    return f'''
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M18 6L6 18" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M6 6L18 18" stroke="{color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    '''


def get_heart_icon(filled: bool = False, color: str = "#6b7280") -> str:
    """
    Retorna SVG de ícone de coração
    
    Args:
        filled: Se o coração deve ser preenchido
        color: Cor do ícone
        
    Returns:
        String SVG
    """
    if filled:
        return f'''
        <svg width="24" height="24" viewBox="0 0 24 24" fill="{color}" xmlns="http://www.w3.org/2000/svg">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
        </svg>
        '''
    else:
        return f'''
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        '''


def get_search_icon(color: str = "#6b7280") -> str:
    """
    Retorna SVG de ícone de busca
    
    Args:
        color: Cor do ícone em hexadecimal
        
    Returns:
        String SVG
    """
    return f'''
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="11" cy="11" r="8" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M21 21L16.65 16.65" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    '''


def get_filter_icon(color: str = "#6b7280") -> str:
    """
    Retorna SVG de ícone de filtro
    
    Args:
        color: Cor do ícone em hexadecimal
        
    Returns:
        String SVG
    """
    return f'''
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M22 3H2L10 12.46V19L14 21V12.46L22 3Z" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    '''


def get_edit_icon(color: str = "#6b7280") -> str:
    """
    Retorna SVG de ícone de edição
    
    Args:
        color: Cor do ícone em hexadecimal
        
    Returns:
        String SVG
    """
    return f'''
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M18.5 2.50001C18.8978 2.10219 19.4374 1.87869 20 1.87869C20.5626 1.87869 21.1022 2.10219 21.5 2.50001C21.8978 2.89784 22.1213 3.43741 22.1213 4.00001C22.1213 4.56262 21.8978 5.10219 21.5 5.50001L12 15L8 16L9 12L18.5 2.50001Z" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    '''


def get_plus_icon(color: str = "#6b7280") -> str:
    """
    Retorna SVG de ícone de adicionar (+)
    
    Args:
        color: Cor do ícone em hexadecimal
        
    Returns:
        String SVG
    """
    return f'''
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 5V19" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M5 12H19" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    '''