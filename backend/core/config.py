# backend/core/config.py
import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "TROQUE-ESTA-CHAVE-EM-PRODUCAO")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Banco
    DB_HOST: str = os.getenv("DB_HOST", "2.25.131.174")
    DB_PORT: int = int(os.getenv("DB_PORT", "33060"))
    DB_NAME: str = os.getenv("DB_NAME", "browser")
    DB_USER: str = os.getenv("DB_USER", "admin")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "V71C2Fd1eqJ8p0Pn0x4aO5mW")

    # CORS — aceita qualquer origem configurada via env
    @property
    def CORS_ORIGINS(self) -> List[str]:
        frontend = os.getenv("FRONTEND_URL", "")
        origins = [
            "http://localhost:5173",
            "http://localhost:3000",
        ]
        if frontend:
            origins.append(frontend)
        # Suporte a múltiplas origens via EXTRA_CORS_ORIGINS separadas por vírgula
        extra = os.getenv("EXTRA_CORS_ORIGINS", "")
        if extra:
            origins.extend([o.strip() for o in extra.split(",") if o.strip()])
        return origins

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Projeto desktop
    DESKTOP_PROJECT_PATH: str = os.getenv("DESKTOP_PROJECT_PATH", "/opt/nuvion-desktop")

    # Mercado Pago
    MP_WEBHOOK_SECRET: str = os.getenv("MP_WEBHOOK_SECRET", "")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()