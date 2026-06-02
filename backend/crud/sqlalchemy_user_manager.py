# crud/sqlalchemy_user_manager.py (ATUALIZADO COM BYPASS ADMINISTRATIVO)
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from crud.base_manager import BaseManager
from database.models.user import User
from database.models.user_favorite import UserFavorite
from utils.logger import LOGGER
from utils.security import PasswordSecurity, SecurityError


class SQLAlchemyUserManager(BaseManager[User]):
    """Manager específico para usuários usando SQLAlchemy"""

    def __init__(self):
        super().__init__(User)

    def register_user(
        self,
        username: str,
        password: str,
        email: str,
        name: str,
        phone: str,
        referral_code: str = None,
        cpf: str = None,
        account_type: str = "Membro",
        status: str = "Inativo",
        bypass_referral_validation: bool = False,
    ) -> Tuple[bool, str]:
        """Registra um novo usuário com validações completas"""
        session = self.get_session()
        try:
            # 🔍 VALIDAR CÓDIGO DE INDICAÇÃO (se não for bypass)
            if not bypass_referral_validation:
                if not referral_code or not referral_code.strip():
                    return False, "Código de indicação é obrigatório"

                # Verificar se o código de indicação existe
                referrer = (
                    session.query(User)
                    .filter(User.referral_code == referral_code.strip().upper())
                    .first()
                )

                if not referrer:
                    return False, "Código de indicação inválido"

            # 🔍 Verificações de unicidade existentes
            existing_user = (
                session.query(User)
                .filter(or_(User.username == username, User.email == email))
                .first()
            )
            if existing_user:
                if existing_user.username == username:
                    return False, "Nome de usuário já existe"
                else:
                    return False, "Email já cadastrado"

            # Verificar telefone único
            existing_phone = session.query(User).filter(User.phone == phone).first()
            if existing_phone:
                return False, "Telefone já cadastrado"

            # Verificar CPF se fornecido
            if cpf and cpf.strip():
                existing_cpf = session.query(User).filter(User.cpf == cpf).first()
                if existing_cpf:
                    return False, "CPF já cadastrado"

            # ✅ Validações de formato
            if not self._validate_phone(phone):
                return False, "Formato de telefone inválido"

            if not self._validate_email(email):
                return False, "Formato de email inválido"

            if len(password) < 6:
                return False, "Senha deve ter pelo menos 6 caracteres"

            if len(name.strip()) < 2:
                return False, "Nome deve ter pelo menos 2 caracteres"

            # 🆕 GERAR CÓDIGO DE INDICAÇÃO ÚNICO PARA O NOVO USUÁRIO
            new_referral_code = self._generate_unique_referral_code(session)

            try:
                # 🆕 Criar novo usuário COM código de indicação
                user = User(
                    username=username,
                    email=email,
                    name=name.strip(),
                    phone=self._clean_phone(phone),
                    cpf=cpf.strip() if cpf and cpf.strip() else None,
                    account_type=account_type,
                    status=status,
                    referral_code=new_referral_code,
                )
                user.set_password(password)
            except SecurityError as e:
                return False, str(e)

            session.add(user)
            session.flush()     # gera o user.id sem fechar a sessao
            new_user_id = user.id
            session.commit()

            LOGGER.info(
                f"Usuario registrado: {username} ({name}) - Codigo: {new_referral_code}"
            )

            # Processar recompensas de indicacao fora da sessao principal
            # para garantir que o commit ja foi concluido antes de tentar ler o usuario
            if not bypass_referral_validation and referral_code and referral_code.strip():
                referrer = (
                    session.query(User)
                    .filter(User.referral_code == referral_code.strip().upper())
                    .first()
                )
                if referrer:
                    LOGGER.info(
                        f"Indicado por: {referrer.username} ({referrer.referral_code})"
                    )
                    # Importar aqui para evitar circular import
                    from core.services.reward_service import RewardService
                    RewardService.process_referral_rewards(
                        new_user_id=new_user_id,
                        referrer_user_id=str(referrer.id),
                    )

            return True, new_user_id

        except Exception as e:
            session.rollback()
            self.logger.error(f"Erro ao registrar usuário: {e}")
            return False, f"Erro interno: {str(e)}"
        finally:
            session.close()

    def _generate_unique_referral_code(self, session: Session) -> str:
        """Gera código de indicação único"""
        max_attempts = 10
        for _ in range(max_attempts):
            code = PasswordSecurity.generate_referral_code()

            # Verificar se o código já existe
            existing = session.query(User).filter(User.referral_code == code).first()
            if not existing:
                return code

        # Se não conseguiu gerar um código único, gerar um mais longo
        return PasswordSecurity.generate_referral_code(8)

    def get_user_by_referral_code(self, referral_code: str) -> Optional[User]:
        """Busca usuário pelo código de indicação"""
        session = self.get_session()
        try:
            return (
                session.query(User)
                .filter(User.referral_code == referral_code.strip().upper())
                .first()
            )
        finally:
            session.close()

    def verify_login(self, username_or_email: str, password: str) -> Tuple[bool, str]:
        """Verifica credenciais de login - MODIFICADO PARA SUPORTAR USUÁRIOS INATIVOS"""
        session = self.get_session()
        try:
            user = (
                session.query(User)
                .filter(
                    or_(
                        User.username == username_or_email,
                        User.email == username_or_email,
                    )
                )
                .first()
            )

            if not user:
                return False, "Usuário não encontrado"

            # NOVO: Verificar se usuário está bloqueado ou cancelado (bloquear acesso)
            if user.status in ["Bloqueado", "Cancelado"]:
                return False, f"Conta {user.status.lower()}"

            if not user.verify_password(password):
                return False, "Senha incorreta"

            # MODIFICADO: Permitir login de usuários inativos
            # O controle de acesso será feito na aplicação
            if user.status == "Inativo":
                LOGGER.info(f"Login permitido para usuário inativo: {user.username}")

            # Atualizar último login
            user.last_login = datetime.now(timezone.utc)
            session.commit()

            # NOVO: Retornar ID do usuário junto com o status
            return True, user.id

        except Exception as e:
            session.rollback()
            self.logger.error(f"Erro ao verificar login: {e}")
            return False, str(e)
        finally:
            session.close()

    def update_user_status(self, user_id: str, new_status: str) -> bool:
        """Atualiza status do usuário"""
        session = self.get_session()
        try:
            # Validar status
            valid_statuses = ["Ativo", "Inativo", "Cancelado", "Bloqueado"]
            if new_status not in valid_statuses:
                self.logger.error(f"Status inválido: {new_status}")
                return False

            # Buscar usuário
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                self.logger.error(f"Usuário não encontrado: {user_id}")
                return False

            old_status = user.status
            user.status = new_status

            session.commit()

            self.logger.info(
                f"Status do usuário {user.username} alterado de {old_status} para {new_status}"
            )
            return True

        except Exception as e:
            session.rollback()
            self.logger.error(f"Erro ao atualizar status do usuário: {e}")
            return False
        finally:
            session.close()

    def get_user_status(self, user_id: str) -> Optional[str]:
        """Retorna o status atual do usuário"""
        session = self.get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            return user.status if user else None
        except Exception as e:
            self.logger.error(f"Erro ao buscar status do usuário: {e}")
            return None
        finally:
            session.close()

    def get_by_username(self, username: str) -> Optional[User]:
        """Busca usuário pelo username"""
        session = self.get_session()
        try:
            return session.query(User).filter(User.username == username).first()
        except Exception as e:
            self.logger.error(f"Erro ao buscar usuário por username: {e}")
            return None
        finally:
            session.close()

    def get_user_with_favorites(self, user_id: str) -> Optional[User]:
        """Busca usuário com seus favoritos carregados"""
        session = self.get_session()
        try:
            user = (
                session.query(User)
                .filter(User.id == user_id)
                .options(joinedload(User.favorites).joinedload(UserFavorite.ai_tool))
                .first()
            )
            return user
        finally:
            session.close()

    def get_by_email(self, email: str) -> Optional[User]:
        """Busca usuário pelo email"""
        session = self.get_session()
        try:
            return session.query(User).filter(User.email == email).first()
        except Exception as e:
            self.logger.error(f"Erro ao buscar usuário por email: {e}")
            return None
        finally:
            session.close()

    def get_by_username_or_email(self, username_or_email: str) -> Optional[User]:
        """Busca usuário por username OU email"""
        session = self.get_session()
        try:
            return (
                session.query(User)
                .filter(
                    or_(
                        User.username == username_or_email,
                        User.email == username_or_email
                    )
                )
                .first()
            )
        except Exception as e:
            self.logger.error(f"Erro ao buscar usuário: {e}")
            return None
        finally:
            session.close()

    def generate_recovery_code_for_user(
        self, 
        user_id: str, 
        expiration_minutes: int = 15
    ) -> Tuple[bool, str]:
        """
        Gera código de recuperação de senha para usuário
        
        Args:
            user_id: ID do usuário
            expiration_minutes: Tempo de validade em minutos
            
        Returns:
            Tuple[bool, str]: (sucesso, código_ou_mensagem_erro)
        """
        session = self.get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                return False, "Usuário não encontrado"
            
            # Gerar código usando método do modelo User
            code = user.generate_recovery_code(expiration_minutes)
            
            session.commit()
            
            LOGGER.info(f"Código de recuperação gerado para usuário: {user.username}")
            return True, code
            
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao gerar código de recuperação: {e}")
            return False, f"Erro ao gerar código: {str(e)}"
        finally:
            session.close()

    def validate_recovery_code_for_user(
        self, 
        user_id: str, 
        code: str
    ) -> Tuple[bool, str]:
        """
        Valida código de recuperação do usuário
        
        Args:
            user_id: ID do usuário
            code: Código fornecido
            
        Returns:
            Tuple[bool, str]: (válido, mensagem)
        """
        session = self.get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                return False, "Usuário não encontrado"
            
            # Validar usando método do modelo User
            is_valid, message = user.validate_recovery_code(code)
            
            # Salvar tentativas no banco
            session.commit()
            
            return is_valid, message
            
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao validar código: {e}")
            return False, "Erro ao validar código"
        finally:
            session.close()

    def reset_password_with_code(
        self, 
        user_id: str, 
        new_password: str
    ) -> Tuple[bool, str]:
        """
        Redefine senha do usuário após validação do código
        
        Args:
            user_id: ID do usuário
            new_password: Nova senha
            
        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        session = self.get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                return False, "Usuário não encontrado"
            
            # Validar força da senha
            is_strong, message = PasswordSecurity.is_password_strong(new_password)
            if not is_strong:
                return False, message
            
            # Definir nova senha
            try:
                user.set_password(new_password)
            except SecurityError as e:
                return False, str(e)
            
            # Limpar código de recuperação
            user.clear_recovery_code()
            
            session.commit()
            
            LOGGER.info(f"Senha redefinida com sucesso para: {user.username}")
            return True, "Senha redefinida com sucesso"
            
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao redefinir senha: {e}")
            return False, "Erro ao redefinir senha"
        finally:
            session.close()

    def clear_recovery_code_for_user(self, user_id: str) -> bool:
        """
        Limpa código de recuperação do usuário
        
        Args:
            user_id: ID do usuário
            
        Returns:
            bool: Sucesso da operação
        """
        session = self.get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                return False
            
            user.clear_recovery_code()
            session.commit()
            
            LOGGER.info(f"Código de recuperação limpo para: {user.username}")
            return True
            
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao limpar código: {e}")
            return False
        finally:
            session.close()

    # 🛠️ Métodos auxiliares de validação
    def _validate_phone(self, phone: str) -> bool:
        """Valida formato do telefone"""
        clean_phone = "".join(filter(str.isdigit, phone))
        return len(clean_phone) in [10, 11]

    def _validate_email(self, email: str) -> bool:
        """Validação básica de email"""
        import re

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None

    def _clean_phone(self, phone: str) -> str:
        """Limpa e formata telefone"""
        clean = "".join(filter(str.isdigit, phone))
        if len(clean) == 11:  # Celular com 9
            return f"({clean[:2]}) {clean[2:7]}-{clean[7:]}"
        elif len(clean) == 10:  # Fixo
            return f"({clean[:2]}) {clean[2:6]}-{clean[6:]}"
        else:
            return phone

    def block_user_temporarily(self, user_id: str, reason: str) -> bool:
        """
        Bloqueia usuário temporariamente
        
        Args:
            user_id: ID do usuário
            reason: Motivo do bloqueio (usar constantes de BlockReasons)
            
        Returns:
            bool: True se bloqueou com sucesso
        """
        session = self.get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                LOGGER.error(f"Usuário não encontrado: {user_id}")
                return False
            
            user.block_temporarily(reason)
            session.commit()
            
            LOGGER.info(f"🔒 Usuário {user.username} bloqueado temporariamente: {reason}")
            return True
        
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao bloquear usuário: {e}")
            return False
        finally:
            session.close()

    def unblock_user(self, user_id: str) -> bool:
        """
        Desbloqueia usuário
        
        Args:
            user_id: ID do usuário
            
        Returns:
            bool: True se desbloqueou com sucesso
        """
        session = self.get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                LOGGER.error(f"Usuário não encontrado: {user_id}")
                return False
            
            user.unblock()
            session.commit()
            
            LOGGER.info(f"🔓 Usuário {user.username} desbloqueado")
            return True
        
        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao desbloquear usuário: {e}")
            return False
        finally:
            session.close()

    def is_user_blocked(self, user_id: str) -> bool:
        """
        Verifica se usuário está bloqueado
        
        Args:
            user_id: ID do usuário
            
        Returns:
            bool: True se bloqueado
        """
        session = self.get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                return False
            
            return user.is_blocked()
        
        except Exception as e:
            LOGGER.error(f"Erro ao verificar bloqueio: {e}")
            return False
        finally:
            session.close()
