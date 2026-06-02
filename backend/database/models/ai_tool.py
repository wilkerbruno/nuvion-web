from sqlalchemy import *
from sqlalchemy.orm import relationship

from database.models.base import BaseModel
from database.sqlalchemy_config import Base
from utils.logger import LOGGER


class AITool(Base, BaseModel):
    """Modelo de ferramentas de IA"""

    # Controle de extensões
    block_extensions = Column(Boolean, default=False, nullable=False)

    __tablename__ = "ai_tools"

    # Informações básicas
    name = Column(String(100), nullable=False, unique=True)
    url = Column(Text, nullable=False)
    description = Column(Text)
    category = Column(String(50), index=True)

    # Campo para cookies diretos1
    login_cookies_raw = Column(JSON, nullable=True)
    login_method = Column(String(20), default="manual")  # "credentials", "cookies"

    observations = Column(Text)
    proxy_id = Column(String(36), ForeignKey("proxy.id"), nullable=True)
    tags = Column(JSON, default=list)
    rating = Column(Numeric(3, 2), default=0.0)
    is_featured = Column(Boolean, default=False)

    direct_credentials = relationship("AIDirectCredentials", back_populates="ai_tool")
    cookie_sessions = relationship("AISessionCookies", back_populates="ai_tool")
    proxy = relationship("Proxy", back_populates="assigned_ias")

    @property
    def proxy_info(self):
        """Retorna informações do proxy associado"""
        if self.proxy:
            return f"{self.proxy.name} ({self.proxy.host}:{self.proxy.port}) - {self.proxy.proxy_type}"
        return "Sem Proxy"

    def has_cookies_configured(self) -> bool:
        """Verifica se IA tem cookies configurados"""
        return any(session.is_active for session in self.cookie_sessions)

    def get_active_cookie_session(self):
        """Retorna sessão de cookies ativa"""
        for session in self.cookie_sessions:
            if session.is_active and session.status == "active":
                return session
        return None

    def get_cookies_status(self) -> dict:
        """Retorna status detalhado dos cookies"""
        active_session = self.get_active_cookie_session()

        if not active_session:
            return {
                "configured": False,
                "status": "not_configured",
                "cookies_count": 0,
                "domain": None,
                "expires_at": None,
            }

        return {
            "configured": True,
            "status": active_session.status,
            "cookies_count": active_session.cookies_count,
            "domain": active_session.domain_extracted,
            "expires_at": active_session.expires_at,
            "is_valid": active_session.is_valid(),
        }

    def add_tag(self, tag: str):
        """Adiciona uma tag à ferramenta"""
        if self.tags is None:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: str):
        """Remove uma tag da ferramenta"""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)

    def get_login_type(self) -> str:
        """Retorna tipo de login configurado"""
        return self.login_method or "manual"

    def get_active_login_method(self):
        """
        Retorna o método de login ativo
        Prioridade: login_method configurado > cookies > manual
        """
        from utils.logger import LOGGER
        
        # 1. Se tem login_method configurado (google ou direct), usar ele
        if self.login_method and self.login_method != "manual":
            LOGGER.info(f"✅ Login method configurado no banco: {self.login_method}")
            return self.login_method
        
        # 2. Se tem cookies ativos, usar cookies
        if self.cookie_sessions:
            for cookie_session in self.cookie_sessions:
                if cookie_session.is_active:
                    LOGGER.info(f"✅ Cookie ativo encontrado - usando 'cookies'")
                    return "cookies"
        
        # 3. Fallback para manual
        LOGGER.info(f"⚠️ Nenhum método ativo - usando 'manual'")
        return "manual"






    def has_direct_configured(self) -> bool:
        """Verifica se tem credenciais diretas configuradas e válidas"""
        if hasattr(self, 'direct_credentials') and self.direct_credentials:
            return self.direct_credentials.is_active and self.direct_credentials.is_valid()
        return False

    def get_login_status_summary(self) -> dict:
        """Retorna resumo completo do status de login"""
        try:
            from crud.database_adapter import crud_system
            
            status = {
                'ai_name': self.name,
                'ai_id': self.id,
                'login_method_db': getattr(self, 'login_method', 'manual'),
                'active_method': self.get_active_login_method(),
                'direct': False,
                'cookies': False,
                'details': {}
            }
                        
            # Verificar Direct
            try:
                direct_creds = crud_system.direct_credentials.get_credentials_by_ai_tool(self.id)
                if direct_creds:
                    status['direct'] = bool(direct_creds.get('username') and direct_creds.get('password'))
                    status['details']['direct'] = {
                        'has_username': bool(direct_creds.get('username')),
                        'has_password': bool(direct_creds.get('password')),
                        'username': direct_creds.get('username', 'N/A')
                    }
            except:
                pass
            
            # Verificar Cookies
            try:
                from core.utils.cookie_session_manager import CookieSessionManager
                cookie_data = CookieSessionManager.get_active_cookies(self.id)
                if cookie_data:
                    status['cookies'] = bool(cookie_data.get("cookies_data"))
                    status['details']['cookies'] = {
                        'count': len(cookie_data.get("cookies_data", [])),
                        'source': cookie_data.get("source", "N/A")
                    }
            except:
                pass
            
            return status
            
        except Exception as e:
            LOGGER.error(f"Erro ao obter status de login: {e}")
            return {'error': str(e)}
