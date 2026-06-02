# database/models/payment.py (COMPLETAMENTE ATUALIZADO)
from datetime import datetime, timedelta, timezone

from sqlalchemy import (JSON, Column, DateTime, Enum, ForeignKey, Numeric,
                        String, Text)
from sqlalchemy.orm import relationship

from database.models.base import BaseModel
from database.sqlalchemy_config import Base


class Payment(Base, BaseModel):
    """Modelo de pagamento do sistema"""

    __tablename__ = "payments"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)  # Valor
    payment_method = Column(
        Enum("pix", "cartao"), nullable=False
    )  # === DESCRIÇÃO/TIPO DE ASSINATURA ===
    description = Column(
        Enum("Standard", "Premium", "VIP"), nullable=False, default="Standard"
    )
    status = Column(
        Enum("Confirmado", "Atrasado", "Pendente", "Cancelado"), default="Pendente"
    )
    payment_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=False)
    payment_details = Column(JSON, default=dict)
    transaction_id = Column(String(100), unique=True, nullable=True)
    notes = Column(Text, nullable=True)

    # RELACIONAMENTOS
    user = relationship("User", back_populates="payments")

    def __init__(self, **kwargs):
        """Inicializa pagamento com vencimento automático"""
        super().__init__(**kwargs)

        # Se não foi definida data de vencimento, definir para 1 mês após criação
        if not self.due_date:
            self.due_date = datetime.now(timezone.utc) + timedelta(days=30)

    def is_overdue(self) -> bool:
        """Verifica se o pagamento está vencido"""
        return datetime.now(timezone.utc) > self.due_date

    def days_overdue(self) -> int:
        """Retorna quantos dias está em atraso (0 se não vencido)"""
        if not self.is_overdue():
            return 0
        delta = datetime.now(timezone.utc) - self.due_date
        return delta.days

    def mark_as_paid(self, transaction_id: str = None) -> None:
        """Marca pagamento como confirmado"""
        self.status = "confirmado"
        self.payment_date = datetime.now(timezone.utc)
        if transaction_id:
            self.transaction_id = transaction_id

    def mark_as_overdue(self) -> None:
        """Marca pagamento como atrasado"""
        if self.is_overdue() and self.status == "pendente":
            self.status = "atrasado"

    def __repr__(self):
        return f"<Payment(user_id={self.user_id}, amount={self.amount}, status={self.status})>"
