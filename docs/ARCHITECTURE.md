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

A resolução acontece **antes** de qualquer linha ser lida.

**Falha de resolução não cai em default ALLOW.** Desde D-040, dois casos que
antes eram um só:

| situação | quem afirma | comportamento |
|---|---|---|
| `ftable = 0` (`DERIVED`) | o PostgreSQL: não há coluna de origem única | estado legítimo; matching recai sobre `output_name` e sobre a análise de AST |
| catálogo responde sem a linha (`UNKNOWN`) | a coluna não está no catálogo | matching recai sobre `output_name` |
| **consulta ao catálogo falha** | erro operacional nosso | **consulta REJEITADA** |

O terceiro caso é o que mudou. Havia proveniência que deveria ser resolvível, e
devolver o resultado assim entregaria em claro uma coluna que deveria estar
mascarada. O resolver levanta `CapabilityError`, que a fronteira MCP traduz em
`CONFIGURATION_ERROR` — sanitizado, sem nada da mensagem do PostgreSQL.

A falha **não** entra no cache: um erro transitório não desliga a proveniência
pelo resto da vida da conexão.

Ver D-021, D-023, D-025 (emendada) e D-040.

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
| `UNKNOWN` | o catálogo respondeu, mas não há linha para essa coluna |

`UNKNOWN` **não** cobre falha operacional de catálogo: essa rejeita a consulta
(D-040). Ver D-020.

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

Exceptions **não** seguem a mesma regra. Elas são avaliadas contra um só nome,
o **autoritativo** — `origin_name` quando existe, `output_name` apenas quando
não há origem determinável.

A assimetria é uma correção de segurança (D-042): o `output_name` é escolhido
pelo cliente, e deixar a exception casar por ele fazia de toda exception
configurada uma forma de desmascarar qualquer coluna (`SELECT cpf AS tipo_cpf`).
O alias pode adicionar proteção, nunca removê-la.

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
bootstrap/ composition root; constroi os planos e conduz startup/shutdown
runtime/   runtime imutavel, refcount, aposentadoria e fechamento unico
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

---

## Separação de planos (Fase 7 em implementação)

A composition root em `bootstrap/` já centraliza a construção e o lifecycle do
data plane MCP. O admin plane ainda não existe nesta etapa; quando for criado,
somente `bootstrap/` poderá conhecer os dois ao mesmo tempo. A separação abaixo
é uma decisão arquitetural aprovada e não pode ser atravessada por conveniência.

```text
Data plane:

AI Client
→ MCP
→ Gateway
→ PostgreSQL

Admin plane:

Administrator
→ Admin API
→ Administrative Configuration
→ Runtime Rebuild / Atomic Swap
```

Invariantes dos dois planos:

- **A Admin API não é caminho de execução SQL.** Não existirão endpoints como
  `/query`, `/sql` ou `/execute`. O Gateway/MCP continua sendo o único caminho
  de query (D-049).
- **O MCP não tem acesso administrativo.** Não há, e não haverá, superfície MCP
  para ler, alterar ou desabilitar configuração.
- **Os dois planos não compartilham handlers**, nem schemas de request/response.
  A Admin API é mais privilegiada; reaproveitar schema do MCP arrastaria o
  modelo de confiança errado.
- **Secrets nunca são expostos pela Admin API** — nem o valor, nem uma
  representação parcial, nem tamanho ou prefixo. Só estado (`configured` /
  `missing`).
- **A fonte administrativa persistida é o arquivo de configuração validado**,
  não os objetos runtime compilados (D-047).
- **Mudança de configuração reconstrói o runtime inteiro** e troca a referência
  de forma atômica. Uma query enxerga o runtime antigo inteiro ou o novo
  inteiro, nunca uma mistura (D-048).
- **Persistência e troca são atômicas separadamente, não em conjunto** (D-048).
  Não há atomicidade entre filesystem e memória: depois do `rename` o arquivo
  já é o novo, e a recuperação de um crash na janela entre persistir e trocar é
  o próximo start ler esse arquivo — que já foi validado, compilado, conectado
  e verificado antes de ser escrito.
- **Operações administrativas de escrita são serializadas** (D-052):
  `expected_revision`, nova revision, persistência e swap na mesma seção
  crítica administrativa.
- **O ciclo de vida dos runtimes é coordenado por refcount + `retired`**
  (D-054). O reload não bloqueia esperando queries antigas; nenhuma query
  adquire um runtime aposentado; o último release o fecha exatamente uma vez.
- **O DSN não é campo administrativo.** Credenciais, host e banco continuam
  vindo exclusivamente de secret/env.
- **Proteções estruturais de segurança não são editáveis** pela Admin API —
  `denied_relations` com `pg_stats`/`pg_statistic` é o exemplo (D-050).
