# crud/sqlalchemy_expense_manager.py
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func

from crud.base_manager import BaseManager
from database.models.expense import Expense
from utils.logger import LOGGER


class SQLAlchemyExpenseManager(BaseManager[Expense]):
    """Manager de gastos operacionais."""

    def __init__(self):
        super().__init__(Expense)

    def get_all_ordered(self, limit: int = 500) -> List[Expense]:
        """Retorna todos os gastos ordenados por data decrescente."""
        session = self.get_session()
        try:
            return (
                session.query(Expense)
                .order_by(Expense.date.desc(), Expense.created_at.desc())
                .limit(limit)
                .all()
            )
        except Exception as e:
            LOGGER.error(f"Erro ao listar gastos: {e}")
            return []
        finally:
            session.close()

    def get_dashboard_statistics(self) -> dict:
        """Calcula estatisticas para os cards do dashboard."""
        session = self.get_session()
        try:
            now       = datetime.now(timezone.utc)
            today     = now.date()
            mes_inicio = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Total hoje
            hoje_result = (
                session.query(func.sum(Expense.amount))
                .filter(Expense.date >= today)
                .scalar()
            ) or 0

            hoje_count = (
                session.query(func.count(Expense.id))
                .filter(Expense.date >= today)
                .scalar()
            ) or 0

            # Total mes
            mes_result = (
                session.query(func.sum(Expense.amount))
                .filter(Expense.date >= mes_inicio)
                .scalar()
            ) or 0

            mes_count = (
                session.query(func.count(Expense.id))
                .filter(Expense.date >= mes_inicio)
                .scalar()
            ) or 0

            # Maior categoria
            cat_rows = (
                session.query(
                    Expense.category,
                    func.sum(Expense.amount).label("total")
                )
                .group_by(Expense.category)
                .order_by(func.sum(Expense.amount).desc())
                .first()
            )

            maior_cat   = cat_rows.category if cat_rows else "N/A"
            maior_valor = float(cat_rows.total or 0) if cat_rows else 0.0

            # Total geral
            total_geral = float(
                session.query(func.sum(Expense.amount)).scalar() or 0
            )

            return {
                "hoje_valor":   float(hoje_result),
                "hoje_count":   hoje_count,
                "mes_valor":    float(mes_result),
                "mes_count":    mes_count,
                "maior_cat":    maior_cat,
                "maior_valor":  maior_valor,
                "total_geral":  total_geral,
            }

        except Exception as e:
            LOGGER.error(f"Erro ao calcular estatisticas de gastos: {e}")
            return {
                "hoje_valor": 0, "hoje_count": 0,
                "mes_valor": 0,  "mes_count": 0,
                "maior_cat": "N/A", "maior_valor": 0, "total_geral": 0,
            }
        finally:
            session.close()

    def get_by_category_totals(self) -> dict:
        """Retorna totais agrupados por categoria."""
        session = self.get_session()
        try:
            rows = (
                session.query(
                    Expense.category,
                    func.sum(Expense.amount).label("total")
                )
                .group_by(Expense.category)
                .all()
            )
            return {r.category: float(r.total or 0) for r in rows}
        except Exception as e:
            LOGGER.error(f"Erro ao agrupar gastos por categoria: {e}")
            return {}
        finally:
            session.close()

    def get_monthly_totals(self) -> list:
        """Retorna totais agrupados por mes (data, total)."""
        from sqlalchemy import func, cast, Date, extract

        session = self.get_session()
        try:
            rows = (
                session.query(
                    func.date_format(Expense.date, "%m/%Y").label("mes"),
                    func.sum(Expense.amount).label("total")
                )
                .group_by(func.date_format(Expense.date, "%m/%Y"))
                .order_by(func.min(Expense.date))
                .all()
            )
            return [(r.mes, float(r.total or 0)) for r in rows]
        except Exception as e:
            LOGGER.error(f"Erro ao agrupar gastos por mes: {e}")
            return []
        finally:
            session.close()