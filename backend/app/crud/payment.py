"""Pagamentos — porta de crud/sqlalchemy_payment_manager.py.

Diferença de fundo em relação ao desktop: lá, quem confirmava o pagamento e
reativava o usuário era `PaymentPage.reactivate_user_account`/
`renew_user_subscription`, chamado depois que uma `QThread`
(`PaymentStatusChecker`) detectava `status == 'approved'` fazendo polling a
cada 5s. Aqui isso vira `mark_paid_and_renew`, chamado tanto pelo webhook
real do Mercado Pago quanto pela rota `GET /payments/{id}` quando o painel
consulta um pagamento ainda pendente (ver app/api/routes/payments.py) — e é
idempotente, porque o Mercado Pago pode reenviar a mesma notificação de
webhook mais de uma vez.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.logging import LOGGER
from app.models.payment import Payment
from app.models.user import User


def create_payment(
    db: Session,
    *,
    user_id: str,
    amount: float,
    payment_method: str,
    description: str,
    due_date: Optional[datetime] = None,
    crypto_amount: Optional[float] = None,
) -> Payment:
    payment = Payment(
        user_id=user_id,
        amount=amount,
        payment_method=payment_method,
        description=description,
        status="Pendente",
        due_date=due_date,
        crypto_amount=crypto_amount,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def generate_unique_usdt_amount(db: Session, base_amount: float) -> float:
    """Gera um valor em USDT único (até a 6ª casa decimal — a precisão do
    token na rede TRC20) entre os pagamentos "usdt" ainda pendentes e não
    vencidos. Como usamos UMA carteira compartilhada em vez de um endereço
    por pedido (ver docs/PAGAMENTOS_CRIPTO.md), esse valor exclusivo é como
    identificamos de qual pedido veio uma transferência recebida —
    incrementa de 0.000001 em 0.000001 até achar um valor livre.
    """
    increment = 0.000001
    candidate = round(base_amount, 6)
    now = datetime.now(timezone.utc)

    for _ in range(1000):
        exists = (
            db.query(Payment)
            .filter(
                Payment.payment_method == "usdt",
                Payment.status == "Pendente",
                Payment.crypto_amount == candidate,
                Payment.due_date > now,
            )
            .first()
        )
        if exists is None:
            return candidate
        candidate = round(candidate + increment, 6)

    raise RuntimeError(
        "Não foi possível gerar um valor único em USDT — muitos pagamentos pendentes simultâneos"
    )


def get_by_id(db: Session, payment_id: str) -> Optional[Payment]:
    return db.query(Payment).filter(Payment.id == payment_id).first()


def get_by_transaction_id(db: Session, transaction_id: str) -> Optional[Payment]:
    return db.query(Payment).filter(Payment.transaction_id == transaction_id).first()


def get_user_payments(db: Session, user_id: str) -> List[Payment]:
    return (
        db.query(Payment)
        .filter(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc())
        .all()
    )


def get_overdue_payments(db: Session) -> List[Payment]:
    """Usuários VIP são isentos de cobrança — mesma regra do
    PaymentScheduler original. Não há ainda um agendador rodando isto em
    produção (o desktop usava QTimer; a versão web precisa de um cron/job
    externo batendo num endpoint admin — ver TODO na Fase 4/5)."""
    now = datetime.now(timezone.utc)
    return (
        db.query(Payment)
        .join(User)
        .filter(
            and_(
                Payment.due_date < now,
                Payment.status.in_(["Pendente", "Atrasado"]),
                User.category != "VIP",
            )
        )
        .all()
    )


def mark_paid_and_renew(db: Session, payment: Payment, transaction_id: Optional[str] = None) -> Payment:
    if payment.status == "Confirmado":
        LOGGER.info(f"Pagamento {payment.id} já estava confirmado — ignorando (idempotência)")
        return payment

    payment.mark_as_paid(transaction_id)

    user = payment.user or db.query(User).filter(User.id == payment.user_id).first()
    if user is not None:
        user.update_category(payment.description)
        user.status = "Ativo"
        user.renew_subscription()
        LOGGER.info(
            f"Usuário {user.username} renovado após pagamento {payment.id} "
            f"({payment.description}) — vencimento: {user.payment_due_date}"
        )
    else:
        LOGGER.error(f"Pagamento {payment.id} confirmado mas usuário {payment.user_id} não encontrado")

    db.commit()
    db.refresh(payment)
    return payment


def mark_failed(db: Session, payment: Payment, status: str = "Cancelado") -> Payment:
    if payment.status == "Confirmado":
        # Nunca reverter um pagamento já confirmado por uma notificação
        # atrasada/fora de ordem do Mercado Pago.
        return payment
    payment.status = status
    db.commit()
    db.refresh(payment)
    return payment
