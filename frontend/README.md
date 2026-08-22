# Nuvion Web — Painel (frontend)

Next.js (App Router) + TypeScript, com uma única dependência além do
próprio Next (`qrcode`, para gerar o QR Code do pagamento em USDT
localmente, sem chamar nenhum serviço externo) — consome a API em
`../backend`. Login, registro, dashboard (Fase 1), assinatura/pagamentos
(Fase 3, atualizado depois: PIX, cartão de crédito e USDT — boleto foi
removido antes de qualquer uso em produção, ver
[`../docs/PAGAMENTOS_CRIPTO.md`](../docs/PAGAMENTOS_CRIPTO.md)) e agora
diamantes, ferramentas de IA, notificações e downloads (Fase 4).
Configurações avançadas de anti-detecção ficam só na extensão por enquanto
(ver [`../docs/PLANO_MIGRACAO.md`](../docs/PLANO_MIGRACAO.md)).

## Rodando localmente

Requer o backend rodando (ver [`../backend/README.md`](../backend/README.md)).

```bash
cd frontend
npm install
cp .env.local.example .env.local   # ajuste NEXT_PUBLIC_API_URL se necessário
npm run dev
```

Painel em `http://localhost:3000`.

## Estrutura

```
app/
├─ login/         # POST /auth/login
├─ register/      # POST /auth/register (exige código de indicação)
├─ dashboard/     # GET /dashboard/me (+ badge de notificações não lidas)
├─ payments/      # checkout PIX/cartão (Mercado Pago Brick)/USDT (TRC20),
│                 #   polling de status, histórico
├─ rewards/       # saldo de diamantes, catálogo de recompensas, resgate
├─ ai-tools/      # catálogo de ferramentas de IA, busca, favoritos
├─ notifications/ # lista, marcar como lida(s), apagar
├─ downloads/     # histórico de downloads (espelhado pela extensão)
└─ layout.tsx, globals.css
lib/api.ts         # cliente HTTP + tokens em localStorage
```

## Fase 4 — o que ficou de fora do painel (por ora)

As rotas de credenciais diretas e cookies de sessão por ferramenta de IA
(`/ai-tools/{id}/credentials`, `/ai-tools/{id}/cookies` no backend) existem
e estão testadas, mas ainda não têm formulário no painel — só a criação
básica de ferramentas (nome/URL/categoria/descrição) está disponível na tela
`/ai-tools`, visível só para contas Admin. Configurar credenciais/cookies
por enquanto exige chamar a API diretamente (`/docs`) ou uma próxima
iteração de UI.

A página `/payments` faz polling de `GET /payments/{id}` a cada 4s enquanto
o pagamento está pendente (até ~5min) — para PIX e USDT (cartão resolve na
hora, não fica pendente). Para PIX, o backend também confia no webhook real
do Mercado Pago para confirmar sem depender do painel estar aberto; o
polling é só para dar feedback imediato de UI. Para USDT não existe
webhook (não há provedor terceiro) — a própria chamada de
`GET /payments/{id}` durante o polling é o que consulta a TronGrid sob
demanda (ver [`../docs/PAGAMENTOS_CRIPTO.md`](../docs/PAGAMENTOS_CRIPTO.md)).

Cartão de crédito usa o **Card Payment Brick** do Mercado Pago
(`sdk.mercadopago.com/js/v2`), carregado sob demanda via `<script>` só
quando o usuário escolhe "Cartão de crédito" (evita baixar o SDK do MP
para quem nunca usa esse método). A chave pública vem de
`GET /payments/mercadopago-public-key`; o número do cartão nunca passa
pelo nosso backend, só o token que o próprio Brick gera no navegador. O
Brick já pede o CPF do pagador dentro do próprio formulário — não há campo
de CPF separado nesta página.

Autenticação: o access/refresh token ficam em `localStorage` do navegador
(equivalente web da sessão que o app desktop guardava em disco). Não há
ainda renovação automática de token expirado — planejado junto com a
Fase 2 (extensão), quando o mesmo mecanismo de auth passa a ser
compartilhado entre painel e extensão.

## Nota sobre dependências

`npm audit` acusa 2 avisos "high" no Next.js 14.2.x (issues de Server
Actions/Image Optimizer/Middleware — recursos que este painel ainda não usa).
A correção completa exige subir para o Next 16, uma major bem recente; fica
como decisão consciente para quando o painel crescer nas próximas fases,
não algo a ignorar. Rode `npm audit` de novo antes de qualquer deploy em
produção.
