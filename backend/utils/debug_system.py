"""
Sistema de Debug Avançado para Auto Login
Captura screenshots, HTML, estado da página e dados para análise
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, QTimer
from PyQt6.QtGui import QImage
from PyQt6.QtWebEngineWidgets import QWebEngineView

from utils.auto_login_logger import AUTO_LOGIN_LOGGER


class DebugSystem:
    """Sistema de debug com captura de screenshots e dados"""
    
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.debug_dir = self._setup_debug_directory()
        self.current_session = None
        self.debug_data = {}
    
    def _setup_debug_directory(self) -> Path:
        """Cria estrutura de diretórios para debug"""
        try:
            # Usar mesmo diretório base dos logs
            base_dir = Path.home() / ".nuvion_browser" / "debug" / "auto_login"
            base_dir.mkdir(parents=True, exist_ok=True)
            return base_dir
        except Exception:
            # Fallback
            base_dir = Path("debug") / "auto_login"
            base_dir.mkdir(parents=True, exist_ok=True)
            return base_dir
    
    def enable(self):
        """Ativa modo debug"""
        self.enabled = True
        AUTO_LOGIN_LOGGER.info("🐛 MODO DEBUG ATIVADO")
    
    def disable(self):
        """Desativa modo debug"""
        self.enabled = False
        AUTO_LOGIN_LOGGER.info("🐛 MODO DEBUG DESATIVADO")
    
    def is_enabled(self) -> bool:
        """Verifica se debug está ativo"""
        return self.enabled
    
    def start_session(self, ai_tool_id: str, ai_name: str):
        """Inicia nova sessão de debug"""
        if not self.enabled:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"{ai_name.replace(' ', '_')}_{timestamp}"
        
        # Criar diretório para esta sessão
        session_dir = self.debug_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_session = {
            'id': session_id,
            'ai_tool_id': ai_tool_id,
            'ai_name': ai_name,
            'start_time': datetime.now().isoformat(),
            'dir': session_dir,
            'screenshots': [],
            'html_dumps': [],
            'selectors_tested': [],
            'javascript_results': [],
            'errors': []
        }
        
        self.debug_data[session_id] = self.current_session
        
        AUTO_LOGIN_LOGGER.debug(f"🐛 Sessão de debug iniciada: {session_id}")
        AUTO_LOGIN_LOGGER.debug(f"   Diretório: {session_dir}")
    
    def end_session(self, success: bool, message: str):
        """Finaliza sessão de debug"""
        if not self.enabled or not self.current_session:
            return
        
        self.current_session['end_time'] = datetime.now().isoformat()
        self.current_session['success'] = success
        self.current_session['message'] = message
        
        # Salvar relatório da sessão
        self._save_session_report()
        
        AUTO_LOGIN_LOGGER.debug(f"🐛 Sessão de debug finalizada: {self.current_session['id']}")
        
        self.current_session = None
    
    def capture_screenshot(self, browser: QWebEngineView, stage: str, description: str = ""):
        """Captura screenshot do navegador"""
        if not self.enabled or not self.current_session:
            return
        
        try:
            # Criar callback para quando screenshot estiver pronto
            def on_screenshot_ready(image: QImage):
                if image.isNull():
                    AUTO_LOGIN_LOGGER.warning(f"Screenshot vazio para stage: {stage}")
                    return
                
                # Salvar imagem
                timestamp = datetime.now().strftime("%H%M%S")
                filename = f"screenshot_{len(self.current_session['screenshots']):02d}_{stage}_{timestamp}.png"
                filepath = self.current_session['dir'] / filename
                
                if image.save(str(filepath)):
                    screenshot_info = {
                        'stage': stage,
                        'description': description,
                        'filename': filename,
                        'timestamp': datetime.now().isoformat(),
                        'size': f"{image.width()}x{image.height()}"
                    }
                    
                    self.current_session['screenshots'].append(screenshot_info)
                    AUTO_LOGIN_LOGGER.debug(f"📸 Screenshot capturado: {filename} ({stage})")
                else:
                    AUTO_LOGIN_LOGGER.warning(f"Falha ao salvar screenshot: {filename}")
            
            # Capturar screenshot
            browser.grab().toImage().copy()  # Força renderização
            QTimer.singleShot(100, lambda: on_screenshot_ready(browser.grab().toImage()))
            
        except Exception as e:
            AUTO_LOGIN_LOGGER.error(f"Erro ao capturar screenshot: {e}")
    
    def capture_page_html(self, browser: QWebEngineView, stage: str):
        """Captura HTML completo da página"""
        if not self.enabled or not self.current_session:
            return
        
        try:
            def on_html_ready(html: str):
                if not html:
                    AUTO_LOGIN_LOGGER.warning(f"HTML vazio para stage: {stage}")
                    return
                
                # Salvar HTML
                timestamp = datetime.now().strftime("%H%M%S")
                filename = f"html_{len(self.current_session['html_dumps']):02d}_{stage}_{timestamp}.html"
                filepath = self.current_session['dir'] / filename
                
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(html)
                    
                    html_info = {
                        'stage': stage,
                        'filename': filename,
                        'timestamp': datetime.now().isoformat(),
                        'size': len(html)
                    }
                    
                    self.current_session['html_dumps'].append(html_info)
                    AUTO_LOGIN_LOGGER.debug(f"📄 HTML capturado: {filename} ({len(html)} bytes)")
                
                except Exception as e:
                    AUTO_LOGIN_LOGGER.error(f"Erro ao salvar HTML: {e}")
            
            # Capturar HTML
            browser.page().toHtml(on_html_ready)
            
        except Exception as e:
            AUTO_LOGIN_LOGGER.error(f"Erro ao capturar HTML: {e}")
    
    def log_selector_test(self, selector: str, found: bool, element_info: Optional[Dict] = None):
        """Registra teste de seletor"""
        if not self.enabled or not self.current_session:
            return
        
        selector_data = {
            'selector': selector,
            'found': found,
            'element_info': element_info,
            'timestamp': datetime.now().isoformat()
        }
        
        self.current_session['selectors_tested'].append(selector_data)
        AUTO_LOGIN_LOGGER.debug(f"🎯 Seletor testado: {selector} - {'✅' if found else '❌'}")
    
    def log_javascript_result(self, script_name: str, result: Any, execution_time: Optional[float] = None):
        """Registra resultado de execução JavaScript"""
        if not self.enabled or not self.current_session:
            return
        
        js_data = {
            'script_name': script_name,
            'result': result,
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat()
        }
        
        self.current_session['javascript_results'].append(js_data)
        AUTO_LOGIN_LOGGER.debug(f"📜 JavaScript executado: {script_name}")
    
    def log_error(self, error_type: str, error_message: str, traceback_str: Optional[str] = None):
        """Registra erro durante automação"""
        if not self.enabled or not self.current_session:
            return
        
        error_data = {
            'type': error_type,
            'message': error_message,
            'traceback': traceback_str,
            'timestamp': datetime.now().isoformat()
        }
        
        self.current_session['errors'].append(error_data)
        AUTO_LOGIN_LOGGER.debug(f"💥 Erro registrado: {error_type}")
    
    def capture_element_info(self, browser: QWebEngineView, selector: str, stage: str):
        """Captura informações detalhadas de um elemento"""
        if not self.enabled or not self.current_session:
            return
        
        js_script = f"""
        (function() {{
            try {{
                const element = document.querySelector('{selector}');
                if (!element) return null;
                
                const rect = element.getBoundingClientRect();
                const styles = window.getComputedStyle(element);
                
                return {{
                    tagName: element.tagName,
                    id: element.id,
                    className: element.className,
                    type: element.type,
                    name: element.name,
                    value: element.value ? '***' : '',  // Não capturar valores sensíveis
                    visible: element.offsetParent !== null,
                    position: {{
                        top: rect.top,
                        left: rect.left,
                        width: rect.width,
                        height: rect.height
                    }},
                    styles: {{
                        display: styles.display,
                        visibility: styles.visibility,
                        opacity: styles.opacity
                    }},
                    disabled: element.disabled,
                    readonly: element.readOnly
                }};
            }} catch(e) {{
                return {{ error: e.toString() }};
            }}
        }})();
        """
        
        def on_element_info(info):
            if info:
                self.log_selector_test(selector, True, info)
                
                # Salvar em arquivo JSON separado
                timestamp = datetime.now().strftime("%H%M%S")
                filename = f"element_{stage}_{timestamp}.json"
                filepath = self.current_session['dir'] / filename
                
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(info, f, indent=2)
                    AUTO_LOGIN_LOGGER.debug(f"🔍 Info do elemento salva: {filename}")
                except Exception as e:
                    AUTO_LOGIN_LOGGER.error(f"Erro ao salvar info do elemento: {e}")
            else:
                self.log_selector_test(selector, False)
        
        try:
            browser.page().runJavaScript(js_script, on_element_info)
        except Exception as e:
            AUTO_LOGIN_LOGGER.error(f"Erro ao capturar info do elemento: {e}")
    
    def capture_page_state(self, browser: QWebEngineView, stage: str):
        """Captura estado completo da página"""
        if not self.enabled or not self.current_session:
            return
        
        js_script = """
        (function() {
            return {
                url: window.location.href,
                title: document.title,
                readyState: document.readyState,
                cookies: document.cookie ? 'present' : 'none',
                forms: document.forms.length,
                inputs: document.querySelectorAll('input').length,
                buttons: document.querySelectorAll('button').length,
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                },
                timestamp: new Date().toISOString()
            };
        })();
        """
        
        def on_state_ready(state):
            if state:
                timestamp = datetime.now().strftime("%H%M%S")
                filename = f"page_state_{stage}_{timestamp}.json"
                filepath = self.current_session['dir'] / filename
                
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(state, f, indent=2)
                    AUTO_LOGIN_LOGGER.debug(f"🌐 Estado da página salvo: {filename}")
                except Exception as e:
                    AUTO_LOGIN_LOGGER.error(f"Erro ao salvar estado da página: {e}")
        
        try:
            browser.page().runJavaScript(js_script, on_state_ready)
        except Exception as e:
            AUTO_LOGIN_LOGGER.error(f"Erro ao capturar estado da página: {e}")
    
    def _save_session_report(self):
        """Salva relatório completo da sessão"""
        if not self.current_session:
            return
        
        report_file = self.current_session['dir'] / "session_report.json"
        
        try:
            # Preparar dados do relatório
            report = {
                'session_id': self.current_session['id'],
                'ai_tool_id': self.current_session['ai_tool_id'],
                'ai_name': self.current_session['ai_name'],
                'start_time': self.current_session['start_time'],
                'end_time': self.current_session.get('end_time'),
                'success': self.current_session.get('success'),
                'message': self.current_session.get('message'),
                'statistics': {
                    'screenshots_captured': len(self.current_session['screenshots']),
                    'html_dumps': len(self.current_session['html_dumps']),
                    'selectors_tested': len(self.current_session['selectors_tested']),
                    'javascript_executions': len(self.current_session['javascript_results']),
                    'errors': len(self.current_session['errors'])
                },
                'screenshots': self.current_session['screenshots'],
                'html_dumps': self.current_session['html_dumps'],
                'selectors_tested': self.current_session['selectors_tested'],
                'javascript_results': self.current_session['javascript_results'],
                'errors': self.current_session['errors']
            }
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            AUTO_LOGIN_LOGGER.debug(f"📊 Relatório da sessão salvo: {report_file}")
            
        except Exception as e:
            AUTO_LOGIN_LOGGER.error(f"Erro ao salvar relatório da sessão: {e}")
    
    def get_debug_directory(self) -> Path:
        """Retorna diretório de debug"""
        return self.debug_dir
    
    def get_session_directory(self) -> Optional[Path]:
        """Retorna diretório da sessão atual"""
        if self.current_session:
            return self.current_session['dir']
        return None


# Instância global do sistema de debug
DEBUG_SYSTEM = DebugSystem(enabled=False)  # Desabilitado por padrão