# AI Data Masking Gateway

Você é o principal engenheiro responsável por desenvolver este projeto.

Gateway MCP entre uma IA e um banco de dados PostgreSQL.

```text
IA → MCP → Gateway → SQL Validator → PostgreSQL → provenance
   → Masking Engine → row limit → resposta segura → MCP → IA
```

## Estado: MVP completo

**As seis fases do roadmap estão concluídas**, mais a Fase 6.1 de hardening.
O produto executa fim a fim: um cliente MCP real consulta um PostgreSQL real e
recebe dados mascarados.

Não há trabalho em andamento. Antes de iniciar qualquer coisa, leia
`docs/HANDOFF.md` — é o documento de entrada e diz exatamente onde o projeto
parou e quais são as opções seguintes.

## Leitura obrigatória antes de alterar código

Nesta ordem:

1. `docs/HANDOFF.md` — estado atual, como rodar, próximos passos
2. `docs/ARCHITECTURE.md` — módulos e responsabilidades
3. `docs/SECURITY.md` — invariantes de segurança
4. `docs/SECURITY-REVIEW.md` — o que foi atacado, o que resistiu, o que não
5. `docs/DECISIONS.md` — 46 decisões (D-001 a D-046) e o porquê de cada uma
6. `docs/MASKING-SPEC.md` — semântica exata do pipeline de masking
7. `docs/TEST-PLAN.md`, `docs/THREAT-MODEL.md`, `docs/FUTURE-HARDENING.md`

`docs/ROADMAP.md` é histórico: as seis fases estão fechadas.

## Objetivo

Permitir que IAs consultem bancos de dados sem expor dados sensíveis.

É um **Data Masking Gateway simples**, não uma plataforma de DLP nem de data
access governance. Essa distinção já rejeitou várias propostas; mantenha-a.

## Stack

Python ≥ 3.11 · psycopg3 · pglast · MCP SDK v2 · Pydantic · PyYAML · pytest.
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

## Fora do escopo

Front-end, Admin API, OAuth/RBAC, multi-tenant, deployment, HTTP MCP, pool de
conexões, MySQL, migrations, schema browser, JSONB deep inspection, lineage
completo de view, controle de inferência (WHERE/ORDER BY/GROUP BY), supressão
de agregações, transformers Python customizados, default deny.

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
