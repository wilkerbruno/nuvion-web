# backend/utils/config_manager.py
# Versão web — sem keyring, sem PyQt6, sem dependências desktop
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 3306
    database: str = "browser"
    user: Optional[str] = "admin"
    password: Optional[str] = ""


@dataclass
class AppConfig:
    debug: bool = False
    language: str = "pt_BR"
    theme: str = "dark"
    auto_save_session: bool = True
    max_tabs: int = 20


@dataclass
class SMTPConfig:
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_email: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    sender_name: str = "Nuvion Browser"


class HardcodedConfigManager:
    """Config manager para ambiente web — lê credenciais das env vars."""

    def get_database_config(self) -> DatabaseConfig:
        return DatabaseConfig(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", "browser"),
            user=os.getenv("DB_USER", "admin"),
            password=os.getenv("DB_PASSWORD", ""),
        )

    def has_database_credentials(self) -> bool:
        config = self.get_database_config()
        return bool(config.user and config.password)

    def store_database_credentials(self, user: str, password: str) -> None:
        pass

    def reset_database_credentials(self) -> None:
        pass

    def save_app_config(self, config: AppConfig) -> None:
        pass

    def load_app_config(self) -> AppConfig:
        return AppConfig()

    def save_smtp_config(self, config: SMTPConfig) -> None:
        pass

    def load_smtp_config(self) -> SMTPConfig:
        return SMTPConfig(
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_email=os.getenv("SMTP_EMAIL", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_use_tls=os.getenv("SMTP_TLS", "true").lower() == "true",
            sender_name=os.getenv("SMTP_SENDER", "Nuvion Browser"),
        )

    def has_smtp_config(self) -> bool:
        cfg = self.load_smtp_config()
        return bool(cfg.smtp_email and cfg.smtp_password)


config_manager = HardcodedConfigManager()