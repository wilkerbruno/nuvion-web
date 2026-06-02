import os
from typing import Dict, Optional
from utils.logger import LOGGER


class StyleCache:
    """Sistema de cache para arquivos CSS - VERSÃO APRIMORADA"""
    
    _cache: Dict[str, str] = {}
    _cache_enabled = True
    _stats = {
        'hits': 0,
        'misses': 0,
        'files_cached': 0
    }

    @classmethod
    def load_stylesheet(cls, filename: str) -> str:
        """
        Carrega stylesheet com cache automático
        
        Args:
            filename: Nome do arquivo CSS
            
        Returns:
            Conteúdo do arquivo CSS
        """
        # Verificar cache primeiro
        if cls._cache_enabled and filename in cls._cache:
            cls._stats['hits'] += 1
            LOGGER.debug(f"CSS cache HIT: {filename}")
            return cls._cache[filename]

        # Cache miss
        cls._stats['misses'] += 1
        LOGGER.debug(f"CSS cache MISS: {filename}")

        # Carregar do disco
        try:
            path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 
                "..", 
                "assets", 
                "css", 
                filename
            )
            
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Armazenar no cache
            if cls._cache_enabled:
                cls._cache[filename] = content
                cls._stats['files_cached'] = len(cls._cache)
                LOGGER.debug(f"CSS cacheado: {filename} ({len(content)} bytes)")
            
            return content
            
        except FileNotFoundError:
            LOGGER.error(f"Arquivo CSS não encontrado: {filename}")
            return ""
        except Exception as e:
            LOGGER.error(f"Erro ao carregar stylesheet {filename}: {e}")
            return ""

    @classmethod
    def preload_stylesheets(cls, filenames: list):
        """
        Pré-carrega múltiplos stylesheets de uma vez
        
        Args:
            filenames: Lista de nomes de arquivos CSS
        """
        LOGGER.info(f"Pré-carregando {len(filenames)} stylesheets...")
        
        loaded = 0
        for filename in filenames:
            if filename not in cls._cache:
                content = cls.load_stylesheet(filename)
                if content:
                    loaded += 1
        
        LOGGER.info(f"Pré-carregados {loaded}/{len(filenames)} stylesheets")

    @classmethod
    def clear_cache(cls, filename: Optional[str] = None):
        """
        Limpa cache de estilos
        
        Args:
            filename: Nome do arquivo específico ou None para limpar tudo
        """
        if filename:
            cls._cache.pop(filename, None)
            LOGGER.info(f"Cache limpo para: {filename}")
        else:
            cls._cache.clear()
            LOGGER.info("Cache de estilos completamente limpo")
        
        cls._stats['files_cached'] = len(cls._cache)

    @classmethod
    def disable_cache(cls):
        """Desabilita sistema de cache (útil para desenvolvimento)"""
        cls._cache_enabled = False
        cls._cache.clear()
        LOGGER.info("Cache de estilos DESABILITADO")

    @classmethod
    def enable_cache(cls):
        """Habilita sistema de cache"""
        cls._cache_enabled = True
        LOGGER.info("Cache de estilos HABILITADO")

    @classmethod
    def get_stats(cls) -> Dict[str, int]:
        """Retorna estatísticas do cache"""
        total_requests = cls._stats['hits'] + cls._stats['misses']
        hit_rate = (cls._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **cls._stats,
            'hit_rate': round(hit_rate, 2),
            'total_requests': total_requests
        }

    @classmethod
    def get_cached_files(cls) -> list:
        """Retorna lista de arquivos em cache"""
        return list(cls._cache.keys())