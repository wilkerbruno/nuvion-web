# utils/favicon_fetcher.py
"""
Utilitário para buscar favicons de sites de IA
Implementa múltiplas estratégias de busca
"""
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from utils.logger import LOGGER


class FaviconFetcher:
    """Classe para buscar favicons de sites"""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fetch_favicon_url(self, site_url: str) -> Optional[str]:
        """
        Busca URL do favicon usando múltiplas estratégias
        
        Args:
            site_url: URL do site da IA
            
        Returns:
            URL do favicon ou None se não encontrar
        """
        try:
            LOGGER.info(f"Buscando favicon para: {site_url}")
            
            # Estratégia 1: Tentar favicon padrão
            favicon_url = self._try_default_favicon(site_url)
            if favicon_url:
                LOGGER.info(f"Favicon encontrado (padrão): {favicon_url}")
                return favicon_url
            
            # Estratégia 2: Buscar no HTML
            favicon_url = self._parse_html_for_favicon(site_url)
            if favicon_url:
                LOGGER.info(f"Favicon encontrado (HTML): {favicon_url}")
                return favicon_url
            
            # Estratégia 3: Usar serviço externo como fallback
            favicon_url = self._use_external_service(site_url)
            if favicon_url:
                LOGGER.info(f"Favicon encontrado (serviço externo): {favicon_url}")
                return favicon_url
            
            LOGGER.warning(f"Nenhum favicon encontrado para: {site_url}")
            return None
            
        except Exception as e:
            LOGGER.error(f"Erro ao buscar favicon para {site_url}: {e}")
            return None

    def _try_default_favicon(self, site_url: str) -> Optional[str]:
        """Tenta acessar favicon.ico padrão"""
        try:
            parsed_url = urlparse(site_url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            favicon_url = f"{base_url}/favicon.ico"
            
            response = self.session.head(favicon_url, timeout=self.timeout, allow_redirects=True)
            if response.status_code == 200:
                return favicon_url
                
        except Exception as e:
            LOGGER.debug(f"Favicon padrão não encontrado: {e}")
        
        return None

    def _parse_html_for_favicon(self, site_url: str) -> Optional[str]:
        """Busca favicon no HTML da página"""
        try:
            response = self.session.get(site_url, timeout=self.timeout)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Procurar por tags de favicon em ordem de prioridade
            favicon_tags = [
                ('link', {'rel': re.compile(r'icon', re.I)}),
                ('link', {'rel': re.compile(r'shortcut icon', re.I)}),
                ('link', {'rel': re.compile(r'apple-touch-icon', re.I)}),
            ]
            
            for tag_name, attrs in favicon_tags:
                tag = soup.find(tag_name, attrs)
                if tag and tag.get('href'):
                    href = tag.get('href')
                    # Converter URL relativa para absoluta
                    favicon_url = urljoin(site_url, href)
                    
                    # Verificar se a URL é válida
                    if self._validate_favicon_url(favicon_url):
                        return favicon_url
            
        except Exception as e:
            LOGGER.debug(f"Erro ao parsear HTML: {e}")
        
        return None

    def _use_external_service(self, site_url: str) -> Optional[str]:
        """Usa serviço externo para obter favicon (Google, DuckDuckGo, etc)"""
        try:
            parsed_url = urlparse(site_url)
            domain = parsed_url.netloc
            
            # Serviços de favicon em ordem de prioridade
            services = [
                f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
                f"https://icons.duckduckgo.com/ip3/{domain}.ico",
                f"https://favicon.im/{domain}",
            ]
            
            for service_url in services:
                try:
                    response = self.session.head(service_url, timeout=5)
                    if response.status_code == 200:
                        return service_url
                except:
                    continue
                    
        except Exception as e:
            LOGGER.debug(f"Erro ao usar serviço externo: {e}")
        
        return None

    def _validate_favicon_url(self, url: str) -> bool:
        """Valida se a URL do favicon é acessível"""
        try:
            response = self.session.head(url, timeout=5)
            return response.status_code == 200
        except:
            return False


# Instância global
favicon_fetcher = FaviconFetcher()