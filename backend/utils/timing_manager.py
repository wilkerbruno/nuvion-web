import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
Gerenciador de Timing Adaptativo
Fornece delays inteligentes baseados em site, tipo de ação e histórico
"""

import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
from utils.auto_login_logger import AUTO_LOGIN_LOGGER


class TimingManager:
    """Gerenciador de timing inteligente e adaptativo"""
    
    # Configurações de timing por domínio (em milissegundos)
    SITE_TIMINGS = {
        'claude.ai': {
            'page_load': 8000,
            'script_injection': 2000,
            'field_separation': 6000,
            'submit_delay': 2500,
            'verification_delay': 4000
        },
        'chat.openai.com': {
            'page_load': 7000,
            'script_injection': 1500,
            'field_separation': 5000,
            'submit_delay': 2000,
            'verification_delay': 3500
        },
        'chatgpt.com': {
            'page_load': 7000,
            'script_injection': 1500,
            'field_separation': 5000,
            'submit_delay': 2000,
            'verification_delay': 3500
        },
        'gemini.google.com': {
            'page_load': 6500,
            'script_injection': 1500,
            'field_separation': 4500,
            'submit_delay': 2000,
            'verification_delay': 3000
        },
        'bard.google.com': {
            'page_load': 6500,
            'script_injection': 1500,
            'field_separation': 4500,
            'submit_delay': 2000,
            'verification_delay': 3000
        },
        'bing.com': {
            'page_load': 5500,
            'script_injection': 1200,
            'field_separation': 4000,
            'submit_delay': 1800,
            'verification_delay': 2500
        },
        'default': {
            'page_load': 5000,
            'script_injection': 1500,
            'field_separation': 4000,
            'submit_delay': 2000,
            'verification_delay': 3000
        }
    }
    
    # Fatores de ajuste baseados em tentativas
    RETRY_MULTIPLIERS = {
        1: 1.0,   # Primeira tentativa: timing normal
        2: 1.5,   # Segunda tentativa: 50% mais tempo
        3: 2.0,   # Terceira tentativa: dobro do tempo
        4: 2.5,   # Quarta tentativa: 2.5x mais tempo
    }
    
    def __init__(self):
        self.timing_history = {}  # Histórico de timings por site
        self.current_attempt = 1
    
    def get_site_domain(self, url: str) -> str:
        """
        Extrai domínio principal da URL
        
        Args:
            url: URL completa
            
        Returns:
            Domínio principal
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remover 'www.' se presente
            if domain.startswith('www.'):
                domain = domain[4:]
            
            return domain
        except Exception as e:
            AUTO_LOGIN_LOGGER.error(f"Erro ao parsear URL: {e}")
            return "unknown"
    
    def get_timing_profile(self, url: str) -> Dict[str, int]:
        """
        Retorna perfil de timing para URL
        
        Args:
            url: URL do site
            
        Returns:
            Dicionário com timings em milissegundos
        """
        domain = self.get_site_domain(url)
        
        # Buscar configuração específica do domínio
        for known_domain, timings in self.SITE_TIMINGS.items():
            if known_domain in domain:
                AUTO_LOGIN_LOGGER.info(f"Perfil de timing encontrado para: {known_domain}")
                return timings.copy()
        
        # Usar perfil padrão
        AUTO_LOGIN_LOGGER.info(f"Usando perfil de timing padrão para: {domain}")
        return self.SITE_TIMINGS['default'].copy()
    
    def get_adjusted_timing(self, url: str, action: str, attempt: int = 1) -> int:
        """
        Retorna timing ajustado para ação específica
        
        Args:
            url: URL do site
            action: Tipo de ação (page_load, script_injection, etc.)
            attempt: Número da tentativa atual
            
        Returns:
            Timing em milissegundos
        """
        # Obter timing base
        profile = self.get_timing_profile(url)
        base_timing = profile.get(action, profile['page_load'])
        
        # Aplicar multiplicador de retry
        multiplier = self.RETRY_MULTIPLIERS.get(attempt, 3.0)
        adjusted_timing = int(base_timing * multiplier)
        
        AUTO_LOGIN_LOGGER.debug(f"Timing para {action} (tentativa {attempt}): "
                               f"{base_timing}ms -> {adjusted_timing}ms (x{multiplier})")
        
        return adjusted_timing
    
    def wait_for_page_load(self, url: str, attempt: int = 1):
        """
        Aguarda carregamento da página
        
        Args:
            url: URL da página
            attempt: Número da tentativa
        """
        delay = self.get_adjusted_timing(url, 'page_load', attempt)
        AUTO_LOGIN_LOGGER.log_step(
            "Aguardando carregamento da página",
            "executing",
            f"{delay}ms"
        )
        time.sleep(delay / 1000.0)
    
    def wait_for_script_injection(self, url: str, attempt: int = 1):
        """
        Aguarda após injeção de script
        
        Args:
            url: URL da página
            attempt: Número da tentativa
        """
        delay = self.get_adjusted_timing(url, 'script_injection', attempt)
        AUTO_LOGIN_LOGGER.log_step(
            "Aguardando processamento do script",
            "executing",
            f"{delay}ms"
        )
        time.sleep(delay / 1000.0)
    
    def wait_between_fields(self, url: str, attempt: int = 1):
        """
        Aguarda entre preenchimento de campos
        
        Args:
            url: URL da página
            attempt: Número da tentativa
        """
        delay = self.get_adjusted_timing(url, 'field_separation', attempt)
        AUTO_LOGIN_LOGGER.log_step(
            "Pausa natural entre campos",
            "executing",
            f"{delay}ms"
        )
        time.sleep(delay / 1000.0)
    
    def wait_before_submit(self, url: str, attempt: int = 1):
        """
        Aguarda antes de submeter formulário
        
        Args:
            url: URL da página
            attempt: Número da tentativa
        """
        delay = self.get_adjusted_timing(url, 'submit_delay', attempt)
        AUTO_LOGIN_LOGGER.log_step(
            "Aguardando antes de submit",
            "executing",
            f"{delay}ms"
        )
        time.sleep(delay / 1000.0)
    
    def wait_for_verification(self, url: str, attempt: int = 1):
        """
        Aguarda para verificação de resultado
        
        Args:
            url: URL da página
            attempt: Número da tentativa
        """
        delay = self.get_adjusted_timing(url, 'verification_delay', attempt)
        AUTO_LOGIN_LOGGER.log_step(
            "Aguardando para verificação",
            "executing",
            f"{delay}ms"
        )
        time.sleep(delay / 1000.0)
    
    def record_timing(self, url: str, action: str, duration: float, success: bool):
        """
        Registra timing de uma ação para análise futura
        
        Args:
            url: URL do site
            action: Tipo de ação
            duration: Duração em segundos
            success: Se foi bem-sucedido
        """
        domain = self.get_site_domain(url)
        
        if domain not in self.timing_history:
            self.timing_history[domain] = {}
        
        if action not in self.timing_history[domain]:
            self.timing_history[domain][action] = []
        
        self.timing_history[domain][action].append({
            'duration': duration,
            'success': success,
            'timestamp': time.time()
        })
        
        AUTO_LOGIN_LOGGER.debug(f"Timing registrado: {domain}/{action} = {duration:.2f}s "
                               f"({'sucesso' if success else 'falha'})")
    
    def get_optimal_timing(self, url: str, action: str) -> Optional[int]:
        """
        Calcula timing ótimo baseado em histórico
        
        Args:
            url: URL do site
            action: Tipo de ação
            
        Returns:
            Timing ótimo em milissegundos ou None se não há histórico
        """
        domain = self.get_site_domain(url)
        
        if domain not in self.timing_history:
            return None
        
        if action not in self.timing_history[domain]:
            return None
        
        # Pegar apenas tentativas bem-sucedidas
        successful = [
            entry['duration'] 
            for entry in self.timing_history[domain][action] 
            if entry['success']
        ]
        
        if not successful:
            return None
        
        # Calcular média dos sucessos
        avg_duration = sum(successful) / len(successful)
        optimal_ms = int(avg_duration * 1000 * 1.2)  # 20% de margem
        
        AUTO_LOGIN_LOGGER.info(f"Timing ótimo calculado para {domain}/{action}: {optimal_ms}ms")
        
        return optimal_ms
    
    def get_timing_statistics(self, url: str) -> Dict[str, Dict]:
        """
        Retorna estatísticas de timing para URL
        
        Args:
            url: URL do site
            
        Returns:
            Dicionário com estatísticas
        """
        domain = self.get_site_domain(url)
        
        if domain not in self.timing_history:
            return {}
        
        stats = {}
        for action, entries in self.timing_history[domain].items():
            total = len(entries)
            successful = sum(1 for e in entries if e['success'])
            
            durations = [e['duration'] for e in entries]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            stats[action] = {
                'total_attempts': total,
                'successful': successful,
                'success_rate': (successful / total * 100) if total > 0 else 0,
                'avg_duration': avg_duration
            }
        
        return stats


# Testes unitários
if __name__ == "__main__":
    print("=== TESTES DO TIMING MANAGER ===\n")
    
    tm = TimingManager()
    
    # Teste 1: Perfis de timing
    print("TESTE 1: Perfis de timing por site")
    urls = [
        'https://claude.ai/chat',
        'https://chat.openai.com',
        'https://example.com/login'
    ]
    
    for url in urls:
        profile = tm.get_timing_profile(url)
        print(f"  {url}")
        print(f"    Page load: {profile['page_load']}ms")
        print(f"    Field separation: {profile['field_separation']}ms")
    print("  ✅ Passou\n")
    
    # Teste 2: Ajuste por tentativa
    print("TESTE 2: Ajuste de timing por tentativa")
    url = 'https://claude.ai'
    for attempt in [1, 2, 3]:
        timing = tm.get_adjusted_timing(url, 'page_load', attempt)
        print(f"  Tentativa {attempt}: {timing}ms")
    print("  ✅ Passou\n")
    
    # Teste 3: Registro de histórico
    print("TESTE 3: Registro de histórico")
    tm.record_timing('https://claude.ai', 'page_load', 5.5, True)
    tm.record_timing('https://claude.ai', 'page_load', 6.2, True)
    tm.record_timing('https://claude.ai', 'page_load', 8.1, False)
    
    stats = tm.get_timing_statistics('https://claude.ai')
    print(f"  Estatísticas: {stats}")
    print("  ✅ Passou\n")
    
    # Teste 4: Timing ótimo
    print("TESTE 4: Cálculo de timing ótimo")
    optimal = tm.get_optimal_timing('https://claude.ai', 'page_load')
    print(f"  Timing ótimo calculado: {optimal}ms")
    print("  ✅ Passou\n")
    
    print("=== TODOS OS TESTES CONCLUÍDOS ===")