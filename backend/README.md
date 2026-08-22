# Nuvion Web — Backend

API em FastAPI. Reaproveita os modelos SQLAlchemy e a lógica de negócio do
app desktop (`Browser/`), expostos agora como uma API HTTP em vez de
chamados direto dentro do processo Qt. Ver [`/docs/PLANO_MIGRACAO.md`](../docs/PLANO_MIGRACAO.md)
para o plano completo.

## Rodando localmente

### Opção 1 — Docker (recomendado)

```bash
cp backend/.env.example backend/.env   # preencha DB_USER, DB_PASSWORD, JWT_SECRET_KEY, ENCRYPTION_KEY
docker compose -f infra/docker-compose.yml up --build
```

API em `http://localhost:8000` (docs interativas em `/docs`).

### Opção 2 — Python local

Requer um MySQL acessível (local ou remoto).

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencha as credenciais
uvicorn app.main:app --reload
```

## Migrações (Alembic)

```bash
cd backend
alembic revision --autogenerate -m "schema inicial"
alembic upgrade head
```

## Testes e lint

```bash
cd backend
pytest -q
ruff check .
```

## Segurança — ação pendente

As credenciais de banco (`DB_USER`/`DB_PASSWORD`) e SMTP do app desktop
original estavam **hardcoded em texto plano** em `utils/config_manager.py` e
versionadas no Git. Elas foram deliberadamente **não copiadas** para este
projeto — aqui a aplicação recusa subir sem essas variáveis no ambiente.
Recomendação: rotacionar a senha do MySQL de produção e a senha de app SMTP
que estavam expostas no repositório desktop antes de ligar este backend em
produção.

## Estrutura

```
app/
├─ api/routes/     # endpoints (health, auth, users, dashboard, proxies,
│                  #   browser-settings, payments, admin_payment_config,
│                  #   rewards, ai_tools, ai_tool_secrets, notifications,
│                  #   downloads)
├─ core/           # config, segurança (hash de senha + JWT), logging
├─ crud/           # acesso a dados por domínio (session injetada por request)
├─ data/           # config estática (diamond_platform_config.json)
├─ db/             # engine, sessão, declarative base
├─ models/         # os 16 modelos SQLAlchemy do app desktop (+ Payment
│                  #   ganhou "usdt" no enum de método — ver models/payment.py)
└─ services/       # integrações externas (mercadopago_client.py,
                   #   reward_service.py, cookie_parser.py)
alembic/           # migrações
tests/             # pytest
```

## Pagamentos (Fase 3)

Integração real com o Mercado Pago (`app/services/mercadopago_client.py`),
substituindo o polling em thread do app desktop por webhook real —
`POST /payments/webhook/mercadopago`. Credenciais e preços por categoria
ficam em `PaymentConfig` (tabela `payment_configs`), editável só por admin
via `GET`/`PUT /admin/payment-config` — mesmo modelo do app desktop, que
permitia trocar de sandbox pra produção sem redeploy.

Escopo desta fase, decidido conscientemente:

- **PIX** — portado com integração real (o app desktop só tinha PIX de
  verdade).
- **Split de comissão para afiliados não foi portado.** O worker original
  fazia transferência automática de parte de cada pagamento pra uma conta
  MP de comissão (`execute_commission_transfer`) — mexe com dinheiro de
  terceiros e não estava no escopo aprovado; se for necessário, merece
  desenho e revisão própria antes de implementar.
- **Cobrança recorrente automática (o `PaymentScheduler`/`QTimer` do
  desktop) não tem equivalente rodando ainda** — `app/crud/payment.py`
  mantém `get_overdue_payments()` portado e pronto, mas falta um
  agendador (cron batendo num endpoint admin, ou Celery/APScheduler) para
  de fato criar cobranças de renovação automaticamente. Por enquanto o
  checkout é sempre iniciado pelo usuário em `/payments`.

`MERCADOPAGO_WEBHOOK_SECRET` (variável de ambiente) habilita verificação de
assinatura HMAC do webhook — sem ela, o webhook aceita notificações sem
verificar (loga aviso); configurar em produção.

## Pagamentos atualizados — cartão + USDT, boleto removido

Decisão de produto posterior à Fase 3 (antes de qualquer uso em produção —
"boleto" nunca chegou a ser usado nem existiu num banco real, ver
`scripts/sync_schema_live.py`): boleto saiu do escopo, entraram **cartão de
crédito via Mercado Pago** e **USDT (rede TRC20) self-custodial**, sem
provedor terceiro. `payments.payment_method` agora é `pix` / `cartao` /
`usdt`.

- **Cartão de crédito** (`mercadopago_client.charge_card`): tokenizado no
  navegador pelo **Card Payment Brick** do Mercado Pago
  (`sdk.mercadopago.com/js/v2`) — o backend nunca vê o número do cartão, só
  o token que o Brick gera (exigência de PCI compliance do próprio MP).
  Resolve na hora (aprovado/recusado), diferente do PIX que fica
  "Pendente" esperando webhook. Nova rota
  `GET /payments/mercadopago-public-key` expõe a `public_key` (não é
  segredo, ao contrário do `access_token` — é feita pra ser usada no
  navegador) para o Brick tokenizar o cartão.
- **USDT (TRC20)** — self-custodial, **sem provedor terceiro**: o backend só
  lê o blockchain público via TronGrid (`app/services/tron_client.py`),
  nunca guarda nem movimenta chave privada. Carteira compartilhada (um só
  endereço, configurado pelo admin) com desambiguação de pedido por
  micro-valor único (`app/crud/payment.py::generate_unique_usdt_amount`,
  incrementos de 0.000001 USDT) — evita precisar de derivação de carteira
  HD ou de um provedor terceiro. Sem webhook (não há terceiro pra
  notificar): `GET /payments/{id}` é a única forma de detectar que o
  pagamento chegou, consultando o TronGrid sob demanda. Preços em USDT são
  configurados manualmente pelo admin por categoria (mesma lógica dos
  preços em BRL) — decisão consciente de **não** implementar conversão
  BRL↔USDT por câmbio ao vivo, para não depender de mais uma API externa.
  Detalhes completos (arquitetura, TronGrid, decimais, tolerância de valor)
  em [`../docs/PAGAMENTOS_CRIPTO.md`](../docs/PAGAMENTOS_CRIPTO.md).
- **PIX continua exatamente como na Fase 3** (Mercado Pago, BRL) — foi
  cogitado fazer o PIX cair como USDT na mesma carteira, mas PIX só
  movimenta BRL; não existe conversão sem um intermediário. Como a
  Divisions Tech pediu a opção "recomendada e com menor taxa", ficou PIX
  em BRL via Mercado Pago (like estava) e USDT totalmente separado — zero
  taxa nova, zero intermediário novo.
- **Configuração de carteira/preços USDT só via API/banco por enquanto**
  (`PUT /admin/payment-config`, campos `usdt_wallet_address`,
  `usdt_network`, `standard_amount_usdt`/`premium_amount_usdt`/
  `vip_amount_usdt`) — sem formulário próprio no painel admin, mesma
  decisão consciente já tomada para credenciais de IA/cookies na Fase 4
  (rotas prontas e testadas, formulário fica para depois).

## Produto completo (Fase 4)

Diamantes/recompensas, catálogo de ferramentas de IA (+ favoritos,
credenciais diretas, cookies de sessão), notificações e histórico de
downloads — 28 testes automatizados novos (64 no total).

- **Diamantes** (`app/services/reward_service.py`, `/rewards/*`): saldo,
  histórico de transações e catálogo de recompensas continuam persistidos em
  `User.profile_settings` (JSON), igual ao app desktop. O catálogo veio de
  `diamond_platform_config.json`, mas **sem** o bloco `pix_settings` do
  arquivo original — ele tinha o `access_token`/`app_id` do Mercado Pago em
  texto puro; essas credenciais já são geridas por `PaymentConfig` no banco
  desde a Fase 3, então duplicá-las aqui reintroduziria o mesmo problema de
  segredo versionado que a migração já corrigiu uma vez. O bônus de
  indicação (`process_referral_rewards`) finalmente foi ligado em
  `app/crud/user.py::register_user` — ficava como TODO desde a Fase 1.
- **Catálogo de IA** (`/ai-tools/*`): leitura liberada para qualquer usuário
  autenticado, escrita (criar/editar/remover ferramenta) restrita a admin —
  é um catálogo compartilhado da plataforma, não dados por usuário.
  Favoritos (`/ai-tools/{id}/favorite`, `/ai-tools/favorites`) são por
  usuário.
- **Credenciais diretas e cookies de sessão** (`/ai-tools/{id}/credentials`,
  `/ai-tools/{id}/cookies`): também são 1:1 com a ferramenta de IA (não por
  usuário) — mesma modelagem do app desktop, que geria login automático de
  contas de IA compartilhadas pela plataforma. Melhoria de segurança
  consciente em relação ao original: lá a senha ia pro banco **em texto
  plano** (comentário no próprio código-fonte: "SEM criptografia para
  testes"); aqui é cifrada em repouso com Fernet (`ENCRYPTION_KEY`, sem
  default — mesma política de `DB_USER`/`DB_PASSWORD`/`JWT_SECRET_KEY`) e
  nenhuma rota jamais retorna o segredo em texto puro, só um resumo
  `configured: bool`. O import quebrado que `app/models/ai_session_cookies.py`
  carregava desde a Fase 0 (`app.services.cookie_parser.CookieParser`,
  guardado num try/except) finalmente existe em
  `app/services/cookie_parser.py`.
- **Notificações** (`/notifications/*`, `/admin/notifications/*`):
  pessoais e globais (broadcast), com contagem de não lidas, marcar
  uma/todas como lidas e limpeza de expiradas. O plano de migração cogitava
  WebSocket para push em tempo real; optamos por polling curto no painel
  (mesma escolha pragmática já usada no status de pagamento da Fase 3) para
  não abrir uma segunda tecnologia de transporte só para isto — fica
  documentado como possível otimização futura, não uma lacuna silenciosa.
- **Downloads** (`/downloads/*`): histórico simples, alimentado pela
  extensão via `chrome.downloads` (ver `extension/README.md`) — o download
  em si sempre aconteceu no navegador, isto é só espelho de status para o
  painel, como já estava previsto no plano de migração (seção 6).

**Fora do escopo desta fase, por decisão consciente:**

- **Login automático de verdade** (`core/auto_login_engine.py`,
  `intelligent_bypass_engine.py`, `credential_tester.py` no app desktop, que
  dirigiam o QtWebEngine embutido pra preencher formulários e resolver
  captchas) não tem equivalente direto na arquitetura web — a extensão só
  injeta script de anti-detecção na página (`world: "MAIN"`), não comanda
  navegação/preenchimento como o QtWebEngine embutido fazia. As rotas de
  credenciais/cookies desta fase só armazenam e mostram status; quem
  consumiria isso de fato ainda não existe. Fica como trabalho futuro, e
  provavelmente exigiria desenho próprio (rodar no content script da
  extensão, não no backend).
- **UI de administração de credenciais/cookies no painel** não foi
  construída nesta fase — as rotas existem e estão testadas, utilizáveis via
  `/docs` ou por um admin técnico; o formulário no painel fica para uma
  próxima iteração (ver `frontend/README.md`).
- **Gestão de gastos operacionais** (`Expense`, back-office admin —
  `core/widgets/settings/gestao_gastos_section.py` no app desktop) não foi
  portada: não está na linha do roadmap aprovado para esta fase ("diamantes,
  IA, notificações, downloads") e é um recurso de back-office interno, não
  voltado ao usuário final — fica para uma fase futura se necessário.

## Migração de dados & piloto (Fase 5)

`scripts/migrate_from_desktop.py` migra os dados do MySQL do app desktop
para o MySQL deste backend — upsert idempotente por `id` (todo PK é UUID
estável, sem remapeamento), dry-run por padrão, schema aditivo confirmado
tabela a tabela nas Fases 0–4. 9 testes automatizados novos (73 no total)
contra fixtures SQLite cobrindo dry-run, normalização de enum de
`payments.status`, defaults das colunas novas de `proxy`, FK órfã em
`ai_tools.proxy_id` e idempotência de reexecução.

Runbook completo de uso (pré-requisitos, passo a passo, rollback, erros
conhecidos) em [`../docs/MIGRACAO_DADOS.md`](../docs/MIGRACAO_DADOS.md).
Plano de convivência desktop+web e critérios de piloto em
[`../docs/PILOTO.md`](../docs/PILOTO.md).

**O que esta fase entrega é a ferramenta e o processo, testados e prontos
para uso — não uma migração de dados reais executada, nem um piloto rodado
com usuários de verdade.** Este sandbox não tem (nem deveria ter) acesso
ao MySQL de produção do app desktop; rodar `--execute` contra dados reais e
conduzir o piloto descrito em `PILOTO.md` é uma ação operacional que cabe à
Divisions Tech, seguindo o runbook.

### Banco compartilhado com o desktop (EasyPanel)

A Divisions Tech decidiu usar o banco MySQL que já mantém no EasyPanel —
com dados reais do app desktop — como o banco também deste backend, em vez
de uma cópia separada (Estratégia B em `PILOTO.md`). Para esse caso,
`scripts/sync_schema_live.py` é o script certo (não `migrate_from_desktop.py`,
que copia para um banco *novo*): ele ajusta o schema de um banco **já em
uso** — cria as tabelas que faltam e adiciona só as duas colunas
novas/o valor de enum novo que faltam — sem nunca fazer `DELETE`, `DROP`
ou `UPDATE` em dado de linha existente. Testado contra um MySQL 8 real
(`tests/test_sync_schema_live.py`, pulado no CI por não haver serviço
MySQL lá — rode localmente com `NUVION_TEST_MYSQL_URL` setado, ver o
cabeçalho do arquivo). Passo a passo completo de deploy (env vars,
ordem de publicação, extensão) em
[`../docs/DEPLOY_EASYPANEL.md`](../docs/DEPLOY_EASYPANEL.md).
