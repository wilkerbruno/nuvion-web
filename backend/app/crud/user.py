"""Lógica de usuário (portada de crud/sqlalchemy_user_manager.py).

Diferença de padrão em relação ao original: lá, cada método do manager
abria e fechava sua própria sessão (`self.get_session()` / `session.close()`
no finally) — necessário porque o app desktop não tinha um ciclo de
request/response para amarrar a sessão a algo. Aqui, a sessão vem injetada
por parâmetro (`db: Session`), fornecida pela dependency `get_db` do
FastAPI, que abre uma sessão por request e fecha ao final — é o padrão
idiomático em APIs web e evita abrir uma conexão nova a cada chamada de
função dentro do mesmo request.

A validação de negócio (indicação obrigatória, unicidade de username/email/
telefone/CPF, formato de telefone/email, força de senha) foi mantida igual.
"""
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.logging import LOGGER
from app.core.security import PasswordSecurity, SecurityError
from app.models.user import User
from app.services import reward_service

_PHONE_RE_LENGTHS = (10, 11)
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _validate_phone(phone: str) -> bool:
    clean_phone = "".join(filter(str.isdigit, phone))
    return len(clean_phone) in _PHONE_RE_LENGTHS


def _clean_phone(phone: str) -> str:
    clean = "".join(filter(str.isdigit, phone))
    if len(clean) == 11:
        return f"({clean[:2]}) {clean[2:7]}-{clean[7:]}"
    elif len(clean) == 10:
        return f"({clean[:2]}) {clean[2:6]}-{clean[6:]}"
    return phone


def _generate_unique_referral_code(db: Session) -> str:
    for _ in range(10):
        code = PasswordSecurity.generate_referral_code()
        exists = db.query(User).filter(User.referral_code == code).first()
        if not exists:
            return code
    return PasswordSecurity.generate_referral_code(8)


def get_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_by_username_or_email(db: Session, username_or_email: str) -> Optional[User]:
    return (
        db.query(User)
        .filter(or_(User.username == username_or_email, User.email == username_or_email))
        .first()
    )


def get_by_referral_code(db: Session, referral_code: str) -> Optional[User]:
    return db.query(User).filter(User.referral_code == referral_code.strip().upper()).first()


def register_user(
    db: Session,
    *,
    username: str,
    password: str,
    email: str,
    name: str,
    phone: str,
    referral_code: Optional[str] = None,
    cpf: Optional[str] = None,
    account_type: str = "Membro",
    status: str = "Inativo",
    bypass_referral_validation: bool = False,
) -> Tuple[bool, str]:
    """Registra um novo usuário. Retorna (sucesso, user_id_ou_mensagem_de_erro)."""

    if not bypass_referral_validation:
        if not referral_code or not referral_code.strip():
            return False, "Código de indicação é obrigatório"
        referrer = get_by_referral_code(db, referral_code)
        if not referrer:
            return False, "Código de indicação inválido"

    existing_user = (
        db.query(User).filter(or_(User.username == username, User.email == email)).first()
    )
    if existing_user:
        if existing_user.username == username:
            return False, "Nome de usuário já existe"
        return False, "Email já cadastrado"

    if db.query(User).filter(User.phone == phone).first():
        return False, "Telefone já cadastrado"

    if cpf and cpf.strip():
        if db.query(User).filter(User.cpf == cpf).first():
            return False, "CPF já cadastrado"

    if not _validate_phone(phone):
        return False, "Formato de telefone inválido"
    if not _EMAIL_RE.match(email):
        return False, "Formato de email inválido"

    is_strong, message = PasswordSecurity.is_password_strong(password)
    if not is_strong:
        return False, message

    if len(name.strip()) < 2:
        return False, "Nome deve ter pelo menos 2 caracteres"

    new_referral_code = _generate_unique_referral_code(db)

    try:
        user = User(
            username=username,
            email=email,
            name=name.strip(),
            phone=_clean_phone(phone),
            cpf=cpf.strip() if cpf and cpf.strip() else None,
            account_type=account_type,
            status=status,
            referral_code=new_referral_code,
        )
        user.set_password(password)
    except SecurityError as e:
        return False, str(e)

    db.add(user)
    db.commit()
    db.refresh(user)

    LOGGER.info(f"Usuário registrado: {username} ({name}) - Código: {new_referral_code}")

    if not bypass_referral_validation and referral_code:
        referrer = get_by_referral_code(db, referral_code)
        if referrer:
            LOGGER.info(f"Indicado por: {referrer.username} ({referrer.referral_code})")
            reward_service.process_referral_rewards(db, new_user=user, referrer=referrer)

    return True, user.id


def verify_login(db: Session, username_or_email: str, password: str) -> Tuple[bool, str]:
    """Verifica credenciais. Retorna (sucesso, user_id_ou_mensagem_de_erro)."""
    user = get_by_username_or_email(db, username_or_email)
    if not user:
        return False, "Usuário não encontrado"

    if user.status in ("Bloqueado", "Cancelado"):
        return False, f"Conta {user.status.lower()}"

    if user.is_blocked():
        return False, user.get_block_message()

    if not user.verify_password(password):
        return False, "Senha incorreta"

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    return True, user.id


def update_profile(db: Session, user: User, **fields) -> User:
    for key, value in fields.items():
        if value is not None and hasattr(user, key):
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user
