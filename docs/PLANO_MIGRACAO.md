# Nuvion Web — Plano de Migração

Roteiro técnico para levar o Nuvion Browser — hoje um app PyQt6/QtWebEngine —
para uma arquitetura web híbrida: painel de gestão na nuvem e extensão de
navegador para a camada de navegação.

*Origem: `Browser/` (PyQt6, ~140 módulos Python) · Destino: `nuvion-web/`
(FastAPI + React + extensão MV3) · Gerado em 22 ago 2026.*

> Versão navegável (com diagrama e tabelas formatadas):
> https://claude.ai/code/artifact/29540493-071a-4b43-b076-88d778eb7843

## 1. Diagnóstico do sistema atual

O Nuvion Browser é um navegador desktop completo construído em PyQt6 +
QtWebEngine (Chromium embutido), com back-end relacional próprio em MySQL via
SQLAlchemy/Alembic. Não é só um navegador: é uma plataforma com conta de
usuário, assinatura paga, moeda interna e uma camada de anti-detecção. O
código-fonte se divide em seis blocos funcionais:

- **Casca do navegador** — `core/browser_window.py`, `core/tabs.py`,
  `core/components/tab_manager_cookies.py`, `core/components/navigation_bar.py`
  e `core/components/menu_sidebar.py`.
- **Anti-detecção e automação** — `config/automation_flags.py`,
  `core/security/browser_protection.py`,
  `core/services/intelligent_bypass_engine.py` e
  `core/widgets/settings/anti_detect_section.py`. É o coração do produto e o
  mais difícil de portar 1:1.
- **Rede e proxies** — `core/managers/chrome_browser_manager.py`,
  `cookie_browser_manager.py`, `pac_proxy_manager.py`, `proxy_detector.py` e,
  em `core/services/`, `proxy_router.py`, `proxy_router_ssl.py`,
  `socks5_server_complete.py`.
- **Conta, pagamentos e diamantes** — `core/login_window.py`,
  `core/payment_page.py`, `core/api/mercadopago_worker.py`,
  `core/services/pix_generator.py`, `core/managers/payment_scheduler.py` e
  `core/services/reward_service.py` (PIX/boleto via Mercado Pago, cobrança
  recorrente e a economia de "diamantes" trocáveis por recompensas).
- **Produto ao redor** — dezenas de widgets em `core/widgets/settings/` (IA,
  downloads, favoritos, gestão de gastos, notificações, tradutor).
- **Persistência** — `database/models/` (17 modelos SQLAlchemy) e `crud/`
  (managers de acesso a dados). É a camada mais reaproveitável tal como está.

A dificuldade de portar este sistema não está no CRUD nem nas telas — está em
recriar, dentro das regras de um navegador comum, o que hoje só existe porque
o app *é* o próprio Chromium.

## 2. Arquitetura alvo

Nenhum site comum consegue embutir e controlar qualquer página de terceiros
como o QtWebEngine faz (bloqueios de `X-Frame-Options`/CSP e política de
mesma origem). A solução: dividir o produto em duas superfícies de cliente
que falam com o mesmo back-end.

- **Painel web** (React/Next.js) — conta, proxies, pagamentos, diamantes, IA,
  configurações.
- **Extensão de navegador** (Manifest V3, Chrome/Edge) — navegação e camada
  anti-detecção de fato.
- **Back-end único** (FastAPI) — reaproveita quase integralmente os modelos
  SQLAlchemy de `database/models/` e a lógica hoje em `managers`/`services`,
  agora exposta como API HTTP/WebSocket.
- App desktop pode conviver com a versão web durante a transição.

## 3. Mapeamento de módulos

| Módulo desktop | Destino | Observação |
|---|---|---|
| `login_window.py` | Tela de login web + `/auth` API | JWT no lugar de sessão local em disco |
| `browser_window.py`, `tabs.py`, `tab_manager_cookies.py` | Extensão — gestão de abas | Núcleo do service worker |
| `chrome_browser_manager.py`, `cookie_browser_manager.py` | Service worker da extensão | Candidatos a reescrita em TypeScript, não porte direto |
| `automation_flags.py`, `intelligent_bypass_engine.py`, `anti_detect_section.py` | Content scripts da extensão | Ver seção 5 para limites reais do Manifest V3 |
| `pac_proxy_manager.py`, `proxy_router*.py`, `socks5_server_complete.py` | Proxy Gateway (back-end) | Extensão consome via API; ver seção 6 |
| `payment_page.py`, `mercadopago_worker.py`, `pix_generator.py`, `payment_scheduler.py` | Módulo de pagamentos (API + webhook) | Troca polling por webhook real do Mercado Pago |
| `rewards_widget.py`, `reward_service.py`, `diamond_platform_config.json` | Módulo de diamantes/recompensas | UI Qt → páginas React + endpoints de saldo/resgate |
| `widgets/settings/*` (12 seções) | Páginas de Configurações do painel | `pagamentos_section.py` e `nova_ia_section.py` são as maiores |
| `notifications_widget.py`, `notification_manager.py`, `notification_crud.py` | Sistema de notificações | WebSocket ou polling curto |
| `downloads_section.py`, `download_manager.py` | Módulo de downloads | Download real fica a cargo do navegador; extensão só espelha status |
| `translator_popup.py` | Feature da extensão + endpoint de tradução | Pode usar API de tradução de terceiros |
| `database/models/*`, `crud/*` | Camada de dados do FastAPI | Reaproveitamento quase 1:1 |
| `assets/css/*` (24 arquivos) | Design system web | Qt Style Sheets não é CSS de navegador — refeito, não copiado |

## 4. Dados & autenticação

Os 17 modelos em `database/models/` continuam fazendo sentido num back-end
web — recomenda-se reaproveitá-los quase sem mudança de schema, só trocando a
forma de acesso: o `crud/` deixa de ser chamado direto dentro do processo Qt
e vira a camada de serviço por trás dos endpoints REST.

O que muda de verdade é autenticação. Hoje a sessão é local (`user_session.py`,
`device_token_manager.py`). Na web vira **JWT de acesso curto + refresh
token**: o painel guarda o token em cookie `httpOnly`, a extensão guarda o
seu em `chrome.storage.local`. CORS do back-end deve aceitar apenas a origem
do painel web e o ID fixo da extensão publicada — nunca `*`. Rate limiting
por conta desde o dia um, dado que o sistema mexe com pagamento e proxy.

## 5. Extensão de navegação — o que dá e o que não dá

**Consegue:** controlar o proxy do navegador inteiro ou por regra de PAC
(`chrome.proxy`), injetar JavaScript antes de qualquer script da página
(`content_scripts` em `document_start`) para mascarar `navigator.webdriver`,
`navigator.userAgent`, canvas e WebGL, e reescrever cabeçalhos de requisição
via `declarativeNetRequest`.

**Não consegue:** alterar o fingerprint de rede (ordem de cabeçalhos
HTTP/2, assinatura TLS/JA3) — nível de socket, fora do alcance de qualquer
API de extensão. Também não isola perfis com a mesma liberdade que
`QWebEngineProfile` tinha no desktop; o equivalente mais próximo são os
Chrome Profiles ou containers do Firefox.

**Decisão em aberto:** a Chrome Web Store revisa com mais rigor extensões
que mexem com proxy e fingerprint. Vale posicionar publicamente como
ferramenta de privacidade/gestão de múltiplas contas para agências, e ter um
canal de distribuição alternativo (instalação manual/enterprise) como plano B.

## 6. Proxies & rede

Hoje `socks5_server_complete.py` sobe um servidor SOCKS5 local dentro do
próprio app; `proxy_router.py`/`proxy_router_ssl.py`/`proxy_router_ssl_fixed.py`
(três variantes — vale consolidar numa só) cuidam do roteamento;
`proxy_test_service.py` e `proxy_cleanup_service.py` testam e limpam proxies
mortos.

Na versão web isso vira um **Proxy Gateway** de back-end: mantém a lista de
proxies por usuário, roda os mesmos testes de saúde em background e expõe
uma API que a extensão consulta para montar a regra de PAC da sessão ativa.

## 7. Pagamentos & assinaturas

A integração com Mercado Pago migra quase inteira para o back-end como está
— `mercadopago_worker.py`, `pix_generator.py`, `payment_scheduler.py`,
`subscription_checker.py`. A mudança estrutural é trocar o polling por
**webhook** real do Mercado Pago. Credenciais (`authorization`, `app_id` em
`diamond_platform_config.json`) são segredo de servidor — nunca expostas ao
painel nem à extensão; centralizar num back-end é, na prática, uma melhoria
de segurança nesse ponto.

## 8. IA, diamantes & o resto do produto

Interface Qt vira página React, lógica de `crud/`/`core/services/` vira
endpoint FastAPI: diamantes e recompensas (regra de conversão de
`diamond_platform_config.json` não muda), ferramentas de IA (`ai_tool.py`,
`ai_session.py`, `ai_session_cookies.py`), gestão de gastos/pagamentos
administrativos como back-office com controle de acesso por papel
(`access_control_manager.py` se mantém como guarda de permissão).

## 9. Estrutura de pastas proposta

```
nuvion-web/
├─ backend/       # FastAPI — auth, proxies, pagamentos, diamantes, IA
│  ├─ app/
│  │  ├─ api/            # routers por domínio
│  │  ├─ models/         # reaproveita database/models/ quase 1:1
│  │  ├─ services/       # reaproveita core/services/ e core/managers/
│  │  ├─ crud/           # reaproveita crud/ quase 1:1
│  │  └─ core/           # config, segurança, JWT
│  ├─ alembic/
│  └─ tests/
├─ frontend/      # React/Next.js — painel de gestão
├─ extension/     # Manifest V3 — Chrome/Edge
│  └─ src/
│     ├─ background/     # service worker
│     ├─ content-scripts/
│     └─ popup/
├─ docs/          # este plano e os próximos ADRs
└─ infra/         # docker-compose, deploy
```

## 10. Roadmap

0. **Fundação** — monorepo, FastAPI + Alembic reaproveitando os modelos,
   Docker local, CI básico.
1. **Conta & painel core** — login/registro web com JWT, perfil, dashboard.
2. **Extensão MVP** — navegação básica autenticada, proxy por PAC, primeiro
   nível de mascaramento de fingerprint. Marco que valida a aposta
   arquitetural inteira.
3. **Pagamentos** — PIX, boleto, assinatura, webhook real.
4. **Produto completo** — diamantes, IA, notificações, downloads.
5. **Migração & piloto** — dados reais, grupo piloto, desktop e web
   convivendo até a web atingir paridade.

## 11. Riscos & decisões em aberto

- **Publicação da extensão** — ver seção 5.
- **Custo de infraestrutura** — o modelo painel + extensão é o mais barato
  dos avaliados. Um navegador remoto (Playwright por sessão) fica reservado
  para um eventual plano "zero instalação" futuro, tratado como fase
  separada.
- **Dados sensíveis em nuvem** — segredo fora do cliente, TLS ponta a ponta,
  log de acesso; revisão de conformidade com a LGPD antes do piloto,
  especialmente pelos dados de pagamento e pelos cookies de sessão de
  terceiros guardados em `ai_session_cookies.py`/`cookie_parser.py`.
- **Código duplicado a consolidar** — três variantes de proxy router e dois
  profile managers; decidir a versão "boa" antes de portar.

## 12. Próximos passos

Criar `nuvion-web/` com o esqueleto de monorepo da seção 9 e começar pela
Fase 0. A Fase 2 (extensão com navegação + proxy básicos) é o ponto de maior
risco técnico do projeto — priorizar um spike curto nela antes de aprofundar
nas fases 3 e 4, para confirmar cedo que a extensão entrega a paridade de
anti-detecção que o produto precisa.
