"""Modelo de usuário (portado de database/models/user.py).

Toda a regra de negócio (bloqueio, recuperação de senha, ciclo de
vencimento de assinatura) é a mesma do desktop — não dependia de nada
específico de Qt. O que muda no resto do sistema é que a sessão deixa de
ser local (ver core/security.py, que agora emite JWT em vez de gravar
sessão em disco).
"""
import logging
from calendar import monthrange
from datetime import datetime, timedelta, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, Integer, String, Text

from app.core.security import PasswordSecurity, SecurityError
from app.db.base_class import Base
from app.models.base import BaseModel

logger = logging.getLogger(__name__)


class User(Base, BaseModel):
    """Modelo de usuário do sistema."""

    __tablename__ = "users"
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    name = Column(String(100), nullable=False)
    cpf = Column(String(20), unique=True, nullable=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    avatar_url = Column(Text)
    referral_code = Column(String(6), unique=True, nullable=False, index=True)
    account_type = Column(
        Enum("Admin", "Equipe", "Membro", "Convidado", "Avulso"), default="Membro"
    )
    status = Column(Enum("Ativo", "Inativo", "Cancelado", "Bloqueado"), default="Inativo")
    category = Column(Enum("Standard", "Premium", "VIP"), default="Standard")

    last_login = Column(DateTime)
    password_changed_at = Column(DateTime)
    last_payment_check = Column(DateTime)

    payment_due_date = Column(
        DateTime,
        nullable=True,
        index=True,
        comment="Data de vencimento da assinatura do usuário",
    )

    profile_settings = Column(JSON, default=dict)

    is_temporarily_blocked = Column(Boolean, default=False, nullable=False, index=True)
    block_reason = Column(String(100), nullable=True)
    blocked_at = Column(DateTime, nullable=True)

    recovery_code = Column(String(5), nullable=True)
    recovery_code_created_at = Column(DateTime, nullable=True)
    recovery_code_expires_at = Column(DateTime, nullable=True)
    recovery_attempts = Column(Integer, default=0)

    def set_password(self, password: str) -> None:
        is_strong, message = PasswordSecurity.is_password_strong(password)
        if not is_strong:
            raise SecurityError(message)
        self.password_hash = PasswordSecurity.hash_password(password)
        self.password_changed_at = datetime.now(timezone.utc)
        logger.info(f"Senha alterada para usuário: {self.username}")

    def verify_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return PasswordSecurity.verify_password(password, self.password_hash)

    def update_category(self, new_category: str) -> None:
        if new_category in ["Standard", "Premium", "VIP"]:
            self.category = new_category
            logger.info(f"Categoria atualizada para: {new_category}")

    def generate_recovery_code(self, expiration_minutes: int = 15) -> str:
        import secrets
        import string

        characters = (
            string.ascii_uppercase.replace("O", "").replace("I", "")
            + string.digits.replace("0", "").replace("1", "")
        )
        code = "".join(secrets.choice(characters) for _ in range(5))

        self.recovery_code = code
        self.recovery_code_created_at = datetime.now(timezone.utc)
        self.recovery_code_expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=expiration_minutes
        )
        self.recovery_attempts = 0
        logger.info(f"Código de recuperação gerado para usuário: {self.username}")
        return code

    def validate_recovery_code(self, code: str) -> tuple:
        if not self.recovery_code:
            return False, "Nenhum código de recuperação ativo"

        try:
            now = datetime.now(timezone.utc)
            expires_at = self.recovery_code_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now > expires_at:
                return False, "Código expirado. Solicite um novo código"
        except Exception as e:
            logger.error(f"Erro ao verificar expiração do código: {e}")
            return False, "Erro ao validar código"

        if self.recovery_attempts >= 3:
            return False, "Número máximo de tentativas excedido. Solicite um novo código"

        if code.upper() != self.recovery_code.upper():
            self.recovery_attempts += 1
            logger.warning(
                f"Tentativa inválida de recuperação para {self.username} "
                f"(tentativa {self.recovery_attempts}/3)"
            )
            return False, f"Código inválido. Restam {3 - self.recovery_attempts} tentativas"

        logger.info(f"Código de recuperação validado com sucesso para: {self.username}")
        return True, "Código válido"

    def clear_recovery_code(self) -> None:
        self.recovery_code = None
        self.recovery_code_created_at = None
        self.recovery_code_expires_at = None
        self.recovery_attempts = 0
        logger.info(f"Código de recuperação limpo para usuário: {self.username}")

    def is_recovery_code_expired(self) -> bool:
        if not self.recovery_code or not self.recovery_code_expires_at:
            return True
        try:
            now = datetime.now(timezone.utc)
            expires_at = self.recovery_code_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            return now > expires_at
        except Exception as e:
            logger.error(f"Erro ao verificar expiração: {e}")
            return True

    def block_temporarily(self, reason: str) -> None:
        self.is_temporarily_blocked = True
        self.block_reason = reason
        self.blocked_at = datetime.now(timezone.utc)
        logger.info(f"Usuário {self.username} bloqueado temporariamente: {reason}")

    def unblock(self) -> None:
        self.is_temporarily_blocked = False
        self.block_reason = None
        self.blocked_at = None
        logger.info(f"Usuário {self.username} desbloqueado")

    def is_blocked(self) -> bool:
        return self.is_temporarily_blocked or self.status == "Bloqueado"

    def get_block_message(self) -> str:
        if self.is_temporarily_blocked:
            return f"Conta bloqueada temporariamente: {self.block_reason or 'Motivo não especificado'}"
        elif self.status == "Bloqueado":
            return "Conta bloqueada permanentemente. Entre em contato com o suporte."
        else:
            return "Conta não está bloqueada"

    def initialize_payment_due_date(self) -> None:
        self.payment_due_date = datetime.now(timezone.utc)
        logger.info(
            f"Vencimento inicial definido para {self.payment_due_date.strftime('%d/%m/%Y')} "
            f"(dia {self.payment_due_date.day}) - Usuário: {self.username}"
        )

    def set_payment_due_date_by_day(self, day: int) -> None:
        if not 1 <= day <= 31:
            raise ValueError("Dia deve estar entre 1 e 31")

        now = datetime.now(timezone.utc)
        current_year = now.year
        current_month = now.month
        max_day_in_month = monthrange(current_year, current_month)[1]
        target_day = min(day, max_day_in_month)

        try:
            due_date = now.replace(day=target_day, hour=23, minute=59, second=59)
        except ValueError:
            due_date = now.replace(day=max_day_in_month, hour=23, minute=59, second=59)

        if due_date < now:
            due_date = self._add_months(due_date, 1)

        self.payment_due_date = due_date
        logger.info(
            f"Vencimento definido para {self.payment_due_date.strftime('%d/%m/%Y')} "
            f"(dia {target_day}) - Usuário: {self.username}"
        )

    def renew_subscription(self) -> None:
        if not self.payment_due_date:
            self.initialize_payment_due_date()
            self.payment_due_date = self.payment_due_date + timedelta(days=30)
            logger.warning(
                f"Usuário sem vencimento definido - Inicializando para daqui 30 dias: {self.username}"
            )
            return

        fixed_day = self.payment_due_date.day
        next_due_date = self._add_months(self.payment_due_date, 1)

        if next_due_date.day != fixed_day:
            year = next_due_date.year
            month = next_due_date.month
            max_day = monthrange(year, month)[1]
            next_due_date = next_due_date.replace(day=min(fixed_day, max_day))

        self.payment_due_date = next_due_date

        if self.status == "Inativo":
            self.status = "Ativo"
            logger.info(f"Usuário reativado após pagamento: {self.username}")

        self.last_payment_check = datetime.now(timezone.utc)
        logger.info(
            f"Assinatura renovada - Novo vencimento: {self.payment_due_date.strftime('%d/%m/%Y')} "
            f"(dia {self.payment_due_date.day}) - Usuário: {self.username}"
        )

    def _add_months(self, source_date: datetime, months: int) -> datetime:
        month = source_date.month - 1 + months
        year = source_date.year + month // 12
        month = month % 12 + 1
        max_day = monthrange(year, month)[1]
        day = min(source_date.day, max_day)
        return source_date.replace(year=year, month=month, day=day)

    def is_payment_overdue(self) -> bool:
        if not self.payment_due_date:
            return False
        due = self.payment_due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > due

    def days_until_due(self) -> int:
        if not self.payment_due_date:
            return 0
        due = self.payment_due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        return (due - datetime.now(timezone.utc)).days

    def get_due_day(self) -> int:
        if not self.payment_due_date:
            return 0
        return self.payment_due_date.day

    def get_payment_status_info(self) -> dict:
        if not self.payment_due_date:
            return {
                "has_due_date": False,
                "status": "Sem vencimento definido",
                "is_overdue": False,
                "days_remaining": None,
                "due_day": 0,
                "next_due_date": None,
            }

        days = self.days_until_due()
        is_overdue = self.is_payment_overdue()
        due_day = self.get_due_day()

        if is_overdue:
            status = f"Vencido há {abs(days)} dia(s)"
        elif days == 0:
            status = "Vence hoje"
        elif days <= 3:
            status = f"Vence em {days} dia(s) - URGENTE"
        elif days <= 7:
            status = f"Vence em {days} dia(s) - Próximo"
        else:
            status = f"Vence em {days} dia(s)"

        return {
            "has_due_date": True,
            "due_date": self.payment_due_date,
            "due_day": due_day,
            "status": status,
            "is_overdue": is_overdue,
            "days_remaining": days,
            "formatted_date": self.payment_due_date.strftime("%d/%m/%Y"),
            "next_renewal_date": self._add_months(self.payment_due_date, 1).strftime("%d/%m/%Y"),
        }

    def set_payment_due_date_full(self, due_date: datetime) -> None:
        if not isinstance(due_date, datetime):
            raise ValueError("due_date deve ser um objeto datetime")

        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)
        else:
            due_date = due_date.astimezone(timezone.utc)

        now = datetime.now(timezone.utc)
        if due_date < now:
            logger.warning(
                f"Data de vencimento {due_date.strftime('%d/%m/%Y')} está no passado. "
                f"Usuário: {self.username}"
            )

        due_date = due_date.replace(hour=23, minute=59, second=59)
        self.payment_due_date = due_date
        logger.info(
            f"Vencimento completo definido para {self.payment_due_date.strftime('%d/%m/%Y %H:%M:%S')} "
            f"- Usuário: {self.username}"
        )
