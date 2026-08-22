"""Migra dados do MySQL do app desktop (`Browser/`) para o MySQL deste
backend (Fase 5 do roadmap — ver docs/MIGRACAO_DADOS.md para o runbook
completo e docs/PILOTO.md para o plano de convivência/piloto).

Por que dá pra migrar com um script genérico (sem reimportar os modelos do
app desktop): a Fase 0 portou os 15 modelos SQLAlchemy do desktop
preservando nome de tabela, nome de coluna e tipo — o schema é **aditivo**
(nada foi removido ou renomeado; só 2 colunas novas em `proxy` e um valor
novo no enum de `payments.payment_method`). Isso foi verificado
tabela-a-tabela antes de escrever este script (comparação old↔new modelo a
modelo). Por isso o script lê o banco antigo via *reflection* (não precisa
do código-fonte do app desktop) e faz um upsert por `id` (todo PK é um UUID
string estável — nunca auto-increment — então não existe remapeamento de ID
para se preocupar).

Uso:
    cd backend
    # 1) sempre rode em dry-run primeiro (é o padrão — não escreve nada):
    python -m scripts.migrate_from_desktop --old-db-url mysql+pymysql://user:pass@host/nuvion_desktop

    # 2) depois de conferir o resumo, execute de verdade:
    python -m scripts.migrate_from_desktop \\
        --old-db-url mysql+pymysql://user:pass@host/nuvion_desktop --execute

    # 3) rodar de novo (dry-run ou --execute) é seguro — é idempotente por id,
    #    então serve tanto para o corte inicial quanto para sincronizar de novo
    #    durante o período de convivência desktop+web (ver docs/PILOTO.md).

Opções úteis:
    --new-db-url URL       Sobrescreve o banco novo (default: settings.DATABASE_URL,
                            o mesmo .env do backend). Usado nos testes deste script.
    --tables a,b,c          Restringe a um subconjunto de tabelas (nomes de tabela,
                            não de arquivo — ver TABLE_ORDER abaixo).
    --continue-on-error     Não aborta a migração inteira se uma tabela falhar
                            (loga o erro e segue para a próxima). Por padrão o
                            script aborta no primeiro erro — é o comportamento
                            mais seguro para dados de pagamento/usuário.
    --verify-only           Não migra nada; só compara contagem de linhas
                            old vs new e reporta IDs antigos ausentes no novo banco.
"""
import argparse
import sys
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.core.logging import LOGGER
from app.models import Base  # noqa: F401 — importar registra todas as tabelas em Base.metadata

# Ordem de inserção respeitando FKs (ver relatório de compatibilidade de schema
# desta fase) — tabelas sem FK podem ir em qualquer posição, mas manter esta
# ordem também deixa o log de progresso mais legível (dono antes de posse).
TABLE_ORDER = [
    "users",
    "proxy",
    "payment_configs",
    "expenses",
    "ai_tools",
    "ai_direct_credentials",
    "ai_sessions_cookies",
    "ai_sessions",
    "user_favorites",
    "payments",
    "browser_settings",
    "user_sessions",
    "downloads",
    "device_data",
    "notifications",
]

# Colunas que só existem no schema novo, com o valor a usar para toda linha
# migrada do banco antigo (que nunca vai ter essas colunas na origem).
NEW_ONLY_COLUMN_DEFAULTS = {
    "proxy": {
        # Proxies do desktop eram admin-gerenciados/compartilhados, não
        # donos por usuário — preserva esse comportamento (ver app/models/proxy.py).
        "user_id": None,
        # Coluna NOT NULL — precisa de valor explícito, não dá pra deixar de fora.
        "is_selected": False,
    },
}

# Normalização defensiva de valores que o código antigo às vezes gravava em
# case diferente do Enum canônico (ver relatório de compatibilidade —
# `Payment.mark_as_paid()`/`mark_as_overdue()` no app desktop escreviam
# "confirmado"/"atrasado" em minúsculo).
COLUMN_VALUE_NORMALIZERS = {
    "payments": {
        "status": {
            "confirmado": "Confirmado",
            "pendente": "Pendente",
            "atrasado": "Atrasado",
            "cancelado": "Cancelado",
        }
    }
}


@dataclass
class TableResult:
    table: str
    old_rows: int = 0
    inserted: int = 0
    updated: int = 0
    skipped_missing_fk: int = 0
    error: Optional[str] = None
    warnings: list = field(default_factory=list)


def _reflect_old_table(old_metadata: MetaData, old_engine: Engine, table_name: str) -> Optional[Table]:
    try:
        return Table(table_name, old_metadata, autoload_with=old_engine)
    except Exception as e:
        LOGGER.warning(f"Tabela '{table_name}' não encontrada no banco antigo ({e}) — pulando.")
        return None


def _build_new_row(table_name: str, old_row: dict, new_columns: set) -> dict:
    row = {k: v for k, v in old_row.items() if k in new_columns}

    for col, default in NEW_ONLY_COLUMN_DEFAULTS.get(table_name, {}).items():
        row.setdefault(col, default)

    normalizers = COLUMN_VALUE_NORMALIZERS.get(table_name, {})
    for col, mapping in normalizers.items():
        if col in row and row[col] in mapping:
            row[col] = mapping[row[col]]

    return row


def _check_fk_integrity(table_name: str, rows: list, new_engine: Engine) -> tuple:
    """Verificação leve das FKs mais arriscadas apontadas no relatório de
    compatibilidade (proxy_id em ai_tools) — evita que um INSERT falhe no
    meio da tabela por uma referência órfã vinda do banco antigo."""
    if table_name != "ai_tools":
        return rows, []

    proxy_ids_in_rows = {r["proxy_id"] for r in rows if r.get("proxy_id")}
    if not proxy_ids_in_rows:
        return rows, []

    with new_engine.connect() as conn:
        proxy_table = Base.metadata.tables["proxy"]
        existing = {
            row[0]
            for row in conn.execute(select(proxy_table.c.id).where(proxy_table.c.id.in_(proxy_ids_in_rows)))
        }

    missing = proxy_ids_in_rows - existing
    if not missing:
        return rows, []

    warnings = [f"{len(missing)} ai_tools.proxy_id órfão(s) (proxy não migrado) — proxy_id zerado"]
    fixed_rows = []
    for r in rows:
        if r.get("proxy_id") in missing:
            r = dict(r)
            r["proxy_id"] = None
        fixed_rows.append(r)
    return fixed_rows, warnings


def _upsert(new_engine: Engine, table: Table, rows: list, execute: bool) -> tuple:
    """Upsert dialect-agnóstico por `id`: busca quais já existem, insere o
    resto, atualiza os existentes. Funciona igual em MySQL (produção) e
    SQLite (usado nos testes deste script) — sem depender de sintaxe
    `ON DUPLICATE KEY UPDATE` específica de dialeto."""
    if not rows:
        return 0, 0

    ids = [r["id"] for r in rows]
    with new_engine.connect() as conn:
        existing_ids = {row[0] for row in conn.execute(select(table.c.id).where(table.c.id.in_(ids)))}

    to_insert = [r for r in rows if r["id"] not in existing_ids]
    to_update = [r for r in rows if r["id"] in existing_ids]

    if not execute:
        return len(to_insert), len(to_update)

    with new_engine.begin() as conn:
        if to_insert:
            conn.execute(table.insert(), to_insert)
        for row in to_update:
            values = {k: v for k, v in row.items() if k != "id"}
            if values:
                conn.execute(table.update().where(table.c.id == row["id"]).values(**values))

    return len(to_insert), len(to_update)


def migrate_table(
    table_name: str, old_engine: Engine, old_metadata: MetaData, new_engine: Engine, execute: bool
) -> TableResult:
    result = TableResult(table=table_name)

    old_table = _reflect_old_table(old_metadata, old_engine, table_name)
    if old_table is None:
        result.error = "tabela ausente no banco antigo"
        return result

    if table_name not in Base.metadata.tables:
        result.error = "tabela ausente no schema novo (não deveria acontecer — ver app/models/__init__.py)"
        return result

    new_table = Base.metadata.tables[table_name]
    new_columns = set(new_table.columns.keys())

    with old_engine.connect() as conn:
        old_rows = [dict(row._mapping) for row in conn.execute(select(old_table))]

    result.old_rows = len(old_rows)
    if not old_rows:
        return result

    new_rows = [_build_new_row(table_name, row, new_columns) for row in old_rows]
    new_rows, fk_warnings = _check_fk_integrity(table_name, new_rows, new_engine)
    result.warnings.extend(fk_warnings)

    try:
        inserted, updated = _upsert(new_engine, new_table, new_rows, execute)
        result.inserted = inserted
        result.updated = updated
    except Exception as e:
        result.error = str(e)

    return result


def verify_table(table_name: str, old_engine: Engine, old_metadata: MetaData, new_engine: Engine) -> str:
    old_table = _reflect_old_table(old_metadata, old_engine, table_name)
    if old_table is None:
        return f"{table_name}: tabela ausente no banco antigo (pulada na verificação)"

    if table_name not in Base.metadata.tables:
        return f"{table_name}: tabela ausente no schema novo"

    new_table = Base.metadata.tables[table_name]

    with old_engine.connect() as conn:
        old_ids = {row[0] for row in conn.execute(select(old_table.c.id))}
    with new_engine.connect() as conn:
        new_ids = {row[0] for row in conn.execute(select(new_table.c.id))}

    missing = old_ids - new_ids
    status = "OK" if not missing else f"FALTAM {len(missing)} linha(s)"
    return f"{table_name}: antigo={len(old_ids)} novo={len(new_ids)} — {status}"


def run(old_db_url: str, new_db_url: str, tables: list, execute: bool, continue_on_error: bool) -> bool:
    old_engine = create_engine(old_db_url)
    new_engine = create_engine(new_db_url)
    old_metadata = MetaData()

    mode = "EXECUTANDO (gravando no banco novo)" if execute else "DRY-RUN (nada será gravado)"
    print(f"\n=== Migração Nuvion desktop → web — {mode} ===")
    print(f"Origem:  {old_engine.url.render_as_string(hide_password=True)}")
    print(f"Destino: {new_engine.url.render_as_string(hide_password=True)}\n")

    results = []
    had_error = False

    for table_name in tables:
        result = migrate_table(table_name, old_engine, old_metadata, new_engine, execute)
        results.append(result)

        if result.error:
            had_error = True
            print(f"  ✗ {table_name}: ERRO — {result.error}")
            if not continue_on_error:
                print("\nAbortando (use --continue-on-error para seguir mesmo com falhas).")
                break
            continue

        verb = "seriam" if not execute else "foram"
        print(
            f"  ✓ {table_name}: {result.old_rows} linha(s) na origem — "
            f"{result.inserted} {verb} inseridas, {result.updated} {verb} atualizadas"
        )
        for warning in result.warnings:
            print(f"    ⚠ {warning}")

    print("\n=== Resumo ===")
    total_old = sum(r.old_rows for r in results)
    total_ins = sum(r.inserted for r in results)
    total_upd = sum(r.updated for r in results)
    print(f"Linhas na origem: {total_old} | inseridas: {total_ins} | atualizadas: {total_upd}")

    if not execute:
        print("\nIsto foi um dry-run — nada foi gravado. Rode de novo com --execute para aplicar.")

    return not had_error


def verify(old_db_url: str, new_db_url: str, tables: list) -> None:
    old_engine = create_engine(old_db_url)
    new_engine = create_engine(new_db_url)
    old_metadata = MetaData()

    print("\n=== Verificação pós-migração (contagem de linhas por id) ===")
    for table_name in tables:
        print(f"  {verify_table(table_name, old_engine, old_metadata, new_engine)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--old-db-url", required=True, help="URL SQLAlchemy do MySQL do app desktop")
    parser.add_argument(
        "--new-db-url",
        default=None,
        help="URL SQLAlchemy do banco novo (default: settings.DATABASE_URL, o .env deste backend)",
    )
    parser.add_argument(
        "--tables", default=None, help="Lista de tabelas separada por vírgula (default: todas)"
    )
    parser.add_argument("--execute", action="store_true", help="Grava de verdade (default: dry-run)")
    parser.add_argument(
        "--continue-on-error", action="store_true", help="Não aborta no primeiro erro de tabela"
    )
    parser.add_argument("--verify-only", action="store_true", help="Só compara contagens, não migra nada")
    args = parser.parse_args()

    new_db_url = args.new_db_url or settings.DATABASE_URL
    tables = [t.strip() for t in args.tables.split(",")] if args.tables else TABLE_ORDER

    unknown = [t for t in tables if t not in TABLE_ORDER]
    if unknown:
        print(f"Tabela(s) desconhecida(s): {unknown}. Válidas: {TABLE_ORDER}")
        sys.exit(2)

    if args.verify_only:
        verify(args.old_db_url, new_db_url, tables)
        return

    ok = run(
        args.old_db_url,
        new_db_url,
        tables,
        execute=args.execute,
        continue_on_error=args.continue_on_error,
    )

    if ok and args.execute:
        verify(args.old_db_url, new_db_url, tables)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
