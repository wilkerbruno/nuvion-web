"""Testes do script de migração de dados (Fase 5,
scripts/migrate_from_desktop.py).

Simula o schema "antigo" (app desktop) com tabelas SQLite construídas à mão
reproduzindo exatamente as diferenças documentadas no relatório de
compatibilidade desta fase — `proxy` sem `user_id`/`is_selected`,
`payments.status` gravado em minúsculo — e o schema "novo" via
`Base.metadata.create_all()` (o mesmo mecanismo usado por `conftest.py` nos
outros testes). Usa bancos SQLite em arquivo (não `:memory:`) porque o
script abre conexões/engines separadas para ler e escrever.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    create_engine,
    insert,
    select,
)

from app.models import Base
from scripts.migrate_from_desktop import migrate_table, run, verify_table


def _old_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/old.db")
    metadata = MetaData()

    Table(
        "users",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("username", String(50)),
        Column("email", String(100)),
        Column("password_hash", Text),
        Column("name", String(100)),
        Column("phone", String(20)),
        Column("referral_code", String(6)),
        Column("account_type", String(20), default="Membro"),
        Column("status", String(20), default="Ativo"),
        Column("category", String(20), default="Standard"),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )

    # Schema antigo de verdade: SEM user_id/is_selected (adicionados na Fase 2).
    Table(
        "proxy",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("name", String(100)),
        Column("host", String(255)),
        Column("port", String(10)),
        Column("proxy_type", String(20)),
        Column("is_active", Boolean, default=True),
        Column("status", String(20), default="unknown"),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )

    Table(
        "ai_tools",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("name", String(100)),
        Column("url", Text),
        Column("category", String(50)),
        Column("proxy_id", String(36)),
        Column("rating", Numeric(3, 2)),
        Column("is_featured", Boolean, default=False),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )

    # payments.status gravado em minúsculo pelo código antigo (ver
    # relatório de compatibilidade — Payment.mark_as_paid()).
    Table(
        "payments",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("user_id", String(36)),
        Column("amount", Numeric(10, 2)),
        Column("payment_method", String(20)),
        Column("description", Text),
        Column("status", String(20)),
        Column("due_date", DateTime),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )

    metadata.create_all(engine)
    return engine, metadata


def _new_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/new.db")
    Base.metadata.create_all(bind=engine)
    return engine


def _uid():
    return str(uuid.uuid4())


def _now():
    # Dados reais do banco antigo sempre têm created_at/updated_at
    # preenchidos (BaseModel do desktop também não permite NULL aqui) — só
    # a fixture de teste precisa simular isso explicitamente.
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def fixtures(tmp_path):
    old_engine, old_metadata = _old_engine(tmp_path)
    new_engine = _new_engine(tmp_path)

    user_a, user_b = _uid(), _uid()
    proxy_ok, proxy_orphan_ref = _uid(), _uid()  # proxy_orphan_ref nunca é inserido
    ai_tool_ok, ai_tool_orphan = _uid(), _uid()
    payment_id = _uid()

    with old_engine.begin() as conn:
        conn.execute(
            insert(old_metadata.tables["users"]),
            [
                {
                    "id": user_a,
                    "username": "usuarioa",
                    "email": "a@old.dev",
                    "password_hash": "hash-a",
                    "name": "Usuário A",
                    "phone": "11999990000",
                    "referral_code": "AAAAAA",
                    "account_type": "Membro",
                    "status": "Ativo",
                    "category": "Standard",
                    "created_at": _now(),
                    "updated_at": _now(),
                },
                {
                    "id": user_b,
                    "username": "usuariob",
                    "email": "b@old.dev",
                    "password_hash": "hash-b",
                    "name": "Usuário B",
                    "phone": "11999990001",
                    "referral_code": "BBBBBB",
                    "account_type": "Admin",
                    "status": "Ativo",
                    "category": "Premium",
                    "created_at": _now(),
                    "updated_at": _now(),
                },
            ],
        )
        conn.execute(
            insert(old_metadata.tables["proxy"]),
            [
                {
                    "id": proxy_ok,
                    "name": "Proxy Antigo",
                    "host": "10.0.0.1",
                    "port": "8080",
                    "proxy_type": "HTTP",
                    "is_active": True,
                    "status": "available",
                    "created_at": _now(),
                    "updated_at": _now(),
                }
            ],
        )
        conn.execute(
            insert(old_metadata.tables["ai_tools"]),
            [
                {
                    "id": ai_tool_ok,
                    "name": "IA com proxy válido",
                    "url": "https://ia-ok.dev",
                    "category": "conversacao",
                    "proxy_id": proxy_ok,
                    "rating": 4.5,
                    "is_featured": True,
                    "created_at": _now(),
                    "updated_at": _now(),
                },
                {
                    "id": ai_tool_orphan,
                    "name": "IA com proxy orfao",
                    "url": "https://ia-orfa.dev",
                    "category": "conversacao",
                    "proxy_id": proxy_orphan_ref,  # nunca existiu / não migrado
                    "rating": 3.0,
                    "is_featured": False,
                    "created_at": _now(),
                    "updated_at": _now(),
                },
            ],
        )
        conn.execute(
            insert(old_metadata.tables["payments"]),
            [
                {
                    "id": payment_id,
                    "user_id": user_a,
                    "amount": 97.00,
                    "payment_method": "pix",
                    "description": "Standard",
                    "status": "confirmado",  # minúsculo, como o código antigo gravava
                    "due_date": _now(),
                    "created_at": _now(),
                    "updated_at": _now(),
                }
            ],
        )

    return {
        "old_engine": old_engine,
        "old_metadata": old_metadata,
        "new_engine": new_engine,
        "old_db_url": str(old_engine.url),
        "new_db_url": str(new_engine.url),
        "ids": {
            "user_a": user_a,
            "user_b": user_b,
            "proxy_ok": proxy_ok,
            "ai_tool_ok": ai_tool_ok,
            "ai_tool_orphan": ai_tool_orphan,
            "payment": payment_id,
        },
    }


def test_dry_run_does_not_write(fixtures):
    result = migrate_table(
        "users", fixtures["old_engine"], MetaData(), fixtures["new_engine"], execute=False
    )
    assert result.error is None
    assert result.old_rows == 2
    assert result.inserted == 2  # "seriam inseridas" — mas nada foi gravado de fato
    assert result.updated == 0

    with fixtures["new_engine"].connect() as conn:
        count = conn.execute(select(Base.metadata.tables["users"])).fetchall()
    assert count == []  # dry-run não grava nada


def test_users_migrate_with_all_columns(fixtures):
    result = migrate_table(
        "users", fixtures["old_engine"], MetaData(), fixtures["new_engine"], execute=True
    )
    assert result.error is None
    assert result.inserted == 2
    assert result.updated == 0

    with fixtures["new_engine"].connect() as conn:
        rows = {
            r.id: r
            for r in conn.execute(select(Base.metadata.tables["users"])).mappings()
        }
    assert fixtures["ids"]["user_a"] in rows
    assert rows[fixtures["ids"]["user_a"]]["username"] == "usuarioa"
    assert rows[fixtures["ids"]["user_b"]]["account_type"] == "Admin"


def test_proxy_gets_new_column_defaults(fixtures):
    # users precisa existir antes por causa da FK (aqui proxy é standalone,
    # mas seguimos a ordem real do script mesmo assim).
    migrate_table("users", fixtures["old_engine"], MetaData(), fixtures["new_engine"], execute=True)
    result = migrate_table(
        "proxy", fixtures["old_engine"], MetaData(), fixtures["new_engine"], execute=True
    )
    assert result.error is None
    assert result.inserted == 1

    with fixtures["new_engine"].connect() as conn:
        row = conn.execute(
            select(Base.metadata.tables["proxy"]).where(
                Base.metadata.tables["proxy"].c.id == fixtures["ids"]["proxy_ok"]
            )
        ).mappings().first()

    assert row is not None
    assert row["user_id"] is None
    assert row["is_selected"] is False
    assert row["name"] == "Proxy Antigo"


def test_payment_status_is_normalized_to_canonical_case(fixtures):
    migrate_table("users", fixtures["old_engine"], MetaData(), fixtures["new_engine"], execute=True)
    result = migrate_table(
        "payments", fixtures["old_engine"], MetaData(), fixtures["new_engine"], execute=True
    )
    assert result.error is None

    with fixtures["new_engine"].connect() as conn:
        row = conn.execute(
            select(Base.metadata.tables["payments"]).where(
                Base.metadata.tables["payments"].c.id == fixtures["ids"]["payment"]
            )
        ).mappings().first()

    assert row["status"] == "Confirmado"  # normalizado, não "confirmado"


def test_ai_tools_orphan_proxy_id_is_nulled_with_warning(fixtures):
    migrate_table("users", fixtures["old_engine"], MetaData(), fixtures["new_engine"], execute=True)
    migrate_table("proxy", fixtures["old_engine"], MetaData(), fixtures["new_engine"], execute=True)
    result = migrate_table(
        "ai_tools", fixtures["old_engine"], MetaData(), fixtures["new_engine"], execute=True
    )
    assert result.error is None
    assert result.inserted == 2
    assert any("órfão" in w for w in result.warnings)

    with fixtures["new_engine"].connect() as conn:
        rows = {
            r.id: r
            for r in conn.execute(select(Base.metadata.tables["ai_tools"])).mappings()
        }

    assert rows[fixtures["ids"]["ai_tool_ok"]]["proxy_id"] == fixtures["ids"]["proxy_ok"]
    assert rows[fixtures["ids"]["ai_tool_orphan"]]["proxy_id"] is None


def test_rerunning_migration_is_idempotent(fixtures):
    first = migrate_table("users", fixtures["old_engine"], MetaData(), fixtures["new_engine"], execute=True)
    assert (first.inserted, first.updated) == (2, 0)

    second = migrate_table(
        "users", fixtures["old_engine"], MetaData(), fixtures["new_engine"], execute=True
    )
    assert (second.inserted, second.updated) == (0, 2)  # já existem — vira update, não duplica

    with fixtures["new_engine"].connect() as conn:
        total = conn.execute(select(Base.metadata.tables["users"])).fetchall()
    assert len(total) == 2  # não duplicou linhas


def test_verify_table_reports_missing_rows(fixtures):
    # Só migra users (não proxy/ai_tools/payments) e confere que a
    # verificação aponta o que ainda falta.
    migrate_table("users", fixtures["old_engine"], MetaData(), fixtures["new_engine"], execute=True)

    users_report = verify_table("users", fixtures["old_engine"], MetaData(), fixtures["new_engine"])
    assert "OK" in users_report

    proxy_report = verify_table("proxy", fixtures["old_engine"], MetaData(), fixtures["new_engine"])
    assert "FALTAM 1" in proxy_report


def test_run_end_to_end_dry_run_then_execute(fixtures, capsys):
    ok_dry = run(
        fixtures["old_db_url"],
        fixtures["new_db_url"],
        ["users", "proxy", "ai_tools", "payments"],
        execute=False,
        continue_on_error=False,
    )
    assert ok_dry is True
    with fixtures["new_engine"].connect() as conn:
        assert conn.execute(select(Base.metadata.tables["users"])).fetchall() == []

    ok_real = run(
        fixtures["old_db_url"],
        fixtures["new_db_url"],
        ["users", "proxy", "ai_tools", "payments"],
        execute=True,
        continue_on_error=False,
    )
    assert ok_real is True

    with fixtures["new_engine"].connect() as conn:
        assert len(conn.execute(select(Base.metadata.tables["users"])).fetchall()) == 2
        assert len(conn.execute(select(Base.metadata.tables["proxy"])).fetchall()) == 1
        assert len(conn.execute(select(Base.metadata.tables["ai_tools"])).fetchall()) == 2
        assert len(conn.execute(select(Base.metadata.tables["payments"])).fetchall()) == 1

    captured = capsys.readouterr()
    assert "Resumo" in captured.out


def test_missing_old_table_is_skipped_not_fatal(fixtures):
    # "notifications" não existe no banco antigo simulado aqui — o script
    # deve logar e pular, não quebrar a migração inteira.
    result = migrate_table(
        "notifications", fixtures["old_engine"], MetaData(), fixtures["new_engine"], execute=True
    )
    assert result.error == "tabela ausente no banco antigo"
    assert result.old_rows == 0
