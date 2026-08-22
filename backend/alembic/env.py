"""Configuração do Alembic (portado de alembic/env.py).

A diferença central em relação ao original: a URL de conexão vem de
app.core.config.settings (variáveis de ambiente / .env), nunca de
credenciais hardcoded no arquivo — ver nota em app/core/config.py.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.core.logging import LOGGER  # noqa: E402
from app.models import Base  # noqa: E402 — importar registra todas as tabelas

target_metadata = Base.metadata
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_database_url() -> str:
    safe_url = (
        f"mysql+pymysql://{settings.DB_USER}:****@{settings.DB_HOST}:"
        f"{settings.DB_PORT}/{settings.DB_NAME}"
    )
    LOGGER.info(f"Alembic usando: {safe_url}")
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Gera SQL sem se conectar de fato ao banco (`alembic upgrade --sql`)."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica as migrações conectando de fato ao banco."""
    connectable = create_engine(
        get_database_url(),
        poolclass=pool.NullPool,
        echo=False,
        connect_args={"charset": "utf8mb4", "connect_timeout": 10, "read_timeout": 30},
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
