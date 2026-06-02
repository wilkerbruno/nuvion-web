# utils/favicon_manager.py
"""
Sistema de gerenciamento de favicons com cache local
Busca automaticamente os ícones das ferramentas de IA
"""
import hashlib
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from utils.logger import LOGGER


class FaviconManager(QObject):
    """Gerenciador de favicons com cache local"""
    
    favicon_loaded = pyqtSignal(str, QPixmap)  # url, pixmap
    
    def __init__(self):
        super().__init__()
        self.network_manager = QNetworkAccessManager()
        self.network_manager.finished.connect(self._on_download_finished)
        
        # Diretório de cache
        self.cache_dir = self._setup_cache_directory()
        
        # Cache em memória para acesso rápido
        self.memory_cache = {}
        
        # Mapeamento de requisições pendentes
        self.pending_requests = {}
        
    def _setup_cache_directory(self) -> Path:
        """Cria diretório para cache de favicons"""
        try:
            cache_path = Path.home() / ".nuvion_browser" / "favicon_cache"
            cache_path.mkdir(parents=True, exist_ok=True)
            LOGGER.info(f"Cache de favicons configurado em: {cache_path}")
            return cache_path
        except Exception as e:
            LOGGER.error(f"Erro ao criar diretório de cache: {e}")
            # Fallback para diretório local
            cache_path = Path("favicon_cache")
            cache_path.mkdir(exist_ok=True)
            return cache_path
    
    def get_favicon(self, url: str) -> Optional[QPixmap]:
        """
        Busca favicon da URL (síncrono se em cache, assíncrono caso contrário)
        
        Args:
            url: URL da ferramenta de IA
            
        Returns:
            QPixmap se já estiver em cache, None se precisar baixar
        """
        # Verificar cache em memória
        if url in self.memory_cache:
            LOGGER.debug(f"Favicon encontrado em memória: {url}")
            return self.memory_cache[url]
        
        # Verificar cache em disco
        cached_pixmap = self._load_from_cache(url)
        if cached_pixmap:
            LOGGER.debug(f"Favicon encontrado em cache: {url}")
            self.memory_cache[url] = cached_pixmap
            return cached_pixmap
        
        # Baixar assincronamente
        self._download_favicon(url)
        return None
    
    def _get_cache_filename(self, url: str) -> str:
        """Gera nome do arquivo de cache baseado na URL"""
        # Usar hash da URL como nome do arquivo
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return f"{url_hash}.png"
    
    def _load_from_cache(self, url: str) -> Optional[QPixmap]:
        """Carrega favicon do cache em disco"""
        try:
            cache_file = self.cache_dir / self._get_cache_filename(url)
            if cache_file.exists():
                pixmap = QPixmap(str(cache_file))
                if not pixmap.isNull():
                    return pixmap
        except Exception as e:
            LOGGER.debug(f"Erro ao carregar do cache: {e}")
        return None
    
    def _save_to_cache(self, url: str, pixmap: QPixmap):
        """Salva favicon no cache em disco"""
        try:
            cache_file = self.cache_dir / self._get_cache_filename(url)
            pixmap.save(str(cache_file), "PNG")
            LOGGER.debug(f"Favicon salvo em cache: {url}")
        except Exception as e:
            LOGGER.error(f"Erro ao salvar no cache: {e}")
    
    def _download_favicon(self, url: str):
        """Baixa favicon da URL"""
        if url in self.pending_requests:
            LOGGER.debug(f"Download já em andamento: {url}")
            return
        
        # Extrair domínio
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            
            # Usar múltiplas estratégias de busca
            favicon_urls = [
                f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
                f"https://www.google.com/s2/favicons?domain={domain}&sz=64",
                f"{parsed.scheme}://{domain}/favicon.ico",
            ]
            
            # Tentar a primeira URL
            self._try_download_url(url, favicon_urls)
            
        except Exception as e:
            LOGGER.error(f"Erro ao preparar download de favicon: {e}")
    
    def _try_download_url(self, original_url: str, favicon_urls: list):
        """Tenta baixar de uma lista de URLs"""
        if not favicon_urls:
            LOGGER.warning(f"Nenhuma URL de favicon disponível para: {original_url}")
            return
        
        favicon_url = favicon_urls[0]
        remaining_urls = favicon_urls[1:]
        
        LOGGER.info(f"Baixando favicon de: {favicon_url}")
        
        request = QNetworkRequest(QUrl(favicon_url))
        request.setAttribute(QNetworkRequest.Attribute.User, {
            'original_url': original_url,
            'remaining_urls': remaining_urls
        })
        
        reply = self.network_manager.get(request)
        self.pending_requests[original_url] = reply
    
    def _on_download_finished(self, reply: QNetworkReply):
        """Callback quando download do favicon terminar"""
        user_data = reply.request().attribute(QNetworkRequest.Attribute.User)
        original_url = user_data['original_url']
        remaining_urls = user_data['remaining_urls']
        
        # Remover das requisições pendentes
        if original_url in self.pending_requests:
            del self.pending_requests[original_url]
        
        if reply.error() == QNetworkReply.NetworkError.NoError:
            # Download bem-sucedido
            data = reply.readAll()
            pixmap = QPixmap()
            
            if pixmap.loadFromData(data):
                LOGGER.info(f"Favicon baixado com sucesso: {original_url}")
                
                # Salvar em cache
                self._save_to_cache(original_url, pixmap)
                self.memory_cache[original_url] = pixmap
                
                # Emitir sinal
                self.favicon_loaded.emit(original_url, pixmap)
            else:
                LOGGER.warning(f"Dados de imagem inválidos para: {original_url}")
                # Tentar próxima URL
                if remaining_urls:
                    self._try_download_url(original_url, remaining_urls)
        else:
            LOGGER.warning(f"Erro ao baixar favicon: {reply.errorString()}")
            # Tentar próxima URL
            if remaining_urls:
                self._try_download_url(original_url, remaining_urls)
        
        reply.deleteLater()
    
    def clear_cache(self):
        """Limpa o cache de favicons"""
        try:
            import shutil
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.memory_cache.clear()
            LOGGER.info("Cache de favicons limpo")
        except Exception as e:
            LOGGER.error(f"Erro ao limpar cache: {e}")


# Instância global
favicon_manager = FaviconManager()