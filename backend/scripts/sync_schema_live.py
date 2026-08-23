"""Ajusta o schema de um banco MySQL que já está em uso — pensado para o
caso confirmado pela Divisions Tech: o banco MySQL do EasyPanel que o app
desktop já usa em produção, com dados reais, vai ser compartilhado com este
backend web desde o início, sem uma cópia separada (ver docs/PILOTO.md,
"Estratégia B").

Complementar a `migrate_from_desktop.py` (que COPIA dados para um banco
NOVO/separado) — este script aqui não copia nada, só garante que o schema
do banco já existente tem o que este backend precisa. É estritamente
aditivo:

  1. Cria as tabelas do schema deste backend que ainda não existirem no
     banco (equivalente a CREATE TABLE IF NOT EXISTS — nunca mexe em
     tabela que já existe).
  2. Adiciona as colunas novas conhecidas (ver `KNOWN_NEW_COLUMNS` abaixo)
     nas tabelas que já existem, se ainda não estiverem lá — linhas já
     existentes recebem `NULL`/o valor default da própria coluna; nenhum
     outro dado é tocado. Hoje isso cobre `proxy.user_id`/`is_selected`
     (Fase 2), `payments.crypto_amount` e as colunas de USDT em
     `payment_configs` (pagamento em cripto self-custodial).
  3. `payments.payment_method`: amplia o ENUM para incluir "usdt" se ainda
     não incluído. Ampliar um ENUM do MySQL é seguro para os dados já
     existentes — o MySQL remapeia pelos nomes dos valores, não pela
     posição, e nenhum valor antigo é removido da lista. ("boleto" existiu
     brevemente nesta migração e foi removido do produto antes de qualquer
     uso em produção — nunca chegou a entrar nesse ENUM em banco real.)
  4. Se a tabela `rewards` for criada agora pela primeira vez (catálogo de
     recompensas, antes um arquivo JSON estático — ver
     app/services/reward_service.py), semeia nela os itens que estavam
     nesse JSON, pra não "sumir" o catálogo que já estava no ar. Só insere
     em tabela vazia — nunca roda de novo depois da primeira vez.
  5. Reporta (sem alterar nada) qualquer outra diferença de coluna que
     encontrar entre o schema do banco e o schema esperado pelo backend,
     para você decidir manualmente — este script não tenta adivinhar
     mudanças além das listadas acima.

O que este script NUNCA faz: DELETE, DROP TABLE, DROP COLUMN, remover valor
de ENUM, ou qualquer UPDATE em dado de linha existente. Só CREATE TABLE,
ALTER TABLE ADD COLUMN e ALTER TABLE MODIFY COLUMN (só pra ampliar enum).

Dry-run por padrão — só imprime o que faria. Passe --execute para aplicar
de verdade. Idempotente: rodar de novo depois de já ter aplicado não faz
nada (tudo já vai estar presente).

Uso:
    cd backend
    python -m scripts.sync_schema_live --db-url mysql+pymysql://user:pass@host:3306/db

    # depois de conferir a saída acima:
    python -m scripts.sync_schema_live --db-url mysql+pymysql://user:pass@host:3306/db --execute

Faça backup do banco antes do --execute — praxe padrão antes de qualquer
alteração de schema em produção, mesmo sendo uma operação aditiva e já
testada contra um MySQL 8 real (ver tests/test_sync_schema_live.py e o
runbook em docs/MIGRACAO_DADOS.md).
"""
import argparse
import sys
from dataclasses import dataclass, field
from typing import List, Tuple

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.core.logging import LOGGER
from app.models import Base  # noqa: F401 — importar registra todas as tabelas em Base.metadata

PAYMENT_METHOD_NEW_VALUE = "usdt"

# Colunas novas conhecidas por tabela: (nome_da_coluna, definição SQL a
# usar no ADD COLUMN). Só entram aqui colunas seguras de adicionar sem
# nenhuma decisão de negócio embutida (nullable, ou com DEFAULT explícito
# pra não quebrar linhas já existentes). `proxy.user_id` tem tratamento
# extra (índice + FK) depois de adicionada — ver `_add_extra_for_column`.
KNOWN_NEW_COLUMNS = {
    "proxy": [
        ("user_id", "VARCHAR(36) NULL"),
        ("is_selected", "TINYINT(1) NOT NULL DEFAULT 0"),
    ],
    "payments": [
        # Valor exato em USDT (6 casas) usado só por pagamentos "usdt" — ver
        # app/crud/payment.py::generate_unique_usdt_amount.
        ("crypto_amount", "DECIMAL(18,6) NULL"),
    ],
    "payment_configs": [
        ("usdt_wallet_address", "VARCHAR(64) NULL"),
        ("usdt_network", "VARCHAR(20) NOT NULL DEFAULT 'TRC20'"),
        ("standard_amount_usdt", "VARCHAR(10) NULL"),
        ("premium_amount_usdt", "VARCHAR(10) NULL"),
        ("vip_amount_usdt", "VARCHAR(10) NULL"),
    ],
}


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


@dataclass
class SyncPlan:
    tables_to_create: List[str] = field(default_factory=list)
    # (tabela, coluna, definição SQL) — colunas de KNOWN_NEW_COLUMNS que
    # ainda faltam numa tabela que já existe.
    columns_to_add: List[Tuple[str, str, str]] = field(default_factory=list)
    payment_method_needs_widen: bool = False
    payment_method_current_enum: List[str] = field(default_factory=list)
    other_drift: List[str] = field(default_factory=list)  # só informativo — nunca aplicado

    @property
    def has_changes(self) -> bool:
        return bool(self.tables_to_create or self.columns_to_add or self.payment_method_needs_widen)


def _existing_columns(engine: Engine, table: str) -> dict:
    return {c["name"]: c for c in inspect(engine).get_columns(table)}


def build_plan(engine: Engine) -> SyncPlan:
    plan = SyncPlan()
    existing_tables = set(inspect(engine).get_table_names())
    expected_tables = set(Base.metadata.tables.keys())
    plan.tables_to_create = sorted(expected_tables - existing_tables)

    known_column_names = set()
    for table_name, columns in KNOWN_NEW_COLUMNS.items():
        for col_name, _ddl in columns:
            known_column_names.add((table_name, col_name))
        if table_name not in existing_tables:
            continue  # tabela inteira será criada do zero, já com essas colunas
        existing_cols = set(_existing_columns(engine, table_name))
        for col_name, ddl in columns:
            if col_name not in existing_cols:
                plan.columns_to_add.append((table_name, col_name, ddl))

    if "payments" in existing_tables:
        payment_cols = _existing_columns(engine, "payments")
        method_col = payment_cols.get("payment_method")
        if method_col is not None:
            current_enum = list(getattr(method_col["type"], "enums", []) or [])
            plan.payment_method_current_enum = current_enum
            plan.payment_method_needs_widen = PAYMENT_METHOD_NEW_VALUE not in current_enum

    # Verificação genérica e só informativa em todas as tabelas já
    # existentes: qualquer coluna do modelo ausente no banco é reportada,
    # nunca alterada automaticamente — só as colunas listadas em
    # KNOWN_NEW_COLUMNS têm tratamento automático.
    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue
        db_cols = set(_existing_columns(engine, table_name))
        expected_cols = set(table.columns.keys())
        for col in sorted(expected_cols - db_cols):
            if (table_name, col) in known_column_names:
                continue
            plan.other_drift.append(
                f"{table_name}.{col} está no modelo mas não no banco (não tratado automaticamente)"
            )

    return plan


def print_plan(plan: SyncPlan) -> None:
    print("\n=== Plano de ajuste de schema ===")
    print(
        f"Tabelas a criar: {', '.join(plan.tables_to_create)}"
        if plan.tables_to_create
        else "Tabelas: nenhuma faltando."
    )

    if plan.columns_to_add:
        print("Colunas a adicionar:")
        for table_name, col_name, ddl in plan.columns_to_add:
            print(f"  - {table_name}.{col_name} ({ddl})")
    else:
        print("Colunas conhecidas: nenhuma faltando.")

    if plan.payment_method_needs_widen:
        new_enum = plan.payment_method_current_enum + [PAYMENT_METHOD_NEW_VALUE]
        print(f"payments.payment_method: ENUM {plan.payment_method_current_enum!r} → {new_enum!r}")
    else:
        print(f"payments.payment_method: já inclui {PAYMENT_METHOD_NEW_VALUE!r} (ou tabela/coluna ausente).")

    if plan.other_drift:
        print("\n⚠ Diferenças adicionais encontradas (NÃO alteradas automaticamente):")
        for line in plan.other_drift:
            print(f"  - {line}")
    print()


def _add_extra_for_column(engine: Engine, table_name: str, col_name: str) -> None:
    """Tratamento extra depois de adicionar uma coluna específica — hoje só
    `proxy.user_id` precisa (índice + foreign key). Falhas aqui viram só um
    aviso, não abortam o script: a coluna em si já foi criada normalmente,
    é só a integridade referencial/índice que ficaria de fora."""
    if table_name != "proxy" or col_name != "user_id":
        return
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE proxy ADD INDEX ix_proxy_user_id (user_id)"))
        except Exception as e:
            LOGGER.warning(f"Não foi possível criar índice em proxy.user_id: {e}")
        try:
            conn.execute(
                text(
                    "ALTER TABLE proxy ADD CONSTRAINT fk_proxy_user_id "
                    "FOREIGN KEY (user_id) REFERENCES users(id)"
                )
            )
        except Exception as e:
            LOGGER.warning(
                "Não foi possível criar a foreign key proxy.user_id → users.id "
                f"(a coluna foi criada normalmente; só a restrição de integridade "
                f"referencial ficou de fora — confira manualmente): {e}"
            )


def _seed_new_tables(engine: Engine, plan: SyncPlan) -> None:
    """Semeia dados default em tabelas que acabaram de ser criadas pela
    primeira vez — hoje só `rewards` (catálogo antes vindo de
    diamond_platform_config.json, ver app/services/reward_service.py). Só
    roda quando a tabela realmente não existia antes: é idempotente por
    natureza (o próprio `seed_default_rewards` só insere em tabela vazia),
    mas isso evita até abrir a sessão à toa numa tabela que já existia."""
    if "rewards" not in plan.tables_to_create:
        return
    from app.services.reward_service import seed_default_rewards

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        count = seed_default_rewards(session)
        if count:
            print(f"✓ Catálogo de recompensas semeado com {count} item(ns) do JSON antigo")
    finally:
        session.close()


def apply_plan(engine: Engine, plan: SyncPlan) -> None:
    if plan.tables_to_create:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print(f"✓ Tabela(s) criada(s): {', '.join(plan.tables_to_create)}")
        _seed_new_tables(engine, plan)

    for table_name, col_name, ddl in plan.columns_to_add:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {ddl}"))
        print(f"✓ {table_name}.{col_name} adicionada")
        _add_extra_for_column(engine, table_name, col_name)

    if plan.payment_method_needs_widen:
        new_enum = plan.payment_method_current_enum + [PAYMENT_METHOD_NEW_VALUE]
        enum_sql = ", ".join(_sql_literal(v) for v in new_enum)
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE payments MODIFY COLUMN payment_method ENUM({enum_sql}) NOT NULL"))
        print(f"✓ payments.payment_method ampliado para {new_enum!r}")


def run(db_url: str, execute: bool) -> bool:
    engine = create_engine(db_url)
    mode = "EXECUTANDO (alterando o banco)" if execute else "DRY-RUN (nada será alterado)"
    print(f"\n=== Ajuste de schema Nuvion — {mode} ===")
    print(f"Banco: {engine.url.render_as_string(hide_password=True)}")

    plan = build_plan(engine)
    print_plan(plan)

    if not execute:
        print("Isto foi um dry-run — nada foi alterado. Rode de novo com --execute para aplicar.")
        return True

    if not plan.has_changes:
        print("Nada a fazer — o schema já está em dia.")
        return True

    apply_plan(engine, plan)

    print("\n=== Verificação pós-ajuste ===")
    verify_plan = build_plan(engine)
    print_plan(verify_plan)
    if verify_plan.has_changes:
        print("⚠ Alguma alteração esperada não foi aplicada — revise a saída acima.")
        return False
    print("Tudo em dia.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--db-url", required=True, help="URL SQLAlchemy do banco (ex.: mysql+pymysql://user:pass@host:3306/db)"
    )
    parser.add_argument("--execute", action="store_true", help="Aplica de verdade (default: dry-run)")
    args = parser.parse_args()

    ok = run(args.db_url, execute=args.execute)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
