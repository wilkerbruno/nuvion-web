# backend/core/database.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from core.config import settings
from utils.logger import LOGGER


engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=20,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    connect_args={
        "charset": "utf8mb4",
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency para injeção de sessão do banco nas rotas."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Testa a conexão ao iniciar o servidor."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        LOGGER.debug("Banco conectado com sucesso")
    except Exception as e:
        LOGGER.error(f"Falha ao conectar ao banco: {e}")
        raise
