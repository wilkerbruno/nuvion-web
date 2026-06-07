# utils/config_manager.py
# Versao web — sem keyring, sem PyQt6, sem psutil, sem dependencias desktop.
# Substitui o config_manager.py original que importa keyring e usa AppConfig
# antes de defini-lo, causando NameError no Python 3.11.
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DatabaseConfig:
    """Configuracao do banco de dados"""
    host: str = "localhost"
    port: int = 3306
    database: str = "browser"
    user: Optional[str] = "admin"
    password: Optional[str] = ""


@dataclass
class AppConfig:
    """Configuracao geral da aplicacao"""
    debug: bool = False
    language: str = "pt_BR"
    theme: str = "dark"
    auto_save_session: bool = True
    max_tabs: int = 20


@dataclass
class SMTPConfig:
    """Configuracao do servidor SMTP"""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_email: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    sender_name: str = "Nuvion Browser"


class HardcodedConfigManager:
    """Config manager para ambiente web — credenciais via env vars."""

    def __init__(self):
        self.app_name = "nuvion"
        self.config_dir = Path.home() / f".{self.app_name}"
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        try:
            from utils.logger import LOGGER
            LOGGER.info("DatabaseConfig inicializado com credenciais hardcoded")
        except Exception:
            pass

    def get_database_config(self) -> DatabaseConfig:
        return DatabaseConfig(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            database=os.getenv("DB_NAME", "browser"),
            user=os.getenv("DB_USER", "admin"),
            password=os.getenv("DB_PASSWORD") or "V71C2Fd1eqJ8p0Pn0x4aO5mW",
        )

    def has_database_credentials(self) -> bool:
        config = self.get_database_config()
        return bool(config.user and config.password)

    def store_database_credentials(self, user: str, password: str) -> None:
        pass  # Sem keyring na versao web

    def reset_database_credentials(self) -> None:
        pass  # Sem keyring na versao web

    def save_app_config(self, config: AppConfig) -> None:
        try:
            with open(self.config_file, "w") as f:
                json.dump(asdict(config), f, indent=2)
        except Exception:
            pass

    def load_app_config(self) -> AppConfig:
        try:
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                return AppConfig(**data)
        except Exception:
            pass
        return AppConfig()

    def save_smtp_config(self, config: SMTPConfig) -> None:
        try:
            smtp_file = self.config_dir / "smtp_config.json"
            with open(smtp_file, "w") as f:
                json.dump(asdict(config), f, indent=2)
        except Exception:
            pass

    def load_smtp_config(self) -> SMTPConfig:
        try:
            smtp_file = self.config_dir / "smtp_config.json"
            if smtp_file.exists():
                with open(smtp_file, "r") as f:
                    data = json.load(f)
                return SMTPConfig(**data)
        except Exception:
            pass
        # Tentar via env vars
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


# Instancia global
config_manager = HardcodedConfigManager()