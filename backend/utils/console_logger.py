"""
Console Logger - Captura logs do console JavaScript e exibe no terminal Python
"""

from PyQt6.QtWebEngineWidgets import QWebEngineView
from utils.logger import LOGGER


class JavaScriptConsoleLogger:
    """Captura e exibe logs do console JavaScript"""
    
    @staticmethod
    def setup_console_capture(page: QWebEngineView, browser_name: str = "Browser"):
        """
        Configura captura de console em uma página
        
        Args:
            page: QWebEnginePage onde capturar logs
            browser_name: Nome identificador do navegador (para logs)
        """
        try:
            # Conectar sinal de mensagens do console
            page.javaScriptConsoleMessage.connect(
                lambda level, message, line, source: 
                JavaScriptConsoleLogger._handle_console_message(
                    level, message, line, source, browser_name
                )
            )
            LOGGER.info(f"Captura de console JavaScript ativada para: {browser_name}")
            
        except Exception as e:
            LOGGER.error(f"Erro ao configurar captura de console: {e}")
    
    @staticmethod
    def _handle_console_message(level, message, line, source, browser_name):
        """
        Processa mensagem do console JavaScript
        
        Args:
            level: Nível da mensagem (0=Info, 1=Warning, 2=Error)
            message: Conteúdo da mensagem
            line: Linha do código
            source: Arquivo fonte
            browser_name: Nome do navegador
        """
        # Formatar nome do arquivo fonte
        source_file = source.split('/')[-1] if source else 'inline'
        
        # Prefixo com nome do navegador
        prefix = f"[JS:{browser_name}]"
        
        # Formatar mensagem completa
        location_info = ""
        if source_file != 'inline' or line > 0:
            location_info = f" ({source_file}:{line})" if line > 0 else f" ({source_file})"
        
        full_message = f"{prefix} {message}{location_info}"
        
        # Log baseado no nível
        if level == 0:  # Info / Log
            LOGGER.info(f"{full_message}")
        elif level == 1:  # Warning
            LOGGER.warning(f"{full_message}")
        elif level == 2:  # Error
            LOGGER.error(f"{full_message}")
        else:
            LOGGER.debug(f"{full_message}")


# Funções de conveniência
def enable_console_logging(page: QWebEngineView, browser_name: str = "Browser"):
    """
    Ativa captura de logs do console para uma página
    
    Args:
        page: QWebEnginePage
        browser_name: Nome do navegador (aparece nos logs)
    """
    JavaScriptConsoleLogger.setup_console_capture(page, browser_name)


def enable_console_logging_for_browser(browser, browser_name: str = "Browser"):
    """
    Ativa captura de logs para um QWebEngineView
    
    Args:
        browser: QWebEngineView
        browser_name: Nome do navegador (aparece nos logs)
    """
    try:
        page = browser.page()
        if page:
            JavaScriptConsoleLogger.setup_console_capture(page, browser_name)
            return True
        return False
    except Exception as e:
        LOGGER.error(f"Erro ao habilitar console logging: {e}")
        return False
