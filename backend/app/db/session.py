"""Engine e sessão do banco.

Equivalente web de database/sqlalchemy_config.py. A diferença principal:
a URL de conexão vem só de app.core.config.settings (variáveis de
ambiente), nunca de credenciais hardcoded no arquivo. O pool tuning
(pool_size, max_overflow etc.) foi mantido igual ao original.
"""
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import settings
from app.core.logging import LOGGER

engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_timeout=60,
    pool_recycle=7200,
    echo=False,
    connect_args={
        "charset": "utf8mb4",
        "connect_timeout": 20,
        "read_timeout": 60,
        "write_timeout": 60,
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency do FastAPI: uma sessão por request, sempre fechada ao final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> bool:
    try:
        with engine.connect():
            return True
    except Exception as e:
        LOGGER.error(f"Falha ao conectar no banco: {e}")
        return False
