import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import keyring

from utils.logger import LOGGER


@dataclass
class DatabaseConfig:
    """Configuração do banco de dados"""

    host: str = "2.25.131.174"
    port: int = 33060
    database: str = "browser"
    user: Optional[str] = "admin"
    password: Optional[str] = "V71C2Fd1eqJ8p0Pn0x4aO5mW"


    debug: bool = False
    language: str = "pt_BR"
    theme: str = "dark"
    auto_save_session: bool = True
    max_tabs: int = 20


@dataclass
class SMTPConfig:
    """Configuração do servidor SMTP para envio de emails"""
    
    smtp_host: str = "smtp.gmail.com"  # Ex: smtp.gmail.com
    smtp_port: int = 587  # 587 para TLS, 465 para SSL
    smtp_email: str = "browserpadrin@gmail.com"  # Email remetente
    smtp_password: str = "ncud wwed ogxc qwnf"  # Senha do email ou senha de aplicativo
    smtp_use_tls: bool = True  # True para TLS (porta 587), False para SSL (porta 465)
    sender_name: str = "Nuvion Browser"  # Nome que aparece no remetente


class HardcodedConfigManager:
    """Manager de configurações com credenciais hardcoded"""

    def __init__(self):
        self.app_name = "upbrowser"
        self.config_dir = Path.home() / f".{self.app_name}"
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        
        LOGGER.info("ConfigManager inicializado com credenciais hardcoded")

    def get_database_config(self) -> DatabaseConfig:
        """Retorna configuração do banco com credenciais hardcoded"""
        try:
            # Verificar se há override em variáveis de ambiente (para desenvolvimento)
            db_host = os.getenv("DB_HOST", "easypanel.pontocomdesconto.com.br")
            db_port = int(os.getenv("DB_PORT", "33060"))
            db_name = os.getenv("DB_NAME", "browser")
            db_user = os.getenv("DB_USER", "admin")  # MODIFICAR AQUI
            db_password = os.getenv("DB_PASSWORD", "V71C2Fd1eqJ8p0Pn0x4aO5mW")  # MODIFICAR AQUI

            config = DatabaseConfig(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_password,
            )
            
            LOGGER.info(f"Configuração DB carregada: {config.user}@{config.host}:{config.port}/{config.database}")
            return config

        except Exception as e:
            LOGGER.error(f"Erro ao carregar configuração do banco: {e}")
            # Retornar configuração padrão hardcoded
            return DatabaseConfig()

    def has_database_credentials(self) -> bool:
        """Sempre retorna True pois credenciais estão hardcoded"""
        config = self.get_database_config()
        has_creds = bool(config.user and config.password)
        LOGGER.info(f"Credenciais disponíveis: {has_creds}")
        return has_creds

    def store_database_credentials(self, user: str, password: str) -> None:
        """Método deprecado - credenciais são hardcoded"""
        LOGGER.warning("store_database_credentials() ignorado - usando credenciais hardcoded")
        pass

    def reset_database_credentials(self) -> None:
        """Método deprecado - credenciais são hardcoded"""
        LOGGER.warning("reset_database_credentials() ignorado - usando credenciais hardcoded")
        pass

    def save_app_config(self, config: AppConfig) -> None:
        """Salva configurações da aplicação"""
        try:
            config_data = asdict(config)
            with open(self.config_file, "w") as f:
                json.dump(config_data, f, indent=2)
            LOGGER.info("Configurações da aplicação salvas")
        except Exception as e:
            LOGGER.error(f"Erro ao salvar configurações: {e}")

    def load_app_config(self) -> AppConfig:
        """Carrega configurações da aplicação"""
        try:
            if not self.config_file.exists():
                LOGGER.info("Arquivo de configuração não existe, usando padrões")
                return AppConfig()

            with open(self.config_file, "r") as f:
                config_dict = json.load(f)

            LOGGER.info("Configurações da aplicação carregadas")
            return AppConfig(**config_dict)
        except Exception as e:
            LOGGER.error(f"Erro ao carregar configurações: {e}")
            return AppConfig()

    def save_smtp_config(self, config: SMTPConfig) -> None:
        """Salva configurações SMTP"""
        try:
            smtp_file = self.config_dir / "smtp_config.json"
            config_data = asdict(config)
            
            with open(smtp_file, "w") as f:
                json.dump(config_data, f, indent=2)
            
            LOGGER.info("Configurações SMTP salvas com sucesso")
        except Exception as e:
            LOGGER.error(f"Erro ao salvar configurações SMTP: {e}")

    def load_smtp_config(self) -> SMTPConfig:
        """Carrega configurações SMTP"""
        try:
            smtp_file = self.config_dir / "smtp_config.json"
            
            if not smtp_file.exists():
                LOGGER.info("Arquivo de configuração SMTP não existe, usando padrões")
                return SMTPConfig()

            with open(smtp_file, "r") as f:
                config_dict = json.load(f)

            LOGGER.info("Configurações SMTP carregadas")
            return SMTPConfig(**config_dict)
        except Exception as e:
            LOGGER.error(f"Erro ao carregar configurações SMTP: {e}")
            return SMTPConfig()

    def has_smtp_config(self) -> bool:
        """Verifica se configurações SMTP estão preenchidas"""
        try:
            config = self.load_smtp_config()
            has_config = bool(
                config.smtp_host and 
                config.smtp_email and 
                config.smtp_password
            )
            return has_config
        except Exception as e:
            LOGGER.error(f"Erro ao verificar configurações SMTP: {e}")
            return False


# Instância global com credenciais hardcoded
config_manager = HardcodedConfigManager()