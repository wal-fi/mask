# Decisions

Decisoes tomadas durante a implementacao que nao estavam especificadas nos
documentos. Criterio aplicado: a alternativa mais simples e segura compativel
com `CLAUDE.md` e `docs/`.

---

## D-001 — Layout de pacotes: `src/maskgw/`

O repositorio ja usa `config/` na raiz para o `masking.yaml`. Um pacote Python
`config/` na raiz colidiria com esse diretorio de dados.

Decisao: codigo em `src/maskgw/`, com os modulos de `docs/ARCHITECTURE.md`
como subpacotes (`maskgw.config`, `maskgw.masking`, e futuramente `maskgw.db`,
`maskgw.sql`, `maskgw.mcp`, `maskgw.gateway`, `maskgw.audit`).

Sem instalacao editavel: `pythonpath = ["src"]` no pytest.

## D-002 — Nome da variavel de ambiente da chave HMAC

`MASKGW_HMAC_KEY`. Nome fixo no codigo, nao configuravel pelo YAML — um
parametro do tipo `key_env` permitiria ao autor da configuracao apontar para
outra variavel, ampliando a superficie sem beneficio.

## D-003 — `regex` sem correspondencia devolve `[REDACTED]`

`re.sub` devolve o texto original quando o padrao nao casa. Isso seria um
vazamento silencioso: um e-mail fora do formato esperado sairia em claro.

Decisao: `count == 0` produz `[REDACTED]`. Falhar redigido, nunca em claro.
Vale tambem para erro inesperado de substituicao.

## D-004 — Conflito entre regras: vence a primeira do arquivo

Quando mais de uma regra de masking casa a mesma coluna, aplica-se a que
aparece primeiro no `masking.yaml`. Ordem explicita e previsivel, sem
heuristica de especificidade.

Exceptions continuam com prioridade absoluta sobre qualquer regra,
independentemente da posicao no arquivo.

## D-005 — `random` usa `secrets`, nao `random`

Gerador criptografico, sem estado global previsivel e sem semente que possa ser
inferida a partir de saidas anteriores.

## D-006 — Chave HMAC: minimo 32 caracteres

Segredo curto derrota o proposito do HMAC. Chave ausente, vazia, so com
espacos ou menor que 32 caracteres impede a inicializacao.

Espacos nas bordas sao removidos antes da validacao — evita o erro comum de
variavel de ambiente com quebra de linha.

## D-007 — `hmac_sha256` nao aceita nenhum parametro

Qualquer `config` em uma regra `hmac_sha256` e erro fatal. Garante que a chave
nao possa chegar pelo YAML por nenhum caminho.

## D-008 — Lista global de parametros proibidos

`key`, `secret`, `hmac_key`, `password`, `token`, `salt`, `pepper` e similares
sao recusados no `config` de QUALQUER transformer, nao so do HMAC. A mensagem
de erro cita o nome do parametro, nunca o valor.

## D-009 — `random` exige `strategy` explicita

Sem default de estrategia: `strategy` e obrigatorio. `length` e obrigatorio
quando `preserve_length: false` e proibido quando `preserve_length: true`
(combinacao ambigua). `preserve_length` tem default `true`.

Consequencia: `config/masking.yaml` foi atualizado — a regra `telefone` agora
declara `strategy: digits`.

## D-010 — `truncate` nao adiciona sufixo

`truncate` devolve `value[:length]`, sem reticencias nem marcador. O
transformer preserva um prefixo do dado original por definicao; e reducao de
exposicao, nao anonimizacao.

## D-011 — Valores nao-string sao convertidos antes da transformacao

> **Emendada na Fase 2 por D-015.** A conversao continua existindo, mas deixou
> de ser `str()`.

`MASKING-SPEC.md` estabelece que a saida pode ser string neste MVP. Valores
nao-nulos que nao sejam `str` sao convertidos antes da transformacao. NULL
nunca e convertido: permanece `None`.

Colunas sem correspondencia preservam o tipo original — nao passam por
conversao alguma.

## D-012 — Fase 1 nao registra log

Nenhum modulo importa `logging`. O componente `audit/` entra na Fase 5, com
log estruturado apenas de metadata. Ate la, a ausencia de log e verificada por
teste (`tests/test_leakage.py`).

## D-013 — Transformers nao expoem atributo `name`

A fonte da verdade do nome de um transformer e a chave do registry, propagada
para `MaskingRule.transformer_name`. Um `name` no proprio transformer seria
uma segunda fonte, passivel de divergir.

## D-014 — Riscos de configuracao: documentar, nao bloquear

A revisao de seguranca da Fase 1 confirmou quatro formas de o `masking.yaml`
anular a protecao. Nenhuma e defeito do engine: em todas o pipeline se comporta
como especificado.

| # | Risco | Efeito |
|---|---|---|
| H-1 | Exception larga (`mode` default e `contains`) | Desliga a regra inteira em silencio |
| H-2 | `regex` com replacement identidade (`(.*)` -> `\1`) | Devolve o valor original |
| H-3 | `truncate` com `length` >= tamanho do valor | Devolve o valor original |
| H-4 | `random` com `preserve_length: true` | Publica o comprimento do original |

Decisao: **documentar e fixar em teste**, nao bloquear no loader.

Motivo: a deteccao generica de "transformer inocuo" nao e decidivel — um
`truncate` longo pode ser legitimo em coluna de texto, e uma exception larga
pode ser intencional. Bloquear geraria falso positivo em configuracao valida.

Os quatro casos estao cobertos por `tests/test_config_hazards.py`, que fixa o
comportamento atual. Validacao no boot (avisar quando o padrao de uma exception
for substring do padrao de uma regra) fica registrada em
`docs/FUTURE-HARDENING.md`.

---

# Fase 2 — PostgreSQL Adapter + ResultSet Masking

## D-015 — Canonicalizacao explicita, nunca `str()`, com falha fechada

Emenda D-011. `str()` servia enquanto a Fase 1 so via valores de teste; contra
um banco real ele produz saida errada em dois casos concretos:

| valor do psycopg | `str()` | problema |
|---|---|---|
| `memoryview` de `bytea` | `<memory at 0x10f2a3040>` | embute o **endereco do objeto**: muda a cada execucao |
| `dict` de `jsonb` | `{'cpf': '...'}` | repr de Python: aspas simples e ordem de insercao |

O primeiro caso e o grave. `hmac_sha256`, `md5`, `sha256` e `sha512` sao
documentados como deterministicos; com `str(memoryview)` a mesma linha
produziria hashes diferentes entre consultas, **em silencio**.

Decisao: `maskgw.masking.canonical.canonicalize` define uma forma canonica por
tipo, e `Transformer.apply` passa a usa-la.

| tipo | forma canonica | observacao |
|---|---|---|
| `str` | o proprio valor | |
| `bool` | `true` / `false` | testado ANTES de `int`: `bool` e subclasse de `int` |
| `int` | `str(int)` | |
| `float` | `repr(float)` | forma curta com round-trip garantido |
| `Decimal` | `str(Decimal)` | preserva a escala do PostgreSQL: `1.10` nao vira `1.1` |
| `bytes`, `bytearray`, `memoryview` | base64 padrao | sem perda e sem endereco |
| `datetime` | ISO 8601 | testado ANTES de `date`: `datetime` e subclasse de `date` |
| `date`, `time` | ISO 8601 | |
| `UUID` | `str(UUID)` | minusculas, com hifens |
| `dict`, `list` | JSON canonico | `sort_keys=True`, separadores `,` e `:`, UTF-8 preservado |

Escalares dentro de JSON usam a mesma tabela, por `default=` do `json.dumps`.

**Qualquer outro tipo FALHA FECHADA**: `TransformerError`, nunca `str(obj)`. Um
`interval` do PostgreSQL chega como `timedelta` e derruba a consulta em vez de
gerar saida arbitraria. `NaN`/`Infinity` dentro de estrutura JSON tambem falham
fechado, porque JSON canonico nao os representa.

A mensagem de erro cita apenas o **nome do tipo**, nunca o valor. E a mensagem
do `json` (que embute o repr do objeto ofensor) e descartada, nao propagada.

O modulo vive em `masking/` porque quem precisa dele e `Transformer.apply`.
Depende so da stdlib, entao a pureza do nucleo continua valendo.

Coluna **sem** transformacao nao passa por nada disso: preserva exatamente o
objeto Python do psycopg. `Decimal` continua `Decimal`, `datetime` continua
`datetime`, JSONB continua `dict`, `bytes` continuam `bytes`.

## D-016 — Transacao: `autocommit`, e rollback defensivo

O adapter nao pode deixar a sessao `idle in transaction` — conexao presa
segura recursos e bloqueia manutencao no banco.

Alternativas descartadas:

- `with connection.transaction():` — o psycopg faz **COMMIT** ao sair sem erro.
  Commitar como mecanismo de limpeza foi vetado.
- `rollback()` incondicional ao fim de toda consulta — trabalho inutil e uma
  ida ao servidor por consulta, ja que em autocommit nao ha transacao aberta.

Decisao: a conexao e aberta com `autocommit=True`. Cada statement roda na sua
propria transacao implicita, que o servidor encerra ao termino — em sucesso ou
em erro. Nao ha COMMIT de operacao arbitraria, e a sessao volta a `idle`
sozinha, inclusive depois de um erro (o que mantem a conexao reutilizavel).

Como rede de seguranca, `_settle()` roda em `finally` apos toda consulta: se o
`transaction_status` nao for `IDLE`, faz **rollback**, nunca commit. Se o
proprio rollback falhar, a conexao e fechada em vez de propagar detalhe do
driver — `_settle` roda em `finally` e nao pode substituir o erro original.

`autocommit=True` e compativel com o enforcement read-only da Fase 4
(`default_transaction_read_only` / role sem privilegio de escrita).

Verificado contra PostgreSQL real por `pg_stat_activity`, de uma segunda
conexao, apos consulta bem-sucedida, apos erro do servidor e apos falha de
canonicalizacao.

## D-017 — O erro sanitizado e levantado FORA do bloco `except`

Descoberto por teste durante a Fase 2, e nao previsto no plano.

`raise DatabaseError(...) from None` zera `__cause__` e liga
`__suppress_context__`, o que basta para o traceback padrao do Python. Mas o
interpretador ainda pendura a excecao original em `__context__` quando o
`raise` acontece dentro de um handler ativo.

Consequencia: `error.__context__` continuava sendo o `psycopg.Error` cru, com
a mensagem do servidor — que pode conter valores, como em
`invalid input syntax for type integer: "12345678901"`. Qualquer formatador,
logger estruturado ou coletor de erros que percorra a cadeia de excecoes
exporia o dado. Com o `audit/` da Fase 5 isso deixaria de ser hipotetico.

Decisao: o adapter guarda o erro sanitizado numa variavel, sai do handler, e so
entao levanta, por `_raise_sanitized`. Fora do handler nao ha excecao corrente,
entao `__cause__` e `__context__` ficam ambos `None`.

Fixado por teste que percorre as duas cadeias e por outro que renderiza o
traceback completo.

## D-018 — Leitura em lotes com `fetchmany`

O adapter le o result set em lotes de `DEFAULT_BATCH_SIZE` (500) linhas e
mascara lote a lote, em vez de `fetchall()`.

**Nao e row limiting** — que e da Fase 4. Nenhuma linha e descartada e nao ha
sinalizacao de truncamento: e apenas a estrategia de consumo, escolhida para
que o limite da Fase 4 entre sem reescrever o adapter.

O gerador que produz os lotes e privado e consumido inteiramente dentro de
`execute`: linha crua nao escapa da funcao.

## D-019 — SQLSTATE classifica, mas nao viaja

A mensagem devolvida ao chamador vem de uma tabela fixa, indexada pela classe
do SQLSTATE (os dois primeiros caracteres). O codigo em si **nao** entra na
mensagem: `42P01` viraria um oraculo barato de existencia de tabela e coluna.

Nada mais da excecao original sai: nem `str(exc)`, nem `repr(exc)`, nem `diag`,
nem query, nem parametros. O `DatabaseError` resultante tambem nao carrega
atributo algum do erro de origem.

---

# Fase 3 — Column provenance / lineage

## D-020 — `DERIVED` e `UNKNOWN` sao coisas diferentes

`docs/ROADMAP.md` sugeria um enum com `DIRECT`, `VIEW`, `DERIVED` e `UNKNOWN`,
deixando em aberto qual usar quando `ftable = 0`. A medicao empirica
(`tests/test_pgresult_metadata.py`) mostrou que os dois casos tem naturezas
opostas e nao devem colapsar:

| | quem afirma | significado |
|---|---|---|
| `DERIVED` | **o PostgreSQL** | `ftable = 0`: a coluna nao vem de uma unica coluna de tabela. Expressao, literal, agregado, UNION |
| `UNKNOWN` | **nos** | O PostgreSQL indicou uma origem, mas nao conseguimos traduzi-la: catalogo inacessivel, ou linha de `pg_attribute` ausente |

Decisao: `ftable = 0` (ou `ftablecol = 0`) e `DERIVED`. Falha de resolucao e
`UNKNOWN`. `UNKNOWN` tambem e o default de um `ColumnDescriptor` construido a
mao, sem proveniencia.

Nos dois casos o efeito no matching e identico — `origin_name = None`, recai
sobre `output_name` — e o default ALLOW nao muda. A distincao existe para
auditoria e para o hardening futuro: `UNKNOWN` frequente e sintoma de
privilegio faltando no catalogo, e nao de consulta legitimamente sem origem.
Um alerta sobre isso ficaria mudo se os dois casos fossem o mesmo valor.

## D-021 — Cache de proveniencia por conexao, com chave `(oid, attnum)`

A resolucao consulta `pg_attribute`, `pg_class` e `pg_namespace`. Sem cache
seriam N consultas por result set.

Decisao: dicionario simples `(oid, attnum) -> ColumnOrigin`, no
`ProvenanceResolver`, com tempo de vida igual ao da conexao. Resolve-se uma vez
por COLUNA, nunca por linha ou celula — verificado por teste que le 200 linhas
e confirma `cache_size == 1`.

Detalhes que valem registro:

- **Uma consulta por result set, no maximo.** As chaves ainda desconhecidas vao
  juntas, via `unnest(%s::oid[], %s::int2[])` com JOIN em `pg_attribute`. Um
  `SELECT *` de 14 colunas custa uma consulta ao catalogo, nao 14.
- **Ausencia tambem e cacheada.** Chave consultada e nao devolvida pelo
  catalogo vira `UNKNOWN` no cache, para nao repetir a consulta a cada
  result set.
- **Falha NAO e cacheada.** Se a consulta ao catalogo levantar, as colunas
  ficam `UNKNOWN` apenas naquela consulta e nada entra no cache. Cachear o erro
  desligaria a proveniencia — e portanto a protecao contra alias — pelo resto
  da vida da conexao, a partir de uma falha transitoria. Fixado em teste.
- **Colunas `DERIVED` nunca entram no cache**: nao ha o que consultar.

Risco aceito: um `ALTER TABLE ... RENAME COLUMN` durante a vida da conexao
deixa a entrada obsoleta. O Gateway e read-only sobre schema estavel, entao o
custo de invalidacao nao se justifica no MVP. Registrado em
`docs/FUTURE-HARDENING.md`.

## D-022 — View resolve para a coluna da view, sem lineage recursivo

Medido: para `SELECT cpf FROM cliente_vw`, o PostgreSQL devolve o oid **da
view**, nao o da tabela base. `relkind` distingue (`v` para view, `m` para
materialized view).

Decisao, conforme o escopo da fase: `origin_name` e `origin_table` recebem a
coluna e o nome DA VIEW, com `provenance_kind = VIEW`. Nao se percorre
`pg_rewrite` para chegar a tabela base.

Consequencia, coberta por teste: uma view que RENOMEIA a coluna apaga o nome
original nesta camada.

```sql
CREATE VIEW v AS SELECT cpf AS documento FROM cliente;
SELECT documento FROM v;   -- origin_name = "documento", nao "cpf"
```

Isso passa em claro. E a mesma classe de risco do default ALLOW: quem define a
view define o que o Gateway enxerga. Registrado em
`docs/FUTURE-HARDENING.md`, nao corrigido nesta fase.

Na pratica a maioria das views preserva o nome da coluna, e nesse caso o
matching funciona normalmente.

## D-023 — Proveniencia e resolvida ANTES de qualquer linha ser lida

`cursor.pgresult` e lido logo apos o `execute`, e a resolucao acontece antes do
primeiro `fetchmany`. Duas razoes:

1. A metadata de baixo nivel e lida enquanto o resultado esta intacto.
2. Deixa explicito no codigo que a proveniencia vem da metadata do PostgreSQL,
   nunca dos valores das linhas.

A consulta ao catalogo usa um cursor proprio, na mesma conexao. Isso e seguro
com o cursor client-side do psycopg3, que ja materializou o resultado. Se a
Fase 4 introduzir cursor server-side para o row limit, esta ordem precisa ser
reavaliada.

## D-024 — `origin_schema` e `origin_table` sao auditoria, nao criterio

O descritor passou a carregar schema e tabela de origem, mas o matching
continua avaliando apenas `output_name` e `origin_name`.

As regras do `masking.yaml` sao globais por nome de coluna
(`docs/MASKING-SPEC.md`). Se schema ou tabela influenciassem o matching, a
mesma configuracao produziria resultados diferentes conforme a consulta, sem
nada no arquivo de regras dizer isso. Regra por tabela e RBAC — fora do MVP.

Fixado por teste: descritores identicos exceto por schema, tabela e
`provenance_kind` produzem o mesmo resultado.

## D-025 — Falha de proveniencia nao muda a politica

Se o catalogo nao responder, a coluna fica `UNKNOWN` e o matching recai sobre
`output_name`, exatamente como na Fase 2. Nao ha nova politica fail-closed.

O erro do PostgreSQL e absorvido no resolver: nao levanta, nao e logado e nao
aparece em `repr`. Ele poderia citar objetos do catalogo e o privilegio
faltando.

Efeito colateral operacional que precisa estar visivel: **uma role sem leitura
em `pg_catalog` reabre o bypass por alias**, silenciosamente. Registrado em
`docs/SECURITY.md` e em `docs/FUTURE-HARDENING.md`.

---

# Fase 4 — SQL validation + execution safety

## D-026 — Capability check de proveniencia: falha alta no startup

> **A premissa deste paragrafo caiu na Fase 6.** D-040 emendou D-025: falha
> operacional de catalogo passou a REJEITAR a consulta. A decisao de checar no
> startup continua valida — e complementar, nao substituta.

*Premissa em 2026-08 (Fase 4):* a resolucao de proveniencia em runtime e
tolerante a falha por desenho (D-025): derrubar uma consulta inteira por um
problema de catalogo seria pior que o problema. O preco e que uma role sem
`SELECT` em `pg_attribute` degrada a protecao contra alias **em silencio**, e
nao ha logging ate a Fase 5.

Decisao: `maskgw.db.capabilities.check_provenance_capability` faz uma
verificacao EXPLICITA, para o startup, e levanta `CapabilityError` quando a
capacidade nao existe. O adapter a executa em `connect()`.

Detalhes que importam:

- A sonda e `pg_catalog.pg_class.relname`, um catalogo do sistema — a
  verificacao nao depende do schema da aplicacao.
- Ela passa pelo **resolver real**, nao por uma consulta paralela. O que se
  quer provar e que o caminho usado em producao funciona nesta instalacao.
- A mensagem nomeia as tabelas de catalogo necessarias, e nada mais: nem o
  erro do PostgreSQL, nem o DSN, nem a role.

Isto **nao** e politica de masking. Colunas `DERIVED` e `UNKNOWN` continuam
seguindo o default ALLOW; o que muda e que o processo nao sobe com a protecao
desligada. Validacao de instalacao, nao de dados.

Testado com uma role real sem `SELECT` em `pg_attribute`.

## D-027 — Politica de funcoes: `pg_` deny-by-default, resto allow-by-default

Uma allowlist COMPLETA de funcoes seguras tornaria o Gateway inutilizavel:
`lower`, `substr`, `count`, `coalesce`, `date_trunc`, todos os agregados e
janelas teriam de ser enumerados, e cada omissao quebraria uma consulta
legitima. O escopo da fase previa apresentar essa decisao antes de expandir.

Decisao: inverter o default onde o risco se concentra.

| namespace | default | mecanismo |
|---|---|---|
| `pg_*` | **negar** | allowlist curta e explicita (`pg_typeof`, `pg_size_pretty`, `pg_column_size`) |
| demais | permitir | denylist de familias perigosas (`dblink*`, `lo_*`, `query_to_xml*`, `set_config`, `setseed`) |

Praticamente toda funcao perigosa do PostgreSQL vive no namespace `pg_`:
`pg_read_file`, `pg_ls_dir`, `pg_stat_file`, `pg_terminate_backend`,
`pg_sleep`, `pg_reload_conf`. Negar o namespace inteiro cobre inclusive
funcoes que ainda nao existem — testado com `pg_funcao_inventada_no_futuro()`.

A decisao e sobre o nome FINAL da funcao, sem o schema:
`pg_catalog.pg_read_file`, `pg_read_file` e `PG_READ_FILE` sao a mesma coisa, e
o parser do PostgreSQL ja normaliza caixa e aspas.

**O limite de seguranca, declarado sem eufemismo:** uma funcao definida pelo
usuario, com efeito colateral e nome comum, PASSA. Esta politica e a primeira
camada, nao a unica. A barreira real e o privilegio: role read-only, sem
EXECUTE em funcoes perigosas, e sem pertencer a `pg_read_server_files` nem a
`pg_execute_server_program`. Registrado em `docs/SECURITY.md`.

A politica e extensivel por configuracao (`sql.allowed_pg_functions` e
`sql.denied_functions`), sem alterar codigo. Em conflito, a negacao vence.

## D-028 — Read-only e timeout por `options` do DSN, conferidos depois

Os dois limites vao ao backend em `options` do conninfo:

```text
-c default_transaction_read_only=on -c statement_timeout=<ms>
```

Escolha sobre as alternativas:

- **`options` em vez de `SET` apos conectar:** o `options` e aplicado pelo
  backend na inicializacao, antes de qualquer statement. Nao existe janela
  entre conectar e proteger.
- **Compativel com `autocommit=True`** (D-016): `default_transaction_read_only`
  vale para as transacoes implicitas.
- **Os `-c` do Gateway vao por ultimo.** Se o DSN ja trouxer `options`
  conflitante, prevalece o do Gateway. Fixado em teste com um DSN hostil
  (`-c default_transaction_read_only=off -c statement_timeout=0`).

E, porque configuracao pode ser silenciosamente neutralizada — por um pooler,
por `ALTER ROLE ... SET`, por um DSN inesperado — `connect()` **confere** os
dois valores em `pg_settings` e levanta `CapabilityError` se nao bateram. O
Gateway nao opera sem eles.

Nada disso substitui a exigencia operacional de uma role sem privilegio de
escrita. Sao camadas distintas, e o teste de defesa em profundidade contorna o
validator de proposito para provar que a de baixo funciona.

## D-029 — Duas portas no adapter, deliberadamente

- `execute_validated(sql)` — valida e so entao executa. E o que um Gateway ou
  servidor MCP deve chamar.
- `execute(sql, params)` — **nao** valida. Porta interna.

Manter a porta sem validacao e intencional: os testes de defesa em profundidade
precisam contornar o validator para provar que o PostgreSQL barra a escrita
sozinho. Se `execute` validasse, esse teste nao existiria — e a suite passaria
a medir o parser duas vezes em vez de medir o privilegio uma.

## D-030 — Row limit: devolver ate `max_rows` e sinalizar `truncated`

Alternativa descartada: rejeitar o resultado inteiro quando passa do limite.
Para uso por IA isso e pior — uma consulta exploratoria comum falharia sem
entregar nada, e o cliente tenderia a repetir com filtros ate acertar.

Decisao: devolver ate `max_rows` linhas e marcar `MaskedResult.truncated`.

O ponto delicado e como saber que havia mais. O adapter busca deliberadamente
UMA linha alem do limite; ao detectar o excesso, **descarta essa linha antes do
masking**. Ela nunca e transformada e nunca chega ao chamador. A linha N+1
existe apenas como um booleano.

O enforcement e no consumo do result set, nao reescrevendo a SQL com `LIMIT`:
reescrever mudaria a semantica de consultas com `ORDER BY`, `OFFSET` ou
agregacao, e exigiria um SQL rewriter — fora do escopo.

A leitura em lotes (D-018) permanece: o tamanho do lote nao altera nem o
resultado nem o `truncated`, fixado em teste para lotes de 1, 3, 7 e 500.

## D-031 — Validacao por tipo de no da AST, incluindo os `*Stmt` aninhados

Quatro regras, todas sobre a arvore que o proprio PostgreSQL produz:

1. Exatamente um statement **executavel**. O parser descarta statements
   vazios: `SELECT 1;;` e um, `;` e nenhum. O criterio e a contagem de
   statements reconhecidos, nunca a de ponto e virgula. Medido em
   `tests/test_sql_parser.py`.
2. Raiz `SelectStmt`. Isso cobre INSERT, UPDATE, DELETE, MERGE, CREATE, ALTER,
   DROP, TRUNCATE, GRANT, REVOKE, COPY, CALL, DO, VACUUM, ANALYZE, REFRESH,
   SET e RESET sem que nenhum precise ser nomeado.
3. Nenhum outro no de statement em lugar nenhum da arvore. A raiz ser
   `SelectStmt` **nao basta**: `WITH x AS (DELETE ... RETURNING *)` tem raiz
   `SelectStmt`. O criterio para "no de statement" e estrutural — toda classe
   de statement da gramatica termina em `Stmt`, e sao 117 delas —, nao uma
   lista de palavras-chave mantida a mao.
4. `IntoClause` e `LockingClause` recusadas em qualquer ponto.

A regra 4 nasceu de uma medicao, nao do plano: **`SELECT 1 INTO nova` parseia
como `SelectStmt` e CRIA UMA TABELA.** Um validator que so olhasse o tipo do no
raiz o aceitaria. `SELECT ... FOR UPDATE` tem o mesmo formato e trava linhas.

## D-032 — Erros de parser e validator nao citam a consulta

- `InvalidQuery` para SQL malformada: mensagem fixa `"sintaxe SQL invalida"`. A
  do pglast cita trechos da consulta (`syntax error at or near "SELEC"`).
- `QueryRejected` para SQL valida que a politica recusa. O motivo vem de um
  conjunto FIXO de sete constantes. Nem a consulta, nem nomes vindos dela —
  nem o nome da funcao proibida — entram na mensagem.
- `QueryTimeout` para SQLSTATE 57014, com texto proprio. E subclasse de
  `DatabaseError`: o chamador distingue o caso sem receber nada do servidor.

A garantia de D-017 vale para todos: nem `__cause__` nem `__context__` apontam
para a excecao original. Fixado por teste que renderiza o traceback completo.

---

# Fase 5 — Gateway + MCP Server

## D-033 — A proveniencia nao sai para o cliente MCP

`ColumnDescriptor` carrega `origin_name`, `origin_schema`, `origin_table` e
`provenance_kind`. Nada disso entra no `QueryResult`.

O cliente recebe, por coluna, apenas `name` e `masked`. `masked` e util: diz ao
modelo que aquele valor foi transformado, o que evita conclusoes erradas sobre
o dado. `origin_table` nao teria uso legitimo — diria a uma IA nao confiavel
qual tabela sustenta cada coluna de cada consulta, o que e reconhecimento de
schema de graca.

Regra geral aplicada: o cliente precisa do dado ja seguro, nao do mapa de como
ele foi protegido. Tambem ficam de fora `table_oid`, `attnum`, indices de
regra, nomes de transformer, o DSN e qualquer objeto psycopg.

## D-034 — Lifecycle da conexao: uma so, aberta no startup

Sem pool nesta fase. O comportamento, para constar:

| momento | comportamento |
|---|---|
| **abertura** | em `build_application`, antes de o MCP existir |
| **por consulta** | `connect()` e chamado sempre; e no-op quando ja aberta |
| **queda da conexao** | a proxima consulta reconecta, com verificacao completa de sessao e capability |
| **erro de consulta** | a conexao sobrevive (autocommit, D-016); a sessao volta a IDLE |
| **PostgreSQL fora no startup** | `build_application` levanta e o processo **nao sobe** |
| **encerramento do MCP** | `Application.close()` no `finally` do bootstrap |

Duas consequencias explicitas:

- **Nao ha estado parcialmente funcional.** Se `build_application` levanta,
  nao existe Gateway, e sem Gateway nao ha servidor MCP. O processo termina com
  codigo 1 em vez de aceitar consultas que falhariam todas.
- **Consultas sao serializadas.** O SDK MCP executa tools sincronas numa thread
  pool, e uma conexao psycopg nao suporta consultas concorrentes intercaladas.
  `Gateway.query` usa um `threading.Lock`. Para um servidor stdio com um
  cliente, o custo e nulo; se um dia houver transporte HTTP concorrente, e aqui
  que um pool entra.

## D-035 — Auditoria: `request_id`, nunca digest da SQL

`audit/` e o unico modulo autorizado a importar `logging`, e o teste global
mudou de "ninguem loga" para "so `audit/log.py` loga". `masking/` continua
proibido, verificado tambem por `test_purity`.

Os campos auditados sao fechados **por construcao**: `QueryAudit` e uma
dataclass com exatamente `request_id`, `outcome`, `duration_ms`, `row_count`,
`truncated` e `error_category`. Nao existe parametro para SQL, valores, linhas
ou segredos — passar um levanta `TypeError`, e isso esta fixado em teste.

O escopo da fase permitia hash ou HMAC da SQL para correlacao. **Descartado.**
Um digest estavel permite confirmar, por comparacao, que uma consulta
especifica rodou; com predicados como `WHERE cpf = '...'`, quem tiver acesso
aos logs testa hipoteses e confirma valores. E o mesmo oraculo de WHERE que
`docs/FUTURE-HARDENING.md` ja registra, so que gravado em disco.

Correlacao usa `request_id` — um UUID por consulta, sem relacao com o conteudo.

## D-036 — Somente stdio; nenhuma porta de rede

O SDK v2 oferece `stdio`, `sse` e `streamable-http`. Apenas `stdio` e usado, e
`run(transport="stdio")` e a unica chamada de transporte no projeto.

Reducao deliberada de superficie: sem socket, sem autenticacao a implementar,
sem CORS, sem DNS rebinding, sem sessao HTTP para sequestrar. O processo fala
com um cliente pelo proprio stdin/stdout.

Streamable HTTP fica para uma fase de deployment, onde tera de vir acompanhado
de autenticacao e de um modelo de sessao — nao como um parametro trocado.

## D-037 — Argumentos extras sao IGNORADOS pelo SDK, nao recusados

Medido no SDK v2.1.1, e diferente do que o escopo da fase supunha.

O `input_schema` publicado nao traz `additionalProperties: false`, e o modelo
de argumentos que o SDK gera usa o default do Pydantic (`extra="ignore"`).
Uma chamada com `{"sql": "...", "disable_masking": true}` retorna
`is_error: false` e executa normalmente, com o argumento extra descartado antes
de chegar ao handler.

Nao ha ponto de extensao publico para tornar isso estrito. Conforme a instrucao
de nao improvisar compatibilidade, **nada foi remendado**: nem monkey patch no
SDK, nem `additionalProperties: false` declarado no schema — anunciar uma
restricao que o servidor nao aplica seria pior que a ausencia dela.

A garantia de seguranca que vale, e que esta fixada em teste, e mais forte que
a recusa: **o argumento extra nao pode mudar nada.** Para cada um dos oito
nomes perigosos (`disable_masking`, `raw`, `unmasked`, `masking`,
`transformer`, `max_rows`, `timeout`, `dsn`), o resultado com o extra e
identico ao sem ele, o Gateway recebe a mesma chamada, e a coluna continua
mascarada. O cliente controla apenas a SQL porque nao existe outro parametro —
nao porque outro seja recusado.

## D-038 — Erro do MCP: categoria fixa, mensagem curta

`Gateway.query` levanta apenas `GatewayError`, com uma de cinco categorias
(`INVALID_QUERY`, `QUERY_REJECTED`, `QUERY_TIMEOUT`, `DATABASE_ERROR`,
`CONFIGURATION_ERROR`) e a mensagem fixa correspondente. O handler MCP traduz
para `ToolError`.

Duas travas:

- **Toda excecao e capturada**, inclusive `RuntimeError` inesperado. Sem isso,
  o SDK registraria o traceback completo via `logging` antes de redigir a
  resposta — o que colocaria a excecao original nos logs do operador.
- `GatewayError` e levantado FORA do handler (D-017): nem `__cause__` nem
  `__context__` apontam para o erro interno.

`QueryTimeout` e checado antes de `DatabaseError`, de que e subclasse.

---

# Fase 6 — Security red team + hardening

## D-039 — Relacoes de estatistica sao bloqueadas no validator

`pg_statistic` guarda AMOSTRAS DOS VALORES REAIS das colunas em `stavaluesN`, e
a view `pg_stats` as expoe em `most_common_vals` e `histogram_bounds`. Medido
na Fase 6: uma consulta devolvia CPFs verdadeiros em claro.

Todas as camadas passavam batido, e por bons motivos:

- os nomes de saida (`most_common_vals`, `histogram_bounds`) nao casam regra;
- nao ha coluna de origem a resolver — e um array agregado;
- nao ha erro, nao ha escrita, nao ha funcao proibida.

Decisao: o validator recusa `pg_statistic`, `pg_stats`, `pg_stats_ext`,
`pg_stats_ext_exprs`, `pg_statistic_ext` e `pg_statistic_ext_data`, por no
`RangeVar`, em qualquer ponto da arvore — CTE, subquery ou ramo de UNION
inclusive. A decisao e pelo nome da relacao, sem o schema, como nas funcoes:
`pg_catalog.pg_stats`, `PG_STATS` e `"pg_stats"` caem juntos.

**Nao e um bloqueio de `pg_catalog`.** O resto do catalogo continua legivel, e
a resolucao de proveniencia usa a conexao do Gateway, nao a SQL do cliente:
nada nela foi afetado. A distincao aplicada e entre metadata (permitida) e
amostras de dado (recusadas).

Isto e uma denylist, e o projeto prefere allowlist. A diferenca importa: a
allowlist de tipos de no da AST (D-031) continua sendo a barreira estrutural;
esta lista cobre um punhado de relacoes que sao dado disfarcado de catalogo, e
e enumeravel porque o PostgreSQL tem exatamente essas.

## D-040 — Falha de resolucao rejeita a consulta; DERIVED nao

Ate a Fase 5, qualquer problema de proveniencia virava `UNKNOWN`, e `UNKNOWN`
caia no default ALLOW. Medido na Fase 6: um Gateway que perde `SELECT` em
`pg_attribute` DEPOIS do startup passava a devolver `SELECT cpf AS documento`
em claro, em silencio. O capability check (D-026) so roda no `connect()`.

Decisao: separar duas situacoes que eram uma so.

| situacao | quem afirma | comportamento |
|---|---|---|
| `ftable = 0` | o PostgreSQL: nao ha coluna de origem unica | `DERIVED`, default ALLOW, inalterado |
| consulta ao catalogo falha | erro operacional nosso | `CapabilityError`, consulta rejeitada |
| catalogo responde sem a linha | coluna nao esta no catalogo | `UNKNOWN`, default ALLOW |

A terceira linha permanece tolerante de proposito: uma coluna ausente do
catalogo nao e falha de infraestrutura, e nao e alcancavel pelo atacante.

Isto **emenda D-025**, que estabelecia que falha de proveniencia nunca muda a
politica. O raciocinio mudou porque a medicao mostrou que a tolerancia nao
custava disponibilidade — custava confidencialidade, que e a garantia central
do produto. Uma instalacao com catalogo inacessivel deixa de responder em vez
de responder errado.

Detalhes que importam:

- a falha **nao** entra no cache, entao um erro transitorio nao desliga a
  proveniencia pelo resto da vida da conexao;
- o erro do PostgreSQL nao sai: nem mensagem, nem `__cause__`, nem
  `__context__` — o mesmo cuidado de D-017, e o teste pegou a primeira versao
  que errava nisso;
- na fronteira MCP vira `CONFIGURATION_ERROR`.

## D-041 — Bypasses conhecidos viram teste, nunca `skip`

`tests/security/` classifica cada ataque como **BLOCKED**, **MASKED** ou
**KNOWN LIMITATION**, e um KNOWN LIMITATION e um teste que **afirma que o
ataque funciona**.

Parece estranho ter uma suite que garante a existencia de um bypass. E
deliberado, por duas razoes:

1. um `skip` some do relatorio; uma asercao positiva nao. O inventario de
   riscos aceitos fica executavel, e nao apenas escrito;
2. quando um hardening futuro fechar o bypass, o teste QUEBRA — e a correcao
   e notada, documentada e datada, em vez de acontecer sem ninguem perceber.

Cada teste desse tipo carrega a mensagem `fechou? atualizar SECURITY-REVIEW`.

---

# Fase 6.1 — Fechamento dos bypasses criticos

## D-042 — A exception responde pelo nome AUTORITATIVO, nao pelo alias

**F-08.** Exceptions eram avaliadas contra `output_name` E `origin_name`. Como
o `output_name` e escolhido pelo cliente, toda exception configurada virava uma
primitiva de desmascaramento: `SELECT cpf AS tipo_cpf` saia em claro.

Decisao: a exception e avaliada contra UM nome, o autoritativo —
`origin_name` quando existe, `output_name` quando nao ha origem resolvivel.

| consulta | antes | agora |
|---|---|---|
| `SELECT tipo_cpf FROM cliente` | original | original |
| `SELECT tipo_cpf AS documento` | original | original |
| `SELECT cpf AS tipo_cpf` | **em claro** | mascarado |
| `SELECT cliente_cpf AS tipo_cpf` | **em claro** | mascarado |
| `SELECT 'x' AS tipo_cpf` | original | original |

O masking segue avaliando os DOIS nomes: um `output_name` que casa regra ainda
mascara mesmo com origem inocente. A assimetria e o ponto — o alias pode
adicionar protecao, nunca remove-la.

Isto muda a regra documentada `EXCEPTION > MASKING`: ela continua valendo, mas
sobre o nome autoritativo, e nao sobre qualquer nome. `docs/MASKING-SPEC.md` e
`docs/SECURITY.md` foram corrigidos.

## D-043 — Sensitividade por AST, aplicada ao resultado da expressao

**F-01 e F-02.** A proveniencia do PostgreSQL cobre alias, subquery, CTE, JOIN,
cast no-op e view. Ela nao cobre o que o proprio PostgreSQL declara sem origem:
expressoes, agregados e UNION. Ali o valor saia em claro.

O que torna a correcao pequena: **as regras de masking sao globais por nome de
coluna**. Para saber se `substr(c.cpf, 1, 11)` e sensivel nao e preciso saber
de qual tabela `cpf` vem — basta o nome, e ele esta na arvore. Se a consulta e
valida, o nome referenciado e um nome de coluna real. Nao ha lineage engine.

`maskgw.sql.sensitivity` produz, por POSICAO do result set, o indice da regra
que a cobre. Para UNION, olha o alvo correspondente em TODOS os ramos: basta um
ramo ter dependencia sensivel para a posicao inteira ser sensivel — um UNION
mistura as linhas dos ramos numa coluna so.

O engine aplica o transformer dessa regra ao RESULTADO da expressao. Nao se
tenta reconstruir a origem: `substr(cpf, 1, 11)` sai como o HMAC do prefixo,
nao o HMAC do CPF. O que importa e que o valor exposto deixa de ser derivavel.

Isso fecha tambem as formas reversiveis, que nunca foram protecao:
`reverse(cpf)`, base64 e hex.

**Ambiguidade recusa, nao escolhe.** Se uma posicao depende de duas regras
DIFERENTES — `concat(cpf, email)`, ou `SELECT cpf FROM a UNION ALL SELECT email
FROM b` — nao ha transformer unico comprovavel, e a consulta e rejeitada. Duas
referencias a MESMA regra (`concat(cpf, nr_cpf)`) nao sao ambiguas.

**A analise complementa, nunca enfraquece.** Ela so acrescenta sensibilidade;
nao ha caminho pelo qual ela libere uma coluna que a proveniencia protegeria. E
so e aplicada quando as posicoes batem com o result set: um `SELECT *` produz
um alvo na arvore e N colunas no resultado, e ali as contagens divergem e a
proveniencia segue sozinha.

Custo: uma passada de AST por CONSULTA, nunca por linha. Fixado por teste com
10.000 linhas e por um contador de chamadas ao analisador.

## D-044 — Serializacao de linha inteira e recusada

`row_to_json(c)` e `to_json(c)` devolvem a linha toda, com todas as colunas
sensiveis, e a arvore nao tem um `ColumnRef` por campo para provar coisa
alguma. Um `ColumnRef` de campo unico que casa o nome ou o alias de uma relacao
do FROM nao e uma coluna: e a linha.

Decisao: recusar. Sem `REJECT`, a alternativa seria mascarar o documento
inteiro por uma regra escolhida arbitrariamente, ou deixar passar.

Falso positivo possivel: uma coluna com o mesmo nome de uma tabela ou alias do
FROM. Recusar e o lado seguro, e `SELECT c.cpf` (qualificado) nao e afetado.

## D-045 — `mode` default das exceptions passa a ser `exact`

**Hazard H-1**, aberto desde a Fase 1 (D-014). Uma exception escrita sem `mode`
herdava `contains` e desligava a regra inteira em silencio.

Decisao: `mode` default `contains` para regras de masking, `exact` para
exceptions. A assimetria e justificada: uma regra larga protege demais, uma
exception larga protege de menos.

**Compatibilidade.** Configuracao existente que dependa de exception por
substring muda de comportamento — uma exception `tipo` que hoje cobre
`tipo_cpf` deixa de cobrir. A correcao e explicitar `mode: contains`, e a
escolha fica visivel no arquivo. `config/masking.yaml` do repositorio ja
declarava `mode: exact` e nao mudou.

Combinada com D-042, o risco de H-1 cai bastante: mesmo uma exception larga
deixou de ser alcancavel por alias.

## D-046 — Um passo entre niveis: os nomes exportados por CTE e subquery

Sem ele, `WITH x AS (SELECT cpf AS d FROM cliente) SELECT upper(d) FROM x`
esconderia `cpf` atras do alias `d`, e o UNION dentro de CTE — exigido no
escopo da fase — continuaria aberto.

Decisao: construir um mapa `nome exportado -> regra` aplicando a MESMA analise
a cada select de CTE e de subquery do FROM, e consultar esse mapa quando o nome
referenciado nao casa regra diretamente.

Limites deliberados:

- **nao resolve escopo.** O mapa e por nome, como toda a politica. Um nome
  exportado por uma subquery afeta a consulta inteira. Isso mascara demais em
  casos raros, nunca de menos.
- **um nivel por vez, com recursao.** O coletor para no primeiro select interno
  (`Skip`) e a recursao trata o resto. Descer a arvore inteira em cada nivel
  tornava a analise quadratica: uma consulta com 200 subqueries aninhadas
  travava o processo — medido, e por isso o `Skip` existe.
- **profundidade maxima de 16.** Alem dela a analise devolve `None` e a
  proveniencia segue sozinha. Desistir e diferente de afirmar que e seguro.

Isto e menos que um lineage engine: nao ha resolucao de escopo, nao ha
propagacao de tipos, nao ha reescrita. E um mapa de nomes.

---

# Fase 7 — Admin API (decisoes aprovadas, implementacao NAO iniciada)

As decisoes abaixo foram aprovadas antes de qualquer codigo. Nao ha modulo
`admin/`, nao ha FastAPI no `pyproject.toml`, nao ha teste. Elas existem para
que a especificacao final — que sera aprovada separadamente — nao reabra
questoes ja resolvidas.

## D-047 — A fonte administrativa e o arquivo validado, nao o runtime compilado

A Admin API NAO deve reconstruir configuracao a partir de `GatewayConfig`,
`MaskingPolicy`, `MaskingEngine` ou `SqlPolicy`. Esses sao objetos runtime.

A fonte administrativa persistida e o modelo validado correspondente ao
arquivo — hoje, `MaskingFileConfig`.

Motivo: a compilacao descarta e transforma informacao. Um `MaskingRule` carrega
uma instancia de `Transformer` ja construida, e nao os parametros que a
originaram; um `RegexTransformer` tem o padrao compilado, nao o texto do YAML.
Reconstruir o arquivo a partir dai devolveria algo que **parece** a
configuracao original sem ser ela — e a diferenca so apareceria depois, num
reload.

Consequencia pratica: o caminho e sempre
`arquivo -> modelo validado -> objetos runtime`, nunca o inverso.

## D-048 — Reload reconstroi o runtime inteiro

Mudanca administrativa nao altera componentes individuais em-place.

Constroi-se um conjunto NOVO e consistente: config compilada, `MaskingEngine`,
`SqlPolicy`, `DatabaseSettings` e `PostgresAdapter`. Uma query enxerga o
runtime antigo inteiro ou o novo inteiro. Nunca uma mistura: um
`MaskingEngine` novo com um `SqlPolicy` antigo produziria decisoes que nenhuma
configuracao jamais descreveu.

### Fluxo obrigatorio

```text
validar a configuracao candidata
  -> compilar e construir o runtime candidato
  -> conectar o novo PostgresAdapter
  -> verificar read-only, statement_timeout e capability de provenance
  -> persistir atomicamente
  -> trocar o runtime atomicamente
  -> fechar o runtime antigo somente quando nenhuma query ainda estiver usando-o
```

A ordem nao e arbitraria. Cada passo existe porque o inverso quebra algo:

| passo | o que garante | se inverter |
|---|---|---|
| validar antes de tudo | config invalida nao toca em nada | arquivo corrompido por config que nao carrega |
| construir antes de persistir | falha de compilacao nao deixa rastro | arquivo novo com runtime velho |
| **conectar e verificar antes de persistir** | o candidato e comprovadamente utilizavel | config salva que derruba o Gateway no proximo restart |
| persistir antes do swap | arquivo e runtime concordam | runtime novo com arquivo velho: o restart regride em silencio |
| swap por ultimo | a troca e o unico ponto observavel | janela em que a query ve estado parcial |

O passo de **conectar e verificar** e o que diferencia esta decisao de um
reload ingenuo. As tres verificacoes ja existem no `PostgresAdapter.connect()`
— sessao read-only, `statement_timeout` conferido em `pg_settings` (D-028) e
`check_provenance_capability` (D-026).

O que torna a reconexao necessaria e que `database.statement_timeout_ms` viaja
em `options` do DSN (D-028) e so vale a partir de uma sessao nova. Um
`statement_timeout_ms` que o servidor recuse, ou uma role que tenha perdido o
acesso ao catalogo desde o startup, precisa falhar **aqui**, com o runtime
antigo intacto — e nao no proximo restart, quando ninguem estiver olhando.

**O DSN nao e campo administrativo.** Credenciais, host e banco continuam vindo
exclusivamente de secret/variavel de ambiente e nao sao editaveis pela Admin
API — nem para leitura. A reconexao usa o mesmo DSN de sempre; o que muda sao
os parametros de sessao derivados da configuracao.

### Semantica de falha, por ponto

Nao existe atomicidade conjunta entre filesystem e memoria. Sao dois meios
distintos, e nenhuma primitiva os cobre junto. O que existe e uma sequencia
cujo unico ponto de nao-retorno e conhecido e documentado.

| falha em | arquivo | runtime | candidato | resposta ao admin |
|---|---|---|---|---|
| validacao | anterior | anterior | nunca existiu | `CONFIG_INVALID` |
| compilacao / construcao | anterior | anterior | fechado | `CONFIG_RELOAD_ERROR` |
| conexao ou capability check | anterior | anterior | fechado, com a conexao | `CONFIG_RELOAD_ERROR` |
| persistencia atomica | **anterior** | anterior | fechado | `CONFIG_WRITE_ERROR` |
| **crash entre persistencia e swap** | **novo** | anterior, e o processo morreu | perdido com o processo | nenhuma — ver abaixo |
| swap | nao ocorre (ver abaixo) | — | — | — |

**Falha da persistencia preserva o arquivo anterior.** A escrita e
`arquivo temporario no mesmo diretorio -> fsync -> rename`. O `rename` dentro
do mesmo filesystem e atomico: ou o arquivo novo passou a existir inteiro, ou o
anterior permaneceu intacto. Nao ha meio-arquivo. Se qualquer passo falhar
antes do `rename`, o temporario e removido e nada mudou.

**Depois que a persistencia termina, o arquivo ja e o novo.** Nao ha rollback
do arquivo. Nao se afirma, em ponto algum, que "qualquer falha antes do swap
preserva o arquivo": isso e falso a partir do `rename`. Um rollback de arquivo
so poderia ser afirmado se existisse, com teste que o exercite; nao existe, e
por isso nao e afirmado.

### A janela de crash entre persistir e trocar

Entre o `rename` concluido e a reatribuicao da referencia de runtime existe uma
janela real. Se o processo morrer nela, o estado e:

- **em disco:** a configuracao nova, ja validada e ja comprovada conectavel;
- **em memoria:** nada — o processo nao existe mais.

**Recuperacao:** o proximo start le o arquivo, que e o novo. O Gateway sobe com
a configuracao nova. Nao ha reconciliacao a fazer, nao ha arquivo a reverter e
nao ha estado corrompido: o arquivo persistido e exatamente aquele que passou
por validacao, compilacao, conexao e capability check antes de ser escrito.
Essa e a razao de a verificacao vir **antes** da persistencia — e nao uma
otimizacao.

**Consequencia que o administrador precisa conhecer:** uma operacao que nao
retornou sucesso pode, ainda assim, ter tomado efeito no proximo start. E o
preco de nao haver atomicidade entre disco e memoria, e a direcao do risco e a
segura — a configuracao que vigora e uma que ja foi validada, nunca uma
mistura nem um arquivo pela metade. Apos qualquer queda durante uma operacao
administrativa, o administrador deve **ler a configuracao vigente** antes de
repetir a operacao.

### O swap

O swap e a reatribuicao de **uma** referencia, sob a mesma secao critica
administrativa que fez a verificacao de `expected_revision` e a persistencia
(D-052). Nao ha passo intermediario dentro dele e nao ha caminho de falha
parcial: ou a referencia nova esta publicada, ou a antiga continua. O ciclo de
vida do runtime aposentado e problema separado, e esta em D-054.

## D-049 — A Admin API nao executa SQL

Nao existirao `/query`, `/sql`, `/execute` nem equivalente.

A execucao de SQL continua exclusivamente pelo caminho Gateway/MCP, que e onde
vivem o validator, a proveniencia, o masking e os limites. Um segundo caminho
de query seria um segundo lugar para errar, com privilegio administrativo — ou
seja, o pior dos dois mundos.

A Admin API administra politicas. Nao e um cliente de banco.

## D-050 — Protecoes estruturais nao sao editaveis pela Admin API

Item criado para fechar vulnerabilidade nao pode ser desligado por
configuracao administrativa. O caso concreto e `denied_relations` com
`pg_statistic` e `pg_stats` (D-039): torna-lo editavel reabriria um finding
CRITICAL por uma chamada de API.

Vale igualmente para qualquer controle que enfraqueca invariante critico. NAO
existirao campos como `read_only: false`, `allow_multiple_statements: true` ou
`disable_sql_validation: true` — nem recusados, mas inexistentes.

Essas protecoes podem ser EXIBIDAS como read-only num front futuro. Ver, sim;
alterar, nao.

## D-051 — Rules e exceptions terao IDs administrativos estaveis

CRUD por indice de lista e fragil: remover a regra 2 renumera a 3, e duas telas
abertas ao mesmo tempo editam coisas diferentes achando que editam a mesma.

O schema evoluira para incluir um ID estavel por regra e por exception.

A ORDEM das masking rules continua semanticamente relevante — "first match
wins" (D-004) — entao ID estavel nao substitui ordenacao: sao coisas distintas,
e a reordenacao precisa de operacao propria.

## D-052 — Controle otimista por revision, dentro de uma secao critica

A configuracao administrativa tera uma `revision` inteira crescente. Operacoes
de escrita informam `expected_revision`; se ela diferir da atual, a operacao e
recusada por conflito e nada e sobrescrito.

E o minimo para dois administradores nao se sobrescreverem em silencio. Nao e
sistema distribuido: um inteiro no arquivo e uma comparacao.

### Toda operacao administrativa de escrita ou reload e serializada

Comparar `expected_revision` fora de uma secao critica nao controla nada: duas
requisicoes leem a mesma revision atual, ambas aprovam a comparacao, e a
segunda sobrescreve a primeira — que ja respondeu sucesso ao seu administrador.
O controle otimista viraria decoracao.

Portanto: **a verificacao de `expected_revision`, a criacao da nova `revision`,
a persistencia e o swap pertencem a uma unica secao critica administrativa.**
Um lock de escrita administrativo, um por processo, adquirido no inicio da
operacao e liberado no fim.

Consequencias:

- **Duas requisicoes com o mesmo `expected_revision` nao podem ambas vencer.**
  A primeira a entrar na secao critica vence e publica `revision + 1`; a
  segunda encontra a revision ja incrementada e recebe conflito (HTTP 409).
  Nao ha ordem de chegada garantida entre as duas — a garantia e que exatamente
  uma vence.
- As operacoes administrativas de escrita sao **serializadas entre si**. Sao
  raras e humanas; serializar nao custa nada.
- Esse lock **nao** toca o caminho de query. Ele cobre a operacao
  administrativa inteira; a query so interage com o runtime pelo mecanismo de
  aquisicao de D-054, cuja secao critica e curta e separada.
- Leitura administrativa (`GET`) nao entra nessa secao critica: le a referencia
  publicada e responde.

A `revision` e persistida **dentro** do proprio arquivo de configuracao. Se
ficasse fora, arquivo e revision poderiam divergir na janela de crash de D-048,
e o controle otimista passaria a mentir depois de um restart.

## D-053 — `enabled` fica fora da primeira versao administrativa

A primeira versao tera criar, editar, remover e reordenar. NAO tera um campo
`enabled` por regra.

Motivo: uma regra desabilitada precisaria ocupar posicao na lista sem
participar do matching, o que interage com a ordem ("first match wins"), com os
indices de regra que o `derived_rule_index` carrega (D-043) e com a compilacao
da policy. Remover a regra tem o mesmo efeito pratico e nenhuma dessas
consequencias.

Registrado como evolucao futura possivel, nao como omissao.

## D-054 — Coordenacao entre queries em andamento e reload

O passo "fechar o runtime antigo somente quando nenhuma query ainda estiver
usando-o" precisa de um mecanismo, e a escolha errada quebra uma das duas
garantias: ou uma query e interrompida no meio, ou o adapter antigo vaza.

**O fechamento do adapter antigo nao pode interromper uma query em andamento.**
Fechar a conexao psycopg sob uma query em execucao aborta a consulta e produz
um erro que o cliente nao causou.

Mecanismo adotado: **referencia imutavel + contagem de uso (refcount) + marca
de aposentadoria (retired)**.

- O runtime e um objeto **imutavel** que agrega config, engine, `SqlPolicy`,
  settings e adapter. Trocar de runtime e reatribuir uma unica referencia.
- Toda query **adquire** a referencia atual uma vez, no inicio, e usa **essa**
  referencia ate o fim. Nao ha releitura no meio: e isso que garante "o antigo
  inteiro ou o novo inteiro".
- A aquisicao incrementa o contador do runtime; o fim da query o decrementa,
  sempre em `finally`.
- O swap publica o runtime novo e **aposenta** o antigo. O antigo e fechado
  quando seu ultimo usuario o libera — nao pelo reload.

### Regras que a implementacao precisa cumprir

1. **O reload nao bloqueia esperando queries antigas.** Ele publica o runtime
   novo, marca o antigo como `retired`, decide se pode fecha-lo ja, e retorna.
   Uma query de 30 s nao segura a resposta da operacao administrativa.

2. **O runtime antigo e marcado como `retired` no swap**, dentro da mesma
   secao critica que publica o novo. `retired` e um estado do proprio objeto
   runtime, nao uma variavel do reload: quem decide fechar precisa ler
   `retired` e o contador **juntos**.

3. **Aquisicao, swap, alteracao do refcount e decisao de fechamento usam a
   mesma sincronizacao.** Todas essas operacoes leem ou escrevem o par
   `(retired, refcount)`, e uma decisao de fechamento tomada sobre uma leitura
   parcial fecha um runtime em uso ou vaza um aposentado. Um unico lock curto
   cobre as quatro; ele **nao** cobre a execucao da query, so a transicao de
   estado.

4. **O ultimo release fecha o runtime aposentado exatamente uma vez.** O
   fechamento pertence a transicao que leva o contador a zero **com `retired`
   verdadeiro**, e essa transicao acontece uma so vez. Nao ha "verificar e
   depois fechar" fora do lock, nem fechamento idempotente por tentativa e
   erro: a condicao e decidida sob o lock, e o `close` do adapter ocorre depois
   de solta-lo — fora da secao critica, porque fechar uma conexao psycopg pode
   demorar.

5. **Se o runtime antigo ja estiver sem usuarios no momento do swap, ele e
   fechado imediatamente.** Esse e o caso comum: um Gateway ocioso recebe um
   reload e nao ha nada a esperar. A condicao e a mesma da regra 4 —
   `retired` verdadeiro e contador zero — avaliada uma vez no proprio swap.
   Sem isso, um runtime sem nenhuma query em andamento nunca seria fechado,
   porque nao havera release algum para dispara-lo.

6. **Nenhuma query adquire um runtime depois que ele foi aposentado.** A
   aquisicao le a referencia publicada e incrementa sob o mesmo lock; um
   runtime aposentado ja nao e a referencia publicada. Se, por qualquer
   caminho, uma tentativa de aquisicao encontrar um runtime com `retired`
   verdadeiro, ela **nao** o adquire — nao o incrementa e nao o usa.

**Um runtime aposentado vive ate a query liberar a referencia — nao existe
teto de tempo, e o `statement_timeout` NAO e um.** Ele limita a execucao do
statement dentro do PostgreSQL; nao limita bloqueio de rede, o `fetchmany` em
lotes (D-018), a canonicalizacao (D-015), o masking por celula, a serializacao
da resposta, nem um cliente que pare de consumir.

O que se limita e o NUMERO de aposentados abertos, nao a duracao de cada um.

Consequencias que a implementacao precisa respeitar:

- **A troca da referencia e a aquisicao precisam ser mutuamente atomicas.** Sem
  isso existe a janela: ler a referencia, o reload trocar e fechar, e so entao
  incrementar — uma query executando sobre uma conexao ja fechada.
- **O fechamento e assincrono em relacao ao reload.** O reload nao espera; quem
  fecha e o ultimo release, ou o proprio swap quando ja nao ha usuarios.
- **O lock nao cobre a execucao da query.** Serializar queries no reload
  transformaria uma operacao administrativa num stall de todo o Gateway.

Alternativa descartada: lock compartilhado de leitura/escrita, com a query
segurando o lock de leitura durante toda a execucao. E mais simples de
escrever, mas um reload passa a esperar a query mais longa segurando o lock de
escrita, e queries novas ficam bloqueadas atras dele. Um `statement_timeout` de
30 s vira 30 s de indisponibilidade administrativa e de fila.

Sao tres locks distintos, e confundi-los quebra alguma das garantias:

| lock | cobre | duracao |
|---|---|---|
| administrativo (D-052) | `expected_revision`, nova revision, persistencia, swap | a operacao administrativa inteira |
| de ciclo de vida (esta decisao) | aquisicao, swap, refcount, decisao de fechamento | transicao de estado, nunca a query |
| de conexao (D-034) | acesso a conexao psycopg de **um** runtime | a execucao da query |

Isto substitui, para o reload, o `threading.Lock` que hoje serializa as
consultas em `Gateway.query` (D-034). Aquele lock existe porque ha **uma**
conexao psycopg e o SDK MCP executa tools numa thread pool — e continua
necessario **por runtime**, ja que cada runtime tem seu proprio adapter. O
refcount e ortogonal: um coordena o acesso a conexao, o outro coordena o ciclo
de vida do runtime.
