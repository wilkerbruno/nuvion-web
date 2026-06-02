# crud/sqlalchemy_cookie_session_manager.py
"""
Manager CRUD para sessões de cookies das IAs
Segue o padrão do projeto herdando de BaseManager
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

from sqlalchemy import and_

from crud.base_manager import BaseManager
from database.models.ai_session_cookies import AISessionCookies
from utils.logger import LOGGER


class SQLAlchemyCookieSessionManager(BaseManager[AISessionCookies]):
    """Manager para operações CRUD de sessões de cookies"""

    def __init__(self):
        super().__init__(AISessionCookies)
        LOGGER.info("SQLAlchemyCookieSessionManager inicializado")

    # ========== CREATE ==========
    def create_cookie_session(
        self,
        ai_tool_id: str,
        cookies_data: List[Dict],
        source_file: str = "nova_ia_form"
    ) -> Tuple[bool, str]:
        """
        Cria uma nova sessão de cookies no banco de dados
        
        Args:
            ai_tool_id: ID da IA
            cookies_data: Lista de cookies já normalizados e validados
            source_file: Origem dos cookies
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem ou ID)
        """
        session = self.get_session()
        try:
            # Verificar se já existe sessão para esta IA
            existing = (
                session.query(AISessionCookies)
                .filter(AISessionCookies.ai_tool_id == ai_tool_id)
                .first()
            )
            
            if existing:
                LOGGER.warning(
                    f"Já existe sessão de cookies para IA {ai_tool_id}. "
                    f"Use update_cookie_session() para atualizar."
                )
                return False, "Sessão de cookies já existe para esta IA"
            
            # Importar helper para processar cookies
            from core.utils.cookie_helper import CookieHelper
            
            # Extrair metadados dos cookies
            domain = CookieHelper.extract_domain_from_cookies(cookies_data)
            expires_at = CookieHelper.calculate_expiration(cookies_data)
            
            # Criar nova sessão
            cookie_session = AISessionCookies(
                ai_tool_id=ai_tool_id,
                cookies_data=cookies_data,
                imported_from="direct",
                source_file=source_file,
                cookies_count=len(cookies_data),
                domain_extracted=domain,
                expires_at=expires_at,
                status="active",
                is_active=True,
                is_enabled=True,
            )
            
            session.add(cookie_session)
            session.commit()
            session.refresh(cookie_session)
            
            LOGGER.info(
                f"✅ Sessão de cookies criada para IA {ai_tool_id} "
                f"(ID: {cookie_session.id}, {cookie_session.cookies_count} cookies)"
            )
            
            return True, cookie_session.id

        except Exception as e:
            session.rollback()
            LOGGER.error(f"❌ Erro ao criar sessão de cookies: {e}")
            return False, str(e)
        finally:
            session.close()

    # ========== READ ==========
    def get_cookie_session_by_ai(self, ai_tool_id: str) -> Optional[AISessionCookies]:
        """
        Busca sessão de cookies de uma IA
        
        Args:
            ai_tool_id: ID da IA
            
        Returns:
            AISessionCookies ou None
        """
        session = self.get_session()
        try:
            cookie_session = (
                session.query(AISessionCookies)
                .filter(AISessionCookies.ai_tool_id == ai_tool_id)
                .first()
            )
            
            if cookie_session:
                LOGGER.info(
                    f"Sessão de cookies encontrada para IA {ai_tool_id}: "
                    f"{cookie_session.cookies_count} cookies, status: {cookie_session.status}"
                )
            else:
                LOGGER.info(f"Nenhuma sessão de cookies encontrada para IA {ai_tool_id}")
            
            return cookie_session

        except Exception as e:
            LOGGER.error(f"Erro ao buscar sessão de cookies: {e}")
            return None
        finally:
            session.close()

    def get_active_cookie_session(self, ai_tool_id: str) -> Optional[AISessionCookies]:
        """
        Busca sessão de cookies ATIVA de uma IA
        
        Args:
            ai_tool_id: ID da IA
            
        Returns:
            AISessionCookies ativa ou None
        """
        session = self.get_session()
        try:
            cookie_session = (
                session.query(AISessionCookies)
                .filter(
                    and_(
                        AISessionCookies.ai_tool_id == ai_tool_id,
                        AISessionCookies.is_active == True,
                        AISessionCookies.is_enabled == True
                    )
                )
                .first()
            )
            
            # Verificar se sessão ainda é válida
            if cookie_session and cookie_session.is_valid():
                LOGGER.info(f"Sessão de cookies ativa encontrada para IA {ai_tool_id}")
                return cookie_session
            elif cookie_session:
                LOGGER.warning(f"Sessão de cookies encontrada mas expirada para IA {ai_tool_id}")
                return None
            else:
                LOGGER.info(f"Nenhuma sessão ativa para IA {ai_tool_id}")
                return None

        except Exception as e:
            LOGGER.error(f"Erro ao buscar sessão ativa: {e}")
            return None
        finally:
            session.close()

    def get_active_cookies_dict(self, ai_tool_id: str) -> Optional[Dict]:
        """
        Retorna cookies ativos em formato dict para uso direto
        
        Args:
            ai_tool_id: ID da IA
            
        Returns:
            Dict com dados dos cookies ou None
        """
        cookie_session = self.get_active_cookie_session(ai_tool_id)
        
        if not cookie_session:
            return None
        
        return {
            "id": cookie_session.id,
            "ai_tool_id": cookie_session.ai_tool_id,
            "cookies_data": cookie_session.cookies_data,
            "cookies_count": cookie_session.cookies_count,
            "domain_extracted": cookie_session.domain_extracted,
            "status": cookie_session.status,
            "is_active": cookie_session.is_active,
            "is_enabled": cookie_session.is_enabled,
            "expires_at": cookie_session.expires_at,
            "source_file": cookie_session.source_file,
            "imported_from": cookie_session.imported_from,
            "created_at": cookie_session.created_at,
            "updated_at": cookie_session.updated_at,
        }

    # ========== UPDATE ==========
    def update_cookie_session(
        self,
        ai_tool_id: str,
        new_cookies: List[Dict],
        source_file: str = None
    ) -> Tuple[bool, str]:
        """
        Atualiza cookies de uma IA existente
        
        Args:
            ai_tool_id: ID da IA
            new_cookies: Lista de novos cookies já validados
            source_file: Origem dos novos cookies (opcional)
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        session = self.get_session()
        try:
            # Buscar sessão existente
            cookie_session = (
                session.query(AISessionCookies)
                .filter(AISessionCookies.ai_tool_id == ai_tool_id)
                .first()
            )
            
            if not cookie_session:
                LOGGER.warning(
                    f"Sessão de cookies não encontrada para IA {ai_tool_id}. "
                    f"Use create_cookie_session() para criar."
                )
                return False, "Sessão de cookies não encontrada"
            
            # Atualizar cookies usando método do modelo
            cookie_session.update_cookies(new_cookies, source_file)
            
            session.commit()
            
            LOGGER.info(
                f"✅ Cookies atualizados para IA {ai_tool_id} "
                f"({cookie_session.cookies_count} cookies)"
            )
            
            return True, "Cookies atualizados com sucesso"

        except Exception as e:
            session.rollback()
            LOGGER.error(f"❌ Erro ao atualizar cookies: {e}")
            return False, str(e)
        finally:
            session.close()

    def create_or_update_cookie_session(
        self,
        ai_tool_id: str,
        cookies_data: List[Dict],
        source_file: str = "nova_ia_form",
        custom_expiration: datetime = None
    ) -> Tuple[bool, str]:
        """
        Cria ou atualiza sessão de cookies com suporte a data customizada
        
        Args:
            ai_tool_id: ID da IA
            cookies_data: Lista de cookies validados
            source_file: Origem dos cookies
            custom_expiration: Data de expiração customizada (OPCIONAL)
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        session = self.get_session()
        try:
            # Verificar se existe
            existing = (
                session.query(AISessionCookies)
                .filter(AISessionCookies.ai_tool_id == ai_tool_id)
                .first()
            )
            
            if existing:
                # Atualizar existente
                existing.update_cookies(cookies_data, source_file)
                
                # Aplicar data customizada se fornecida
                if custom_expiration:
                    existing.expires_at = custom_expiration
                    LOGGER.info(f"📅 Data customizada: {custom_expiration.strftime('%Y-%m-%d %H:%M:%S')}")
                
                session.commit()
                
                # *** CALCULAR DIAS COM PROTEÇÃO DE TIMEZONE ***
                try:
                    if existing.expires_at:
                        exp_at = existing.expires_at
                        if exp_at.tzinfo is None:
                            exp_at = exp_at.replace(tzinfo=timezone.utc)
                        days_left = (exp_at - datetime.now(timezone.utc)).days
                    else:
                        days_left = 0
                except Exception as e:
                    LOGGER.warning(f"Erro ao calcular dias: {e}")
                    days_left = 0
                
                LOGGER.info(
                    f"✅ Cookies atualizados para IA {ai_tool_id}\n"
                    f"   Cookies: {existing.cookies_count}\n"
                    f"   Expira em: {days_left} dias"
                )
                
                return True, "Cookies atualizados com sucesso"
            else:
                # Criar novo
                from core.utils.cookie_helper import CookieHelper
                
                domain = CookieHelper.extract_domain_from_cookies(cookies_data)
                
                # Usar data customizada ou calcular
                if custom_expiration:
                    expires_at = custom_expiration
                    LOGGER.info(f"📅 Usando data customizada: {custom_expiration.strftime('%Y-%m-%d')}")
                else:
                    expires_at = CookieHelper.calculate_expiration(cookies_data)
                    LOGGER.info("📅 Usando data calculada automaticamente")
                
                cookie_session = AISessionCookies(
                    ai_tool_id=ai_tool_id,
                    cookies_data=cookies_data,
                    imported_from="direct",
                    source_file=source_file,
                    cookies_count=len(cookies_data),
                    domain_extracted=domain,
                    expires_at=expires_at,
                    status="active",
                    is_active=True,
                    is_enabled=True,
                )
                
                session.add(cookie_session)
                session.commit()
                
                # *** CALCULAR DIAS COM PROTEÇÃO DE TIMEZONE ***
                try:
                    if expires_at:
                        exp_at = expires_at
                        if exp_at.tzinfo is None:
                            exp_at = exp_at.replace(tzinfo=timezone.utc)
                        days_left = (exp_at - datetime.now(timezone.utc)).days
                    else:
                        days_left = 0
                except Exception as e:
                    LOGGER.warning(f"Erro ao calcular dias: {e}")
                    days_left = 0
                
                LOGGER.info(
                    f"✅ Nova sessão criada para IA {ai_tool_id}\n"
                    f"   Cookies: {len(cookies_data)}\n"
                    f"   Expira em: {days_left} dias"
                )
                
                return True, "Cookies salvos com sucesso"

        except Exception as e:
            session.rollback()
            LOGGER.error(f"❌ Erro ao criar/atualizar cookies: {e}")
            import traceback
            LOGGER.error(traceback.format_exc())
            return False, str(e)
        finally:
            session.close()

    # ========== DELETE ==========
    def delete_cookie_session(self, ai_tool_id: str) -> Tuple[bool, str]:
        """Remove sessão de cookies de uma IA"""
        session = self.get_session()
        try:
            deleted_count = (
                session.query(AISessionCookies)
                .filter(AISessionCookies.ai_tool_id == ai_tool_id)
                .delete()
            )
            
            session.commit()
            
            if deleted_count > 0:
                LOGGER.info(f"✅ Sessão removida para IA {ai_tool_id}")
                return True, "Sessão removida com sucesso"
            else:
                LOGGER.warning(f"Nenhuma sessão encontrada (IA {ai_tool_id})")
                return False, "Nenhuma sessão encontrada"

        except Exception as e:
            session.rollback()
            LOGGER.error(f"❌ Erro ao remover: {e}")
            return False, str(e)
        finally:
            session.close()

    # ========== MÉTODOS AUXILIARES ==========
    def get_cookie_session_summary(self, ai_tool_id: str) -> Dict:
        """Retorna resumo da sessão"""
        cookie_session = self.get_cookie_session_by_ai(ai_tool_id)
        
        if not cookie_session:
            return {"configured": False, "ai_tool_id": ai_tool_id}
        
        return {
            "configured": True,
            "ai_tool_id": ai_tool_id,
            "cookies_count": cookie_session.cookies_count,
            "domain": cookie_session.domain_extracted,
            "status": cookie_session.status,
            "is_active": cookie_session.is_active,
            "is_valid": cookie_session.is_valid(),
            "expires_at": cookie_session.expires_at.isoformat() if cookie_session.expires_at else None,
            "created_at": cookie_session.created_at.isoformat() if cookie_session.created_at else None,
            "updated_at": cookie_session.updated_at.isoformat() if cookie_session.updated_at else None,
            "source_file": cookie_session.source_file
        }

    def mark_session_as_expired(self, ai_tool_id: str) -> bool:
        """Marca sessão como expirada"""
        session = self.get_session()
        try:
            cookie_session = (
                session.query(AISessionCookies)
                .filter(AISessionCookies.ai_tool_id == ai_tool_id)
                .first()
            )
            
            if cookie_session:
                cookie_session.mark_as_expired()
                session.commit()
                LOGGER.info(f"Sessão marcada como expirada: {ai_tool_id}")
                return True
            
            return False

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao marcar como expirada: {e}")
            return False
        finally:
            session.close()

    def mark_session_as_invalid(self, ai_tool_id: str) -> bool:
        """Marca sessão como inválida"""
        session = self.get_session()
        try:
            cookie_session = (
                session.query(AISessionCookies)
                .filter(AISessionCookies.ai_tool_id == ai_tool_id)
                .first()
            )
            
            if cookie_session:
                cookie_session.mark_as_invalid()
                session.commit()
                LOGGER.info(f"Sessão marcada como inválida: {ai_tool_id}")
                return True
            
            return False

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao marcar como inválida: {e}")
            return False
        finally:
            session.close()

    def get_all_active_sessions(self) -> List[AISessionCookies]:
        """Retorna todas as sessões ativas"""
        session = self.get_session()
        try:
            sessions = (
                session.query(AISessionCookies)
                .filter(
                    and_(
                        AISessionCookies.is_active == True,
                        AISessionCookies.is_enabled == True
                    )
                )
                .all()
            )
            
            LOGGER.info(f"Encontradas {len(sessions)} sessões ativas")
            return sessions

        except Exception as e:
            LOGGER.error(f"Erro ao buscar sessões: {e}")
            return []
        finally:
            session.close()