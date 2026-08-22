"""Configuração central do backend, via variáveis de ambiente.

No app desktop original (utils/config_manager.py), as credenciais de banco
e SMTP estavam HARDCODED direto no código-fonte e versionadas no Git — isso
foi identificado durante a migração como uma exposição de segurança real
(inclusive senha de produção do MySQL e senha de app do Gmail em texto
plano). Aqui isso é corrigido por padrão: nada de credencial tem valor
default; a aplicação recusa subir sem elas configuradas via ambiente/.env
(que fica no .gitignore).

Ação recomendada em paralelo a esta migração: rotacionar a senha do MySQL e
a senha de app SMTP que estavam expostas no repositório desktop.
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Aplicação ---
    APP_NAME: str = "Nuvion Web API"
    ENVIRONMENT: str = Field(default="development")  # development | staging | production
    LOG_LEVEL: str = "INFO"

    # --- Banco de dados (sem defaults para host/usuário/senha de verdade) ---
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "nuvion"
    DB_USER: str = Field(...)
    DB_PASSWORD: str = Field(...)

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    # --- Autenticação (JWT) ---
    JWT_SECRET_KEY: str = Field(...)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- CORS: origem do painel web + ID da extensão publicada ---
    # Nunca usar "*" aqui — o sistema lida com pagamento e proxy de usuários.
    CORS_ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    EXTENSION_ID: str = ""  # preenchido quando a extensão for publicada

    # --- Mercado Pago / PIX (sem defaults — segredo fica só em ambiente) ---
    # Na prática, quem manda são as credenciais guardadas em PaymentConfig
    # (tabela payment_configs, editável por admin em /admin/payment-config)
    # — mesma arquitetura do app desktop, que permitia trocar de sandbox
    # para produção sem redeploy. Estas aqui só servem de fallback/seed
    # inicial (ex.: primeira config via variável de ambiente/CI).
    MERCADOPAGO_ACCESS_TOKEN: str = ""
    MERCADOPAGO_APP_ID: str = ""
    # Segredo do webhook do Mercado Pago (assinatura HMAC do header
    # x-signature) — opcional; se vazio, o webhook aceita notificações sem
    # verificar assinatura (loga aviso). Configurar em produção.
    MERCADOPAGO_WEBHOOK_SECRET: str = ""

    # --- USDT (TRC20) — pagamento cripto self-custodial (sem provedor
    # terceiro; ver app/services/tron_client.py e docs/PAGAMENTOS_CRIPTO.md).
    # Não é segredo — é só a API pública do TronGrid pra ler transferências
    # da blockchain (nunca assina nem envia transação). Opcional: sem ela,
    # a API pública do TronGrid ainda funciona, só com limite de taxa menor.
    TRONGRID_API_KEY: str = ""

    # --- Criptografia de credenciais de terceiros (Fase 4) ---
    # Usada para cifrar (Fernet) usuário/senha de login direto salvos em
    # AIDirectCredentials — credenciais que o app desktop original salvava
    # em texto plano no banco (ver crud/sqlalchemy_direct_credentials_manager.py:
    # "SEM criptografia para testes"). Sem default de propósito, mesma
    # política de DB_USER/DB_PASSWORD/JWT_SECRET_KEY: gerar com
    # `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
    ENCRYPTION_KEY: str = Field(...)

    # --- SMTP ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_EMAIL: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_SENDER_NAME: str = "Nuvion Browser"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
