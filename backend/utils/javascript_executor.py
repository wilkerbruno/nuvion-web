"""
Executor de JavaScript com Callbacks Sincronizados
Resolve problema de callbacks assíncronos que não aguardam resultado real
"""

import time
import asyncio
from typing import Optional, Any, Callable, Dict
from PyQt6.QtCore import QTimer, QEventLoop
from PyQt6.QtWebEngineWidgets import QWebEngineView

from utils.auto_login_logger import AUTO_LOGIN_LOGGER


class JavaScriptExecutor:
    """Executor de JavaScript com sincronização adequada"""
    
    def __init__(self, browser: QWebEngineView):
        self.browser = browser
        self.execution_results = {}
        self.execution_counter = 0
    
    def execute_with_promise(self, script: str, timeout: int = 30000):
        """
        Executa JavaScript e aguarda resultado real usando promessas
        
        Args:
            script: Script JavaScript a executar
            timeout: Timeout em milissegundos
            
        Returns:
            Tupla (sucesso, resultado)
        """
        execution_id = self.execution_counter
        self.execution_counter += 1
        
        AUTO_LOGIN_LOGGER.debug(f"Executando JavaScript #{execution_id}")
        AUTO_LOGIN_LOGGER.debug(f"Script: {script[:200]}..." if len(script) > 200 else f"Script: {script}")
        
        # Container para resultado
        result_container = {
            'completed': False,
            'success': False,
            'result': None,
            'error': None,
            'start_time': time.time()
        }
        
        # Callback que será chamado quando JavaScript terminar
        def on_result(js_result):
            AUTO_LOGIN_LOGGER.debug(f"Callback recebido para execução #{execution_id}")
            AUTO_LOGIN_LOGGER.debug(f"Resultado: {js_result}")
            
            result_container['completed'] = True
            result_container['result'] = js_result
            
            # Analisar resultado
            if js_result is None:
                result_container['success'] = False
                result_container['error'] = "Resultado é None"
            elif isinstance(js_result, dict):
                result_container['success'] = js_result.get('success', False)
                if not result_container['success']:
                    result_container['error'] = js_result.get('message', 'Erro desconhecido')
            else:
                result_container['success'] = True
            
            duration = time.time() - result_container['start_time']
            AUTO_LOGIN_LOGGER.log_timing(f"Execução JavaScript #{execution_id}", duration)
        
        # Executar JavaScript
        try:
            self.browser.page().runJavaScript(script, on_result)
        except Exception as e:
            AUTO_LOGIN_LOGGER.error(f"Erro ao executar JavaScript: {e}")
            return False, None
        
        # Aguardar conclusão com timeout
        start_wait = time.time()
        timeout_seconds = timeout / 1000.0
        
        while not result_container['completed']:
            # Processar eventos Qt para permitir callbacks
            QEventLoop().processEvents()
            
            # Pequeno sleep para não sobrecarregar CPU
            time.sleep(0.05)
            
            # Verificar timeout
            if time.time() - start_wait > timeout_seconds:
                AUTO_LOGIN_LOGGER.error(f"Timeout na execução JavaScript #{execution_id}")
                return False, {"error": "timeout", "message": "Execução excedeu tempo limite"}
        
        # Retornar resultado
        AUTO_LOGIN_LOGGER.info(f"Execução JavaScript #{execution_id} concluída: "
                              f"{'SUCESSO' if result_container['success'] else 'FALHA'}")
        
        return result_container['success'], result_container['result']
    
    def execute_async_with_callback(self, script: str, callback: Callable[[Any], None]):
        """
        Executa JavaScript de forma assíncrona com callback personalizado
        
        Args:
            script: Script JavaScript
            callback: Função a ser chamada com resultado
        """
        AUTO_LOGIN_LOGGER.debug("Executando JavaScript assíncrono com callback")
        
        def internal_callback(result):
            AUTO_LOGIN_LOGGER.debug(f"Callback assíncrono recebido: {result}")
            try:
                callback(result)
            except Exception as e:
                AUTO_LOGIN_LOGGER.error(f"Erro no callback customizado: {e}")
        
        try:
            self.browser.page().runJavaScript(script, internal_callback)
        except Exception as e:
            AUTO_LOGIN_LOGGER.error(f"Erro ao executar JavaScript assíncrono: {e}")
    
    def execute_with_retry(self, script: str, max_attempts: int = 3, 
                          retry_delay: int = 2000):
        """
        Executa JavaScript com retry automático
        
        Args:
            script: Script JavaScript
            max_attempts: Número máximo de tentativas
            retry_delay: Delay entre tentativas em milissegundos
            
        Returns:
            Tupla (sucesso, resultado)
        """
        AUTO_LOGIN_LOGGER.info(f"Executando JavaScript com retry (max {max_attempts} tentativas)")
        
        for attempt in range(1, max_attempts + 1):
            AUTO_LOGIN_LOGGER.log_retry_attempt(attempt, max_attempts, "Executando script")
            
            success, result = self.execute_with_promise(script)
            
            if success:
                AUTO_LOGIN_LOGGER.info(f"JavaScript executado com sucesso na tentativa {attempt}")
                return True, result
            
            if attempt < max_attempts:
                AUTO_LOGIN_LOGGER.warning(f"Tentativa {attempt} falhou, aguardando {retry_delay}ms...")
                time.sleep(retry_delay / 1000.0)
        
        AUTO_LOGIN_LOGGER.error(f"JavaScript falhou após {max_attempts} tentativas")
        return False, result


class PromiseBasedExecutor:
    """Executor baseado em promessas JavaScript para máxima confiabilidade"""
    
    def __init__(self, browser: QWebEngineView):
        self.browser = browser
        self.executor = JavaScriptExecutor(browser)
    
    def wrap_script_in_promise(self, script: str) -> str:
        """
        Envolve script em Promise para garantir resultado assíncrono
        
        Args:
            script: Script JavaScript original
            
        Returns:
            Script envolvido em Promise
        """
        wrapped_script = f"""
        (async function() {{
            try {{
                console.log('🚀 Iniciando execução do script...');
                
                // Executar script original
                const result = await (async function() {{
                    {script}
                }})();
                
                console.log('✅ Script executado, retornando resultado:', result);
                return result;
                
            }} catch (error) {{
                console.error('❌ Erro na execução do script:', error);
                return {{
                    success: false,
                    step: 'execution_error',
                    message: error.toString(),
                    error: error.stack || error.toString()
                }};
            }}
        }})();
        """
        
        return wrapped_script
    
    def execute_with_verification(self, script: str, 
                                  verification_script: Optional[str] = None,
                                  timeout: int = 30000):
        """
        Executa script e verifica resultado com script adicional
        
        Args:
            script: Script principal
            verification_script: Script de verificação (opcional)
            timeout: Timeout em milissegundos
            
        Returns:
            Tupla (sucesso, resultado)
        """
        AUTO_LOGIN_LOGGER.info("Executando JavaScript com verificação")
        
        # Executar script principal
        wrapped_script = self.wrap_script_in_promise(script)
        success, result = self.executor.execute_with_promise(wrapped_script, timeout)
        
        if not success:
            AUTO_LOGIN_LOGGER.error("Script principal falhou")
            return False, result
        
        # Se há script de verificação, executar
        if verification_script:
            AUTO_LOGIN_LOGGER.debug("Executando script de verificação...")
            time.sleep(1.0)  # Aguardar 1 segundo antes de verificar
            
            verify_success, verify_result = self.executor.execute_with_promise(
                verification_script, 
                timeout=10000
            )
            
            if verify_success:
                AUTO_LOGIN_LOGGER.info("Verificação bem-sucedida")
                # Combinar resultados
                if isinstance(result, dict):
                    result['verified'] = True
                    result['verification_result'] = verify_result
            else:
                AUTO_LOGIN_LOGGER.warning("Verificação falhou")
                if isinstance(result, dict):
                    result['verified'] = False
        
        return success, result


# Testes unitários
if __name__ == "__main__":
    print("=== TESTES DO JAVASCRIPT EXECUTOR ===")
    print("Nota: Testes completos requerem um QWebEngineView ativo")
    print("Execute os testes de integração para validação completa")
    print("✅ Módulo carregado com sucesso")