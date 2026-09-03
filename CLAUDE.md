# AI Data Masking Gateway

Você é o principal engenheiro responsável por desenvolver este projeto.

Gateway MCP entre uma IA e um banco de dados PostgreSQL.

```text
IA → MCP → Gateway → SQL Validator → PostgreSQL → provenance
   → Masking Engine → row limit → resposta segura → MCP → IA
```

## Estado: MVP completo + Fase 7 em andamento

**As seis fases do roadmap estão concluídas**, mais a Fase 6.1 de hardening.
O produto executa fim a fim: um cliente MCP real consulta um PostgreSQL real e
recebe dados mascarados.

A Fase 7 foi iniciada de forma incremental. As **Etapas 1–8 estão concluídas**;
a próxima tarefa é exclusivamente a Etapa 9 — rotas de escrita e adoção com
backup —, ainda não iniciada. Antes de alterar qualquer coisa, leia `docs/HANDOFF.md` — é
o documento de entrada e diz exatamente onde o projeto parou.

## Leitura obrigatória antes de alterar código

Nesta ordem:

1. `docs/HANDOFF.md` — estado atual, como rodar, próximos passos
2. `docs/ARCHITECTURE.md` — módulos e responsabilidades
3. `docs/SECURITY.md` — invariantes de segurança
4. `docs/SECURITY-REVIEW.md` — o que foi atacado, o que resistiu, o que não
5. `docs/DECISIONS.md` — 58 decisões (D-001 a D-058) e o porquê de cada uma
6. `docs/MASKING-SPEC.md` — semântica exata do pipeline de masking
7. `docs/TEST-PLAN.md`, `docs/THREAT-MODEL.md`, `docs/FUTURE-HARDENING.md`

`docs/ROADMAP.md` preserva o histórico das seis fases fechadas e registra o
andamento atual da Fase 7.

## Objetivo

Permitir que IAs consultem bancos de dados sem expor dados sensíveis.

É um **Data Masking Gateway simples**, não uma plataforma de DLP nem de data
access governance. Essa distinção já rejeitou várias propostas; mantenha-a.

## Stack

Python ≥ 3.11 · psycopg3 · pglast · MCP SDK v2 · Pydantic · PyYAML · pytest.
FastAPI + uvicorn desde a Fase 7 / Etapa 7, **só** na fronteira HTTP
administrativa: o MCP continua stdio only (D-036).
Versões testadas em `docs/HANDOFF.md`.

## Pipeline de masking

Por coluna do result set, nesta ordem:

```text
DERIVED (a AST provou dependência sensível)  → TRANSFORMER
EXCEPTION (pelo nome AUTORITATIVO)           → ORIGINAL
MASKING (por output_name OU origin_name)     → TRANSFORMER
NO MATCH                                     → ORIGINAL
```

Default **ALLOW**: coluna sem correspondência passa em claro. Não mudar para
default deny sem aprovação explícita.

### Matching

Case-insensitive. `contains` é o default das **regras**; `exact` é o default
das **exceptions** (D-045). A regra `cpf` casa `cpf`, `CPF`, `num_cpf`,
`cliente_cpf`, `nr_cpf`.

O masking avalia `output_name` **e** `origin_name` — basta um casar. É o que
neutraliza `SELECT cpf AS documento`.

### Exceptions — leia com atenção

Exceptions são avaliadas contra **um só** nome, o autoritativo: `origin_name`
quando existe, `output_name` apenas quando não há origem determinável.

A assimetria em relação ao masking é deliberada e é uma correção de segurança
(D-042). O `output_name` é escolhido pelo cliente: se a exception casasse por
ele, toda exception configurada seria uma forma de desmascarar qualquer coluna
(`SELECT cpf AS tipo_cpf`). **O alias pode adicionar proteção, nunca removê-la.**

### Origem e sensibilidade derivada

`origin_name` vem da metadata do PostgreSQL (`ftable`/`ftablecol` cruzados com
o catálogo), nunca dos valores das linhas.

Quando o PostgreSQL não informa origem — expressões, agregados, UNION — a
análise de AST (`sql/sensitivity.py`) identifica de quais colunas a expressão
depende e aplica a regra delas ao **resultado**. Ambiguidade entre duas regras
diferentes, ou serialização de linha inteira (`row_to_json`), **recusa** a
consulta em vez de escolher (D-043, D-044).

## Segurança — invariantes

- O cliente MCP/IA é **não confiável**.
- Dado original nunca chega ao cliente sem passar pelo Masking Engine.
- Nunca registrar valores, SQL ou segredos em log, erro ou traceback.
- O cliente não pode ler, alterar ou desabilitar regras — não existe superfície
  para isso.
- Somente SELECT, um statement executável, conexão read-only, `statement_timeout`
  e `max_rows` — todos aplicados **pelo PostgreSQL** e conferidos após conectar.
- Configuração inválida ou capacidade essencial ausente impedem a inicialização.
- Erros do PostgreSQL sanitizados; nem `__cause__` nem `__context__` podem
  apontar para a exceção original (D-017 — este trap já foi introduzido duas
  vezes e pego por teste nas duas).
- A chave HMAC vem de env, nunca do `masking.yaml`, nunca do cliente.
- `audit/` é o **único** módulo autorizado a importar `logging`, e registra só
  metadata. `masking/` continua proibido.

### Antes de expor o Gateway

`REVOKE EXECUTE ON ALL FUNCTIONS ... FROM PUBLIC` para a role do Gateway. Não é
default do PostgreSQL e é a única mitigação do finding F-04. Detalhes e demais
riscos aceitos em `docs/SECURITY-REVIEW.md`.

## Evolução em andamento — Fase 7 / Admin API

A **Fase 7 — Admin API** está em implementação incremental conforme
`docs/PHASE-7-SPEC.md`. As Etapas 1–8 estão concluídas:

- Etapa 1 — IDs e revision no modelo do arquivo: `053cf66`;
- Etapa 2 — `RuntimeRegistry`: `3114c14`;
- Etapa 3 — aquisição/liberação de runtime por query: `3c8de4c`;
- Etapa 4 — composition root e lifecycle: `7c06132`;
- Etapa 5 — filesystem seguro: `d651fe0`;
- Etapa 6 — seção crítica administrativa e escrita/reload;
- Etapa 7 — fronteira HTTP e rotas de leitura;
- Etapa 8 — `POST /admin/v1/config:validate`, validação sem efeito.

Confira a sincronização com `origin/master` pelo Git em vez de inferi-la deste
documento. A Etapa 4 criou `maskgw/bootstrap/` como composition root, removeu
`gateway/factory.py` e centralizou startup/shutdown. Os entrypoints
`python -m maskgw` e `python -m maskgw.mcp` delegam ao bootstrap e preservam o
transporte MCP stdio.

A Etapa 5 criou `maskgw/config/filesystem.py`, independente de HTTP: valida
arquivo/diretório/lock, mantém o sidecar `masking.yaml.lock`, calcula digest
dos bytes exatos, limpa somente temporários de nome estrito e escreve por
temporário + `fsync` + `os.replace`. Falhas antes do replace preservam o arquivo
anterior; falha de `fsync` do diretório depois dele informa `applied=True`.

A Etapa 6 criou `maskgw/admin/` — `errors.py`, `document.py` e `service.py` —
também sem HTTP. `AdminConfigService.apply` executa os onze passos da §7.4 sob
**um** lock por processo: adoção, `expected_revision`, digest, limite de
aposentados, validação, compilação, conexão com os capability checks,
persistência atômica, swap, digest novo e fechamento do aposentado. Os quatro
primeiros passos precedem construir ou conectar qualquer candidato.

A Etapa 7 criou `maskgw/admin/http/` — a **primeira porta de rede do projeto**,
opcional e desligada por default. Oito rotas `GET`/`HEAD` sob `/admin/v1`:
`status`, `config`, `rules`, `rules/{id}`, `exceptions`, `exceptions/{id}`,
`transformers` e `protected`. **Nenhuma escrita.** FastAPI e uvicorn entraram na
stack, e são usados só ali: `maskgw.admin` continua importável sem carregar
FastAPI, e isso é teste com contraprova.

A Etapa 8 acrescentou **uma** rota com corpo, `POST /admin/v1/config:validate`,
que **não é uma escrita**: valida o schema, compila os transformers e a policy,
e descarta o resultado. Não conecta ao PostgreSQL, não persiste, não altera
`revision`, não entra na seção crítica e não incrementa contador — a ausência de
efeito é propriedade da assinatura de `validate_candidate`, provada por
contadores estruturais. O request é o documento candidato na raiz, com schema
HTTP próprio; `expected_revision` no corpo dá `422 SCHEMA_INVALID`. A resposta de
sucesso são quatro booleanos; falha de compilação é `422 CONFIG_INVALID` (D-058).
O conjunto literal de rotas passou a ser oito leituras mais um `POST`.

O admin passa a ser habilitado por `MASKGW_ADMIN_ENABLED=1` (qualquer outro
valor **não** habilita), com `MASKGW_ADMIN_TOKEN` (≥ 32 caracteres),
`MASKGW_ADMIN_BIND` (só `127.0.0.1`, `::1`, `localhost`) e `MASKGW_ADMIN_PORT`
(default `8765`). `build_application` tem dois parâmetros distintos:
`admin_enabled` compõe a seção crítica, `admin_http` acrescenta a fronteira
HTTP — e o segundo implica o primeiro, nunca o contrário.

Invariantes da fronteira, todos com teste:

- **token só em `Authorization: Bearer`**, comparado com `hmac.compare_digest`;
  query string e cookie nunca são aceitos; ausente, malformado e errado dão o
  mesmo `401`; **sem credencial válida nunca ocorre um `422`**;
- **`Origin`/`Referer` presentes → `403`** (pela presença, não pelo valor);
  **`Host` fora da allowlist → `400`**; **`Content-Type` ≠ JSON em método com
  corpo → `415`**; **corpo > 1 MiB → `413`**, cortando streaming sem bufferizar
  e de forma **autoritativa** — a Etapa 8 corrigiu o `BodyLimitMiddleware` para
  responder o `413` no próprio `receive`, porque o roteador do FastAPI captura a
  exceção interna antes que ela volte ao middleware (D-058);
- **`Cache-Control: no-store` em toda resposta** e **nenhum header CORS**;
  `OPTIONS` não registrado, `redirect_slashes` desligado, `/docs`, `/redoc` e
  `/openapi.json` desligados;
- **erro sempre da mesma forma**, categoria fechada e texto fixo, sem
  `str(exc)`, traceback, `input` rejeitado ou cadeia de exceção;
- **`stdout` continua exclusivo do MCP**: uvicorn sem handlers e sem access log,
  `admin/` sem `logging` e sem `print`;
- **startup confirma o bind antes de liberar o MCP**; shutdown faz `join` da
  thread HTTP **antes** de fechar runtimes, e libera o lock por último. Esse
  `join` **não tem timeout** — `stop()` só retorna com a thread terminada —, e o
  que se limita é o trabalho, via `timeout_graceful_shutdown` do uvicorn. A
  referência do servidor é adotada **antes** de `start()`, e `_closing` é
  permanente: `run()` recusa e `repr()` nunca diz `ready` depois do início do
  shutdown (D-057);
- **uma resposta administrativa nasce de UMA leitura do runtime publicado**
  (D-057): `snapshot()` devolve revision, documento e política juntos, e as
  funções de `views.py` recebem esse snapshot em vez do serviço — não misturam
  porque não têm como fazer a segunda leitura.

A próxima tarefa é a **Etapa 9**, ainda não iniciada: rotas de escrita e adoção
com backup. `AdminAudit` é a Etapa 10; a suíte adversarial HTTP é a Etapa 11. Não
antecipe as Etapas 9–11.

Dois pontos que valem como invariante:

- **`allowed_pg_functions` é somente leitura na Admin API.** O campo pode
  liberar `pg_read_file`, e administrá-lo por HTTP reabriria leitura de
  arquivos do servidor (D-050). O loader **não muda** nesta fase.
- **Bind administrativo só em loopback.** Sem TLS, interface externa põe o
  bearer token em HTTP claro. Não há variável de escape, e bind externo faz o
  processo recusar o startup. Bind externo é Fase 9.

Invariantes já decididos (D-047 a D-054) — não os reabra:

- **MCP nunca altera configuração.**
- **Admin API nunca executa SQL.** Não haverá `/query`, `/sql` ou `/execute`;
  o Gateway/MCP continua sendo o único caminho de query.
- **Admin API e MCP são planos separados**: sem handler e sem schema
  compartilhado.
- **Secrets nunca são retornados**, nem parcialmente mascarados.
- **A configuração administrativa persistida é o arquivo validado**, distinta
  dos objetos runtime compilados — a compilação descarta informação.
- **Mudanças constroem runtime novo por inteiro**; runtime nunca é alterado
  parcialmente. A query vê o antigo inteiro ou o novo inteiro.
- **Proteções estruturais de segurança não podem ser desligadas pela Admin
  API** — `denied_relations` com `pg_stats` é o caso concreto.
- **Não há atomicidade conjunta entre filesystem e memória** (D-048). Depois do
  `rename` o arquivo já é o novo, e não há rollback de arquivo. Existe uma
  janela de crash entre persistir e trocar; a recuperação é o próximo start
  ler o arquivo novo, que já foi validado e comprovado conectável.
- **Operações administrativas de escrita/reload são serializadas** (D-052):
  `expected_revision`, nova revision, persistência e swap na mesma seção
  crítica. Duas requisições com o mesmo `expected_revision` não vencem ambas.
- **O DSN nunca é campo administrativo** — credenciais, host e banco continuam
  vindo só de secret/env.
- **Ciclo de vida do runtime por refcount + `retired`** (D-054): o reload não
  espera queries antigas, o último release fecha o runtime aposentado
  exatamente uma vez, e nenhuma query adquire um runtime já aposentado.

D-055 registra o que a Etapa 6 decidiu e a especificação não fixava: o runtime
candidato é construído a partir do documento **reparseado dos bytes que serão
persistidos**, de modo que o digest de referência corresponda ao runtime
publicado por construção; o callback de mutação e a leitura administrativa
recebem **cópia profunda**, nunca o documento do runtime publicado, porque
`frozen=True` do Pydantic não congela as listas e dicionários de dentro; e o
plano administrativo traduz toda falha para o **seu** conjunto fechado de
categorias, sem reexportar exceção interna.

D-056 registra o que a Etapa 7 decidiu e a especificação não fixava: quatro
categorias de erro novas para as recusas de fronteira, cujos status a §3.3 fixa
mas cujos nomes a §10.2 não fornecia; a ordem entre as camadas de middleware; a
contenção da exceção **por fora** do Starlette, porque o `ServerErrorMiddleware`
responde e **relevanta**, e o uvicorn registraria o traceback; o `bind` na
thread chamadora, para que porta ocupada falhe sincronamente; a declaração dos
parâmetros de transformer no registry, confrontada com os builders por teste; e
os contadores de `/status` derivados de metadata já existente. A revisão da
Etapa 7 aprovou D-056 como decisão de contrato, incluindo as cinco categorias
novas e a ordem dos middlewares.

D-057 registra as duas correções exigidas nessa mesma revisão: o **snapshot
administrativo coerente**, porque revision e conteúdo lidos separadamente
permitiam devolver o runtime antigo rotulado com a revision nova — e, na Etapa
9, uma escrita com essa `expected_revision` sobrescreveria em silêncio uma
mudança que ninguém viu; e o **shutdown sem timeout**, porque
`Thread.join(timeout=...)` não distingue sucesso de expiração: a thread HTTP era
abandonada enquanto o processo seguia fechando runtimes e soltando o lock, e
conferir `is_alive()` apenas trocaria o abandono por um retorno parcial que todo
chamador teria de saber interpretar.

D-058 registra o contrato de `config:validate` (Etapa 8) que a especificação não
fixava: o request é o documento candidato na raiz com schema HTTP próprio (não
compartilhado com o MCP, distinto de `config/models.py`); `expected_revision`
recusado por `extra="forbid"`; a resposta de sucesso são quatro booleanos, sem
identidade de configuração; falha de compilação vira `CONFIG_INVALID` e falha
inesperada `INTERNAL_ERROR`, sempre sanitizados. E registra a correção de
fronteira que a primeira rota com corpo exigiu: o `BodyLimitMiddleware` passou a
cortar em `413` **autoritativamente** no `receive`, porque o roteador do FastAPI
lê o corpo dentro de `wrap_app_handling_exceptions` e capturava a exceção interna
antes que ela voltasse ao middleware, produzindo um status do framework no lugar
do `413`.

## Fora do escopo

Front-end, OAuth/RBAC, multi-tenant, deployment, HTTP MCP, pool de conexões,
MySQL, migrations, schema browser, JSONB deep inspection, lineage completo de
view, controle de inferência (WHERE/ORDER BY/GROUP BY), supressão de
agregações, transformers Python customizados, default deny.

As Etapas 8–11 da Admin API não fazem parte do fechamento atual.

Propostas avaliadas e adiadas estão em `docs/FUTURE-HARDENING.md` com custo e
impacto — consulte antes de propor de novo.

## Desenvolvimento

Antes de mudanças importantes: entender arquitetura, consultar docs, analisar
segurança, implementar, testar e revisar.

Regras que valeram nas seis fases e continuam valendo:

- **Medir antes de decidir.** Várias suposições dos documentos estavam erradas
  sobre o comportamento real do PostgreSQL e do psycopg. Onde há dúvida, existe
  um teste de medição (`test_pgresult_metadata.py`, `test_sql_parser.py`).
- **Bypass conhecido vira teste que o afirma, nunca `skip`** (D-041). Quando
  uma correção o fecha, o teste quebra e a mudança é notada.
- Não avançar de fase sem aprovação, nem com teste falhando.
- Toda decisão não trivial vai para `docs/DECISIONS.md` com o motivo.

Security > correctness > performance > convenience.
