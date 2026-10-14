# AI Data Masking Gateway

Você é o principal engenheiro responsável por desenvolver este projeto.

O sistema é um Gateway MCP entre uma IA e bancos de dados.

Fluxo:
IA → MCP → Gateway → Database → Result Set → Masking Engine → MCP → IA

## Objetivo
Permitir que IAs consultem bancos de dados sem expor dados sensíveis.

## Escopo atual
- MCP Server
- PostgreSQL
- SELECT read-only
- Masking Engine
- regras globais
- matching case-insensitive
- matching por contains
- exceptions
- transformers extensíveis
- configuração externa
- testes automatizados

Não implementar agora: CI/CD, RBAC complexo, interfaces genéricas, gerenciamento de schema, migrations, MySQL ou funcionalidades de DBA.

### Exceção aprovada — Fase 8

A partir da aprovação de 2026-09-09, somente a UI administrativa **local,
opt-in e estritamente delimitada por `docs/PHASE-8-SPEC.md`** está autorizada
como escopo de front-end. A especificação foi aprovada integralmente, incluindo
as quatro decisões da seção 8 (D-061 a D-064 em `docs/DECISIONS.md`).

As Etapas 1–9 foram revisadas e aprovadas; a publicação final da Etapa 9 está
autorizada. As Etapas 1–8 foram publicadas sem emenda. A **Etapa 9:
pacote instalado, revisão adversarial final e fechamento dos critérios de aceite**
foi concluída, com todos os gates aprovados. A Fase 8 está concluída conforme
`docs/PHASE-8-SPEC.md`, com os limites documentados na evidência.
Nenhuma funcionalidade, rota, modelo, permissão ou dependência da Fase 8 foi
ampliada. Preservar memória volátil, uma escrita pendente, gestos explícitos e
ausência de retry/rebase/fila/rollback automático. A Fase 9 foi autorizada em
2026-09-22 para sua Etapa 1 documental e para a Etapa 2 (modelos, store
cifrado/autenticado, validação de destino e migração explícita), e em
2026-09-23 para a Etapa 3: registry multi-datasource e lifecycle, ativados
somente pelo parâmetro interno `datasource_catalog` do composition root
(D-087–D-091). Em 2026-09-24 foi autorizada localmente, sem push, somente a
Etapa 4: Admin API v2 de datasources sob `/admin/v2`, com decisões de contrato,
concorrência e limite de DNS apresentadas antes do código e aprovadas
(D-092–D-096); ela foi implementada com evidência em
`docs/PHASE-9-STAGE-4-VALIDATION.md`. Em 2026-09-24, depois da publicação das Etapas 3 e 4 em `c37be36`, foi
autorizada localmente, sem push, somente a Etapa 5: protótipo e Admin UX v2
somente leitura, com estrutura visual, fluxos e decisões apresentados antes do
código. A Etapa 5 é estritamente
somente leitura: sem POST/PUT/DELETE novo, coleta de senha ou CRUD de
datasources; o limite pós-conexão da D-090 continua aberto e bloqueia a
ativação da v2 pelo operador (Etapa 7). Ela foi implementada (D-097–D-100) com
evidência em `docs/PHASE-9-STAGE-5-VALIDATION.md`; o refinamento visual (D-101,
D-102) e as capturas em `docs/ux-v2/` foram aprovados pelo usuário em 2026-09-28, e a
Etapa 5 foi publicada em `4d5b78f`. Na mesma data foi autorizada somente a Etapa 6:
CRUD visual de datasources e policies pelas nove escritas v2 já aprovadas, com
senha write-only, concorrência otimista, uma escrita pendente, rascunho volátil e
confirmação explícita; sem PGWire, bind externo, variável de ativação, MCP
multi-datasource ou definição do datasource default. O limite pós-conexão da D-090
continua aberto e impede ativar a v2 para operação real. A Etapa 6 foi implementada
localmente e **aprovada pelo usuário em 2026-09-30** (D-103–D-106, capturas e
fechamento; `docs/PHASE-9-STAGE-6-VALIDATION.md`), com a correção por Esc e os
testes de regressão; ela foi publicada em `5115a75`.

A Etapa 7 está **parcial**. Há quatro exceções estreitas, e só elas:

- a infraestrutura do verificador em processo filho (D-107), commitada em
  `e9eb01a`;
- o incremento de executor, barreira e leitura selada (D-108), autorizado
  pelas escolhas A1, B e C e validado conforme
  `docs/PHASE-9-STAGE-7-VALIDATION.md`, §1.4. O usuário aprovou o fechamento e
  autorizou a publicação em 2026-10-07;
- as peças puras do startup PGWire (D-109): framing, credencial, troca
  SCRAM-SHA-256/-PLUS e channel binding, em `src/maskgw/pgwire/`, com
  `scramp==1.4.17` e `asn1crypto==1.5.1` fixados. O usuário deu aval a
  SCRAM-SHA-256, -PLUS sobre TLS e SASLprep em 2026-10-08 e delegou as
  escolhas restantes. Implementadas localmente, sem commit, em revisão
  independente (§1.5 da mesma evidência). O pacote não é importado pelo
  composition root;
- a integração do listener PGWire (D-110), **autorizada explicitamente pelo
  usuário em 2026-10-09**: listener, TLS e autenticação **sem SQL**;
  configuração externa `MASKGW_PGWIRE_*`; admissão e shutdown seguros; testes
  só em loopback e em ambientes descartáveis; revisão antes de qualquer
  commit/push. **Sem** deploy, liberação de produção nem ativação operacional:
  no `main`, `MASKGW_PGWIRE_ENABLED=1` será recusado com erro fixo enquanto a
  ativação não for entregue. O runtime moderno é um gate separado: não
  recriar a `.venv` nem instalar Python no sistema. Em 2026-10-13 o usuário
  autorizou, de forma estreita, CPython 3.14.8 **temporário e isolado** (pacote
  oficial do nuget.org extraído fora do checkout, sem PATH, registro, launcher
  ou associações), só para validar o runtime. Os lotes A, B e C foram medidos
  (§1.6). O lote B deu 2 falhas, ambas nos casos NUL de um teste. O lote C
  corrigiu só esse teste, com autorização do usuário e revisão independente,
  e a nova suíte integral com PG16 ficou verde no Windows com CPython 3.14.8.
  Os 4 `union-attr` do mypy com o alvo 3.14 seguem abertos, e o lote C foi
  revisado. A execução é em lotes revisados: o
  lote 1 (`pgwire/settings.py` e `pgwire/tls.py`) e o lote 2
  (`pgwire/transport.py` e `pgwire/driver.py`) e o lote 3
  (`pgwire/listener.py`) e o lote 4 (composição INTERNA em
  `build_application(pgwire=...)`, `pgwire/composition.py`), revisados,
  estão implementados localmente, sem commit (§1.6). Os gates finais do lote
  4 foram medidos em 2026-10-12: suíte integral e `integration` com PG16 real,
  e wheel/sdist com a sonda, todos verdes. O `main`
  recusa `MASKGW_PGWIRE_ENABLED=1` (STARTUP_FAILURE) e não lê nenhum outro
  setting PGWire; não há caminho operacional que ligue o listener. Em
  2026-10-14 o usuário aprovou fechar esse trabalho validado (D-109/D-110 e
  a resolução limitada do bind) num **commit local**, sem push. As menções a
  "sem commit" acima descrevem o estado anterior a esse fechamento.

O estado de publicação desses commits é o que o Git confirmar (`git fetch` e
`git rev-list --left-right --count origin/master...HEAD`). O restante da
Etapa 7 — ativação operacional — não foi feito. Em 2026-10-14 o usuário
autorizou implementar a
resolução limitada do hostname do bind (opção B da D-110), em lotes revisados;
ela está implementada localmente, com medições finais no Windows (suíte com
PG16 e pacotes) no runtime legado e no runtime moderno temporário 3.14.8. A
ativação operacional segue bloqueada no `main`. O gate de runtime moderno foi medido só no
Windows com CPython 3.14.8 (lotes A–C) e não libera operação real.

A D-090 continua aberta no gate 2, e a v2 segue proibida em operação real.
Fora dessas quatro exceções, não iniciar listener PGWire, autenticação
SCRAM/TLS de produção, dependência ou variável de ambiente nova, bind externo,
extensão da tool MCP (MCP multi-datasource) nem qualquer etapa posterior
(Etapas 8–12).
Evidência: `docs/PHASE-8-STAGE-9-VALIDATION.md`.

Interfaces genéricas, editor SQL administrativo, resultados do banco na UI,
funções de DBA, auditoria consultável e front-end para MCP continuam fora do
escopo. Listener/bind PGWire, TLS de produção, ativação do catálogo por
ambiente e integração multi-datasource do MCP continuam pendentes. As rotas v2
da Etapa 4 e a Admin UX v2 das Etapas 5–6 já existem, somente na composição
interna autorizada e sem liberação para operação real. As rotas permanecem
delimitadas pela §8 da especificação.

## Matching
Por padrão: case-insensitive + substring/contains.

Regra `cpf` deve corresponder a `cpf`, `CPF`, `num_cpf`, `tipo_cpf`, `cliente_cpf`, `cpf_cliente` etc.

## Exceptions
Exceptions têm prioridade sobre masking.

Ordem:
EXCEPTION → MASKING RULE → ORIGINAL VALUE

## Segurança
- O cliente MCP/IA é não confiável.
- O dado original nunca pode chegar ao cliente sem passar pelo Masking Engine.
- Nunca registrar dados sensíveis em logs ou erros.
- Nunca permitir que a IA altere ou desative regras.
- Apenas SELECT no MVP.
- A conexão do Gateway deve ser read-only.

## Desenvolvimento
Antes de mudanças importantes: entender arquitetura, consultar docs, analisar segurança, implementar, testar e revisar.

Security > correctness > performance > convenience.
