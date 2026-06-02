from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, or_, desc, func

from crud.base_manager import BaseManager
from database.models.notification import Notification
from database.models.user import User
from utils.logger import LOGGER


class NotificationCRUD(BaseManager[Notification]):
    """
    Manager para gerenciar notificações do sistema
    Suporta notificações pessoais e globais
    """

    def __init__(self):
        super().__init__(Notification)
        LOGGER.info("NotificationCRUD inicializado")

    def count_active_users(self) -> int:
        """
        Conta o numero total de usuarios ativos no sistema
        
        Returns:
            Numero de usuarios com status "Ativo"
        """
        session = self.get_session()
        try:
            count = (
                session.query(func.count(User.id))
                .filter(User.status == "Ativo")
                .scalar()
            )
            
            LOGGER.debug(f"Total de usuarios ativos no sistema: {count}")
            return count or 0
            
        except Exception as e:
            LOGGER.error(f"Erro ao contar usuarios ativos: {e}")
            return 0
        finally:
            session.close()

    def create_personal_notification(
        self,
        user_id: str,
        type: str,
        priority: str,
        title: str,
        message: str,
        icon: str = "🔔",
        extra_data: dict = None,
        expires_at: datetime = None,
    ) -> Optional[Notification]:
        """
        Cria uma notificação pessoal para um usuário específico

        Args:
            user_id: ID do usuário
            type: Tipo da notificação (sistema, download, atualizacao, etc)
            priority: Prioridade (normal, importante, critica)
            title: Título da notificação
            message: Mensagem da notificação
            icon: Ícone da notificação (emoji)
            extra_data: Dados extras em formato dict
            expires_at: Data de expiração (opcional)

        Returns:
            Notificação criada ou None em caso de erro
        """
        session = self.get_session()
        try:
            # Verificar se usuário existe
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                LOGGER.error(f"Usuário não encontrado: {user_id}")
                return None

            # Criar notificação
            notification = Notification(
                user_id=user_id,
                is_global=False,
                type=type,
                priority=priority,
                title=title,
                message=message,
                icon=icon,
                extra_data=extra_data or {},
                expires_at=expires_at,
            )

            session.add(notification)
            session.commit()
            session.refresh(notification)

            LOGGER.info(
                f"Notificação pessoal criada: {notification.id} para usuário {user_id}"
            )
            return notification

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao criar notificação pessoal: {e}")
            return None
        finally:
            session.close()

    def create_global_notification(
        self,
        admin_id: str,
        type: str,
        priority: str,
        title: str,
        message: str,
        icon: str = "📢",
        extra_data: dict = None,
        expires_at: datetime = None,
    ) -> Optional[Notification]:
        """
        Cria uma notificação global visível para todos os usuários

        Args:
            admin_id: ID do admin que criou a notificação
            type: Tipo da notificação (admin_broadcast, atualizacao, etc)
            priority: Prioridade (normal, importante, critica)
            title: Título da notificação
            message: Mensagem da notificação
            icon: Ícone da notificação (emoji)
            extra_data: Dados extras em formato dict
            expires_at: Data de expiração (opcional)

        Returns:
            Notificação criada ou None em caso de erro
        """
        session = self.get_session()
        try:
            # Verificar se admin existe e é realmente admin
            admin = session.query(User).filter(User.id == admin_id).first()
            if not admin:
                LOGGER.error(f"Admin não encontrado: {admin_id}")
                return None

            if admin.account_type != "Admin":
                LOGGER.warning(
                    f"Usuário {admin_id} não é admin, mas tentou criar notificação global"
                )
                # Permitir mesmo assim, mas logar warning

            # Criar notificação global
            notification = Notification(
                user_id=None,  # NULL para notificações globais
                is_global=True,
                created_by_admin_id=admin_id,
                type=type,
                priority=priority,
                title=title,
                message=message,
                icon=icon,
                extra_data=extra_data or {},
                expires_at=expires_at,
            )

            session.add(notification)
            session.commit()
            session.refresh(notification)

            LOGGER.info(
                f"Notificação global criada: {notification.id} por admin {admin_id}"
            )
            return notification

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao criar notificação global: {e}")
            return None
        finally:
            session.close()

    def get_user_notifications(
        self,
        user_id: str,
        include_read: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        """
        Busca notificações de um usuário (pessoais + globais)

        Args:
            user_id: ID do usuário
            include_read: Se True, inclui notificações já lidas
            limit: Número máximo de notificações
            offset: Offset para paginação

        Returns:
            Lista de notificações ordenadas por data (mais recentes primeiro)
        """
        session = self.get_session()
        try:
            now = datetime.now(timezone.utc)

            # Query base - notificações não expiradas
            base_filter = or_(
                Notification.expires_at.is_(None), Notification.expires_at > now
            )

            # Notificações pessoais
            personal_query = session.query(Notification).filter(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_global == False,
                    base_filter,
                )
            )

            if not include_read:
                personal_query = personal_query.filter(Notification.is_read == False)

            # Notificações globais
            global_query = session.query(Notification).filter(
                and_(Notification.is_global == True, base_filter)
            )

            # Se não incluir lidas, filtrar apenas globais não lidas pelo usuário
            if not include_read:
                # Usar expressão SQL para verificar se user_id NÃO está no array read_by
                global_query = global_query.filter(
                    ~Notification.read_by.contains([user_id])
                )

            # Unir queries e ordenar
            notifications = (
                personal_query.union(global_query)
                .order_by(desc(Notification.created_at))
                .limit(limit)
                .offset(offset)
                .all()
            )

            return notifications

        except Exception as e:
            LOGGER.error(f"Erro ao buscar notificações do usuário {user_id}: {e}")
            return []
        finally:
            session.close()

    def count_unread(self, user_id: str) -> int:
        """
        Conta notificações não lidas de um usuário

        Args:
            user_id: ID do usuário

        Returns:
            Número de notificações não lidas
        """
        session = self.get_session()
        try:
            now = datetime.now(timezone.utc)

            # Contar notificações pessoais não lidas
            personal_count = (
                session.query(func.count(Notification.id))
                .filter(
                    and_(
                        Notification.user_id == user_id,
                        Notification.is_read == False,
                        Notification.is_global == False,
                        or_(
                            Notification.expires_at.is_(None),
                            Notification.expires_at > now,
                        ),
                    )
                )
                .scalar()
            )

            # Contar notificações globais não lidas
            global_count = (
                session.query(func.count(Notification.id))
                .filter(
                    and_(
                        Notification.is_global == True,
                        ~Notification.read_by.contains([user_id]),
                        or_(
                            Notification.expires_at.is_(None),
                            Notification.expires_at > now,
                        ),
                    )
                )
                .scalar()
            )

            total = (personal_count or 0) + (global_count or 0)

            return total

        except Exception as e:
            LOGGER.error(f"Erro ao contar notificações não lidas: {e}")
            return 0
        finally:
            session.close()

    def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """
        Marca uma notificacao como lida para um usuario
        Para notificacoes globais, verifica se todos leram e atualiza is_read

        Args:
            notification_id: ID da notificação
            user_id: ID do usuário

        Returns:
            True se sucesso, False caso contrário
        """
        session = self.get_session()
        try:
            notification = (
                session.query(Notification)
                .filter(Notification.id == notification_id)
                .first()
            )

            if not notification:
                LOGGER.warning(f"Notificacao nao encontrada: {notification_id}")
                return False

            # Usar metodo do modelo para marcar como lida
            notification.mark_read_by_user(user_id)

            # Se for notificacao global, verificar se todos os usuarios leram
            if notification.is_global:
                total_active_users = self.count_active_users()
                
                if notification.check_if_all_users_read(total_active_users):
                    # Todos os usuarios ativos leram - marcar is_read=True
                    notification.mark_fully_read()
                    LOGGER.info(
                        f"Notificacao global {notification_id} completamente lida por todos os usuarios"
                    )

            session.commit()

            LOGGER.info(
                f"Notificacao {notification_id} marcada como lida por usuario {user_id}"
            )
            return True

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao marcar notificacao como lida: {e}")
            return False
        finally:
            session.close()

    def mark_all_as_read(self, user_id: str) -> int:
        """
        Marca todas as notificações de um usuário como lidas

        Args:
            user_id: ID do usuário

        Returns:
            Número de notificações marcadas como lidas
        """
        session = self.get_session()
        try:
            count = 0

            # Marcar notificações pessoais como lidas
            personal_notifications = (
                session.query(Notification)
                .filter(
                    and_(
                        Notification.user_id == user_id,
                        Notification.is_read == False,
                    )
                )
                .all()
            )

            for notification in personal_notifications:
                notification.is_read = True
                count += 1

            # Marcar notificações globais como lidas (adicionar user_id ao read_by)
            global_notifications = (
                session.query(Notification)
                .filter(
                    and_(
                        Notification.is_global == True,
                        ~Notification.read_by.contains([user_id]),
                    )
                )
                .all()
            )

            # Contar total de usuarios ativos uma vez
            total_active_users = self.count_active_users()

            for notification in global_notifications:
                if not notification.read_by:
                    notification.read_by = []
                if user_id not in notification.read_by:
                    notification.read_by.append(user_id)
                    count += 1
                    
                    # Verificar se todos leram
                    if notification.check_if_all_users_read(total_active_users):
                        notification.mark_fully_read()

            session.commit()

            LOGGER.info(f"{count} notificacoes marcadas como lidas para usuario {user_id}")
            return count

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao marcar todas notificacoes como lidas: {e}")
            return 0
        finally:
            session.close()

    def delete_notification(self, notification_id: str, user_id: str = None) -> bool:
        """
        Deleta uma notificação (apenas pessoais ou se for admin)

        Args:
            notification_id: ID da notificação
            user_id: ID do usuário (para validação de permissão)

        Returns:
            True se sucesso, False caso contrário
        """
        session = self.get_session()
        try:
            notification = (
                session.query(Notification)
                .filter(Notification.id == notification_id)
                .first()
            )

            if not notification:
                LOGGER.warning(f"Notificacao nao encontrada: {notification_id}")
                return False

            # Validar permissões
            if notification.is_global:
                # Apenas admins podem deletar notificações globais
                if user_id:
                    user = session.query(User).filter(User.id == user_id).first()
                    if not user or user.account_type != "Admin":
                        LOGGER.warning(
                            f"Usuario {user_id} tentou deletar notificacao global sem permissao"
                        )
                        return False
            else:
                # Notificações pessoais só podem ser deletadas pelo próprio usuário
                if user_id and notification.user_id != user_id:
                    LOGGER.warning(
                        f"Usuario {user_id} tentou deletar notificacao de outro usuario"
                    )
                    return False

            session.delete(notification)
            session.commit()

            LOGGER.info(f"Notificacao {notification_id} deletada")
            return True

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao deletar notificacao: {e}")
            return False
        finally:
            session.close()

    def delete_expired(self) -> int:
        """
        Remove todas as notificações expiradas do sistema

        Returns:
            Número de notificações removidas
        """
        session = self.get_session()
        try:
            now = datetime.now(timezone.utc)

            # Buscar notificações expiradas
            expired = (
                session.query(Notification)
                .filter(
                    and_(
                        Notification.expires_at.isnot(None),
                        Notification.expires_at <= now,
                    )
                )
                .all()
            )

            count = len(expired)

            for notification in expired:
                session.delete(notification)

            session.commit()

            LOGGER.info(f"{count} notificacoes expiradas removidas")
            return count

        except Exception as e:
            session.rollback()
            LOGGER.error(f"Erro ao remover notificacoes expiradas: {e}")
            return 0
        finally:
            session.close()

    def get_global_notifications_stats(
        self, admin_id: str = None
    ) -> List[dict]:
        """
        Retorna estatísticas de notificações globais para admins

        Args:
            admin_id: ID do admin (se fornecido, retorna apenas suas notificações)

        Returns:
            Lista de dicts com estatísticas de cada notificação global
        """
        session = self.get_session()
        try:
            query = session.query(Notification).filter(Notification.is_global == True)

            if admin_id:
                query = query.filter(Notification.created_by_admin_id == admin_id)

            notifications = query.order_by(desc(Notification.created_at)).all()

            # Contar total de usuários ativos no sistema
            total_users = self.count_active_users()

            stats = []
            for notification in notifications:
                read_count = len(notification.read_by or [])
                stats.append(
                    {
                        "id": notification.id,
                        "title": notification.title,
                        "type": notification.type,
                        "priority": notification.priority,
                        "created_at": notification.created_at,
                        "read_count": read_count,
                        "total_users": total_users,
                        "read_percentage": (
                            (read_count / total_users * 100) if total_users > 0 else 0
                        ),
                        "is_expired": notification.is_expired(),
                    }
                )

            LOGGER.info(f"Estatisticas geradas para {len(stats)} notificacoes globais")
            return stats

        except Exception as e:
            LOGGER.error(f"Erro ao gerar estatisticas de notificacoes globais: {e}")
            return []
        finally:
            session.close()

    def get_by_type(
        self, notification_type: str, user_id: str = None, limit: int = 50
    ) -> List[Notification]:
        """
        Busca notificações por tipo

        Args:
            notification_type: Tipo de notificação
            user_id: ID do usuário (opcional - se fornecido, filtra por usuário)
            limit: Limite de resultados

        Returns:
            Lista de notificações
        """
        session = self.get_session()
        try:
            query = session.query(Notification).filter(Notification.type == notification_type)

            if user_id:
                query = query.filter(
                    or_(
                        Notification.user_id == user_id, Notification.is_global == True
                    )
                )

            notifications = (
                query.order_by(desc(Notification.created_at)).limit(limit).all()
            )

            LOGGER.info(f"Buscadas {len(notifications)} notificacoes do tipo {notification_type}")
            return notifications

        except Exception as e:
            LOGGER.error(f"Erro ao buscar notificacoes por tipo: {e}")
            return []
        finally:
            session.close()