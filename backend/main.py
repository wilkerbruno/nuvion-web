# backend/main.py
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

sys.path.insert(0, os.environ.get("DESKTOP_PROJECT_PATH", "/opt/nuvion-desktop"))

from api.routes import auth, tools, favorites, payments, notifications, admin, proxy, worker
from core.config import settings, CORS_ORIGINS
from core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Nuvion Browser API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url=None,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

app.include_router(auth.router,          prefix="/api/auth",          tags=["auth"])
app.include_router(tools.router,         prefix="/api/tools",         tags=["tools"])
app.include_router(favorites.router,     prefix="/api/favorites",     tags=["favorites"])
app.include_router(payments.router,      prefix="/api/payments",      tags=["payments"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(admin.router,         prefix="/api/admin",         tags=["admin"])
app.include_router(proxy.router,         prefix="/api/proxy",         tags=["proxy"])
app.include_router(worker.router,        prefix="/api/worker",        tags=["worker"])


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "cors_origins": CORS_ORIGINS,
    }