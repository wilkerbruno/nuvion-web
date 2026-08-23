"""Config compartilhada dos testes.

Duas responsabilidades:
1. Garantir variáveis de ambiente mínimas para `app.core.config.Settings`
   conseguir instanciar em CI, sem precisar de um banco real para os testes
   que não tocam o banco.
2. Fixtures `db_session`/`client` usadas por todos os arquivos de teste que
   batem na API (test_auth.py, test_proxies.py, test_browser_settings.py).

Importante: `app.dependency_overrides` é um dicionário no objeto `app`
compartilhado por todo o processo de teste. Um override feito no nível do
módulo (como as primeiras versões destes testes faziam) fica valendo para
TODOS os arquivos de teste depois que o pytest termina de importar todo
mundo na fase de coleta — o último arquivo importado "vence" e os testes
dos arquivos anteriores passam a rodar contra o banco em memória errado
(sintoma visto: `UNIQUE constraint failed` cruzando testes de arquivos
diferentes). As fixtures abaixo isolam isso por teste: cada teste ganha seu
próprio engine SQLite em memória e o override é desfeito no teardown.
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-ci-only")
# Fernet exige uma chave de 32 bytes urlsafe-base64 válida — não pode ser
# uma string arbitrária como as outras (JWT_SECRET_KEY aceita qualquer texto).
os.environ.setdefault("ENCRYPTION_KEY", "ASwOOLlSPXQ02i9TupC7AX-ESN5u-CR5gW6uzGXHN0Q=")

from app.db.session import get_db  # noqa: E402 (depende dos env vars acima)
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture()
def db_session():
    """Sessionmaker de um banco SQLite em memória exclusivo deste teste."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    # Semeia o catálogo de recompensas (tabela nova, ver
    # app/models/reward.py) — mesma chamada que scripts/sync_schema_live.py
    # faz em produção logo depois de criar a tabela pela primeira vez, para
    # que os testes de /rewards continuem vendo um catálogo não-vazio sem
    # precisar conhecer detalhes de reward_service.
    from app.services.reward_service import seed_default_rewards

    _seed_db = TestingSessionLocal()
    try:
        seed_default_rewards(_seed_db)
    finally:
        _seed_db.close()

    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestingSessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """TestClient da API já apontando para o banco isolado de `db_session`."""
    return TestClient(app)
