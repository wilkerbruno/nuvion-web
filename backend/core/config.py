# backend/core/config.py
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DEBUG: bool = False
    SECRET_KEY: str = "TROQUE-ESTA-CHAVE-EM-PRODUCAO"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    DB_HOST: str = "2.25.131.174"
    DB_PORT: int = 33060
    DB_NAME: str = "browser"
    DB_USER: str = "admin"
    DB_PASSWORD: str = "V71C2Fd1eqJ8p0Pn0x4aO5mW"

    FRONTEND_URL: str = "https://divisions-nuvion-web.lcgx8u.easypanel.host"
    REDIS_URL: str = "redis://localhost:6379/0"
    DESKTOP_PROJECT_PATH: str = "/opt/nuvion-desktop"
    MP_WEBHOOK_SECRET: str = ""

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

# CORS origins — sempre atualizado com o FRONTEND_URL real
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    settings.FRONTEND_URL,
]