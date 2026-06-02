"""
Sistema de Logging Avançado para Auto Login
Fornece logs detalhados, estruturados e com múltiplos destinos
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import json
import traceback


class AutoLoginLogger:
    """Logger especializado para automação de login"""
    
    def __init__(self, name: str = "AutoLogin"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Remover handlers existentes para evitar duplicação
        self.logger.handlers.clear()
        
        # Diretório de logs
        self.logs_dir = self._setup_logs_directory()
        
        # Configurar handlers
        self._setup_console_handler()
        self._setup_file_handlers()
        
        # Contador de sessões
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Estatísticas
        self.stats = {
            'total_attempts': 0,
            'successful': 0,
            'failed': 0,
            'errors': 0
        }
    
    def _setup_logs_directory(self) -> Path:
        """Cria estrutura de diretórios para logs"""
        try:
            # Tentar usar diretório do usuário primeiro
            base_dir = Path.home() / ".nuvion_browser" / "logs" / "auto_login"
            base_dir.mkdir(parents=True, exist_ok=True)
            return base_dir
        except Exception:
            # Fallback para diretório local
            base_dir = Path("logs") / "auto_login"
            base_dir.mkdir(parents=True, exist_ok=True)
            return base_dir
    
    def _setup_console_handler(self):
        """Configura handler para console com formato limpo"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Formato simplificado para console
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
    
    def _setup_file_handlers(self):
        """Configura handlers para arquivos com diferentes níveis"""
        
        # Handler para log geral (INFO+)
        general_log = self.logs_dir / f"autologin_{datetime.now().strftime('%Y%m%d')}.log"
        general_handler = logging.FileHandler(general_log, encoding='utf-8')
        general_handler.setLevel(logging.INFO)
        
        # Formato detalhado para arquivo
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(funcName)-25s:%(lineno)-4d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        general_handler.setFormatter(file_formatter)
        self.logger.addHandler(general_handler)
        
        # Handler para debug detalhado (DEBUG+)
        debug_log = self.logs_dir / f"autologin_debug_{datetime.now().strftime('%Y%m%d')}.log"
        debug_handler = logging.FileHandler(debug_log, encoding='utf-8')
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(file_formatter)
        self.logger.addHandler(debug_handler)
        
        # Handler para erros (ERROR+)
        error_log = self.logs_dir / f"autologin_errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.FileHandler(error_log, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        
        # Formato ainda mais detalhado para erros
        error_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(pathname)s:%(lineno)d | %(funcName)s\n%(message)s\n',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_formatter)
        self.logger.addHandler(error_handler)
    
    # ===== MÉTODOS DE LOG BÁSICOS =====
    
    def info(self, message: str):
        """Log de informação"""
        self.logger.info(message)
    
    def debug(self, message: str):
        """Log de debug"""
        self.logger.debug(message)
    
    def warning(self, message: str):
        """Log de aviso"""
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False):
        """Log de erro"""
        self.logger.error(message, exc_info=exc_info)
        self.stats['errors'] += 1
    
    def critical(self, message: str, exc_info: bool = True):
        """Log crítico"""
        self.logger.critical(message, exc_info=exc_info)
    
    # ===== MÉTODOS ESPECIALIZADOS PARA AUTO LOGIN =====
    
    def log_attempt_start(self, ai_tool_id: str, ai_name: str, username: str, url: str):
        """Registra início de tentativa de login"""
        self.stats['total_attempts'] += 1
        
        separator = "=" * 80
        self.logger.info(separator)
        self.logger.info(f"INICIANDO TENTATIVA DE LOGIN #{self.stats['total_attempts']}")
        self.logger.info(separator)
        self.logger.info(f"IA ID      : {ai_tool_id}")
        self.logger.info(f"IA Nome    : {ai_name}")
        self.logger.info(f"Username   : {username}")
        self.logger.info(f"URL        : {url}")
        self.logger.info(f"Sessão     : {self.session_id}")
        self.logger.info(f"Timestamp  : {datetime.now().isoformat()}")
        self.logger.info(separator)
    
    def log_attempt_end(self, success: bool, method: str, message: str, duration: Optional[float] = None):
        """Registra fim de tentativa de login"""
        
        if success:
            self.stats['successful'] += 1
            status = "✅ SUCESSO"
        else:
            self.stats['failed'] += 1
            status = "❌ FALHA"
        
        separator = "=" * 80
        self.logger.info(separator)
        self.logger.info(f"RESULTADO: {status}")
        self.logger.info(f"Método     : {method}")
        self.logger.info(f"Mensagem   : {message}")
        
        if duration:
            self.logger.info(f"Duração    : {duration:.2f}s")
        
        self.logger.info(f"Estatísticas - Total: {self.stats['total_attempts']} | "
                        f"Sucesso: {self.stats['successful']} | "
                        f"Falha: {self.stats['failed']}")
        self.logger.info(separator)
        self.logger.info("")  # Linha em branco para separação
    
    def log_step(self, step_name: str, status: str = "executing", details: Optional[str] = None):
        """Registra etapa específica do processo"""
        status_symbols = {
            'executing': '⏳',
            'success': '✅',
            'failed': '❌',
            'warning': '⚠️',
            'info': 'ℹ️'
        }
        
        symbol = status_symbols.get(status, '▶️')
        message = f"{symbol} ETAPA: {step_name}"
        
        if details:
            message += f" | {details}"
        
        self.logger.info(message)
    
    def log_credentials_validation(self, username: str, password_length: int, has_special_chars: bool):
        """Registra validação de credenciais (SEM expor senha)"""
        self.logger.debug("=== VALIDAÇÃO DE CREDENCIAIS ===")
        self.logger.debug(f"Username          : {username}")
        self.logger.debug(f"Tamanho da senha  : {password_length} caracteres")
        self.logger.debug(f"Caracteres especiais: {'Sim' if has_special_chars else 'Não'}")
    
    def log_timing(self, action: str, duration: float):
        """Registra timing de ações específicas"""
        self.logger.debug(f"⏱️  TIMING: {action} levou {duration:.3f}s")
    
    def log_javascript_execution(self, script_name: str, status: str, result: Optional[Any] = None):
        """Registra execução de JavaScript"""
        self.logger.debug(f"📜 JAVASCRIPT: {script_name} - {status}")
        
        if result:
            try:
                result_str = json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                self.logger.debug(f"Resultado: {result_str}")
            except Exception:
                self.logger.debug(f"Resultado: {result}")
    
    def log_selector_attempt(self, selector: str, found: bool, element_info: Optional[str] = None):
        """Registra tentativa de seleção de elemento"""
        status = "✅ ENCONTRADO" if found else "❌ NÃO ENCONTRADO"
        self.logger.debug(f"🎯 SELETOR: {selector} - {status}")
        
        if element_info and found:
            self.logger.debug(f"   Info: {element_info}")
    
    def log_page_state(self, url: str, ready_state: str, load_time: Optional[float] = None):
        """Registra estado da página"""
        self.logger.debug(f"🌐 PÁGINA: {url}")
        self.logger.debug(f"   Estado: {ready_state}")
        
        if load_time:
            self.logger.debug(f"   Tempo de carregamento: {load_time:.2f}s")
    
    def log_exception(self, exception: Exception, context: str = ""):
        """Registra exceção com traceback completo"""
        self.logger.error(f"💥 EXCEÇÃO{' em ' + context if context else ''}")
        self.logger.error(f"Tipo: {type(exception).__name__}")
        self.logger.error(f"Mensagem: {str(exception)}")
        self.logger.error(f"Traceback:\n{traceback.format_exc()}")
    
    def log_retry_attempt(self, attempt: int, max_attempts: int, reason: str):
        """Registra tentativa de retry"""
        self.logger.warning(f"🔄 RETRY {attempt}/{max_attempts}: {reason}")
    
    def log_data_structure(self, name: str, data: Any):
        """Registra estrutura de dados complexa (para debug)"""
        try:
            if isinstance(data, (dict, list)):
                data_str = json.dumps(data, indent=2, ensure_ascii=False)
            else:
                data_str = str(data)
            
            self.logger.debug(f"📊 ESTRUTURA DE DADOS: {name}")
            self.logger.debug(data_str)
        except Exception as e:
            self.logger.debug(f"📊 ESTRUTURA DE DADOS: {name} (erro ao serializar: {e})")
    
    def log_browser_console(self, console_message: str, level: str = "info"):
        """Registra mensagens do console do navegador"""
        level_map = {
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'debug': logging.DEBUG
        }
        
        log_level = level_map.get(level.lower(), logging.INFO)
        self.logger.log(log_level, f"🖥️  CONSOLE BROWSER [{level.upper()}]: {console_message}")
    
    # ===== MÉTODOS DE RELATÓRIO =====
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas da sessão"""
        total = self.stats['total_attempts']
        success_rate = (self.stats['successful'] / total * 100) if total > 0 else 0
        
        return {
            'session_id': self.session_id,
            'total_attempts': total,
            'successful': self.stats['successful'],
            'failed': self.stats['failed'],
            'errors': self.stats['errors'],
            'success_rate': round(success_rate, 2)
        }
    
    def log_session_summary(self):
        """Registra resumo da sessão"""
        stats = self.get_statistics()
        
        separator = "=" * 80
        self.logger.info(separator)
        self.logger.info("RESUMO DA SESSÃO DE AUTO LOGIN")
        self.logger.info(separator)
        self.logger.info(f"Sessão ID        : {stats['session_id']}")
        self.logger.info(f"Total de tentativas : {stats['total_attempts']}")
        self.logger.info(f"Sucessos         : {stats['successful']}")
        self.logger.info(f"Falhas           : {stats['failed']}")
        self.logger.info(f"Erros            : {stats['errors']}")
        self.logger.info(f"Taxa de sucesso  : {stats['success_rate']}%")
        self.logger.info(separator)
    
    def get_logs_directory(self) -> Path:
        """Retorna diretório de logs"""
        return self.logs_dir


# Instância global do logger
AUTO_LOGIN_LOGGER = AutoLoginLogger()