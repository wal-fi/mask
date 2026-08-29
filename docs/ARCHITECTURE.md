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

### Query Validator
Parsing com pglast. Allowlist de nós: somente `SelectStmt` na raiz.
Bloqueia escrita, DDL e múltiplos statements.

### Database Adapter
Abstração de conexão. PostgreSQL é o primeiro e único adapter do MVP.
Responsável por: conexão read-only, `statement_timeout`, limite de linhas,
sanitização de erros e extração de metadados de coluna.

### Column Descriptor Resolver
Constrói, para cada coluna do result set, um descritor com os dois nomes
usados no matching.

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
  output_name    nome da coluna como retornada ao cliente (alias, se houver)
  origin_name    nome real da coluna de origem, quando determinável
  type_oid       tipo da coluna
```

`origin_name` é resolvido a partir dos metadados que o próprio PostgreSQL
devolve em `RowDescription` (`table_oid` + `table_column`), cruzados com
`pg_attribute`.

**Correção medida na Fase 2:** o `Column` de `cursor.description` **não** expõe
`table_oid` nem `table_column` (verificado em psycopg 3.3.4 — os atributos
disponíveis são `name`, `type_code`, `display_size`, `internal_size`,
`precision`, `scale` e `null_ok`). Os dois campos existem, porém no resultado
de baixo nível: `cursor.pgresult.ftable(i)` e `cursor.pgresult.ftablecol(i)`.
O resolver da Fase 3 deve ler de lá.

Para expressões (`md5(cpf)`, `cpf::text`, `substr(cpf,1,3)`) o PostgreSQL
devolve `table_oid = 0`: não há origem determinável e `origin_name` fica
`None`. Nesse caso o matching usa apenas `output_name`.

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
mcp/       adapter de I/O, sem logica de seguranca
gateway/   orquestrador; unica camada que toca valor original
sql/       parser e validator (allowlist de SELECT)
db/        adapter PostgreSQL: execucao, metadados, sanitizacao de erro
masking/   matcher, exceptions, registry, engine  <- nucleo PURO, sem I/O
config/    loader validado, imutavel, carregado uma vez no boot
audit/     log estruturado, somente metadata
```

`masking/` não depende de rede, banco ou MCP e deve ser testável isoladamente.
`gateway/` é a única fronteira onde o valor original existe.

## Princípios

- O valor original permanece dentro do Gateway e não pode ser incluído na
  resposta MCP antes da transformação.
- Manter o Masking Engine independente do MCP e do database adapter.
- Evitar acoplamento entre regras, matching e transformers.
- Configuração inválida impede a inicialização do processo (fail-closed).
