# Piloto — convivência desktop + web

Plano de rollout da Fase 5 (seção 10 do
[`PLANO_MIGRACAO.md`](PLANO_MIGRACAO.md)): como sair do app desktop atual
para a versão web sem interromper quem já usa o produto, usando a
ferramenta de migração descrita em [`MIGRACAO_DADOS.md`](MIGRACAO_DADOS.md).

**Este documento é o plano — a decisão de quando começar o piloto, quem
entra nele e quando fazer o corte final é da Divisions Tech. Nada aqui foi
executado contra usuários reais; o que existe pronto e testado é a
ferramenta e o processo.**

**Atualização — decisão já tomada:** a Divisions Tech confirmou que o
banco MySQL do EasyPanel (o mesmo que o app desktop já usa em produção,
com dados reais) vai ser compartilhado com o backend web desde o início —
ou seja, parte direto para a **Estratégia B** abaixo, sem uma cópia
separada. Isso muda a ferramenta usada para preparar o banco:
`backend/scripts/sync_schema_live.py` (aditivo, ajusta o schema do banco
já existente sem apagar nada) em vez de `migrate_from_desktop.py` (que
copia dados para um banco novo/separado — continua existindo e serve se,
no futuro, algum ambiente precisar de uma cópia isolada, ex. staging). Ver
[`MIGRACAO_DADOS.md`](MIGRACAO_DADOS.md) para o script e
[`DEPLOY_EASYPANEL.md`](DEPLOY_EASYPANEL.md) para o passo a passo completo
de deploy. O restante deste documento (seleção de piloto, critérios de
sucesso/rollback, LGPD) continua valendo do mesmo jeito.

## Por que dá para conviver

O schema é aditivo (ver `MIGRACAO_DADOS.md`) e todo PK é um UUID estável —
isso permite duas estratégias de convivência, descritas abaixo. A
Divisions Tech já decidiu ir direto pela Estratégia B (banco único, ver
nota no topo deste documento); a Estratégia A fica documentada como
alternativa mais conservadora, útil para outros ambientes (ex. um staging
com cópia isolada) caso venham a ser necessários no futuro.

### Estratégia A (alternativa mais conservadora, não é o caminho escolhido): bancos separados + sincronização periódica

- Desktop continua apontando para o MySQL de produção atual, sem nenhuma
  mudança.
- Web (backend deste repositório) aponta para um **banco novo**, populado
  inicialmente por `migrate_from_desktop.py --execute` e mantido
  sincronizado rodando o mesmo comando periodicamente (cron, ou manual,
  dependendo do volume de mudança — ver "Frequência de sincronização"
  abaixo).
- Vantagem: zero risco para o app desktop em produção — ele nunca sabe que
  a web existe. Se algo der errado na web, é isolado.
- Limitação: um usuário que usa desktop e web ao mesmo tempo pode ver dados
  levemente desatualizados na web até a próxima sincronização (ex.: mudou
  o proxy pelo desktop, só aparece atualizado na web depois do próximo
  `--execute`). Para o piloto — grupo pequeno, ciente de que é piloto —
  essa janela é aceitável; não seria para uso geral.

### Estratégia B — banco único compartilhado (decisão já tomada)

- Desktop e web MySQL são o **mesmo banco** (o do EasyPanel) — sem
  sincronização, porque não há duas cópias.
- Esta seção descrevia originalmente uma etapa "avançada", só recomendada
  depois de validar a Estratégia A por um tempo — mas a Divisions Tech já
  decidiu ir direto por aqui, aproveitando que o banco do EasyPanel já tem
  dados reais e é o que deve seguir sendo a fonte de verdade. Ver a nota no
  topo deste documento e [`DEPLOY_EASYPANEL.md`](DEPLOY_EASYPANEL.md).
- Risco a ter em mente: qualquer bug de escrita no backend novo afeta o
  banco que o desktop também usa — por isso `sync_schema_live.py` é
  estritamente aditivo (nunca `DELETE`/`DROP`/`UPDATE` de dado existente,
  só `CREATE TABLE`/`ADD COLUMN`/ampliar `ENUM`) e testado contra um MySQL
  real antes de ser usado contra o banco de produção. Ainda assim, backup
  antes de qualquer alteração de schema continua sendo praxe recomendada.

## Seleção do grupo piloto

Sugestão de critério, para a Divisions Tech ajustar ao contexto real do
usuário base:

- Grupo pequeno (dezenas, não milhares) e, se possível, voluntário —
  usuários avisados de que estão testando uma versão nova.
- Preferir usuários com uso "simples" no desktop primeiro (sem automações
  de IA muito específicas, sem grande volume de proxies) — funcionalidades
  fora do escopo das Fases 0–4 (ver `backend/README.md`, seção "Fora do
  escopo") são as que mais provavelmente faltam para esse grupo.
- Evitar, no primeiro grupo, contas com pagamentos recorrentes ativos
  pendentes de cobrança — o agendador de cobrança automática do desktop
  (`PaymentScheduler`) ainda não tem equivalente rodando na web (ver
  `backend/README.md`, seção "Pagamentos"); o piloto inicial deve validar
  o produto, não depender dessa lacuna já conhecida.

## Frequência de sincronização (só se aplica à Estratégia A)

Com a Estratégia B (banco único, o caminho escolhido) não existe
sincronização — desktop e web leem/escrevem no mesmo banco em tempo real,
então esta seção não se aplica. Fica documentada só para quem eventualmente
usar a Estratégia A em outro ambiente (ex. staging).

Não há um número certo — depende de quanto os usuários do piloto alternam
entre desktop e web no dia a dia. Ponto de partida sugerido: sincronizar a
cada poucas horas nos primeiros dias (para detectar problemas rápido) e
espaçar para 1x/dia depois que a operação se mostrar estável. Rodar
`--verify-only` (ver `MIGRACAO_DADOS.md`) antes de aumentar o intervalo,
para confirmar que não há divergência acumulada.

## Critério de sucesso (para avançar de piloto → geral)

Sugestões objetivas, para a Divisions Tech validar/ajustar:

- Na Estratégia B (o caminho escolhido) não há divergência a checar — é o
  mesmo banco. Confirme antes de ampliar o piloto: nenhuma anomalia de
  dado (proxy sumido, pagamento duplicado, saldo de diamantes errado)
  reportada por usuários do desktop OU da web durante o período do piloto.
- Usuários do piloto conseguem completar os fluxos centrais só pela web:
  login, gerenciar proxy, ver/editar configurações de navegação, checkout
  de pagamento (PIX, cartão de crédito ou USDT — ver
  `docs/PAGAMENTOS_CRIPTO.md`), resgatar diamantes, favoritar ferramenta de
  IA. (Todos já implementados e testados nas Fases 1–4 + atualização de
  pagamentos.)
- Nenhum incidente de segurança/vazamento de dado durante o piloto —
  particular atenção às credenciais de IA e cookies de sessão (cifrados em
  repouso desde a Fase 4, mas o piloto é o primeiro uso com dados reais).
- Feedback qualitativo do grupo piloto sobre as lacunas conhecidas (login
  automático de IA, UI de admin de credenciais/cookies, UI de admin de
  carteira/preços USDT, cobrança recorrente automática — ver
  `backend/README.md`) não bloqueia o uso do dia a dia deles.

## Critério de rollback (voltar só para o desktop)

Com a Estratégia B, "rollback" não significa restaurar um banco separado —
é sempre o mesmo banco. Significa pausar o **uso da web** e deixar o
desktop seguir funcionando normalmente enquanto se investiga:

- Se qualquer usuário do piloto reportar perda ou inconsistência de dado
  visível (ex.: proxy sumiu, pagamento duplicado, saldo errado).
- Se `sync_schema_live.py --verify-only`-equivalente (rodar o script de
  novo em dry-run) mostrar qualquer alteração de schema pendente/inesperada
  depois que já devia estar tudo em dia — indício de algo mexendo no schema
  fora do esperado.
- Nesses casos: peça para o grupo piloto voltar a usar só o desktop
  (nenhuma ação é necessária no banco — ele nunca teve uma cópia separada
  pra restaurar), investigue e corrija o backend/painel, e só depois libere
  a web de novo para o grupo. **Importante**: como é o mesmo banco, um bug
  de *escrita* no backend web (não só de leitura) pode ter gravado dado
  incorreto que o desktop também passa a ver — por isso o critério acima
  inclui reports vindos de usuários do desktop, não só da web.

## LGPD e dados sensíveis

Conforme já sinalizado na seção 11 do `PLANO_MIGRACAO.md`, antes de migrar
dados reais de usuários (não só dados de teste) para a nuvem, revisar:

- **Base legal e consentimento**: usuários do piloto devem ser informados
  de que os dados deles trafegam por uma nova infraestrutura (backend na
  nuvem, ao invés de só local/desktop).
- **Dados de pagamento**: `PaymentConfig` e `Payment` guardam informações
  ligadas a cobrança — confirmar que o ambiente onde o backend novo roda
  em produção atende aos mesmos requisitos de segurança (TLS ponta a
  ponta, controle de acesso ao banco, logs de acesso) que o app desktop já
  tinha.
- **Cookies de sessão de terceiros** (`ai_sessions_cookies`,
  `cookie_parser.py`): são dados de autenticação de serviços de terceiros
  guardados pela plataforma — cifrados em repouso desde a Fase 4, mas vale
  confirmar politica de retenção/expiração antes do piloto ir para dados
  reais.
- **Direito de exclusão**: se um usuário do piloto pedir para sair, os
  dados dele precisam poder ser removidos do banco (com a Estratégia B é
  só um lugar, não dois) — não há uma rota automatizada para isso hoje; é
  um processo manual até existir demanda para automatizar.

Esta seção é um ponto de partida, não uma revisão jurídica — recomenda-se
validar com quem cuida de conformidade da Divisions Tech antes de incluir
o primeiro usuário real (não de teste) no piloto.

## Cronograma sugerido (orientativo)

Ajustado para a Estratégia B (banco único do EasyPanel), o caminho já
escolhido:

1. **Semana 1**: rodar `sync_schema_live.py` em dry-run contra o banco do
   EasyPanel (seção 0 de `DEPLOY_EASYPANEL.md`), revisar a saída, fazer
   backup do banco, depois rodar com `--execute` fora de horário de pico.
   Nenhum usuário ainda usando a web.
2. **Semana 2**: publicar backend e painel no EasyPanel
   (`DEPLOY_EASYPANEL.md`), configurar Mercado Pago via admin, configurar a
   extensão (tela de configurações) para o grupo piloto. Testar
   internamente antes de convidar qualquer usuário real.
3. **Semanas 3–4**: convidar o grupo piloto para a web (desktop continua
   funcionando normalmente, mesmo banco), acompanhar os critérios de
   sucesso/rollback diariamente.
4. **A partir da semana 5** (se os critérios de sucesso forem atingidos):
   avaliar ampliar o grupo piloto e, eventualmente, desligar o app desktop
   para os usuários migrados (ou deixar convivendo, se fizer sentido pro
   negócio — a Estratégia B não exige desligar nada).

Datas são ilustrativas — o ritmo real depende da disponibilidade da
Divisions Tech para acompanhar de perto, principalmente nas duas primeiras
semanas.
