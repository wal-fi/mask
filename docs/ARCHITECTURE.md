# Architecture

## Objetivo

Criar uma camada independente entre clientes MCP e bancos de dados.

Escopo: um **Data Masking Gateway simples**, não uma plataforma de DLP ou de
data access governance. Ver `docs/FUTURE-HARDENING.md` para o que ficou fora.

## Stack aprovada

- Python
- psycopg3 (driver PostgreSQL)
- pglast (parser oficial do PostgreSQL via libpg_query)
- Pydantic (validação de configuração)
- YAML (formato de configuração)
- pytest (testes)

## Fluxo

```text
AI Client
   |
   | MCP
   v
MCP Server
   |
   v
Database Gateway
   |
   +--> Query Validator        (somente SELECT)
   |
   +--> Database Adapter       (read-only, timeout, row limit)
   |
   v
Database
   |
   v
Result Set + Column Metadata
   |
   v
Masking Engine
   |
   v
MCP Response
   |
   v
AI Client
```

## Componentes

### MCP Server
Interface para Claude, ChatGPT, Cursor e outros clientes MCP.
Apenas entrada/saída. Nenhuma regra de masking nos handlers.

SDK oficial `mcp` v2 (`from mcp.server import MCPServer`). Transporte **stdio
apenas** — nenhuma porta de rede é aberta (D-036).

Uma única tool, `query_database(sql: str)`, com structured output tipado. Sem
`resources`, sem `prompts`. O cliente controla exclusivamente a SQL: não existe
parâmetro para desabilitar masking, escolher transformer, alterar limites ou
informar credenciais.

### Gateway
Fachada pública. Orquestra validação, execução, provenance, masking e limites,
e traduz o resultado interno para o modelo seguro. É a única camada que a
interface MCP conhece — handlers nunca falam com `PostgresAdapter`.

Levanta apenas `GatewayError`, com uma de cinco categorias externas.

### Audit
Log estruturado, somente metadata: `request_id`, desfecho, duração, contagem de
linhas, `truncated` e categoria de erro. Único módulo do projeto autorizado a
importar `logging`. Nunca a SQL, nunca valores (D-035).

### Query Validator
Parsing com pglast (`sql/`). Allowlist de nós, nunca blocklist de texto.

Quatro regras: um statement executável; raiz `SelectStmt`; nenhum outro nó
`*Stmt` em ponto algum da árvore (cobre CTE modificadora, aninhada ou dentro de
subquery); e `IntoClause`/`LockingClause` recusadas — porque `SELECT 1 INTO t`
parseia como `SelectStmt` e **cria uma tabela**.

Política de funções separada (`sql/policy.py`): namespace `pg_` negado por
default com allowlist curta, demais funções permitidas com denylist de famílias
perigosas. Extensível por configuração. Ver D-027 e o limite declarado em
`docs/SECURITY.md`.

Independente de MCP e de banco: recebe texto, devolve árvore validada ou
levanta.

### Sensitivity Analyzer
`sql/sensitivity.py` (Fase 6.1). Determina, por posição do result set, qual
regra de masking cobre as colunas de que a expressão depende — o que a
proveniência do PostgreSQL não alcança para expressões, agregados e UNION.

Complementa a proveniência, nunca a enfraquece: só acrescenta sensibilidade, e
só é aplicada quando as posições batem com o result set. Roda uma vez por
consulta, jamais por linha. Ver D-043.

### Database Adapter
Abstração de conexão. PostgreSQL é o primeiro e único adapter do MVP.
Responsável por: conexão read-only, `statement_timeout`, limite de linhas,
sanitização de erros e extração de metadados de coluna.

Duas portas, deliberadamente distintas (D-029):

- `execute_validated(sql)` — valida e só então executa. É o que um Gateway ou
  servidor MCP deve chamar.
- `execute(sql, params)` — **não** valida. Porta interna, mantida para que os
  testes possam contornar o validator e provar que o PostgreSQL barra a escrita
  sozinho.

### Column Descriptor Resolver
Constrói, para cada coluna do result set, um descritor com os dois nomes
usados no matching.

Implementado em `db/provenance.py` (Fase 3). Lê `ftable`/`ftablecol` do
resultado de baixo nível, traduz `(oid, attnum)` via `pg_attribute`,
`pg_class` e `pg_namespace`, e mantém um cache `(oid, attnum)` por conexão.
Resolve uma vez por **coluna**, nunca por linha ou célula.

A resolução acontece **antes** de qualquer linha ser lida, e falha de forma
segura: sem catálogo, a coluna fica `UNKNOWN` e o matching recai sobre
`output_name`. Ver D-021, D-023 e D-025.

### Masking Engine
Núcleo puro. Sem I/O, sem dependência de MCP ou de banco.
Recebe descritores de coluna e valores; devolve valores transformados.

### Rule Matcher
Matching global por nome. Default: case-insensitive + contains.

### Transformer Registry
Registry extensível de transformadores.

## Column Descriptor

O Masking Engine não opera sobre uma string solta de nome de coluna. Ele
recebe um descritor:

```text
ColumnDescriptor
  output_name         nome da coluna como retornada ao cliente (alias, se houver)
  origin_name         nome real da coluna de origem, quando determinável
  origin_schema       schema da relação de origem
  origin_table        relação de origem (tabela ou view)
  provenance_kind     DIRECT | VIEW | DERIVED | UNKNOWN
  derived_rule_index  regra provada pela análise de AST, quando houver
```

`origin_schema` e `origin_table` são **metadata de auditoria**: o matching não
os usa. As regras continuam globais por nome de coluna. Ver D-024.

`derived_rule_index` carrega a regra que a análise de AST provou cobrir a
posição, quando a proveniência não alcança. É metadata **interna**: nunca sai
para o cliente MCP.

`provenance_kind` distingue a afirmação do PostgreSQL da nossa ignorância:

| valor | significado |
|---|---|
| `DIRECT` | coluna de tabela; origem resolvida |
| `VIEW` | coluna de view ou materialized view; a origem é a coluna **da view** |
| `DERIVED` | o PostgreSQL informa `ftable = 0`: não há coluna de origem única |
| `UNKNOWN` | há origem, mas não foi possível traduzi-la |

Ver D-020.

`origin_name` é resolvido a partir dos metadados que o próprio PostgreSQL
devolve em `RowDescription` (`table_oid` + `table_column`), cruzados com
`pg_attribute`.

**Correção medida na Fase 2:** o `Column` de `cursor.description` **não** expõe
`table_oid` nem `table_column` (verificado em psycopg 3.3.4 — os atributos
disponíveis são `name`, `type_code`, `display_size`, `internal_size`,
`precision`, `scale` e `null_ok`). Os dois campos existem, porém no resultado
de baixo nível: `cursor.pgresult.ftable(i)` e `cursor.pgresult.ftablecol(i)`.
O resolver da Fase 3 deve ler de lá.

Para expressões (`md5(cpf)`, `substr(cpf,1,3)`) e literais o PostgreSQL
devolve `ftable = 0`: não há origem determinável e `origin_name` fica `None`.
Nesse caso o matching usa apenas `output_name`.

Medido na Fase 3, contra PostgreSQL 16 (`tests/test_pgresult_metadata.py`):

| cenário | origem resolvida? |
|---|---|
| coluna direta, alias, `SELECT *`, JOIN | sim |
| subquery, alias dentro de subquery, CTE | sim |
| cast (`cpf::text`) | sim |
| view | sim, mas aponta para a coluna **da view** |
| UNION | **não** (`ftable = 0`) |
| expressão, literal, agregado | não (`ftable = 0`) |

Note que `cpf::text` **preserva** a origem — um cast para o mesmo tipo não cria
expressão. O contrário do que `docs/THREAT-MODEL.md` supunha.

## Matching por dois nomes

A regra é aplicada se **qualquer um** dos nomes corresponder:

```text
match(rule, output_name) OR match(rule, origin_name)
```

Isso neutraliza o bypass por alias sem abandonar o modelo global por nomes:

```sql
SELECT cpf AS documento FROM cliente
```

- `output_name` = `documento` → não casa
- `origin_name` = `cpf` → casa
- resultado: **mascarado**

Exceptions são avaliadas contra os mesmos dois nomes e mantêm prioridade
absoluta: basta um deles casar uma exception para o valor passar original.

## Pipeline do Masking Engine

```text
ColumnDescriptor + valor
   |
   v
Exception Matcher  --casou--> ORIGINAL
   |
   nao casou
   v
Masking Matcher    --casou--> Transformer --> MASKED
   |
   nao casou
   v
ORIGINAL
```

Comportamento default: **ALLOW**. Coluna que não corresponde a nenhuma regra
passa normalmente. Não há default deny neste MVP.

## Módulos

```text
mcp/       adapter de I/O, sem logica de seguranca; stdio apenas
gateway/   orquestrador e fachada publica; unica camada que toca valor original
sql/       parser, validator, politica de funcoes e analise de sensitividade
db/        adapter PostgreSQL: execucao, proveniencia, sanitizacao de erro
masking/   matcher, exceptions, registry, engine  <- nucleo PURO, sem I/O
config/    loader validado, imutavel, carregado uma vez no boot
audit/     log estruturado, somente metadata; unico modulo que loga
```

`masking/` não depende de rede, banco ou MCP e deve ser testável isoladamente.
`gateway/` é a única fronteira onde o valor original existe.

O que **nunca** atravessa a fronteira para o cliente MCP: psycopg, cursor, DSN,
`MaskingEngine`, regras, segredos, validator interno, conexão PostgreSQL,
provenance (`origin_*`, `table_oid`, `attnum`), nomes de transformer,
tracebacks e mensagens do PostgreSQL.

## Princípios

- O valor original permanece dentro do Gateway e não pode ser incluído na
  resposta MCP antes da transformação.
- Manter o Masking Engine independente do MCP e do database adapter.
- Evitar acoplamento entre regras, matching e transformers.
- Configuração inválida impede a inicialização do processo (fail-closed).
- Uma capacidade essencial ausente também impede a inicialização: sem
  resolução de proveniência, a proteção contra alias estaria desligada em
  silêncio (D-026).
