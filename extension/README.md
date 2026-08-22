# Nuvion Web — Extensão (Manifest V3)

Fase 2 do roadmap (ver [`../docs/PLANO_MIGRACAO.md`](../docs/PLANO_MIGRACAO.md),
seção 5): navegação autenticada contra `../backend`, proxy por usuário via
PAC (`chrome.proxy`) e um content script de anti-detecção — equivalentes
parciais de `chrome_browser_manager.py`, `pac_proxy_manager.py` e
`anti_detect_section.py` no app desktop. A Fase 4 acrescentou dois recursos
pequenos que se apoiam na infraestrutura já existente (auth/API client desta
extensão): espelhar `chrome.downloads` no histórico do painel e mostrar a
contagem de notificações não lidas no popup — ver "Fase 4" abaixo. Já fora
do roadmap de fases original, a preparação para o deploy no EasyPanel (ver
[`../docs/DEPLOY_EASYPANEL.md`](../docs/DEPLOY_EASYPANEL.md)) trocou a URL
fixa do backend/painel por uma tela de configurações na própria extensão —
ver "Carregar no Chrome/Edge" e "Verificação feita na tela de
configurações" abaixo.

## Estrutura

```
extension/
├─ manifest.json
├─ src/
│  ├─ background/
│  │  ├─ service-worker.js   # auth, aplica o proxy ativo, onAuthRequired
│  │  └─ api.js               # cliente HTTP (token em chrome.storage.local)
│  ├─ content/
│  │  └─ anti-fingerprint.js  # world "MAIN", document_start — mascaramento fixo
│  ├─ popup/
│  │  ├─ popup.html
│  │  └─ popup.js             # login/status/logout, mostra o proxy ativo
│  └─ options/
│     ├─ options.html
│     └─ options.js           # URL do backend/painel, guardadas em chrome.storage.local
```

## O que já funciona (MVP)

- Login/logout pelo popup, token JWT guardado em `chrome.storage.local`
  (equivalente ao `localStorage` do painel, mas acessível pelo service worker).
- Refresh automático do access token em respostas 401 (`src/background/api.js`).
- Proxy por usuário: o popup mostra o proxy atualmente selecionado
  (`GET /proxies/active`) e o background aplica um PAC script via
  `chrome.proxy.settings.set` sempre que o usuário loga, reabre o navegador,
  ou clica em "Reaplicar proxy". Autenticação do proxy (usuário/senha) é
  resolvida via `chrome.webRequest.onAuthRequired`.
- Content script de anti-detecção roda em todo site (`world: "MAIN"`,
  `document_start`): mascara `navigator.webdriver` e adiciona ruído leve no
  canvas. Ainda é fixo — não lê `anti_detection_settings` por usuário (ver
  comentário no topo de `anti-fingerprint.js` para o porquê e o plano da
  Fase 4).

## Fase 4 — downloads e notificações

- **Espelho de downloads** (`src/background/service-worker.js`): escuta
  `chrome.downloads.onCreated`/`onChanged` e registra/atualiza o histórico
  via `POST /downloads` e `PATCH /downloads/{id}` — precisou da permissão
  `downloads` no `manifest.json`. O download em si já aconteceu no
  navegador antes de qualquer chamada à API; isto é só espelho de status
  (ver plano de migração, seção 6). O mapa `id do chrome → id do backend` é
  em memória: se o service worker for descartado por inatividade no meio de
  um download, aquele item específico fica sem status final — não afeta o
  download real nem os demais itens.
- **Badge de notificações no popup**: `GET /notifications/me/unread-count`
  mostrado na tela de status, ao lado do proxy ativo.

## Limitações conhecidas (documentadas desde o plano aprovado)

- Não há isolamento de perfil/TLS por aba como o QtWebEngine embutido do
  app desktop fazia — `chrome.proxy` é uma configuração global do
  navegador.
- O mascaramento de fingerprint é só na camada de JavaScript; não spoofa
  TLS/JA3/HTTP2 (exigiria um proxy/MITM de rede, fora do escopo de uma
  extensão comum).

## Carregar no Chrome/Edge para desenvolvimento

1. `chrome://extensions`
2. Ativar "Modo do desenvolvedor"
3. "Carregar sem compactação" → selecionar esta pasta (`extension/`)
4. Com o backend rodando em `http://localhost:8000` (ver
   [`../backend/README.md`](../backend/README.md)), abra o popup da
   extensão e entre com uma conta já cadastrada no painel.

Por padrão a extensão aponta para `http://localhost:8000` (backend) e
`http://localhost:3000` (painel) — bons valores pra desenvolvimento local.
Pra apontar pra outro ambiente (produção, staging), **não precisa mais
editar código nem recarregar a extensão**: clique no ícone ⚙ no popup, que
abre a tela de configurações (`src/options/`), preencha as duas URLs,
"Testar conexão" pra confirmar que o backend responde, e "Salvar". Fica
guardado em `chrome.storage.local` daquele navegador. Ver
[`../docs/DEPLOY_EASYPANEL.md`](../docs/DEPLOY_EASYPANEL.md) para o passo
a passo completo depois que o backend/painel estiverem publicados.

## Verificação feita nesta fase

- `node --check` em todos os arquivos `.js` da extensão.
- Validação estrutural do `manifest.json` (schema MV3, arquivos referenciados existem).
- Carregamento real via Playwright + Chromium (`--load-extension`):
  service worker sobe sem erros, content script aplica os overrides de
  fingerprint, popup renderiza a tela de login sem sessão.
- Fluxo de ponta a ponta contra um backend local (SQLite em memória): login
  pela UI do popup → criação/seleção de proxy pela API → "Reaplicar proxy"
  aplica o PAC script correto via `chrome.proxy.settings` → logout limpa
  token e proxy.

## Verificação feita na Fase 4

- `node --check --input-type=module` nos três arquivos alterados
  (`service-worker.js`, `api.js`, `popup.js`) e validação do `manifest.json`
  atualizado (permissão `downloads` nova).
- Carregamento real via Playwright + Chromium (`--load-extension`): service
  worker registra sem erros com os novos listeners `chrome.downloads.*`,
  popup abre a tela de login sem lançar exceção — não incluiu um teste de
  ponta a ponta com download real (exigiria um backend rodando + um arquivo
  de verdade sendo baixado no Chromium headless), então trate a lógica de
  espelhamento como verificada por leitura de código + carregamento, não por
  execução ponta a ponta.

## Verificação feita na tela de configurações (deploy no EasyPanel)

- `node --check` em `api.js`, `popup.js` e `options.js`; `manifest.json`
  validado (campo `options_ui` novo).
- Carregamento real via Playwright + Chromium (`--load-extension`), de
  ponta a ponta: popup mostra o botão ⚙ → abre `src/options/options.html`
  em aba nova → campos vêm preenchidos com os padrões de desenvolvimento
  (`localhost`) → alterar e salvar persiste em `chrome.storage.local`
  (confirmado recarregando a página) → "Testar conexão" contra um host
  inexistente mostra erro corretamente (sem travar a extensão) → de volta
  no popup, "Abrir painel"/"Criar conta" chamam `chrome.tabs.create` com a
  URL salva (confirmado interceptando a chamada, já que este sandbox não
  tem rede externa pra resolver domínio de teste de verdade).
