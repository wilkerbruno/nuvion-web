"""Ponto de entrada da API — equivalente web de main.py no app desktop.

Lá, main.py subia uma QApplication; aqui sobe um app FastAPI. A validação de
credenciais de banco antes de tudo (validate_database_credentials) também
tem equivalente: app.core.config.Settings falha ao instanciar se
DB_USER/DB_PASSWORD/JWT_SECRET_KEY não estiverem no ambiente.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    admin_payment_config,
    admin_proxies,
    admin_rewards,
    admin_users,
    ai_tool_secrets,
    ai_tools,
    auth,
    browser_settings,
    dashboard,
    downloads,
    health,
    notifications,
    payments,
    proxies,
    rewards,
    tool_bookmarks,
    users,
)
from app.core.config import settings
from app.core.logging import LOGGER


def _cors_origins() -> list[str]:
    """Origens liberadas: painel web + a extensão (Fase 2), se já publicada.

    Extensões Manifest V3 enviam `Origin: chrome-extension://<id>` — como o
    ID só existe depois de publicada (ou carregada localmente em modo dev),
    `settings.EXTENSION_ID` fica vazio por padrão e essa origem simplesmente
    não é adicionada até ser configurada.
    """
    origins = list(settings.CORS_ALLOWED_ORIGINS)
    if settings.EXTENSION_ID:
        origins.append(f"chrome-extension://{settings.EXTENSION_ID}")
    return origins


@asynccontextmanager
async def lifespan(_app: FastAPI):
    LOGGER.info(f"{settings.APP_NAME} iniciando — ambiente: {settings.ENVIRONMENT}")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="API do Nuvion Web — painel de gestão e camada de dados "
    "compartilhada com a extensão de navegação.",
    lifespan=lifespan,
)

# CORS restrito à origem do painel web (nunca "*" — o sistema lida com
# pagamento e proxy de usuários; ver plano de migração, seção 4).
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    """Sem isso, `GET /` cai em 404 — inofensivo pra quem usa a API direto
    (ninguém chama `/`), mas plataformas como o EasyPanel costumam checar a
    saúde do serviço batendo na raiz `/` por padrão, quando nenhum caminho
    de health check é configurado explicitamente. Um 404 ali pode ser lido
    como "serviço não saudável" e disparar reinícios repetidos do container
    mesmo com a API funcionando normalmente — ver `/health` para o check
    real (com status do banco)."""
    return {"service": settings.APP_NAME, "status": "ok", "docs": "/docs", "health": "/health"}


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(dashboard.router)
app.include_router(proxies.router)
app.include_router(browser_settings.router)
app.include_router(payments.router)
app.include_router(admin_payment_config.router)
app.include_router(admin_proxies.router)
app.include_router(admin_rewards.router)
app.include_router(admin_users.router)
app.include_router(rewards.router)
app.include_router(ai_tools.router)
app.include_router(ai_tool_secrets.router)
app.include_router(tool_bookmarks.router)
app.include_router(notifications.router)
app.include_router(notifications.admin_router)
app.include_router(downloads.router)
