# database/models/expense.py
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, Numeric, String, Text

from database.models.base import BaseModel
from database.sqlalchemy_config import Base


class Expense(Base, BaseModel):
    """Modelo de gastos operacionais da plataforma."""

    __tablename__ = "expenses"

    date = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    description = Column(String(255), nullable=False)
    category = Column(
        Enum(
            "Infraestrutura",
            "APIs",
            "Licencas",
            "Marketing",
            "Outros",
            name="expense_category",
        ),
        nullable=False,
        default="Outros",
    )
    amount = Column(Numeric(10, 2), nullable=False, default=0)
    responsible = Column(String(100), nullable=True)
    status = Column(
        Enum(
            "Aprovado",
            "Pendente",
            "Recusado",
            "Processando",
            name="expense_status",
        ),
        nullable=False,
        default="Pendente",
    )
    notes = Column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<Expense("
            f"description={self.description}, "
            f"amount={self.amount}, "
            f"status={self.status}"
            f")>"
        )