from calendar import monthrange
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import relationship

from database.models.base import BaseModel
from database.sqlalchemy_config import Base
from utils.security import PasswordSecurity

logger = logging.getLogger(__name__)


class User(Base, BaseModel):
    """Modelo de usuário do sistema"""

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
    status = Column(
        Enum("Ativo", "Inativo", "Cancelado", "Bloqueado"), default="Inativo"
    )
    category = Column(Enum("Standard", "Premium", "VIP"), default="Standard")

    # Timestamps especiais
    last_login = Column(DateTime)
    password_changed_at = Column(DateTime)
    last_payment_check = Column(DateTime)

    # Data de vencimento do pagamento/assinatura
    payment_due_date = Column(
        DateTime, 
        nullable=True,
        index=True,  # Index para otimizar consultas de vencimento
        comment="Data de vencimento da assinatura do usuário"
    )

    # Configurações do perfil em JSON
    profile_settings = Column(JSON, default=dict)

    # Sistema de Bloqueio Temporário
    is_temporarily_blocked = Column(Boolean, default=False, nullable=False, index=True)
    block_reason = Column(String(100), nullable=True)
    blocked_at = Column(DateTime, nullable=True)

    # Sistema de Recuperação de Senha
    recovery_code = Column(String(5), nullable=True)
    recovery_code_created_at = Column(DateTime, nullable=True)
    recovery_code_expires_at = Column(DateTime, nullable=True)
    recovery_attempts = Column(Integer, default=0)

    def set_password(self, password: str) -> None:
        """Define senha com validação de segurança"""
        is_strong, message = PasswordSecurity.is_password_strong(password)
        if not is_strong:
            raise SecurityError(message)

        self.password_hash = PasswordSecurity.hash_password(password)
        self.password_changed_at = datetime.now(timezone.utc)
        logger.info(f"Senha alterada para usuário: {self.username}")

    def verify_password(self, password: str) -> bool:
        """Verifica senha"""
        if not self.password_hash:
            return False
        return PasswordSecurity.verify_password(password, self.password_hash)

    def update_category(self, new_category: str) -> None:
        """Atualiza categoria do usuário (Standard/Premium/VIP)"""
        if new_category in ["Standard", "Premium", "VIP"]:
            self.category = new_category
            logger.info(f"Categoria atualizada para: {new_category}")

    def generate_recovery_code(self, expiration_minutes: int = 15) -> str:
        """
        Gera código de recuperação de senha válido por X minutos
        
        Args:
            expiration_minutes: Tempo de validade do código em minutos (padrão: 15)
            
        Returns:
            str: Código de 5 caracteres gerado
        """
        import secrets
        import string
        
        # Gerar código de 5 caracteres (letras maiúsculas + números)
        # Evitar caracteres confusos: O, 0, I, 1
        characters = string.ascii_uppercase.replace('O', '').replace('I', '') + string.digits.replace('0', '').replace('1', '')
        code = ''.join(secrets.choice(characters) for _ in range(5))
        
        # Armazenar código e timestamps
        self.recovery_code = code
        self.recovery_code_created_at = datetime.now(timezone.utc)
        self.recovery_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes)
        self.recovery_attempts = 0
        
        logger.info(f"Código de recuperação gerado para usuário: {self.username}")
        return code

    def validate_recovery_code(self, code: str) -> tuple:
        """
        Valida código de recuperação fornecido
        
        Args:
            code: Código fornecido pelo usuário
            
        Returns:
            tuple: (válido: bool, mensagem: str)
        """
        # Verificar se existe código ativo
        if not self.recovery_code:
            return False, "Nenhum código de recuperação ativo"
        
        # Verificar expiração - CORREÇÃO AQUI
        try:
            # Obter datetime atual com timezone
            now = datetime.now(timezone.utc)
            
            # Se recovery_code_expires_at não tem timezone, adicionar
            expires_at = self.recovery_code_expires_at
            if expires_at.tzinfo is None:
                # Converter para UTC se estiver naive
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            # Agora ambos têm timezone e podem ser comparados
            if now > expires_at:
                return False, "Código expirado. Solicite um novo código"
                
        except Exception as e:
            logger.error(f"Erro ao verificar expiração do código: {e}")
            return False, "Erro ao validar código"
        
        # Verificar tentativas
        if self.recovery_attempts >= 3:
            return False, "Número máximo de tentativas excedido. Solicite um novo código"
        
        # Validar código (case-insensitive)
        if code.upper() != self.recovery_code.upper():
            self.recovery_attempts += 1
            logger.warning(f"Tentativa inválida de recuperação para {self.username} (tentativa {self.recovery_attempts}/3)")
            return False, f"Código inválido. Restam {3 - self.recovery_attempts} tentativas"
        
        # Código válido
        logger.info(f"Código de recuperação validado com sucesso para: {self.username}")
        return True, "Código válido"

    def clear_recovery_code(self) -> None:
        """Limpa código de recuperação após uso ou expiração"""
        self.recovery_code = None
        self.recovery_code_created_at = None
        self.recovery_code_expires_at = None
        self.recovery_attempts = 0
        logger.info(f"Código de recuperação limpo para usuário: {self.username}")

    def is_recovery_code_expired(self) -> bool:
        """Verifica se código de recuperação expirou"""
        if not self.recovery_code or not self.recovery_code_expires_at:
            return True
        
        try:
            # Obter datetime atual com timezone
            now = datetime.now(timezone.utc)
            
            # Se recovery_code_expires_at não tem timezone, adicionar
            expires_at = self.recovery_code_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            return now > expires_at
            
        except Exception as e:
            logger.error(f"Erro ao verificar expiração: {e}")
            return True

    def block_temporarily(self, reason: str) -> None:
        """
        Bloqueia usuário temporariamente
        
        Args:
            reason: Motivo do bloqueio (usar constantes de BLOCK_REASONS)
        """
        self.is_temporarily_blocked = True
        self.block_reason = reason
        self.blocked_at = datetime.now(timezone.utc)
        logger.info(f"Usuário {self.username} bloqueado temporariamente: {reason}")

    def unblock(self) -> None:
        """Desbloqueia usuário"""
        self.is_temporarily_blocked = False
        self.block_reason = None
        self.blocked_at = None
        logger.info(f"Usuário {self.username} desbloqueado")

    def is_blocked(self) -> bool:
        """
        Verifica se usuário está bloqueado
        
        Returns:
            bool: True se bloqueado (temporário ou permanente)
        """
        return self.is_temporarily_blocked or self.status == "Bloqueado"

    def get_block_message(self) -> str:
        """
        Retorna mensagem de bloqueio formatada
        
        Returns:
            str: Mensagem explicativa do bloqueio
        """
        if self.is_temporarily_blocked:
            return f"Conta bloqueada temporariamente: {self.block_reason or 'Motivo não especificado'}"
        elif self.status == "Bloqueado":
            return "Conta bloqueada permanentemente. Entre em contato com o suporte."
        else:
            return "Conta não está bloqueada"

    def initialize_payment_due_date(self) -> None:
        """
        Inicializa data de vencimento com o dia atual
        Usado quando usuário cria conta pela primeira vez
        """
        self.payment_due_date = datetime.now(timezone.utc)
        logger.info(
            f"Vencimento inicial definido para {self.payment_due_date.strftime('%d/%m/%Y')} "
            f"(dia {self.payment_due_date.day}) - Usuário: {self.username}"
        )
    
    def set_payment_due_date_by_day(self, day: int) -> None:
        """
        Define data de vencimento para um dia específico do mês
        Usado pelo ADM para ajustar o dia de vencimento do usuário
        
        Args:
            day: Dia do mês (1-31)
        
        Raises:
            ValueError: Se o dia for inválido
        """
        if not 1 <= day <= 31:
            raise ValueError("Dia deve estar entre 1 e 31")
        
        now = datetime.now(timezone.utc)
        current_year = now.year
        current_month = now.month
        
        # Verificar se o dia existe no mês atual
        max_day_in_month = monthrange(current_year, current_month)[1]
        
        # Se o dia solicitado não existe no mês atual (ex: 31 em fevereiro)
        # usar o último dia do mês
        target_day = min(day, max_day_in_month)
        
        # Criar data de vencimento
        try:
            due_date = now.replace(day=target_day, hour=23, minute=59, second=59)
        except ValueError:
            # Fallback: usar último dia do mês
            due_date = now.replace(day=max_day_in_month, hour=23, minute=59, second=59)
        
        # Se a data já passou neste mês, definir para o próximo mês
        if due_date < now:
            due_date = self._add_months(due_date, 1)
        
        self.payment_due_date = due_date
        logger.info(
            f"Vencimento definido para {self.payment_due_date.strftime('%d/%m/%Y')} "
            f"(dia {target_day}) - Usuário: {self.username}"
        )
    
    def renew_subscription(self) -> None:
        """
        Renova assinatura mantendo o mesmo DIA de vencimento
        LÓGICA: Renova para o mesmo dia do próximo mês, independente de quando pagou
        
        Exemplo:
        - Vencimento: 20/01/2025
        - Paga em: 13/01/2025
        - Novo vencimento: 20/02/2025
        """
        if not self.payment_due_date:
            # Se não tem vencimento, definir para hoje + 30 dias
            self.initialize_payment_due_date()
            self.payment_due_date = self.payment_due_date + timedelta(days=30)
            logger.warning(
                f"Usuário sem vencimento definido - Inicializando para daqui 30 dias: {self.username}"
            )
            return
        
        # Pegar o dia fixo do vencimento atual
        fixed_day = self.payment_due_date.day
        
        # Calcular próximo vencimento (1 mês depois, mesmo dia)
        next_due_date = self._add_months(self.payment_due_date, 1)
        
        # Garantir que mantém o mesmo dia (tratamento para meses com menos dias)
        if next_due_date.day != fixed_day:
            # Se o próximo mês tem menos dias (ex: 31 -> 28 em fevereiro)
            # usar o último dia do mês
            year = next_due_date.year
            month = next_due_date.month
            max_day = monthrange(year, month)[1]
            next_due_date = next_due_date.replace(day=min(fixed_day, max_day))
        
        self.payment_due_date = next_due_date
        
        # Atualizar status para Ativo se estiver Inativo
        if self.status == "Inativo":
            self.status = "Ativo"
            logger.info(f"Usuário reativado após pagamento: {self.username}")
        
        # Atualizar timestamp de verificação
        self.last_payment_check = datetime.now(timezone.utc)
        
        logger.info(
            f"Assinatura renovada - Novo vencimento: {self.payment_due_date.strftime('%d/%m/%Y')} "
            f"(dia {self.payment_due_date.day}) - Usuário: {self.username}"
        )
    
    def _add_months(self, source_date: datetime, months: int) -> datetime:
        """
        Adiciona N meses a uma data
        Trata corretamente mudanças de ano e dias inválidos
        
        Args:
            source_date: Data de origem
            months: Quantidade de meses para adicionar
            
        Returns:
            datetime: Nova data
        """
        month = source_date.month - 1 + months
        year = source_date.year + month // 12
        month = month % 12 + 1
        
        # Tratar dias que não existem no mês de destino
        max_day = monthrange(year, month)[1]
        day = min(source_date.day, max_day)
        
        return source_date.replace(year=year, month=month, day=day)
    
    def is_payment_overdue(self) -> bool:
        """Verifica se pagamento esta vencido. Normaliza naive datetime do MySQL."""
        if not self.payment_due_date:
            return False
        due = self.payment_due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > due

    def days_until_due(self) -> int:
        """Calcula dias ate o vencimento. Normaliza naive datetime do MySQL."""
        if not self.payment_due_date:
            return 0
        due = self.payment_due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        return (due - datetime.now(timezone.utc)).days
    
    
    def get_due_day(self) -> int:
        """
        Retorna o dia fixo do vencimento mensal
        
        Returns:
            int: Dia do mês (1-31) ou 0 se não definido
        """
        if not self.payment_due_date:
            return 0
        
        return self.payment_due_date.day
    
    def get_payment_status_info(self) -> dict:
        """
        Retorna informações completas sobre status de pagamento
        
        Returns:
            dict: Informações detalhadas do pagamento
        """
        if not self.payment_due_date:
            return {
                "has_due_date": False,
                "status": "Sem vencimento definido",
                "is_overdue": False,
                "days_remaining": None,
                "due_day": 0,
                "next_due_date": None
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
            "next_renewal_date": self._add_months(self.payment_due_date, 1).strftime("%d/%m/%Y")
        }

    def set_payment_due_date_full(self, due_date: datetime) -> None:
        """
        Define data de vencimento completa (dia/mês/ano)
        Usado pelo ADM para definir datas específicas (ex: assinaturas trimestrais)
        
        Args:
            due_date: Data completa de vencimento
        
        Raises:
            ValueError: Se a data for inválida ou no passado
        """
        if not isinstance(due_date, datetime):
            raise ValueError("due_date deve ser um objeto datetime")
        
        # Garantir que a data tem timezone UTC
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=timezone.utc)
        else:
            due_date = due_date.astimezone(timezone.utc)
        
        # Opcional: verificar se data está no futuro
        now = datetime.now(timezone.utc)
        if due_date < now:
            logger.warning(
                f"Data de vencimento {due_date.strftime('%d/%m/%Y')} está no passado. "
                f"Usuário: {self.username}"
            )
        
        # Definir horário para fim do dia (23:59:59)
        due_date = due_date.replace(hour=23, minute=59, second=59)
        
        self.payment_due_date = due_date
        logger.info(
            f"Vencimento completo definido para {self.payment_due_date.strftime('%d/%m/%Y %H:%M:%S')} "
            f"- Usuário: {self.username}"
        )


class BlockReasons:
    """Motivos padronizados para bloqueio de usuários"""
    
    NEW_DEVICE = "Tentativa de login em dispositivo não autorizado"
    PAYMENT_OVERDUE = "Pagamento em atraso - renove sua assinatura"
    ADMIN_ACTION = "Conta bloqueada por administrador"
    SECURITY_VIOLATION = "Atividade suspeita detectada"
    MULTIPLE_FAILED_LOGINS = "Múltiplas tentativas de login falhadas"
    USER_REQUEST = "Bloqueio solicitado pelo usuário"
    
    @classmethod
    def get_all(cls):
        """Retorna todos os motivos disponíveis"""
        return {
            "new_device": cls.NEW_DEVICE,
            "payment_overdue": cls.PAYMENT_OVERDUE,
            "admin_action": cls.ADMIN_ACTION,
            "security_violation": cls.SECURITY_VIOLATION,
            "multiple_failed_logins": cls.MULTIPLE_FAILED_LOGINS,
            "user_request": cls.USER_REQUEST,
        }


class SecurityError(Exception):
    """Exceção para erros de segurança"""
    pass
