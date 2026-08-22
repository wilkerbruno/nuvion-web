"""Modelo de pagamento (portado de database/models/payment.py)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.models.base import BaseModel


class Payment(Base, BaseModel):
    """Modelo de pagamento do sistema."""

    __tablename__ = "payments"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    # "usdt" é novo (self-custodial, rede TRC20 — ver app/services/tron_client.py
    # e docs/PAGAMENTOS_CRIPTO.md). "boleto" existiu brevemente na Fase 3 e
    # foi removido por decisão de produto antes de qualquer uso em produção
    # — não fica mais no enum. "cartao" agora tem endpoint de verdade (ver
    # app/services/mercadopago_client.py::charge_card); antes só existia no
    # enum sem implementação.
    payment_method = Column(Enum("pix", "cartao", "usdt"), nullable=False)
    # Valor exato em USDT (6 casas decimais, a precisão do token) usado só
    # por pagamentos "usdt" — serve pra identificar de qual pedido veio uma
    # transferência recebida na carteira compartilhada, já que não geramos
    # um endereço por pedido (ver app/crud/payment.py::generate_unique_usdt_amount).
    # `amount` continua guardando o valor arredondado a 2 casas, só para
    # exibição consistente com os outros métodos.
    crypto_amount = Column(Numeric(18, 6), nullable=True)
    description = Column(Enum("Standard", "Premium", "VIP"), nullable=False, default="Standard")
    status = Column(Enum("Confirmado", "Atrasado", "Pendente", "Cancelado"), default="Pendente")
    payment_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=False)
    payment_details = Column(JSON, default=dict)
    transaction_id = Column(String(100), unique=True, nullable=True)
    notes = Column(Text, nullable=True)

    user = relationship("User", back_populates="payments")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.due_date:
            self.due_date = datetime.now(timezone.utc) + timedelta(days=30)

    def is_overdue(self) -> bool:
        return datetime.now(timezone.utc) > self.due_date

    def days_overdue(self) -> int:
        if not self.is_overdue():
            return 0
        return (datetime.now(timezone.utc) - self.due_date).days

    def mark_as_paid(self, transaction_id: str = None) -> None:
        self.status = "Confirmado"
        self.payment_date = datetime.now(timezone.utc)
        if transaction_id:
            self.transaction_id = transaction_id

    def mark_as_overdue(self) -> None:
        if self.is_overdue() and self.status == "Pendente":
            self.status = "Atrasado"

    def __repr__(self):
        return f"<Payment(user_id={self.user_id}, amount={self.amount}, status={self.status})>"
