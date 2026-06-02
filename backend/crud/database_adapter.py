# crud/database_adapter.py

from typing import Dict, Optional
from sqlalchemy import text

from crud.device_data_manager import DeviceDataManager
from crud.sqlalchemy_ai_tools_manager import SQLAlchemyAIToolsManager
from crud.sqlalchemy_payment_config_manager import SQLAlchemyPaymentConfigManager
from crud.sqlalchemy_payment_manager import SQLAlchemyPaymentManager
from crud.sqlalchemy_proxy_manager import SQLAlchemyProxyManager
from crud.sqlalchemy_user_favorite_manager import SQLAlchemyUserFavoriteManager
from crud.sqlalchemy_user_manager import SQLAlchemyUserManager
from crud.sqlalchemy_direct_credentials_manager import SQLAlchemyDirectCredentialsManager
from crud.sqlalchemy_cookie_session_manager import SQLAlchemyCookieSessionManager  # <- NOVO
from crud.notification_crud import NotificationCRUD
from database.sqlalchemy_config import db_config
from utils.logger import LOGGER


class DatabaseAdapter:
    """Adaptador lazy - cria managers apenas quando necessário"""

    def __init__(self):
        self._users = None
        self._ai_tools = None
        self._proxies = None
        self._payments = None
        self._payment_configs = None
        self._user_favorites = None
        self._devices = None
        self._direct_credentials = None
        self._cookie_sessions = None  # <- NOVO
        self._notifications = None
        self._expenses = None

    @property
    def users(self):
        """Lazy loading do UserManager"""
        if self._users is None:
            self._users = SQLAlchemyUserManager()
        return self._users

    @property
    def ai_tools(self):
        """Lazy loading do AIToolsManager"""
        if self._ai_tools is None:
            self._ai_tools = SQLAlchemyAIToolsManager()
        return self._ai_tools

    @property
    def proxies(self):
        """Lazy loading do ProxyManager"""
        if self._proxies is None:
            self._proxies = SQLAlchemyProxyManager()
        return self._proxies

    @property
    def payments(self):
        """Lazy loading do PaymentManager"""
        if self._payments is None:
            self._payments = SQLAlchemyPaymentManager()
        return self._payments

    @property
    def payment_configs(self):
        """Lazy loading do PaymentConfigManager"""
        if self._payment_configs is None:
            self._payment_configs = SQLAlchemyPaymentConfigManager()
        return self._payment_configs

    @property
    def user_favorites(self):
        """Lazy loading do UserFavoriteManager"""
        if self._user_favorites is None:
            self._user_favorites = SQLAlchemyUserFavoriteManager()
        return self._user_favorites

    @property
    def devices(self):
        """Lazy loading do DeviceManager"""
        if self._devices is None:
            self._devices = DeviceDataManager()
        return self._devices

    @property
    def payment_configs(self):
        """Lazy loading do PaymentConfigManager"""
        if self._payment_configs is None:
            self._payment_configs = SQLAlchemyPaymentConfigManager()
        return self._payment_configs

    @property
    def direct_credentials(self):
        """Lazy loading do DirectCredentialsManager"""
        if self._direct_credentials is None:
            self._direct_credentials = SQLAlchemyDirectCredentialsManager()
        return self._direct_credentials

    @property
    def cookie_sessions(self):
        """Lazy loading do CookieSessionManager"""
        if self._cookie_sessions is None:
            self._cookie_sessions = SQLAlchemyCookieSessionManager()
        return self._cookie_sessions

    @property
    def notifications(self):
        """Lazy loading do NotificationManager"""
        if self._notifications is None:
            self._notifications = NotificationCRUD()
        return self._notifications
    

    @property
    def expenses(self):
        """Lazy loading do ExpenseManager"""
        if self._expenses is None:
            from crud.sqlalchemy_expense_manager import SQLAlchemyExpenseManager
            self._expenses = SQLAlchemyExpenseManager()
        return self._expenses

    def is_connected(self) -> bool:
        """Testa conexão com banco"""
        try:
            session = db_config.get_session()
            session.execute(text("SELECT 1"))
            session.close()
            return True
        except Exception as e:
            LOGGER.error(f"Erro ao testar conexão: {e}")
            return False

    def get_status(self):
        """Retorna status do sistema"""
        return {
            "database_connected": self.is_connected(),
            "managers_loaded": {
                "users": self._users is not None,
                "ai_tools": self._ai_tools is not None,
                "payments": self._payments is not None,
                "payment_configs": self._payment_configs is not None,
                "user_favorites": self._user_favorites is not None,
                "proxies": self._proxies is not None,
                "devices": self._devices is not None,
                "direct_credentials": self._direct_credentials is not None,
                "cookie_sessions": self._cookie_sessions is not None,  # <- NOVO
                "notifications": self._notifications is not None,
            },
        }

    def get_ai_with_credentials(self, ai_tool_id: str) -> Optional[Dict]:
        """Método convenience para obter IA com suas credenciais"""
        try:
            return self.ai_tools.get_tool_with_credentials(ai_tool_id)
        except Exception as e:
            LOGGER.error(f"Erro ao obter IA com credenciais: {e}")
            return None

    def test_ai_credentials(self, ai_tool_id: str):
        """Método convenience para testar credenciais"""
        try:
            from core.services.credential_tester import credential_tester
            return credential_tester.run_credentials_test(ai_tool_id)
        except Exception as e:
            LOGGER.error(f"Erro ao testar credenciais: {e}")
            return False, f"Erro no teste: {str(e)}"

    def get_credentials_report(self, ai_tool_id: str) -> Dict:
        """Método convenience para obter relatório de credenciais"""
        try:
            from core.services.credential_tester import credential_tester
            return credential_tester.get_test_report(ai_tool_id)
        except Exception as e:
            LOGGER.error(f"Erro ao gerar relatório: {e}")
            return {"error": str(e)}


crud_system = DatabaseAdapter()