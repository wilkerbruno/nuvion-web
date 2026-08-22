# Deploy no EasyPanel

Guia de deploy da versão web (backend + painel) no EasyPanel, usando o
banco MySQL que a Divisions Tech já mantém lá — o mesmo banco que o app
desktop usa em produção, com dados reais. Ver
[`MIGRACAO_DADOS.md`](MIGRACAO_DADOS.md) e [`PILOTO.md`](PILOTO.md) para o
contexto da decisão de compartilhar esse banco (Estratégia B) em vez de uma
cópia separada.

## Visão geral

Dois serviços no EasyPanel, cada um com seu próprio `Dockerfile` já pronto
no repositório:

- **Backend** (`backend/Dockerfile`) — API FastAPI, porta 8000.
- **Frontend** (`frontend/Dockerfile`) — painel Next.js, porta 3000.

A extensão (Manifest V3) não é um serviço do EasyPanel — ela roda no
navegador de cada usuário e só precisa ser apontada para as URLs públicas
do backend/painel depois que eles estiverem no ar (ver "Extensão" no final
deste guia).

## 0. Antes do primeiro deploy: ajustar o schema do banco existente

O banco do EasyPanel já tem o schema do app desktop, que é quase idêntico
ao que este backend espera — faltam só algumas colunas novas (2 em `proxy`,
1 em `payments` para o valor exato de pagamentos USDT, 5 em
`payment_configs` para carteira/preços USDT) e um valor a mais no ENUM de
`payments.payment_method` (`usdt`). Rode `backend/scripts/sync_schema_live.py`
(script aditivo, testado contra um MySQL 8 real, nunca apaga/sobrescreve
dado nenhum — ver o cabeçalho do próprio script) **antes** de apontar o
backend novo para esse banco:

```bash
cd backend
pip install -r requirements.txt
python -m scripts.sync_schema_live --db-url "mysql+pymysql://usuario:senha@host-do-easypanel:3306/nome_do_banco"
# confira a saída (dry-run, nada é alterado ainda), depois:
python -m scripts.sync_schema_live --db-url "mysql+pymysql://usuario:senha@host-do-easypanel:3306/nome_do_banco" --execute
```

Isso pode ser rodado da sua própria máquina (se o MySQL do EasyPanel aceitar
conexão externa) ou de um serviço temporário dentro do EasyPanel com acesso
à rede interna, apontando `--db-url` para o host interno do banco. Faça um
backup do banco antes, como praxe padrão — mesmo sendo uma operação aditiva
já testada.

## 1. Variáveis de ambiente do backend

Configure em EasyPanel → seu serviço de backend → **Environment**. Nenhuma
delas tem valor padrão de produção no código — o backend recusa subir sem
as marcadas como obrigatórias.

| Variável | Obrigatória? | O que colocar |
|---|---|---|
| `ENVIRONMENT` | não | `production` |
| `DB_HOST` | **sim** | host do MySQL no EasyPanel (interno, ex. `nuvion-mysql` ou o hostname do serviço de banco) |
| `DB_PORT` | não (default 3306) | porta do MySQL |
| `DB_NAME` | não (default `nuvion`) | nome do banco existente |
| `DB_USER` | **sim** | usuário do MySQL |
| `DB_PASSWORD` | **sim** | senha do MySQL |
| `JWT_SECRET_KEY` | **sim** | gere com `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | **sim** | gere com `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` — ⚠️ **depois que existir alguma credencial de IA salva cifrada com essa chave (Fase 4), trocá-la torna esses dados ilegíveis.** Gere uma vez, guarde em local seguro (o próprio cofre de variáveis do EasyPanel já serve), não regenere depois. |
| `CORS_ALLOWED_ORIGINS` | não (default só localhost) | lista JSON com a(s) URL(s) do painel publicado, ex. `["https://app.seudominio.com.br"]` — **sem isso o painel em produção não consegue chamar a API** (CORS bloqueado) |
| `EXTENSION_ID` | não | ID da extensão depois de carregada/publicada (ver seção "Extensão" abaixo) — sem ele, a extensão ainda funciona, só não é adicionada à lista de origens CORS explicitamente liberadas (não costuma ser necessário, já que extensões MV3 não são bloqueadas por CORS do mesmo jeito que um site; deixe em branco se não tiver certeza) |
| `MERCADOPAGO_WEBHOOK_SECRET` | recomendado em produção | o mesmo segredo que você cadastrar no painel do Mercado Pago ao configurar a URL do webhook — habilita verificação de assinatura HMAC |
| `MERCADOPAGO_ACCESS_TOKEN` / `MERCADOPAGO_APP_ID` | não | **deixe em branco** — ver "Sobre os dados de pagamento" abaixo |
| `TRONGRID_API_KEY` | não | chave (gratuita) da TronGrid, só para aumentar o limite de requisições ao consultar pagamentos em USDT — **não é segredo sensível** (não move fundos, só lê dados públicos do blockchain); funciona em branco também, com limite menor. Ver [`PAGAMENTOS_CRIPTO.md`](PAGAMENTOS_CRIPTO.md) |
| `SMTP_*` | não | nenhuma rota usa isso ainda (config portada do desktop, sem funcionalidade de recuperação de senha por e-mail implementada nesta versão web) — pode deixar tudo em branco por enquanto |

### Sobre os dados de pagamento ("dados bancários")

O token de acesso do Mercado Pago e a chave PIX **não vão em variável de
ambiente** — ficam na tabela `payment_configs` do próprio banco, editáveis
só por uma conta admin via `GET`/`PUT /admin/payment-config` (peça pra
confirmar em `/docs` do backend publicado). Essa foi uma decisão consciente
desde a Fase 3, mantida agora por decisão sua: dá pra trocar de sandbox
para produção, ou girar uma chave vazada, sem precisar reimplantar o
backend — só chamando essa rota autenticada como admin.

Passo a passo depois que o backend estiver no ar:

1. Entre com uma conta `Admin` (o banco já compartilhado com o desktop
   provavelmente já tem uma — não precisa criar um novo admin só pra isso).
2. `PUT /admin/payment-config` com `access_token`, `public_key`, `pix_key`,
   `pix_name`, `environment` (`sandbox` ou `production`) etc.
3. `POST /admin/payment-config/test-connection` pra confirmar que o token
   é válido antes de liberar pagamentos de verdade.

`MERCADOPAGO_ACCESS_TOKEN`/`MERCADOPAGO_APP_ID` (variável de ambiente)
só existem como *fallback* caso a tabela `payment_configs` ainda esteja
vazia — não é o caminho recomendado, deixe em branco e configure pelo
admin.

### Sobre o pagamento em USDT (carteira cripto)

Diferente do Mercado Pago, aqui não existe token de acesso nenhum — é uma
carteira **self-custodial**, sem provedor terceiro (o backend só lê o
blockchain público, nunca guarda chave privada). Mesmo assim, a carteira e
os preços em USDT também ficam no banco (`payment_configs`), não em
variável de ambiente — mesmo padrão do Mercado Pago, pelo mesmo motivo
(trocar sem redeploy). Passo a passo e detalhes completos (endereço,
rede TRC20, como funciona a detecção de pagamento) em
[`PAGAMENTOS_CRIPTO.md`](PAGAMENTOS_CRIPTO.md).

## 2. Variáveis de ambiente do frontend

| Variável | Quando | O que colocar |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | **build-time**, não runtime | a URL pública do backend, ex. `https://api.seudominio.com.br` |

**Atenção**: diferente de todas as variáveis do backend, `NEXT_PUBLIC_API_URL`
é embutida no JavaScript já compilado durante `next build` (é assim que o
Next.js funciona com variáveis `NEXT_PUBLIC_*`) — não é lida em tempo de
execução. No EasyPanel, isso normalmente significa configurá-la como
**build arg** do serviço (não só como variável de ambiente do container em
runtime) — o `frontend/Dockerfile` já está preparado pra receber
`NEXT_PUBLIC_API_URL` como `ARG`. Se você mudar a URL do backend depois,
precisa gerar um novo deploy do frontend (rebuild), reiniciar o container
sozinho não é suficiente.

## 3. Ordem recomendada de deploy

1. Rodar `sync_schema_live.py` contra o banco do EasyPanel (seção 0).
2. Publicar o **backend** com as variáveis da seção 1. Confirmar em
   `https://api.seudominio.com.br/health` e `/docs`.
3. Publicar o **frontend** com `NEXT_PUBLIC_API_URL` apontando para a URL
   do passo 2. Confirmar que a tela de login carrega.
4. Voltar no backend e ajustar `CORS_ALLOWED_ORIGINS` para incluir a URL
   do frontend do passo 3 (se ainda não tinha colocado) e reiniciar o
   serviço — sem isso o painel consegue carregar mas as chamadas à API
   falham por CORS.
5. Configurar o Mercado Pago (PIX + cartão) via `/admin/payment-config`
   (seção 1) com uma conta admin existente.
6. Configurar a carteira e os preços em USDT, também via
   `/admin/payment-config` — ver [`PAGAMENTOS_CRIPTO.md`](PAGAMENTOS_CRIPTO.md).
   Opcional: se não for aceitar USDT ainda, pule este passo — o checkout em
   USDT simplesmente fica indisponível até ser configurado (o resto do
   sistema funciona normalmente sem ele).
7. Configurar a extensão para todo mundo que for usar a versão web (seção
   4 abaixo).

## 4. Extensão — como usar depois do deploy

A extensão (pasta `extension/`) não precisa mais ser reconstruída pra
apontar para produção — desde esta atualização ela tem uma tela de
configuração própria.

### Carregar a extensão

1. `chrome://extensions` (ou `edge://extensions`)
2. Ativar "Modo do desenvolvedor"
3. "Carregar sem compactação" → selecionar a pasta `extension/`

Isso é suficiente para uso interno/piloto. Para distribuir a um grupo maior
sem cada pessoa precisar clonar o repositório, dá pra empacotar a pasta
`extension/` como `.zip` e publicar na Chrome Web Store (fica sujeito à
revisão da Google, por causa das permissões de proxy/`<all_urls>` — não é
instantâneo; trate como um passo separado, fora deste guia de deploy).

### Apontar para o backend/painel de produção

1. Clique no ícone da extensão → no popup, clique no ⚙ (canto superior
   direito) — abre a tela de configurações em uma aba nova.
2. Preencha **URL do backend (API)** com a URL do passo 2 do deploy (ex.
   `https://api.seudominio.com.br`) e **URL do painel** com a do passo 3
   (ex. `https://app.seudominio.com.br`).
3. Clique em **Testar conexão** — deve mostrar "✓ Backend respondeu..." se
   a URL estiver certa e o backend estiver no ar.
4. Clique em **Salvar**. Essas URLs ficam guardadas só naquele navegador
   (`chrome.storage.local`) — cada instalação da extensão configura a sua.
5. Volte ao popup e entre com uma conta já existente (a mesma que já
   funciona no painel, já que o banco é compartilhado).

Isso substitui o que antes exigia editar `DEFAULT_API_BASE_URL` em
`src/background/api.js` e recarregar a extensão a cada troca de ambiente
(ver `extension/README.md`, que documentava essa limitação antes desta
atualização) — agora dá pra alternar entre localhost (desenvolvimento) e
produção sem tocar em código.
