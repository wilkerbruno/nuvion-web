"""Testes de integração de scripts/sync_schema_live.py contra um MySQL real.

Por que MySQL de verdade e não SQLite (como os outros testes do projeto):
o comportamento central deste script — ampliar um ENUM do MySQL sem perder
dado (`ALTER TABLE ... MODIFY COLUMN ... ENUM(...)`) — não existe no
SQLite (o dialeto SQLite reflete `Enum` do SQLAlchemy como VARCHAR + CHECK,
sem um tipo ENUM próprio para inspecionar). Testar isso contra um fake
seria testar a suposição, não o comportamento real.

Pulados automaticamente se NUVION_TEST_MYSQL_URL não estiver definido — não
é o caso do CI deste projeto (sem serviço MySQL, ver
.github/workflows/backend-ci.yml), então rodar `pytest -q` normalmente
pula este arquivo sem falhar. Para rodar de verdade, localmente ou em CI
com um serviço MySQL:

    export NUVION_TEST_MYSQL_URL="mysql+pymysql://usuario:senha@localhost/banco_de_teste"
    pytest tests/test_sync_schema_live.py -v

O banco apontado por NUVION_TEST_MYSQL_URL é dropado/recriado tabela por
tabela a cada teste — não aponte para um banco com dados que importam.
"""
import os

import pytest
from sqlalchemy import create_engine, inspect, text

from app.models import Base as AppBase
from scripts.sync_schema_live import build_plan, run

MYSQL_URL = os.environ.get("NUVION_TEST_MYSQL_URL")

pytestmark = pytest.mark.skipif(
    not MYSQL_URL,
    reason="NUVION_TEST_MYSQL_URL não definido — teste de integração com MySQL real pulado",
)


OLD_SCHEMA_DDL = [
    """
    CREATE TABLE users (
        id VARCHAR(36) PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME
    )
    """,
    """
    CREATE TABLE proxy (
        id VARCHAR(36) PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        host VARCHAR(255) NOT NULL,
        port INT NOT NULL,
        proxy_type VARCHAR(20) NOT NULL,
        username VARCHAR(100),
        password TEXT,
        is_active TINYINT(1) DEFAULT 1,
        status VARCHAR(20) DEFAULT 'unknown',
        current_ai VARCHAR(100),
        response_time INT,
        last_tested DATETIME,
        created_at DATETIME NOT NULL,
        updated_at DATETIME
    )
    """,
    """
    CREATE TABLE payments (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        payment_method ENUM('pix','cartao') NOT NULL,
        description ENUM('Standard','Premium','VIP') NOT NULL DEFAULT 'Standard',
        status ENUM('Confirmado','Atrasado','Pendente','Cancelado') DEFAULT 'Pendente',
        payment_date DATETIME,
        due_date DATETIME NOT NULL,
        payment_details JSON,
        transaction_id VARCHAR(100) UNIQUE,
        notes TEXT,
        created_at DATETIME NOT NULL,
        updated_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """,
    # Shape pré-USDT (antes desta migração): sem usdt_wallet_address/
    # usdt_network/standard_amount_usdt/premium_amount_usdt/vip_amount_usdt.
    """
    CREATE TABLE payment_configs (
        id VARCHAR(36) PRIMARY KEY,
        config_key VARCHAR(50) UNIQUE NOT NULL,
        access_token TEXT,
        public_key TEXT,
        client_id TEXT,
        client_secret TEXT,
        webhook_url TEXT,
        pix_key VARCHAR(200),
        pix_name VARCHAR(100),
        environment ENUM('sandbox','production') NOT NULL DEFAULT 'sandbox',
        currency VARCHAR(3) NOT NULL DEFAULT 'BRL',
        min_amount VARCHAR(10) DEFAULT '1.00',
        standard_amount VARCHAR(10) NOT NULL DEFAULT '97.00',
        premium_amount VARCHAR(10) NOT NULL DEFAULT '70.00',
        vip_amount VARCHAR(10) NOT NULL DEFAULT '0.00',
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        last_tested_at DATETIME,
        additional_config JSON,
        created_at DATETIME NOT NULL,
        updated_at DATETIME
    )
    """,
]


@pytest.fixture()
def old_schema_engine():
    engine = create_engine(MYSQL_URL)
    # Limpa qualquer resto de execução anterior (inclusive tabelas do
    # schema novo, caso um teste anterior tenha falhado no meio).
    AppBase.metadata.drop_all(bind=engine, checkfirst=True)
    with engine.begin() as conn:
        for table in ("payments", "proxy", "payment_configs", "users"):
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        for ddl in OLD_SCHEMA_DDL:
            conn.execute(text(ddl))

    yield engine

    AppBase.metadata.drop_all(bind=engine, checkfirst=True)
    engine.dispose()


def _seed(engine):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, username, created_at, updated_at) "
                "VALUES ('u1', 'alice', NOW(), NOW())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO proxy "
                "(id, name, host, port, proxy_type, is_active, status, created_at, updated_at) "
                "VALUES ('p1', 'Proxy 1', '1.2.3.4', 8080, 'HTTP', 1, 'available', NOW(), NOW())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO payments (id, user_id, amount, payment_method, description, status, "
                "due_date, created_at, updated_at) "
                "VALUES ('pay1', 'u1', 97.00, 'pix', 'Standard', 'Confirmado', NOW(), NOW(), NOW())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO payment_configs "
                "(id, config_key, access_token, standard_amount, premium_amount, vip_amount, "
                "is_active, created_at, updated_at) "
                "VALUES ('cfg1', 'mercadopago_main', 'APP_USR-teste', '97.00', '70.00', '0.00', "
                "1, NOW(), NOW())"
            )
        )


def test_dry_run_detects_known_diffs_and_writes_nothing(old_schema_engine):
    _seed(old_schema_engine)

    plan = build_plan(old_schema_engine)
    columns_to_add = {(t, c) for t, c, _ddl in plan.columns_to_add}
    assert ("proxy", "user_id") in columns_to_add
    assert ("proxy", "is_selected") in columns_to_add
    assert ("payments", "crypto_amount") in columns_to_add
    assert ("payment_configs", "usdt_wallet_address") in columns_to_add
    assert ("payment_configs", "usdt_network") in columns_to_add
    assert ("payment_configs", "standard_amount_usdt") in columns_to_add
    assert ("payment_configs", "premium_amount_usdt") in columns_to_add
    assert ("payment_configs", "vip_amount_usdt") in columns_to_add
    assert plan.payment_method_needs_widen is True
    assert plan.payment_method_current_enum == ["pix", "cartao"]
    assert "notifications" in plan.tables_to_create
    assert "ai_tools" in plan.tables_to_create

    assert run(MYSQL_URL, execute=False) is True

    proxy_cols = {c["name"] for c in inspect(old_schema_engine).get_columns("proxy")}
    assert "user_id" not in proxy_cols
    assert "is_selected" not in proxy_cols
    payment_cols = {c["name"] for c in inspect(old_schema_engine).get_columns("payments")}
    assert "crypto_amount" not in payment_cols
    config_cols = {c["name"] for c in inspect(old_schema_engine).get_columns("payment_configs")}
    assert "usdt_wallet_address" not in config_cols
    assert "notifications" not in inspect(old_schema_engine).get_table_names()


def test_execute_adds_columns_and_widens_enum_without_losing_data(old_schema_engine):
    _seed(old_schema_engine)

    assert run(MYSQL_URL, execute=True) is True

    insp = inspect(old_schema_engine)
    proxy_cols = {c["name"] for c in insp.get_columns("proxy")}
    assert {"user_id", "is_selected"} <= proxy_cols

    payment_cols = {c["name"]: c for c in insp.get_columns("payments")}
    assert set(payment_cols["payment_method"]["type"].enums) == {"pix", "cartao", "usdt"}
    assert "crypto_amount" in payment_cols

    config_cols = {c["name"] for c in insp.get_columns("payment_configs")}
    assert {
        "usdt_wallet_address",
        "usdt_network",
        "standard_amount_usdt",
        "premium_amount_usdt",
        "vip_amount_usdt",
    } <= config_cols

    assert "notifications" in insp.get_table_names()
    assert "ai_tools" in insp.get_table_names()

    with old_schema_engine.connect() as conn:
        proxy_row = conn.execute(
            text("SELECT name, host, port, is_active, user_id, is_selected FROM proxy WHERE id='p1'")
        ).mappings().first()
        assert proxy_row["name"] == "Proxy 1"
        assert proxy_row["host"] == "1.2.3.4"
        assert proxy_row["port"] == 8080
        assert proxy_row["is_active"] == 1
        assert proxy_row["user_id"] is None
        assert proxy_row["is_selected"] == 0

        payment_row = conn.execute(
            text("SELECT amount, payment_method, status, crypto_amount FROM payments WHERE id='pay1'")
        ).mappings().first()
        assert str(payment_row["amount"]) == "97.00"
        assert payment_row["payment_method"] == "pix"
        assert payment_row["status"] == "Confirmado"
        assert payment_row["crypto_amount"] is None

        config_row = conn.execute(
            text(
                "SELECT access_token, standard_amount, usdt_wallet_address, usdt_network "
                "FROM payment_configs WHERE id='cfg1'"
            )
        ).mappings().first()
        assert config_row["access_token"] == "APP_USR-teste"
        assert config_row["standard_amount"] == "97.00"
        assert config_row["usdt_wallet_address"] is None
        assert config_row["usdt_network"] == "TRC20"

        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM proxy")).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM payments")).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM payment_configs")).scalar() == 1


def test_rerunning_execute_is_idempotent(old_schema_engine):
    _seed(old_schema_engine)

    assert run(MYSQL_URL, execute=True) is True
    # segunda execução: nada deveria mudar, e não pode dar erro de
    # "coluna/tabela já existe" (é exatamente esse cenário que acontece se
    # o script rodar de novo depois que já rodou uma vez em produção).
    assert run(MYSQL_URL, execute=True) is True

    plan = build_plan(old_schema_engine)
    assert plan.has_changes is False

    with old_schema_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM proxy")).scalar() == 1


def test_fresh_empty_database_gets_full_schema_created():
    # Simula um banco novo/vazio (nenhuma tabela do schema antigo ainda) —
    # deve simplesmente criar tudo, sem erro.
    engine = create_engine(MYSQL_URL)
    AppBase.metadata.drop_all(bind=engine, checkfirst=True)

    try:
        plan = build_plan(engine)
        assert set(plan.tables_to_create) == set(AppBase.metadata.tables.keys())

        assert run(MYSQL_URL, execute=True) is True

        insp = inspect(engine)
        assert "users" in insp.get_table_names()
        assert {"user_id", "is_selected"} <= {c["name"] for c in insp.get_columns("proxy")}
    finally:
        AppBase.metadata.drop_all(bind=engine, checkfirst=True)
        engine.dispose()
