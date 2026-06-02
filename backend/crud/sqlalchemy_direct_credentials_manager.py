# crud/sqlalchemy_direct_credentials_manager.py
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy import and_
from crud.base_manager import BaseManager
from database.models.ai_direct_credentials import AIDirectCredentials
from cryptography.fernet import Fernet
from utils.logger import LOGGER
import os


class SQLAlchemyDirectCredentialsManager(BaseManager[AIDirectCredentials]):
    """Manager para credenciais diretas usando SQLAlchemy"""

    def __init__(self):
        super().__init__(AIDirectCredentials)
        self._fernet = self._init_encryption()

    def _init_encryption(self):
        """Inicializa sistema de criptografia"""
        try:
            # Usar a mesma chave do sistema existente
            key = os.getenv("ENCRYPTION_KEY")
            if not key:
                # Gerar chave se não existir (para desenvolvimento)
                key = Fernet.generate_key()
                LOGGER.warning("Usando chave de criptografia temporária - configure ENCRYPTION_KEY")
            
            if isinstance(key, str):
                key = key.encode()
                
            return Fernet(key)
        except Exception as e:
            LOGGER.error(f"Erro ao inicializar criptografia: {e}")
            return None

    def create_direct_credentials(
        self,
        ai_tool_id: str,
        username: str,
        password: str,
        login_url: str = None,
        username_selector: str = None,
        password_selector: str = None,
        submit_selector: str = None
    ) -> Tuple[bool, str]:
        """
        Cria credenciais diretas com seletores
        
        Args:
            ai_tool_id: ID da IA
            username: Nome de usuário/email
            password: Senha
            login_url: URL específica de login (opcional)
            username_selector: Seletores CSS para campo username
            password_selector: Seletores CSS para campo password  
            submit_selector: Seletores CSS para botão submit
        """
        session = self.get_session()
        try:
            LOGGER.info(f"🔐 Criando credenciais diretas para IA {ai_tool_id}")
            
            # Verificar se já existe e remover
            existing = session.query(AIDirectCredentials).filter(
                AIDirectCredentials.ai_tool_id == ai_tool_id
            ).first()
            
            if existing:
                LOGGER.info(f"Removendo credenciais existentes para IA {ai_tool_id}")
                session.delete(existing)
                session.flush()

            # Criar novas credenciais usando apenas campos válidos do modelo
            credentials = AIDirectCredentials(
                ai_tool_id=ai_tool_id,
                username=username,
                password=password,  # SEM criptografia para testes
                login_url=login_url,
                is_active=True,
                # Seletores com valores padrão se não fornecidos
                username_selector=username_selector or "#email, #username, input[name='email'], input[name='username']",
                password_selector=password_selector or "#password, input[name='password'], input[type='password']", 
                submit_selector=submit_selector or "button[type='submit'], input[type='submit'], #login-button",
                # Status inicial
                login_status="pending",
                failed_attempts=0,
                max_attempts=3
            )

            session.add(credentials)
            session.commit()

            LOGGER.info(f"✅ Credenciais diretas criadas com sucesso para IA {ai_tool_id}")
            LOGGER.info(f"Username: {username}")
            LOGGER.info(f"Login URL: {login_url or 'Não especificada'}")
            LOGGER.info(f"Username selector: {credentials.username_selector}")
            LOGGER.info(f"Password selector: {credentials.password_selector}")
            LOGGER.info(f"Submit selector: {credentials.submit_selector}")
            
            return True, credentials.id

        except Exception as e:
            session.rollback()
            LOGGER.error(f"❌ Erro ao criar credenciais diretas: {e}")
            return False, str(e)
        finally:
            session.close()

    def get_direct_credentials(self, ai_tool_id: str) -> Optional[AIDirectCredentials]:
        """Busca credenciais diretas ativas para uma IA"""
        session = self.get_session()
        try:
            credentials = session.query(AIDirectCredentials).filter(
                and_(
                    AIDirectCredentials.ai_tool_id == ai_tool_id,
                    AIDirectCredentials.is_active == True
                )
            ).first()

            return credentials

        except Exception as e:
            LOGGER.error(f"Erro ao buscar credenciais diretas: {e}")
            return None
        finally:
            session.close()

    def get_decrypted_credentials(self, ai_tool_id: str) -> Optional[Dict]:
        """Obtém credenciais descriptografadas - SEM DESCRIPTOGRAFIA PARA TESTES"""
        session = self.get_session()
        try:
            credentials = session.query(AIDirectCredentials).filter(
                AIDirectCredentials.ai_tool_id == ai_tool_id,
                AIDirectCredentials.is_active == True
            ).first()

            if not credentials:
                LOGGER.warning(f"Credenciais diretas não encontradas para IA {ai_tool_id}")
                return None

            # Retornar credenciais diretas - SEM descriptografia para testes
            creds = {
                'username': credentials.username,
                'password': credentials.password,  # Direto do banco
                'login_url': credentials.login_url,
                'is_valid': credentials.is_valid(),
                'username_selector': credentials.username_selector,
                'password_selector': credentials.password_selector,
                'submit_selector': credentials.submit_selector,
                'login_status': credentials.login_status,
                'failed_attempts': credentials.failed_attempts
            }

            LOGGER.info(f"✅ Credenciais diretas obtidas para IA {ai_tool_id}")
            LOGGER.info(f"Username: {creds['username']}")
            LOGGER.info(f"Status: {creds['login_status']}")
            
            return creds

        except Exception as e:
            LOGGER.error(f"❌ Erro ao obter credenciais diretas: {e}")
            return None
        finally:
            session.close()

    def mark_login_attempt(self, ai_tool_id: str, success: bool, error_message: str = None) -> bool:
        """Marca tentativa de login"""
        session = self.get_session()
        try:
            credentials = session.query(AIDirectCredentials).filter(
                AIDirectCredentials.ai_tool_id == ai_tool_id
            ).first()

            if credentials:
                credentials.mark_login_attempt(success)
                session.commit()
                LOGGER.info(f"Tentativa de login marcada para IA {ai_tool_id}: {'sucesso' if success else 'falha'}")
                return True

            return False

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao marcar tentativa de login: {e}")
            return False
        finally:
            session.close()

    def reset_failed_attempts(self, ai_tool_id: str) -> bool:
        """Reset contador de tentativas falhadas"""
        session = self.get_session()
        try:
            credentials = session.query(AIDirectCredentials).filter(
                AIDirectCredentials.ai_tool_id == ai_tool_id
            ).first()

            if credentials:
                credentials.reset_failed_attempts()
                session.commit()
                LOGGER.info(f"Reset de tentativas para IA {ai_tool_id}")
                return True

            return False

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao resetar tentativas: {e}")
            return False
        finally:
            session.close()

    def get_credentials_summary(self, ai_tool_id: str) -> Dict:
        """Retorna resumo das credenciais (sem dados sensíveis)"""
        credentials = self.get_direct_credentials(ai_tool_id)
        
        if not credentials:
            return {"configured": False}

        return {
            "configured": True,
            "username": credentials.username,
            "has_password": bool(credentials.password),
            "login_url": credentials.login_url,
            "is_active": credentials.is_active,
            "login_status": credentials.login_status,
            "failed_attempts": credentials.failed_attempts,
            "max_attempts": credentials.max_attempts,
            "is_valid": credentials.is_valid(),
            "should_retry": credentials.should_retry(),
            "has_selectors": bool(credentials.username_selector and 
                                 credentials.password_selector and 
                                 credentials.submit_selector)
        }

    def update_selectors(self, ai_tool_id: str, username_selector: str = None, 
                        password_selector: str = None, submit_selector: str = None) -> bool:
        """Atualiza seletores CSS de uma IA"""
        session = self.get_session()
        try:
            credentials = session.query(AIDirectCredentials).filter(
                AIDirectCredentials.ai_tool_id == ai_tool_id
            ).first()

            if not credentials:
                return False

            if username_selector:
                credentials.username_selector = username_selector
            if password_selector:
                credentials.password_selector = password_selector
            if submit_selector:
                credentials.submit_selector = submit_selector

            session.commit()
            LOGGER.info(f"Seletores atualizados para IA {ai_tool_id}")
            return True

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao atualizar seletores: {e}")
            return False
        finally:
            session.close()

    def _encrypt_credential(self, credential: str) -> Optional[str]:
        """Criptografa credencial"""
        if not credential or not self._fernet:
            return None
        
        try:
            return self._fernet.encrypt(credential.encode()).decode()
        except Exception as e:
            LOGGER.error(f"Erro ao criptografar credencial: {e}")
            return None

    def _decrypt_credential(self, encrypted_credential: str) -> Optional[str]:
        """Descriptografa credencial"""
        if not encrypted_credential or not self._fernet:
            return None
        
        try:
            return self._fernet.decrypt(encrypted_credential.encode()).decode()
        except Exception as e:
            LOGGER.error(f"Erro ao descriptografar credencial: {e}")
            return None
