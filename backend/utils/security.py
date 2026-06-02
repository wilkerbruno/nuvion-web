import logging
import secrets
import string
from typing import Tuple

import bcrypt

logger = logging.getLogger(__name__)


class PasswordSecurity:
    """Utilitários seguros para senhas"""

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Gera hash seguro da senha usando bcrypt com salt automático.

        Args:
            password: Senha em texto plano

        Returns:
            Hash seguro da senha (string)

        Example:
            >>> hash_password("minhasenha123")
            '$2b$12$...'
        """
        try:
            # Gerar salt aleatório (custo 12 = bom equilíbrio segurança/performance)
            salt = bcrypt.gensalt(rounds=12)

            # Gerar hash com salt
            password_hash = bcrypt.hashpw(password.encode("utf-8"), salt)

            # Retornar como string
            return password_hash.decode("utf-8")

        except Exception as e:
            logger.error(f"Erro ao gerar hash da senha: {e}")
            raise SecurityError("Erro ao processar senha")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verifica se a senha corresponde ao hash armazenado.

        Args:
            password: Senha em texto plano
            password_hash: Hash armazenado no banco

        Returns:
            True se a senha está correta, False caso contrário
        """
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("utf-8")
            )
        except Exception as e:
            logger.error(f"Erro na verificação da senha: {e}")
            return False

    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """
        Gera token seguro para sessões, reset de senha, etc.

        Args:
            length: Tamanho do token em bytes

        Returns:
            Token hexadecimal seguro
        """
        return secrets.token_hex(length)

    @staticmethod
    def generate_referral_code(length: int = 6) -> str:
        """
        Gera código de indicação aleatório (letras maiúsculas + números).

        Args:
            length: Tamanho do código (padrão 6)

        Returns:
            Código de indicação seguro (ex: 'A1B2C3')
        """
        # Caracteres permitidos: letras maiúsculas + números
        characters = string.ascii_uppercase + string.digits

        # Gerar código aleatório de forma segura
        return "".join(secrets.choice(characters) for _ in range(length))

    @staticmethod
    def is_password_strong(password: str) -> Tuple[bool, str]:
        """
        Verifica se a senha atende aos critérios de segurança.

        Args:
            password: Senha para validar

        Returns:
            (é_forte, mensagem_erro)
        """
        if len(password) < 8:
            return False, "Senha deve ter pelo menos 8 caracteres"

        if len(password) > 128:
            return False, "Senha muito longa (máximo 128 caracteres)"

        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)

        if not (has_upper and has_lower and has_digit):
            return False, "Senha deve ter maiúscula, minúscula e número"

        # Verificar senhas comuns
        common_passwords = {
            "12345678",
            "password",
            "123456789",
            "qwerty",
            "abc123",
            "password123",
            "admin",
            "letmein",
        }

        if password.lower() in common_passwords:
            return False, "Senha muito comum. Escolha uma senha mais segura"

        return True, "Senha segura"


class SecurityError(Exception):
    """Exceção para erros de segurança"""

    pass
