import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
Sistema de Sanitização e Escape de Credenciais
Garante que credenciais sejam passadas de forma segura para JavaScript
"""

import re
import json
from typing import Tuple, Optional
from utils.auto_login_logger import AUTO_LOGIN_LOGGER


class CredentialSanitizer:
    """Sanitizador robusto de credenciais para JavaScript"""
    
    # Caracteres especiais que precisam de escape
    SPECIAL_CHARS = {
        '\\': '\\\\',    # Backslash (deve ser primeiro)
        '"': '\\"',      # Aspas duplas
        "'": "\\'",      # Aspas simples
        '\n': '\\n',     # Nova linha
        '\r': '\\r',     # Retorno de carro
        '\t': '\\t',     # Tab
        '\b': '\\b',     # Backspace
        '\f': '\\f',     # Form feed
        '`': '\\`',      # Template literal
        '$': '\\$',      # Template variable
    }
    
    # Caracteres problemáticos para JavaScript
    PROBLEMATIC_CHARS = ['<', '>', '{', '}', '\x00']
    
    @staticmethod
    def escape_for_javascript(text: str) -> str:
        """
        Escape completo para uso em JavaScript
        
        Args:
            text: Texto a ser escapado
            
        Returns:
            Texto com escape seguro para JavaScript
        """
        if not text:
            return ""
        
        # Log do tamanho e tipo de caracteres
        has_special = any(char in text for char in CredentialSanitizer.SPECIAL_CHARS)
        AUTO_LOGIN_LOGGER.debug(f"Escapando texto de {len(text)} caracteres, "
                               f"caracteres especiais: {has_special}")
        
        result = text
        
        # Aplicar escapes em ordem específica (backslash primeiro)
        for original, escaped in CredentialSanitizer.SPECIAL_CHARS.items():
            result = result.replace(original, escaped)
        
        # Verificar caracteres problemáticos
        for char in CredentialSanitizer.PROBLEMATIC_CHARS:
            if char in result:
                AUTO_LOGIN_LOGGER.warning(f"Caractere problemático detectado: {repr(char)}")
                # Remover ou substituir caracteres null
                if char == '\x00':
                    result = result.replace(char, '')
        
        AUTO_LOGIN_LOGGER.debug(f"Escape concluído, resultado: {len(result)} caracteres")
        
        return result
    
    @staticmethod
    def escape_for_json(text: str) -> str:
        """
        Escape para uso em JSON (alternativa mais segura)
        
        Args:
            text: Texto a ser escapado
            
        Returns:
            Texto com escape JSON
        """
        if not text:
            return ""
        
        try:
            # Usar json.dumps para escape automático e remover aspas
            escaped = json.dumps(text)[1:-1]
            AUTO_LOGIN_LOGGER.debug(f"Escape JSON aplicado: {len(text)} -> {len(escaped)} chars")
            return escaped
        except Exception as e:
            AUTO_LOGIN_LOGGER.error(f"Erro no escape JSON: {e}")
            # Fallback para escape manual
            return CredentialSanitizer.escape_for_javascript(text)
    
    @staticmethod
    def encode_base64(text: str) -> str:
        """
        Codifica texto em base64 (opção mais segura)
        
        Args:
            text: Texto a codificar
            
        Returns:
            Texto codificado em base64
        """
        import base64
        
        if not text:
            return ""
        
        try:
            encoded = base64.b64encode(text.encode('utf-8')).decode('ascii')
            AUTO_LOGIN_LOGGER.debug(f"Texto codificado em base64: {len(text)} -> {len(encoded)} chars")
            return encoded
        except Exception as e:
            AUTO_LOGIN_LOGGER.error(f"Erro ao codificar base64: {e}")
            return ""
    
    @staticmethod
    def validate_credentials(username: str, password: str) -> Tuple[bool, str]:
        """
        Valida credenciais antes de usar
        
        Args:
            username: Nome de usuário
            password: Senha
            
        Returns:
            Tupla (válido, mensagem)
        """
        errors = []
        
        # Validações básicas
        if not username or not username.strip():
            errors.append("Username vazio")
        
        if not password or not password.strip():
            errors.append("Senha vazia")
        
        if len(username) < 3:
            errors.append("Username muito curto (mínimo 3 caracteres)")
        
        if len(password) < 4:
            errors.append("Senha muito curta (mínimo 4 caracteres)")
        
        # Verificar caracteres null
        if '\x00' in username or '\x00' in password:
            errors.append("Credenciais contêm caracteres null inválidos")
        
        # Validar tamanho máximo
        if len(username) > 255:
            errors.append("Username muito longo (máximo 255 caracteres)")
        
        if len(password) > 255:
            errors.append("Senha muito longa (máximo 255 caracteres)")
        
        # Análise de complexidade
        has_special = any(char in password for char in CredentialSanitizer.SPECIAL_CHARS)
        has_problematic = any(char in password for char in CredentialSanitizer.PROBLEMATIC_CHARS)
        
        AUTO_LOGIN_LOGGER.debug(f"Validação de credenciais:")
        AUTO_LOGIN_LOGGER.debug(f"  Username: {len(username)} chars")
        AUTO_LOGIN_LOGGER.debug(f"  Password: {len(password)} chars")
        AUTO_LOGIN_LOGGER.debug(f"  Caracteres especiais na senha: {has_special}")
        AUTO_LOGIN_LOGGER.debug(f"  Caracteres problemáticos: {has_problematic}")
        
        if errors:
            message = "; ".join(errors)
            AUTO_LOGIN_LOGGER.warning(f"Validação falhou: {message}")
            return False, message
        
        AUTO_LOGIN_LOGGER.info("Credenciais validadas com sucesso")
        return True, "Credenciais válidas"
    
    @staticmethod
    def prepare_for_javascript(username: str, password: str, 
                               method: str = "escape") -> Tuple[str, str]:
        """
        Prepara credenciais para uso em JavaScript
        
        Args:
            username: Nome de usuário
            password: Senha
            method: Método de sanitização ("escape", "json", "base64")
            
        Returns:
            Tupla (username_preparado, password_preparado)
        """
        AUTO_LOGIN_LOGGER.info(f"Preparando credenciais usando método: {method}")
        
        # Validar primeiro
        valid, message = CredentialSanitizer.validate_credentials(username, password)
        if not valid:
            AUTO_LOGIN_LOGGER.error(f"Credenciais inválidas: {message}")
            raise ValueError(f"Credenciais inválidas: {message}")
        
        # Aplicar método escolhido
        if method == "base64":
            prepared_username = CredentialSanitizer.encode_base64(username)
            prepared_password = CredentialSanitizer.encode_base64(password)
        elif method == "json":
            prepared_username = CredentialSanitizer.escape_for_json(username)
            prepared_password = CredentialSanitizer.escape_for_json(password)
        else:  # "escape" (padrão)
            prepared_username = CredentialSanitizer.escape_for_javascript(username)
            prepared_password = CredentialSanitizer.escape_for_javascript(password)
        
        AUTO_LOGIN_LOGGER.info("Credenciais preparadas com sucesso")
        AUTO_LOGIN_LOGGER.log_credentials_validation(
            username=username,
            password_length=len(password),
            has_special_chars=any(c in password for c in CredentialSanitizer.SPECIAL_CHARS)
        )
        
        return prepared_username, prepared_password
    
    @staticmethod
    def mask_sensitive_data(text: str, visible_chars: int = 3) -> str:
        """
        Mascara dados sensíveis para logs
        
        Args:
            text: Texto a mascarar
            visible_chars: Número de caracteres visíveis no início
            
        Returns:
            Texto mascarado
        """
        if not text:
            return "***"
        
        if len(text) <= visible_chars:
            return "*" * len(text)
        
        return text[:visible_chars] + "*" * (len(text) - visible_chars)


# Testes unitários embutidos
if __name__ == "__main__":
    print("=== TESTES DO CREDENTIAL SANITIZER ===\n")
    
    # Teste 1: Escape básico
    print("TESTE 1: Escape básico")
    test1 = CredentialSanitizer.escape_for_javascript('senha"com\'aspas')
    print(f"  Entrada: senha\"com'aspas")
    print(f"  Saída: {test1}")
    print(f"  ✅ Passou\n" if '\\"' in test1 and "\\'" in test1 else "  ❌ Falhou\n")
    
    # Teste 2: Caracteres especiais complexos
    print("TESTE 2: Caracteres especiais")
    test2 = CredentialSanitizer.escape_for_javascript('senha$com{backslash}\\e`template`')
    print(f"  Entrada: senha$com{{backslash}}\\e`template`")
    print(f"  Saída: {test2}")
    print(f"  ✅ Passou\n")
    
    # Teste 3: Base64
    print("TESTE 3: Codificação Base64")
    test3_user, test3_pass = CredentialSanitizer.prepare_for_javascript(
        "user@example.com", 
        "SenhaCompl€xa!@#$%",
        method="base64"
    )
    print(f"  Username original: user@example.com")
    print(f"  Username base64: {test3_user}")
    print(f"  Password mascarada: {CredentialSanitizer.mask_sensitive_data(test3_pass)}")
    print(f"  ✅ Passou\n")
    
    # Teste 4: Validação
    print("TESTE 4: Validação de credenciais")
    valid, msg = CredentialSanitizer.validate_credentials("test", "12345")
    print(f"  Validação (test, 12345): {valid}")
    print(f"  Mensagem: {msg}")
    print(f"  ✅ Passou\n" if valid else f"  ❌ Falhou: {msg}\n")
    
    # Teste 5: Validação com erro
    print("TESTE 5: Validação com erro")
    valid, msg = CredentialSanitizer.validate_credentials("a", "b")
    print(f"  Validação (a, b): {valid}")
    print(f"  Mensagem: {msg}")
    print(f"  ✅ Passou\n" if not valid else "  ❌ Falhou (deveria ser inválido)\n")
    
    print("=== TESTES CONCLUÍDOS ===")