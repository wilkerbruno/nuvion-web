# crud/sqlalchemy_payment_manager.py
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from crud.base_manager import BaseManager
from database.models.payment import Payment
from database.models.user import User
from utils.logger import LOGGER


class SQLAlchemyPaymentManager(BaseManager[Payment]):
    """Manager específico para pagamentos usando SQLAlchemy"""

    def __init__(self):
        super().__init__(Payment)

    def create_payment(
        self,
        user_id: str,
        amount: float,
        payment_method: str,
        description: str = "Standard",
        due_date: datetime = None,
    ) -> Optional[Payment]:
        """Cria um novo pagamento"""

        if not due_date:
            due_date = datetime.now(timezone.utc) + timedelta(days=30)

        return self.create(
            user_id=user_id,
            amount=amount,
            payment_method=payment_method,
            description=description,
            due_date=due_date,
            status="pendente",
        )
    

    def get_all_payments_grouped_by_user(self) -> dict:
        """
        Retorna dict {user_id_str: due_date_mais_recente} em UMA query.
        Usado pelo cache de vencimentos de user_section para evitar
        N queries individuais durante populate_user_table.
        """
        from sqlalchemy import func

        session = self.get_session()
        try:
            # Subquery: maior due_date por user_id
            rows = (
                session.query(
                    Payment.user_id,
                    func.max(Payment.due_date).label("max_due")
                )
                .group_by(Payment.user_id)
                .all()
            )
            return {str(row.user_id): row.max_due for row in rows}
        except Exception as e:
            LOGGER.error(f"Erro ao carregar vencimentos agrupados: {e}")
            return {}
        finally:
            session.close()

    def get_user_payments(self, user_id: str) -> List[Payment]:
        """Busca todos os pagamentos de um usuário"""
        session = self.get_session()
        try:
            return (
                session.query(Payment)
                .filter(Payment.user_id == user_id)
                .order_by(Payment.created_at.desc())
                .all()
            )
        finally:
            session.close()

    def get_overdue_payments(self) -> List[Payment]:
        """Busca pagamentos vencidos"""
        session = self.get_session()
        try:
            now = datetime.now(timezone.utc)
            
            # Buscar pagamentos vencidos com join no usuário para filtrar VIP
            overdue_payments = (
                session.query(Payment)
                .join(User)
                .filter(
                    and_(
                        Payment.due_date < now,
                        Payment.status.in_(["Pendente", "Atrasado"]),
                        User.category != "VIP"  # FILTRAR VIP
                    )
                )
                .all()
            )
            
            self.logger.info(
                f"Encontrados {len(overdue_payments)} pagamentos vencidos "
                f"(VIP filtrados automaticamente)"
            )
            
            return overdue_payments
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar pagamentos vencidos: {e}")
            return []
        finally:
            session.close()

    def get_payments_with_users(
        self, limit: int = 100, offset: int = 0
    ) -> List[Payment]:
        """Lista pagamentos com informações do usuário"""
        session = self.get_session()
        try:
            return (
                session.query(Payment)
                .options(joinedload(Payment.user))
                .order_by(Payment.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
        finally:
            session.close()

    def confirm_payment(self, payment_id: str, transaction_id: str = None) -> bool:
        """Confirma um pagamento"""
        session = self.get_session()
        try:
            payment = session.query(Payment).filter(Payment.id == payment_id).first()
            if not payment:
                return False

            payment.mark_as_paid(transaction_id)
            session.commit()

            # Atualizar categoria do usuário se necessário
            self._update_user_category_after_payment(payment)

            return True
        except Exception as e:
            session.rollback()
            self.logger.error(f"Erro ao confirmar pagamento: {e}")
            return False
        finally:
            session.close()

    def _update_user_category_after_payment(self, payment: Payment) -> None:
        """Atualiza categoria do usuário após confirmação do pagamento"""
        session = self.get_session()
        try:
            user = session.query(User).filter(User.id == payment.user_id).first()
            if user and payment.status == "confirmado":
                user.update_category(payment.description)
                user.update_status("ativo")
                session.commit()
        except Exception as e:
            self.logger.error(f"Erro ao atualizar categoria do usuário: {e}")
        finally:
            session.close()

    def get_statistics(self) -> dict:
        """Retorna estatísticas de pagamentos"""
        session = self.get_session()
        try:
            today = datetime.now(timezone.utc).date()

            # Total confirmado hoje
            confirmed_today = (
                session.query(Payment)
                .filter(
                    and_(
                        Payment.payment_date.isnot(None),
                        Payment.payment_date >= today,
                        Payment.status == "confirmado",
                    )
                )
                .count()
            )

            # Total pendente
            pending_count = (
                session.query(Payment).filter(Payment.status == "pendente").count()
            )

            # Total vencido
            overdue_count = len(self.get_overdue_payments())

            return {
                "confirmed_today": confirmed_today,
                "pending_count": pending_count,
                "overdue_count": overdue_count,
                "last_update": datetime.now(timezone.utc),
            }
        finally:
            session.close()







    def get_dashboard_statistics(self) -> dict:
        """
        Estatisticas reais para o dashboard de gestao de pagamentos.
        Corrige o case dos status — banco armazena com inicial maiuscula.
        """
        from sqlalchemy import func
        from datetime import datetime, timezone

        session = self.get_session()
        try:
            now     = datetime.now(timezone.utc)
            today   = now.date()
            mes_ini = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Total arrecadado hoje (pagamentos confirmados com payment_date de hoje)
            # Total arrecadado hoje
            hoje_valor = (
                session.query(func.sum(Payment.amount))
                .filter(
                    Payment.status == "Confirmado",
                    Payment.payment_date >= today,
                )
                .scalar()
            ) or 0

            hoje_count = (
                session.query(func.count(Payment.id))
                .filter(
                    Payment.status == "Confirmado",
                    Payment.payment_date >= today,
                )
                .scalar()
            ) or 0

            # Contagem hoje
            hoje_count = (
                session.query(func.count(Payment.id))
                .filter(
                    Payment.status == "Confirmado",
                    Payment.payment_date >= today,
                )
                .scalar()
            ) or 0

            # Pendentes
            pendente_valor = (
                session.query(func.sum(Payment.amount))
                .filter(Payment.status == "Pendente")
                .scalar()
            ) or 0

            pendente_count = (
                session.query(func.count(Payment.id))
                .filter(Payment.status == "Pendente")
                .scalar()
            ) or 0

            # Este mes
            mes_valor = (
                session.query(func.sum(Payment.amount))
                .filter(
                    Payment.status == "Confirmado",
                    Payment.payment_date >= mes_ini,
                )
                .scalar()
            ) or 0

            mes_count = (
                session.query(func.count(Payment.id))
                .filter(
                    Payment.status == "Confirmado",
                    Payment.payment_date >= mes_ini,
                )
                .scalar()
            ) or 0

            # Taxa de sucesso (confirmados / total com status final)
            total_finalizados = (
                session.query(func.count(Payment.id))
                .filter(
                    Payment.status.in_(["Confirmado", "Cancelado", "Atrasado"])
                )
                .scalar()
            ) or 0

            total_confirmados = (
                session.query(func.count(Payment.id))
                .filter(Payment.status == "Confirmado")
                .scalar()
            ) or 0

            taxa = (
                round((total_confirmados / total_finalizados) * 100, 1)
                if total_finalizados > 0 else 0
            )

            return {
                "hoje_valor":    float(hoje_valor),
                "hoje_count":    hoje_count,
                "pendente_valor": float(pendente_valor),
                "pendente_count": pendente_count,
                "mes_valor":     float(mes_valor),
                "mes_count":     mes_count,
                "taxa_sucesso":  taxa,
                "total_confirmados": total_confirmados,
            }

        except Exception as e:
            LOGGER.error(f"Erro ao calcular estatisticas do dashboard: {e}")
            return {
                "hoje_valor": 0, "hoje_count": 0,
                "pendente_valor": 0, "pendente_count": 0,
                "mes_valor": 0, "mes_count": 0,
                "taxa_sucesso": 0, "total_confirmados": 0,
            }
        finally:
            session.close()

    def get_all_payments_grouped_by_user(self) -> dict:
        """
        Retorna dict {user_id_str: due_date_mais_recente} em UMA query.
        Usado pelo cache de vencimentos de user_section.
        """
        from sqlalchemy import func

        session = self.get_session()
        try:
            rows = (
                session.query(
                    Payment.user_id,
                    func.max(Payment.due_date).label("max_due")
                )
                .group_by(Payment.user_id)
                .all()
            )
            return {str(row.user_id): row.max_due for row in rows}
        except Exception as e:
            LOGGER.error(f"Erro ao carregar vencimentos agrupados: {e}")
            return {}
        finally:
            session.close()