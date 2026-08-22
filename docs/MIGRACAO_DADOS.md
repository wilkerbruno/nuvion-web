# Migração de dados — desktop → web

Runbook operacional para `backend/scripts/migrate_from_desktop.py`, a
ferramenta que copia os dados do MySQL do app desktop (`Browser/`) para o
MySQL deste backend. Ver [`PILOTO.md`](PILOTO.md) para o plano de
convivência e o piloto que usa esta migração, e a seção 11 de
[`PLANO_MIGRACAO.md`](PLANO_MIGRACAO.md) para os riscos já mapeados
(LGPD, dados sensíveis).

**Este documento é o runbook — a ferramenta em si já está pronta e testada
(9 testes automatizados, `backend/tests/test_migrate_from_desktop.py`,
contra fixtures locais em SQLite). Executar a migração contra um banco de
produção de verdade é uma decisão e uma ação que cabe à Divisions Tech, não
a algo que rodei neste sandbox — aqui não há acesso ao MySQL de produção.**

## Por que é seguro rodar

- O schema novo é **aditivo** em relação ao antigo: nenhuma tabela ou coluna
  foi removida ou renomeada durante as Fases 0–4. Só duas colunas novas em
  `proxy` (`user_id`, `is_selected`) e um valor novo no enum de
  `payments.payment_method` (`"boleto"` na época — removido do produto
  antes de qualquer uso em produção e substituído por `"usdt"`, ver
  `docs/PAGAMENTOS_CRIPTO.md`; não afeta este script, que só copia dados
  existentes, nunca decide valores de enum). Isso foi conferido tabela a
  tabela antes de escrever o script.
- Todo PK é um UUID string estável (nunca auto-increment) — não existe
  remapeamento de ID para se preocupar; um registro migrado tem o mesmo
  `id` nos dois bancos.
- O script faz **upsert por `id`**: se a linha já existe no banco novo,
  atualiza; se não existe, insere. Rodar o script várias vezes é seguro e
  idempotente — não duplica nem falha na segunda execução. É assim que o
  piloto sincroniza dados repetidamente durante o período de convivência
  (ver `PILOTO.md`).
- O script sempre roda em **dry-run por padrão** (não escreve nada) até
  você passar `--execute` explicitamente.
- O script lê o banco antigo via *reflection* do SQLAlchemy — não precisa
  do código-fonte do app desktop instalado, só de uma connection string.

## Pré-requisitos

- Acesso de leitura ao MySQL do app desktop (`--old-db-url`).
- Acesso de escrita ao MySQL deste backend (via `DATABASE_URL` no `.env`,
  ou `--new-db-url` para apontar para outro banco).
- Backend com as dependências instaladas (`pip install -r requirements.txt`)
  e as migrações do Alembic já aplicadas no banco novo (`alembic upgrade
  head`) — o script espera que as tabelas do schema novo já existam.
- **Backup do banco antigo e do banco novo antes de qualquer `--execute`.**
  O script só escreve (insert/update), nunca apaga linhas — mas um backup
  recente ainda é a rede de segurança padrão antes de qualquer migração de
  dados de produção, incluindo dados de pagamento.

## Passo a passo

### 1. Dry-run (sempre primeiro)

```bash
cd backend
python -m scripts.migrate_from_desktop \
    --old-db-url "mysql+pymysql://usuario:senha@host/nuvion_desktop"
```

Isso não grava nada — só conecta nos dois bancos, lê o antigo, e imprime o
que **seria** inserido/atualizado em cada uma das 15 tabelas, na ordem que
respeita as chaves estrangeiras:

```
users, proxy, payment_configs, expenses, ai_tools, ai_direct_credentials,
ai_sessions_cookies, ai_sessions, user_favorites, payments,
browser_settings, user_sessions, downloads, device_data, notifications
```

Confira o resumo no final (`Linhas na origem: X | inseridas: Y |
atualizadas: Z`) contra o que você espera do banco antigo. Preste atenção
em avisos (`⚠`) — por exemplo, `ai_tools.proxy_id` órfão (referência a um
proxy que não existe no banco antigo nem seria migrado) é zerado
automaticamente, com aviso, em vez de travar a migração inteira.

### 2. Migrar uma tabela por vez (opcional, recomendado na primeira vez)

Para reduzir o raio de impacto de qualquer surpresa, dá pra restringir a um
subconjunto de tabelas com `--tables`:

```bash
python -m scripts.migrate_from_desktop \
    --old-db-url "mysql+pymysql://usuario:senha@host/nuvion_desktop" \
    --tables users,proxy --execute
```

Comece por `users` (todo o resto depende dela via FK) e confira no banco
novo antes de seguir para as demais.

### 3. Execução completa

Depois de validar o dry-run, rode com `--execute`:

```bash
python -m scripts.migrate_from_desktop \
    --old-db-url "mysql+pymysql://usuario:senha@host/nuvion_desktop" \
    --execute
```

Por padrão o script **aborta na primeira tabela com erro** — é o
comportamento mais seguro para dados de pagamento e usuário, para evitar
migrar dados parciais/inconsistentes sem perceber. Use
`--continue-on-error` só se você já entende o erro e decidiu
conscientemente seguir em frente mesmo assim.

Ao final de uma execução bem-sucedida (`--execute` sem erros), o script já
roda a verificação pós-migração automaticamente (passo 4).

### 4. Verificação

Pode ser rodada a qualquer momento, inclusive sem migrar nada:

```bash
python -m scripts.migrate_from_desktop \
    --old-db-url "mysql+pymysql://usuario:senha@host/nuvion_desktop" \
    --verify-only
```

Compara a contagem de linhas e os `id`s de cada tabela entre os dois
bancos e reporta `OK` ou `FALTAM N linha(s)` por tabela. Rode isso depois
de qualquer `--execute` (mesmo que o script já tenha rodado sozinho) e
periodicamente durante o piloto, para garantir que a sincronização
contínua (ver `PILOTO.md`) não está ficando pra trás.

### 5. Re-sincronizar (durante o piloto)

Enquanto desktop e web convivem apontando para bancos separados (ver
`PILOTO.md` para por que começar assim), rodar o mesmo comando do passo 3
de novo — periodicamente, ou sob demanda — traz para o banco novo qualquer
dado criado/alterado no desktop desde a última sincronização. É seguro
porque o upsert é idempotente: linhas já migradas e inalteradas são
reescritas com os mesmos valores (upsert sempre faz update se o id já
existe, mesmo sem mudança de conteúdo); nada é duplicado.

## Rollback

O script nunca deleta linhas do banco novo — só insere/atualiza. Isso
significa que "desfazer" uma migração não é uma operação do script, e sim
uma decisão operacional:

- **Se o banco novo era vazio antes da migração** (caso comum: primeiro
  corte para o piloto): restaurar o backup do banco novo pré-migração
  (tirado no passo de pré-requisitos) volta ao estado anterior.
- **Se o banco novo já tinha dados próprios da web** (ex.: usuários que se
  cadastraram direto na web antes da migração do desktop rodar) — um
  rollback bruto por restore de backup apagaria esses dados também. Nesse
  caso, o caminho seguro é reverter manualmente só as linhas afetadas
  (identificáveis pelos `id`s reportados como `inserted`/`updated` na saída
  do script — vale copiar o output de cada execução `--execute` para um
  log) em vez de restaurar o backup inteiro.

Por isso o passo 2 (migrar tabela por tabela, começando pequeno) e manter
o output de cada execução são recomendados: tornam um rollback cirúrgico
possível caso algo dê errado.

## Erros conhecidos e o que significam

- `Tabela 'X' não encontrada no banco antigo — pulando`: o script tolera
  tabelas ausentes no banco antigo (loga aviso e segue) — pode acontecer
  se o banco antigo for de uma versão mais velha do app desktop sem
  alguma tabela nova (ex.: `device_data`).
  Não é fatal.
- `N ai_tools.proxy_id órfão(s) — proxy_id zerado`: alguma ferramenta de
  IA no banco antigo apontava para um `proxy_id` que não existe (ou não
  foi migrado) no banco novo. O script zera a referência em vez de falhar
  o insert — revise manualmente essas linhas depois se o vínculo
  proxy↔ferramenta de IA importar para o piloto.
- Erro de tipo/constraint do MySQL durante `--execute`: o script aborta a
  tabela atual (e a migração inteira, a menos que `--continue-on-error`
  esteja setado) e imprime a mensagem de erro do SQLAlchemy/MySQL — geralmente
  indica um dado real fora do formato esperado (ex.: um valor de enum não
  previsto em `COLUMN_VALUE_NORMALIZERS`, no topo do script). Se isso
  acontecer, é preciso olhar a linha específica no banco antigo e decidir
  se corrige o dado na origem ou estende o normalizador do script.

## Testando localmente antes de ir para produção

`backend/tests/test_migrate_from_desktop.py` já cobre o comportamento do
script (dry-run não escreve, upsert idempotente, normalização de enum,
FK órfã, tabela ausente) contra bancos SQLite em memória — não precisa de
um MySQL de verdade para validar a lógica. Para testar contra uma cópia
real do banco antigo antes do piloto, o caminho recomendado é apontar
`--old-db-url` para um **dump/restore de teste** do MySQL do desktop (nunca
o banco de produção do desktop direto) e `--new-db-url` para um banco novo
descartável, e conferir o resumo e o `--verify-only`.
