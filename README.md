# Nuvion Web

Versão web do Nuvion Browser (hoje um app desktop em PyQt6/QtWebEngine).

O plano de arquitetura e o roteiro de migração completos estão em
[`docs/PLANO_MIGRACAO.md`](docs/PLANO_MIGRACAO.md). As 6 fases do roadmap
(0 a 5) já estão prontas — ver "Rodando localmente" abaixo.

## Resumo da decisão de arquitetura

- **Painel web** (FastAPI + React/Next.js) para conta, proxies, pagamentos,
  diamantes/recompensas, IA e configurações.
- **Extensão de navegador** (Manifest V3, Chrome/Edge) para a navegação em si
  e a camada de anti-detecção — um site comum não consegue embutir/controlar
  páginas de terceiros como o QtWebEngine embutido faz hoje.
- Um único back-end compartilhado pelas duas superfícies, reaproveitando os
  modelos SQLAlchemy e a lógica de negócio já existentes em `Browser/`.

## Estrutura

```
nuvion-web/
├─ backend/     # FastAPI — 16 modelos, auth JWT, dashboard, proxies, browser-settings,
│               #   pagamentos (PIX/cartão/USDT/webhook), diamantes, catálogo de IA
│               #   (+favoritos/credenciais/cookies), notificações, downloads, Alembic, testes, Docker
├─ frontend/    # Next.js — login, registro, dashboard, assinatura/pagamentos,
│               #   diamantes, ferramentas de IA, notificações, downloads
├─ extension/   # Manifest V3 — auth, proxy por usuário, anti-detecção (MVP), espelho de downloads
├─ docs/        # plano de migração, runbook de migração de dados, plano de piloto
└─ infra/       # docker-compose
```

## Rodando localmente

```bash
cp backend/.env.example backend/.env   # preencha DB_USER, DB_PASSWORD, JWT_SECRET_KEY, ENCRYPTION_KEY
docker compose -f infra/docker-compose.yml up --build
```

API em `http://localhost:8000/docs`. Depois, para o painel:

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Painel em `http://localhost:3000`. Como o cadastro exige código de indicação
de um usuário existente, crie o primeiro usuário com:

```bash
cd backend
python -m scripts.create_admin
```

Para a extensão (Chrome/Edge): `chrome://extensions` → "Modo do
desenvolvedor" → "Carregar sem compactação" → selecionar a pasta
`extension/`. Ela já aponta para `http://localhost:8000` por padrão.

Detalhes e notas de segurança em [`backend/README.md`](backend/README.md),
[`frontend/README.md`](frontend/README.md) e
[`extension/README.md`](extension/README.md) — inclusive sobre as
credenciais que estavam hardcoded no projeto desktop original.

## Status

- [x] Diagnóstico do sistema atual (`Browser/`)
- [x] Plano de arquitetura e roadmap
- [x] Aprovação do plano
- [x] **Fase 0 — fundação**: monorepo, backend FastAPI, 15 modelos SQLAlchemy
      portados e testados, Alembic configurado, Docker + docker-compose,
      CI (lint + testes)
- [x] **Fase 1 — conta & painel core**: registro/login/refresh com JWT
      (`app/api/routes/auth.py`), perfil (`/users/me`), dashboard inicial
      (`/dashboard/me`), script de bootstrap do primeiro usuário, painel
      Next.js (login, registro, dashboard) consumindo a API — 9 testes
      automatizados, build de produção do frontend verificado
- [x] **Fase 2 — extensão MVP**: modelo `Proxy` ganhou posse por usuário
      (`user_id`, `is_selected`), rotas `/proxies` (CRUD + seleção de proxy
      ativo) e `/browser-settings/me` (config de anti-detecção), CORS
      liberado para a extensão (`EXTENSION_ID`) — 10 testes automatizados
      novos (19 no total). Extensão Manifest V3: login/logout/status no popup, proxy
      aplicado via `chrome.proxy` + PAC script, autenticação de proxy via
      `onAuthRequired`, content script de anti-detecção (`world: "MAIN"`)
      mascarando `navigator.webdriver` e canvas — verificado de ponta a
      ponta com Chromium real via Playwright (login pela UI, proxy
      aplicado corretamente, limpo no logout)
- [x] **Fase 3 — pagamentos**: integração real com o Mercado Pago
      (`app/services/mercadopago_client.py`) para PIX e boleto — troca o
      polling em thread do app desktop por webhook real
      (`POST /payments/webhook/mercadopago`, com verificação opcional de
      assinatura HMAC). Checkout (`/payments/checkout`), status sob demanda
      (`/payments/{id}`), histórico (`/payments/me`) e preços por categoria
      (`/payments/prices`); configuração do Mercado Pago editável por admin
      em `/admin/payment-config`, com segredos nunca expostos em texto
      puro. Painel ganhou a página `/payments` (escolha de plano, PIX com QR
      Code, boleto com linha digitável, histórico). 17 testes automatizados
      novos (36 no total). **Fora do escopo, por decisão consciente**:
      cartão de crédito e split de comissão para afiliados não foram
      portados — ver `backend/README.md` para o porquê. **Atualizado
      depois** (ver bullet "Pagamentos atualizados" na seção de EasyPanel
      abaixo): boleto foi removido e cartão de crédito + USDT entraram no
      lugar, antes de qualquer uso em produção
- [x] **Fase 4 — produto completo**: diamantes/recompensas (saldo, catálogo,
      resgate, bônus de indicação finalmente ligado no cadastro), catálogo
      de ferramentas de IA com favoritos por usuário e credenciais
      diretas/cookies de sessão por ferramenta (cifrados em repouso — ver
      `backend/README.md`), notificações pessoais/globais com contador de
      não lidas, histórico de downloads espelhado da extensão via
      `chrome.downloads`. 28 testes automatizados novos (64 no total),
      painel ganhou `/rewards`, `/ai-tools`, `/notifications`, `/downloads`.
      **Fora do escopo, por decisão consciente**: login automático de IA de
      verdade (sem equivalente direto na arquitetura web), UI de admin para
      credenciais/cookies (rotas prontas, formulário fica para depois) e
      gestão de gastos operacionais (back-office, fora da linha do roadmap
      aprovado) — ver `backend/README.md` para o detalhamento
- [x] **Fase 5 — migração de dados & piloto**: script de migração
      dado-a-dado do MySQL do app desktop para o MySQL deste backend
      (`backend/scripts/migrate_from_desktop.py`) — upsert idempotente por
      `id` (PKs são UUID estável, sem remapeamento), dry-run por padrão,
      aproveitando que o schema ficou aditivo desde a Fase 0 (nada
      removido/renomeado; só 2 colunas novas em `proxy` e um valor novo no
      enum de pagamento). 9 testes automatizados novos (73 no total) contra
      fixtures locais. Runbook operacional completo (pré-requisitos, passo
      a passo, verificação, rollback) em
      [`docs/MIGRACAO_DADOS.md`](docs/MIGRACAO_DADOS.md) e plano de
      convivência desktop+web com critérios de piloto/rollback e
      considerações de LGPD em [`docs/PILOTO.md`](docs/PILOTO.md).
      **Importante**: esta fase entrega a ferramenta e o processo, testados
      e prontos — não uma migração de dados reais nem um piloto de fato
      executado com usuários reais, já que este sandbox não tem acesso ao
      MySQL de produção do app desktop; essa execução cabe à Divisions Tech
      seguindo o runbook.

Com a Fase 5 concluída, as 6 fases do roadmap aprovado (seção 10 de
[`docs/PLANO_MIGRACAO.md`](docs/PLANO_MIGRACAO.md)) estão prontas.

## Preparação para deploy no EasyPanel (pós-roadmap)

Fora das 6 fases originais — trabalho feito sob demanda para o deploy real
no EasyPanel usando o banco MySQL que a Divisions Tech já mantém lá, com
dados de produção do app desktop:

- **`backend/scripts/sync_schema_live.py`** — ajusta o schema de um banco
  **já em uso** (diferente do `migrate_from_desktop.py` da Fase 5, que
  copia pra um banco novo/separado): cria as tabelas que faltarem e
  adiciona as colunas novas conhecidas (2 em `proxy`, 1 em `payments`, 5
  em `payment_configs` — ver `PAGAMENTOS_CRIPTO.md`) e o valor novo do
  enum de `payments.payment_method` — nunca `DELETE`/`DROP`/`UPDATE` em
  dado existente. Testado contra um MySQL 8 real (não só fixtures SQLite)
  — ver `backend/tests/test_sync_schema_live.py`.
- **[`docs/DEPLOY_EASYPANEL.md`](docs/DEPLOY_EASYPANEL.md)** — guia
  completo de deploy: a lista exata de variáveis de ambiente do backend e
  do painel, o que **não** vai em variável de ambiente e por quê (token do
  Mercado Pago/PIX e carteira/preços USDT continuam geridos pelo banco via
  admin, decisão da Fase 3 mantida e estendida ao USDT), e a ordem
  recomendada de publicação.
- **`docs/PILOTO.md` atualizado** — registra a decisão de ir direto pela
  Estratégia B (banco único compartilhado com o desktop) em vez de uma
  cópia separada.
- **Pagamentos atualizados — boleto removido, cartão + USDT adicionados**:
  decisão de produto posterior à Fase 3, antes de qualquer uso em produção
  (boleto nunca chegou a ser usado nem existiu num banco real). Cartão de
  crédito via Mercado Pago (Card Payment Brick, tokenizado no navegador) e
  USDT na rede TRC20 direto numa carteira self-custodial da Divisions
  Tech, sem provedor terceiro — PIX continua exatamente como na Fase 3
  (Mercado Pago, BRL). Arquitetura completa do pagamento em USDT (por que
  TRC20, como um pedido é identificado sem endereço por pedido, como a
  confirmação funciona sem webhook, configuração da carteira) em
  [`docs/PAGAMENTOS_CRIPTO.md`](docs/PAGAMENTOS_CRIPTO.md). Painel
  (`/payments`) ganhou o formulário de cartão (Brick embutido) e a tela de
  pagamento em USDT (QR Code gerado localmente, endereço e valor exato
  para copiar); testes automatizados atualizados (backend e
  `sync_schema_live`), build e typecheck do frontend verificados.
- **Extensão — tela de configurações** (`extension/src/options/`): a URL
  do backend/painel deixou de ser uma constante fixa no código — agora dá
  pra trocar pelo próprio popup da extensão (ícone ⚙), com um botão de
  "Testar conexão". Ver `extension/README.md`.
- **`frontend/Dockerfile`** novo (o backend já tinha um desde a Fase 0) —
  build em `standalone` do Next.js, recebendo `NEXT_PUBLIC_API_URL` como
  build arg (variável embutida no bundle em tempo de build, não lida em
  runtime — documentado em `DEPLOY_EASYPANEL.md`).
