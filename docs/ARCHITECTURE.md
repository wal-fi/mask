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
- FastAPI + uvicorn (Fase 7, Etapa 7) — **exclusivamente** na fronteira HTTP
  administrativa. O MCP continua stdio only (D-036), e nenhuma porta é aberta
  sem `MASKGW_ADMIN_ENABLED=1`.

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
admin/     secao critica administrativa e fluxo de escrita/reload
admin/http/ fronteira HTTP administrativa, somente leitura; unico lugar com rede
bootstrap/ composition root; constroi os planos e conduz startup/shutdown
runtime/   runtime imutavel, refcount, aposentadoria e fechamento unico
sql/       parser, validator, politica de funcoes e analise de sensitividade
db/        adapter PostgreSQL: execucao, proveniencia, sanitizacao de erro
masking/   matcher, exceptions, registry, engine  <- nucleo PURO, sem I/O
config/    loader validado, imutavel; filesystem seguro da configuracao
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

A composition root em `bootstrap/` centraliza a construção e o lifecycle dos
dois planos. Desde a Etapa 6 o admin plane existe como **seção crítica**, sem
HTTP: ele conhece o `RuntimeRegistry` e o `ConfigFileStore`, e não conhece
`gateway/` nem `mcp/`. Somente `bootstrap/` conhece os dois ao mesmo tempo — e
isso é teste de AST. A separação abaixo é uma decisão arquitetural aprovada e
não pode ser atravessada por conveniência.

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

### Filesystem seguro da Etapa 5

`config/filesystem.py` é independente dos dois planos. `ConfigFileStore`
valida `masking.yaml`, diretório pai e sidecar antes de operar, mantém o lock
exclusivo aberto pelo próprio lifecycle, lê snapshots dos bytes exatos e
realiza a troca atômica no mesmo diretório. Ele não conhece HTTP, modelos de
request, `RuntimeRegistry` nem runtime candidato.

O componente separa explicitamente três resultados:

- antes de `os.replace`, a falha preserva o arquivo anterior;
- depois de `os.replace`, falha de `fsync` do diretório informa
  `ConfigDurabilityError(applied=True)` e o arquivo novo permanece;
- digest divergente em qualquer uma das duas verificações informa
  `CONFIG_OUT_OF_SYNC` e não sobrescreve a edição externa.

### Seção crítica administrativa (Etapa 6)

`admin/` compõe esses primitivos com o `RuntimeRegistry` e o carregador
validado. Três módulos, nenhum deles HTTP:

```text
admin/errors.py    AdminError e o conjunto FECHADO de categorias (§10.2)
admin/document.py  MaskingFileConfig <-> bytes YAML, com round-trip conferido
admin/service.py   AdminConfigService: o fluxo de onze passos da §7.4
```

`AdminConfigService.apply` executa, sob **um** lock por processo: verificação
do estado de adoção, de `expected_revision`, do digest em disco e do limite de
aposentados; aplicação da mudança e validação; compilação e construção do
runtime candidato; conexão com os três capability checks; persistência
atômica; swap; atualização do digest; e fechamento do aposentado. Os quatro
primeiros passos são **anteriores** a construir e conectar — nenhuma conexão é
aberta para uma operação já condenada.

O único ponto de extensão é uma **mutação** que recebe o documento persistido e
devolve o candidato. As operações granulares da Etapa 9 são açúcar sobre ela:
não existe caminho que altere o arquivo parcialmente. A `revision` é sempre
escolhida pelo servidor.

A mutação recebe uma **cópia profunda**, nunca o documento do runtime
publicado, e a leitura administrativa também devolve cópia. `frozen=True` do
Pydantic impede reatribuir um campo, mas não congela as listas e dicionários de
dentro; sem a cópia, uma mutação que falhasse deixaria o runtime publicado sem
regras e a escrita seguinte persistiria essa corrupção (D-055).

O documento candidato é o **reparseado dos bytes que serão persistidos**, e não
o modelo anterior à serialização: o runtime publicado é, literalmente, o que o
arquivo descreve.

O ponto de não-retorno é o `os.replace`. Antes dele, qualquer falha preserva o
arquivo byte a byte, mantém o mesmo objeto runtime publicado, mantém o digest
e fecha o candidato exatamente uma vez. Depois dele, uma falha de `fsync` do
diretório **não** afirma rollback: o candidato é publicado, o digest e a
revision são atualizados e a resposta é `CONFIG_DURABILITY_ERROR` com
`applied=True`.

Com o admin habilitado, `bootstrap/` adquire o `ConfigFileStore` antes de tudo
e o libera por último no shutdown, depois de fechar os runtimes. O runtime
inicial é construído dos **bytes do snapshot** lido sob o lock, para que o
digest de referência corresponda exatamente ao runtime publicado (D-055).

### Fronteira HTTP administrativa (Etapa 7)

`admin/http/` é a superfície HTTP, e é **somente leitura** nesta etapa. Ela vive
num subpacote separado de propósito: importar `maskgw.admin` continua **não**
carregando FastAPI, uvicorn nem starlette, e isso é teste com contraprova. A
seção crítica da Etapa 6 permanece utilizável — e testável — sem servidor.

```text
admin/http/settings.py    enable, token, bind e porta; o passo 1 do startup
admin/http/middleware.py  as camadas de fronteira, ASGI puro
admin/http/responses.py   forma única de erro e categoria -> status HTTP
admin/http/schemas.py     modelos de resposta, extra="forbid" e frozen=True
admin/http/views.py       respostas de leitura derivadas do modelo validado
admin/http/validate.py    config:validate: valida e compila, sem efeito (Etapa 8)
admin/http/app.py         leitura, config:validate e os handlers de erro
admin/http/server.py      uvicorn numa thread não-daemon, com bind confirmado
```

As oito rotas de leitura são `GET`/`HEAD` sob `/admin/v1`: `status`, `config`,
`rules`, `rules/{id}`, `exceptions`, `exceptions/{id}`, `transformers` e
`protected`. A Etapa 8 acrescentou **uma** rota com corpo,
`POST /admin/v1/config:validate` — que valida e compila um documento candidato
**sem efeito algum** (não conecta, não persiste, não altera revision, não entra
na seção crítica). O conjunto — oito leituras mais o `POST` — é comparado com a
lista literal da especificação por teste; rota nova quebra a suíte. `/docs`, `/redoc` e `/openapi.json` são desligados na
construção; `redirect_slashes` é desligado, então `/rules/` é `404` e nunca um
`307`; `OPTIONS` não é registrado e não há header CORS em resposta alguma.

**A ordem das camadas de fronteira** (D-056), de fora para dentro: `Host` fora
da allowlist `400`; `Origin`/`Referer` presentes `403`; `Content-Length` acima
de 1 MiB `413`; `Authorization: Bearer` ausente/errado `401`; `Content-Type`
diferente de `application/json` em método com corpo `415`; leitura contada do
corpo `413`; roteador. `Host` e `Origin` precedem a autenticação porque não
dependem do token; a autenticação precede o `Content-Type` e o roteador, que é
o que garante que **sem credencial válida nunca ocorre um `422`**.

O limite de corpo conta os bytes no `receive` cru, sem bufferizar: um envio
chunked de vários MiB é cortado em 1 MiB, e o chunk que estoura o limite não é
repassado adiante. Desde a Etapa 8 o corte é **autoritativo**: assim que o
limite é ultrapassado, o middleware responde o `413` no próprio `receive` e
devolve `http.disconnect` ao app interno, engolindo qualquer resposta que ele
ainda tente enviar. Sem isso, o roteador do FastAPI — a primeira rota com corpo é
`config:validate` — captura a exceção interna antes que ela volte ao middleware,
e o resultado seria um status do framework no lugar do `413` (D-058).

A camada mais externa é um middleware próprio, **por fora do Starlette**. Ela
põe `Cache-Control: no-store` e apaga qualquer header CORS em toda resposta —
inclusive o `404` do roteador e o `405` do Starlette —, e contém qualquer
exceção: sem isso, o `ServerErrorMiddleware` responde e **relevanta**, e o
uvicorn registraria o traceback com `exc_info` (D-056, mesmo trap de D-038).

`admin/` continua **não importando `logging`**: `AdminAudit` é a Etapa 10, e o
registro será feito por `audit/`. O uvicorn sobe com `log_config=None` e
`access_log=False`, então nenhum byte vai para `stdout` — que continua sendo
exclusivamente o canal do protocolo MCP.

**Cada resposta nasce de UMA leitura do runtime publicado** (D-057).
`AdminConfigService.snapshot()` devolve `revision`, documento e `SqlPolicy` do
mesmo runtime, e `adopted` sai da revision capturada; as funções de `views.py`
recebem esse `AdminSnapshot`, e não o serviço, de modo que não têm como fazer a
segunda leitura. Sem isso, um reload entre duas leituras devolveria o conteúdo
antigo carimbado com a revision nova — e, na Etapa 9, uma escrita baseada nesse
par passaria pelo `expected_revision` e sobrescreveria uma mudança que ninguém
viu. A cópia profunda acontece **fora** do lock do registry.

**O startup confirma o bind antes de o MCP existir.** O socket é criado e
vinculado na thread chamadora, e só então entregue ao uvicorn: porta ocupada
levanta sincronamente, e o processo não sobe. No shutdown, a thread HTTP recebe
`join` **antes** de os runtimes fecharem, e o lock de arquivo sai por último.

**E o `join` não tem timeout** (D-057). `Thread.join(timeout=...)` não
distingue sucesso de expiração, e expirado só há duas saídas, ambas ruins:
abandonar a thread ou devolver o controle com o shutdown pela metade, obrigando
cada chamador a lidar com esse meio-estado. `stop()` espera até a thread
terminar; quando retorna, ela acabou, e só então `_thread`, `_server` e
`_socket` são soltos. O que se limita é o trabalho, não a espera: o uvicorn
recebe `timeout_graceful_shutdown` e cancela sozinho requisições que se
arrastem, então a thread sempre chega ao fim.

A referência do servidor é **adotada antes de `start()`**: `_build_admin_http`
constrói sem iniciar. Assim, um `start()` que crie a thread e falhe depois
continua tendo dono, e o `except` de `build_application` chama `stop()` em vez
de fechar registry e lock com a thread viva.

`_closing` marca que o shutdown começou e nunca volta atrás: `run()` recusa a
aplicação a partir daí e `repr()` reporta `closing`, nunca `ready`.

`admin_enabled` e `admin_http` são parâmetros distintos do composition root: o
primeiro compõe a seção crítica, o segundo acrescenta a fronteira HTTP. O
segundo implica o primeiro, nunca o contrário.

As rotas de escrita e a adoção com backup são a Etapa 9; `AdminAudit` é a Etapa
10.
