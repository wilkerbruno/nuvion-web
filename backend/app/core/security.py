"""Segurança: hash de senha (portado quase 1:1 de utils/security.py) + JWT.

A parte de hash de senha (PasswordSecurity) é a mesma lógica do desktop —
não dependia de nada específico de Qt/arquivo local, então foi reaproveitada
sem mudanças de comportamento. A parte nova é JWT de acesso/refresh, que
substitui a sessão local em disco (user_session.py/device_token_manager.py
no projeto original) pelo modelo padrão de autenticação web.
"""
import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Exceção para erros de segurança."""


class PasswordSecurity:
    """Utilitários seguros para senhas (portado de utils/security.py)."""

    @staticmethod
    def hash_password(password: str) -> str:
        try:
            salt = bcrypt.gensalt(rounds=12)
            password_hash = bcrypt.hashpw(password.encode("utf-8"), salt)
            return password_hash.decode("utf-8")
        except Exception as e:
            logger.error(f"Erro ao gerar hash da senha: {e}")
            raise SecurityError("Erro ao processar senha") from e

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception as e:
            logger.error(f"Erro na verificação da senha: {e}")
            return False

    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        return secrets.token_hex(length)

    @staticmethod
    def generate_referral_code(length: int = 6) -> str:
        characters = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(characters) for _ in range(length))

    @staticmethod
    def is_password_strong(password: str) -> Tuple[bool, str]:
        if len(password) < 8:
            return False, "Senha deve ter pelo menos 8 caracteres"
        if len(password) > 128:
            return False, "Senha muito longa (máximo 128 caracteres)"

        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        if not (has_upper and has_lower and has_digit):
            return False, "Senha deve ter maiúscula, minúscula e número"

        common_passwords = {
            "12345678", "password", "123456789", "qwerty",
            "abc123", "password123", "admin", "letmein",
        }
        if password.lower() in common_passwords:
            return False, "Senha muito comum. Escolha uma senha mais segura"

        return True, "Senha segura"


# --------------------------------------------------------------------------
# JWT — novo nesta versão web (substitui a sessão local em disco do desktop)
# --------------------------------------------------------------------------

def create_access_token(subject: str, extra_claims: Optional[dict] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire, "type": "access"}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        logger.warning(f"Token inválido/expirado: {e}")
        return None
