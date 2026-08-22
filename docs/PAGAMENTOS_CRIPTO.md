# Pagamento em USDT (TRC20) — self-custodial, sem provedor terceiro

Decisão de produto (pós-Fase 3, antes de qualquer uso em produção): além de
PIX e cartão via Mercado Pago, o sistema aceita **USDT na rede Tron
(TRC20)** direto numa carteira cripto da Divisions Tech — sem passar por
nenhum provedor de pagamento terceiro (nem exchange, nem gateway cripto).
Este documento explica a arquitetura, como configurar e como operar.

## Por que TRC20 e por que self-custodial

- **TRC20 (rede Tron)** foi a rede escolhida entre as opções de USDT —
  taxa de rede (energia/bandwidth Tron) tipicamente centavos de dólar,
  bem mais barata que USDT na rede Ethereum (ERC20), e confirmação rápida
  (poucos segundos a minutos).
- **Self-custodial** significa que a carteira que recebe os pagamentos é
  seu, gerenciada por você fora deste sistema (ex.: TronLink, Ledger, ou
  qualquer carteira TRC20) — o backend **nunca vê nem guarda a chave
  privada** dessa carteira. Ele só *lê* o blockchain público (via TronGrid)
  para detectar quando um pagamento chegou. Isso foi um requisito explícito
  do produto (nenhum provedor terceiro no meio) e também é mais simples de
  operar: você move os fundos quando e como quiser, com a própria carteira.

## Por que o PIX não vira USDT automaticamente

Foi cogitado inicialmente fazer o PIX "cair" como USDT na mesma carteira.
Isso não é tecnicamente possível sem um intermediário: PIX só movimenta
BRL (é um sistema de pagamento do Banco Central), e uma carteira cripto só
guarda cripto — não existe uma ponte direta entre os dois sem alguém no
meio convertendo (uma exchange, uma fintech cripto) cobrando taxa de
câmbio/spread. Como a decisão final foi ficar com a opção "recomendada e
de menor taxa", o PIX continua exatamente como na Fase 3 (Mercado Pago,
BRL, zero taxa nova) e o USDT é um método de pagamento **totalmente
separado**, também sem taxa de provedor (só a taxa de rede Tron, paga pelo
próprio pagador, como em qualquer transferência cripto).

## Arquitetura

```
Usuário                Backend                      TronGrid (API pública)      Blockchain Tron
   │                       │                                  │                        │
   │  POST /payments/      │                                  │                        │
   │  checkout (usdt)      │                                  │                        │
   ├──────────────────────>│                                  │                        │
   │                       │  gera valor único (6 casas)       │                        │
   │                       │  cria Payment (Pendente)          │                        │
   │  <───────────────────┤  retorna endereço + valor exato    │                        │
   │                       │                                  │                        │
   │  paga na carteira do próprio app (fora deste sistema) ─────────────────────────────>│
   │                       │                                  │                        │
   │  GET /payments/{id}   │                                  │                        │
   ├──────────────────────>│  GET /v1/accounts/{addr}/         │                        │
   │                       │  transactions/trc20 ──────────────>│  consulta transfers   │
   │                       │                                  │  confirmadas ─────────>│
   │                       │  <────────────────────────────────┤                        │
   │                       │  bate valor? -> marca Confirmado  │                        │
   │  <───────────────────┤  e renova assinatura               │                        │
```

Peças-chave, com seus arquivos:

- `app/services/tron_client.py` — cliente HTTP só de leitura da TronGrid
  (`api.trongrid.io`, API pública e gratuita — `TRONGRID_API_KEY` é
  opcional, só aumenta o limite de requisições). Consulta
  `GET /v1/accounts/{endereco}/transactions/trc20`, filtrando pelo
  contrato oficial do USDT-TRC20 (`TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`,
  confirmado em tether.to e no TronScan) e por transferências recebidas
  (`to == endereco`) desde a criação do pagamento.
- `app/crud/payment.py::generate_unique_usdt_amount` — como identificamos
  de qual pedido veio uma transferência (ver seção abaixo).
- `app/api/routes/payments.py` (`_checkout_usdt`, `_recheck_usdt`) — gera a
  cobrança e faz a re-checagem sob demanda.
- `app/crud/payment_config.py` (`get_usdt_wallet`,
  `get_usdt_amount_by_category`) — leitura da configuração (carteira e
  preços) salva pelo admin.

## Como um pedido é identificado (carteira compartilhada + valor único)

Diferente de gerar um endereço novo por pedido (derivação HD, que exigiria
guardar/derivar chaves — incompatível com "self-custodial sem o backend
tocar em chave"), este sistema usa **um único endereço de carteira**
(configurado uma vez pelo admin) para todos os pagamentos em USDT. Para
saber de qual pedido veio uma transferência recebida, cada pagamento
pendente ganha um **valor exclusivo**, com incrementos de 0.000001 USDT
(a menor unidade representável — USDT tem 6 casas decimais na rede TRC20)
sobre o preço configurado para aquela categoria, até achar um valor que
nenhum outro pagamento pendente e não vencido já está usando.

Exemplo: se o preço do plano Standard em USDT é 19.99 e já existe um
pagamento pendente esperando exatamente 19.99, o próximo pedido recebe
19.990001; se esse também já estiver em uso, 19.990002; e assim por
diante. Isso é por que **é importante o usuário enviar o valor exato**
mostrado na tela (até a 6ª casa decimal) — um valor arredondado (ex.
"20" em vez de "19.990001") pode não bater com nenhum pagamento pendente
e não ser reconhecido automaticamente. A interface do painel deixa isso
explícito e oferece um botão para copiar o valor exato.

Não há problema de colisão entre pedidos de usuários diferentes: a busca
por "valor já em uso" olha todos os pagamentos `usdt` pendentes e não
vencidos no sistema inteiro (a carteira é compartilhada, então o espaço de
valores também precisa ser).

## Como a confirmação funciona (sem webhook)

Diferente do Mercado Pago (que notifica o backend via webhook quando um
pagamento muda de status), não existe nenhum "provedor" para nos avisar de
uma transferência TRC20 — é só blockchain público. Por isso, a única forma
de detectar que um pagamento em USDT chegou é o próprio backend consultar
a TronGrid **sob demanda**, toda vez que `GET /payments/{id}` é chamado
enquanto o pagamento ainda está "Pendente" (o painel faz isso em polling
curto enquanto mostra a tela de pagamento, do mesmo jeito que já fazia
para PIX). Quando encontra uma transferência confirmada (`only_confirmed`)
com o valor esperado (com uma tolerância de meia menor-unidade, só para
imprecisão de ponto flutuante — não para aceitar valores "quase certos"),
marca o pagamento como `Confirmado` e renova a assinatura, usando o mesmo
`mark_paid_and_renew` que PIX/cartão usam.

Consequência prática: se ninguém abrir a tela de pagamento depois de pagar,
a confirmação só acontece na próxima vez que alguém consultar o status
daquele pagamento (o painel ou, futuramente, uma rotina administrativa que
rechecar pagamentos pendentes em lote — não implementada nesta fase, já
que reconsultar sob demanda cobre o fluxo normal de uso).

## Configuração (admin)

Tudo fica na tabela `payment_configs` (mesma tabela do Mercado Pago),
editável só por conta `Admin` via `PUT /admin/payment-config` — **não** em
variável de ambiente (endereço de carteira não é segredo, mas ainda assim
segue o mesmo padrão do resto da configuração de pagamento: trocar sem
precisar reimplantar o backend).

Campos:

| Campo | Obrigatório para aceitar USDT? | O que colocar |
|---|---|---|
| `usdt_wallet_address` | sim | endereço TRC20 (começa com `T`) da sua carteira — copie da própria carteira (TronLink, Ledger, etc.) |
| `usdt_network` | não (default `TRC20`) | deixe `TRC20` — é a única rede suportada por este sistema hoje |
| `standard_amount_usdt` | sim, por categoria | preço em USDT do plano Standard, ex. `"19.99"` |
| `premium_amount_usdt` | sim, por categoria | idem para Premium |
| `vip_amount_usdt` | sim, por categoria | idem para VIP |

Enquanto `usdt_wallet_address` não estiver configurado, o checkout em USDT
responde `503 Serviço indisponível`. Enquanto o preço de uma categoria
específica não estiver configurado (`null`/vazio), o checkout em USDT para
essa categoria responde `400` — as outras categorias continuam disponíveis
normalmente. O painel (`/payments`) já trata isso: mostra "USDT ainda não
disponível para o plano X" em vez do botão de gerar cobrança quando o
preço daquela categoria não está configurado.

Não existe conversão automática de câmbio BRL → USDT — os preços em USDT
são definidos manualmente pelo admin, exatamente como já era feito para os
preços em BRL. Foi uma decisão consciente para não depender de mais uma
API externa (de cotação) só por isso; ajuste os preços em USDT
manualmente quando quiser refletir a cotação atual.

## Segurança e operação

- O backend nunca solicita, recebe ou guarda uma chave privada — é
  fisicamente impossível para ele mover fundos da carteira. O único dado
  sensível relacionado a essa carteira que passa por ele é o endereço
  público (que não é segredo — é o que qualquer pagador precisa ver para
  pagar).
- Retirar/mover os fundos recebidos é uma operação que você faz
  diretamente na sua própria carteira (TronLink, Ledger, etc.), fora deste
  sistema, como qualquer outra carteira cripto.
- `TRONGRID_API_KEY` (variável de ambiente, opcional) só aumenta o limite
  de requisições por segundo à API pública da TronGrid — não concede
  nenhum acesso à carteira nem é um dado sensível (pode ficar em branco;
  o rate limit sem chave é suficiente para o volume normal de checagens).
- `_AMOUNT_TOLERANCE` (0.0000005 USDT) em `tron_client.py` existe só para
  absorver imprecisão de ponto flutuante na comparação — os valores
  gerados já são exclusivos até a 6ª casa decimal, então essa tolerância
  não abre margem para confundir dois pedidos diferentes.
