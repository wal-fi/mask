# Handoff

Estado do projeto ao final da sessao que implementou a **Fase 4**.
Documento de entrada para a proxima sessao.

Leitura obrigatoria antes de continuar: `CLAUDE.md`, `docs/ARCHITECTURE.md`,
`docs/SECURITY.md`, `docs/MASKING-SPEC.md`, `docs/ROADMAP.md`,
`docs/DECISIONS.md`.

---

## 1. Fases concluidas

**FASE 1 — Config Loader + Masking Engine puro.** Concluida.
**FASE 2 — PostgreSQL Adapter + ResultSet Masking.** Concluida.
**FASE 3 — Column provenance / lineage.** Concluida.
**FASE 4 — SQL validation + execution safety.** Concluida e verificada contra
PostgreSQL real.

As Fases 5 e 6 **nao foram iniciadas**. Nao existe uma linha de MCP.

Entregue na Fase 4:

- pacote `sql/`: parser, validator e politica de funcoes, com pglast
- um statement executavel, raiz `SelectStmt`, nenhum `*Stmt` aninhado,
  `IntoClause`/`LockingClause` recusadas
- politica de funcoes: namespace `pg_` deny-by-default
- sessao read-only e `statement_timeout` aplicados pelo PostgreSQL e
  conferidos apos a conexao
- `max_rows` com `truncated`; a linha N+1 nunca e mascarada nem devolvida
- capability check de proveniencia, fatal no startup
- 267 testes novos (875 no total)

## 2. Stack e dependencias

Python >= 3.11.

| Pacote | Uso | Desde |
|---|---|---|
| psycopg[binary] | driver PostgreSQL | Fase 2 |
| pydantic | validacao de configuracao | Fase 1 |
| PyYAML | leitura do `masking.yaml` | Fase 1 |
| pytest | testes | Fase 1 |
| ruff | lint + format | Fase 1 |
| mypy | type-check strict | Fase 1 |

| pglast | parser oficial do PostgreSQL | Fase 4 |

Configuracao em `pyproject.toml`. Nao ha instalacao editavel: o pytest resolve
o pacote via `pythonpath = ["src"]`.

### Ambiente

O `.venv/` versionado ao lado deste repositorio foi criado no **Windows**
(`C:\Users\...`, Python 3.11.3) e nao funciona em macOS ou Linux. Ele esta em
`.gitignore` e nao deve ser usado como referencia.

Recrie o ambiente a partir do `pyproject.toml`:

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

Comandos (ajuste `.venv/bin` para `.venv/Scripts` no Windows):

```bash
.venv/bin/python -m pytest
```

```bash
.venv/bin/python -m ruff check src tests && .venv/bin/python -m ruff format --check src tests
```

```bash
.venv/bin/python -m mypy src tests
```

### Variaveis de ambiente

| Variavel | Uso | Obrigatoria? |
|---|---|---|
| `MASKGW_HMAC_KEY` | chave do `hmac_sha256`, minimo 32 caracteres | sim, se alguma regra usar `hmac_sha256` |
| `MASKGW_TEST_DSN` | DSN do PostgreSQL dos testes de integracao | nao; sem ela os testes `integration` dao SKIP |

Nenhum usuario, senha, host ou DSN esta escrito no codigo ou nos testes.

Para rodar a integracao com um PostgreSQL descartavel em Docker:

```bash
docker run -d --name maskgw-pg -e POSTGRES_PASSWORD="$(openssl rand -base64 24)" -e POSTGRES_DB=maskgw_test -p 55432:5432 postgres:16-alpine
```

Depois exporte `MASKGW_TEST_DSN` apontando para ele. Testcontainers foi
deliberadamente **nao** adotado.

## 3. Arquitetura consolidada

```text
AI Client -> MCP Server -> Gateway -> Query Validator -> DB Adapter -> PostgreSQL
   (Fase 5)                (Fase 5)     (Fase 4)          (Fase 2)
                                                              |
                                              Result Set + Column Metadata
                                                              |
                                MaskingEngine (Exception -> Masking -> Original)
                                                              |
                                                        MaskedResult
```

Pipeline por coluna, default **ALLOW**:

```text
EXCEPTION MATCH -> ORIGINAL
MASKING MATCH   -> TRANSFORMER
NO MATCH        -> ORIGINAL
```

Desde a Fase 3 o matching avalia `output_name` OR `origin_name`, com
`origin_name` resolvido a partir da metadata do PostgreSQL. O default ALLOW e a
prioridade absoluta das exceptions nao mudaram.

## 4. Estrutura dos modulos

```text
src/maskgw/
  errors.py              ConfigError, TransformerError, DatabaseError
  secretsource.py        SecretProvider, EnvSecretProvider, MappingSecretProvider
  config/
    models.py            modelos Pydantic (extra="forbid", frozen)
    loader.py            load_config, load_config_text, parse_config
  masking/               <- nucleo PURO: sem banco, MCP, rede ou psycopg
    descriptor.py        ColumnDescriptor
    canonical.py         canonicalize  (Fase 2, D-015)
    rules.py             MatchMode, MatchSpec, MaskingRule, MaskingException, MaskingPolicy
    matcher.py           RuleMatcher, ExceptionMatcher
    engine.py            Action, Decision, MaskingEngine
    transformers/        base, params, registry, hashes, regex, randomize, simple
  db/                    <- Fases 2, 3 e 4
    columns.py           ColumnOrigin, describe_columns
    provenance.py        ftable/ftablecol -> catalogo -> origem  (Fase 3)
    capabilities.py      check_provenance_capability             (Fase 4)
    result.py            MaskedResult (+ truncated)
    sanitize.py          psycopg.Error -> DatabaseError / QueryTimeout
    postgres.py          PostgresAdapter: read-only, timeout, row limit
  sql/                   <- Fase 4
    parser.py            pglast; um statement executavel
    validator.py         allowlist de nos da AST
    policy.py            politica de funcoes, extensivel

tests/
  conftest.py                    fixtures, DSN e dublês de conexao/cursor
  test_config_loader.py     35   test_canonical.py             52
  test_matching.py          44   test_db_columns.py            13
  test_transformers.py      94   test_db_masking.py            55
  test_engine.py            36   test_db_errors.py             38
  test_purity.py            32   test_db_leakage.py            46
  test_leakage.py           13   test_db_integration.py        80
  test_config_hazards.py     8   test_db_provenance.py         36
  test_config_gateway.py    33   test_pgresult_metadata.py     27
                                 test_sql_parser.py            36
                                 test_sql_validator.py        149
                                 test_execution_safety.py      48
```

`tests/test_pgresult_metadata.py` nao testa codigo do Gateway: mede o que o
PostgreSQL e o psycopg devolvem. Se uma versao futura mudar esse contrato, ele
quebra antes do resto.

`masking/` continua puro: `test_purity.py` verifica por AST e em subprocesso
que importar `maskgw.masking` nao carrega `maskgw.db` nem psycopg, e a
contraprova confirma que `maskgw.db` de fato depende de psycopg.

Modulos ainda inexistentes: `maskgw/sql/`, `maskgw/gateway/`, `maskgw/mcp/`,
`maskgw/audit/`.

## 5. Decisoes

D-001 a D-014 na Fase 1; D-015 a D-019 na Fase 2. Detalhamento em
`docs/DECISIONS.md`.

| # | Decisao |
|---|---|
| D-015 | Canonicalizacao explicita por tipo, nunca `str()`; tipo desconhecido falha fechado. Emenda D-011 |
| D-016 | `autocommit=True` mais rollback defensivo; nunca COMMIT como limpeza |
| D-017 | Erro sanitizado levantado FORA do `except`, para zerar tambem `__context__` |
| D-018 | Leitura em lotes com `fetchmany`; nao e row limiting |
| D-019 | SQLSTATE classifica internamente, mas nao entra na mensagem |
| D-020 | `DERIVED` (o PostgreSQL afirma) e `UNKNOWN` (nos admitimos) sao distintos |
| D-021 | Cache `(oid, attnum)` por conexao; falha NAO e cacheada |
| D-022 | View resolve para a coluna da view; sem lineage recursivo |
| D-023 | Proveniencia resolvida antes de qualquer linha ser lida |
| D-024 | `origin_schema`/`origin_table` sao auditoria, nao criterio de matching |
| D-025 | Falha de proveniencia nao muda a politica; nao ha nova regra fail-closed |
| D-026 | Capability check de proveniencia, fatal no startup |
| D-027 | Funcoes: namespace `pg_` deny-by-default; resto allow com denylist |
| D-028 | Read-only e timeout por `options` do DSN, conferidos apos conectar |
| D-029 | Duas portas no adapter: `execute_validated` e `execute` sem validacao |
| D-030 | Row limit devolve ate `max_rows` e marca `truncated`; N+1 descartada |
| D-031 | Validacao por tipo de no da AST, incluindo `*Stmt` aninhados |
| D-032 | Erros de parser e validator nao citam a consulta |

## 6. Resultado das verificacoes

Com `MASKGW_TEST_DSN` apontando para PostgreSQL 16 em Docker:

```text
pytest   875 passed
pytest   155 passed  (-m integration)
ruff     All checks passed
ruff     53 files already formatted
mypy     Success: no issues found in 53 source files  (strict)
```

Sem `MASKGW_TEST_DSN`: `720 passed, 155 skipped`.

## 7. Protecao contra alias: o que a Fase 3 fechou

`SELECT cpf AS documento` agora retorna **mascarado**. Cobertos e verificados
contra banco real:

| cenario | resultado |
|---|---|
| `SELECT cpf AS documento` | mascarado |
| alias dentro de subquery | mascarado |
| alias dentro de CTE | mascarado |
| alias sobre JOIN | mascarado |
| alias sobre cast (`cpf::text AS documento`) | mascarado |
| alias sobre view | mascarado (`provenance_kind = VIEW`) |
| `SELECT *`, nomes duplicados | cada posicao com origem propria |
| identificador entre aspas / maiusculas | mascarado |

## 8. Limitacoes de proveniencia que permanecem

Medidas, nao supostas (`tests/test_pgresult_metadata.py`).

| cenario | `ftable` | efeito |
|---|---|---|
| coluna direta, alias, `SELECT *`, JOIN | oid da relacao | origem resolvida |
| subquery, alias em subquery, CTE, cast | oid da relacao | origem resolvida |
| view | **oid da VIEW** | origem e a coluna DA VIEW |
| **UNION** | **0** | sem origem |
| expressao, literal, agregado | 0 | sem origem (esperado) |

Tres limitacoes conhecidas, todas em `docs/FUTURE-HARDENING.md`:

- **UNION nao preserva proveniencia.** Com o nome preservado o `output_name`
  ainda mascara, mas `SELECT cpf AS documento FROM a UNION ALL SELECT cpf FROM b`
  passa em claro. E o bypass mais barato que sobrou.
- **View que renomeia apaga o nome original.** `CREATE VIEW v AS SELECT cpf AS
  documento FROM cliente` da `origin_name = "documento"`. Sem lineage recursivo
  por `pg_rewrite` nesta fase (D-022).
- **Role sem leitura em `pg_catalog` reabria o bypass em silencio.** Fechado na
  Fase 4: `check_provenance_capability` roda no `connect()` e o processo nao
  sobe sem a capacidade (D-026). A resolucao em runtime segue tolerante a falha
  (D-025), mas a instalacao deixou de poder estar errada sem ninguem saber.

Expressoes continuam sendo o bypass residual principal do MVP:
`SELECT substr(cpf,1,3) AS x` passa em claro.

## 8b. Configuracao nova da Fase 4

```yaml
database:
  statement_timeout_ms: 30000   # 100 .. 600000
  max_rows: 1000                # 1 .. 1000000
sql:
  allowed_pg_functions: []      # acrescenta a allowlist do namespace pg_
  denied_functions: []          # acrescenta a denylist; a negacao vence
```

Ambas as secoes sao opcionais e validadas fail-closed. DSN e credenciais
continuam fora do `masking.yaml`: declarar `password`, `dsn` ou `host` ali e
erro fatal, nao campo ignorado.

`load_config` continua devolvendo so a `MaskingPolicy`; `load_gateway_config`
devolve tambem `database` e `sql`.

## 9. Sondagem para a Fase 4

`SELECT 1 AS a; SELECT 2 AS b` **e aceito** pelo psycopg3 quando a consulta nao
leva parametros: o protocolo simples permite multiplos statements, `fetchall()`
devolve o primeiro result set e `nextset()` retorna `True`. Com parametros o
protocolo estendido rejeita (`cannot insert multiple commands into a prepared
statement`).

Ou seja: **o bloqueio de multiplos statements da Fase 4 e obrigatorio** e nao
pode depender do driver. Ate la o adapter e componente interno, sem superficie
MCP.

Ponto de atencao herdado da Fase 3 (D-023): a proveniencia e resolvida com um
cursor proprio na mesma conexao, antes do primeiro `fetchmany`. Isso e seguro
com o cursor client-side do psycopg3, que ja materializou o resultado. Se o row
limit da Fase 4 introduzir cursor server-side, essa ordem precisa ser
reavaliada.

## 10. Fase 5 — objetivo e criterios

**FASE 5 — MCP Server.**

Escopo (`docs/ROADMAP.md`): servidor MCP expondo a capacidade de consulta;
handlers finos, sem nenhuma regra de masking; nenhuma superficie que permita ao
cliente ler, alterar ou desabilitar regras; logging estruturado com metadata.

Criterios de aceite:

1. Fluxo end-to-end com cliente MCP real.
2. Inspecao do codigo confirma que nenhum caminho devolve valor original antes
   do Masking Engine.
3. Tentativa do cliente de alterar configuracao e rejeitada.

O ponto de entrada ja existe e esta pronto: `PostgresAdapter.execute_validated`.
Os handlers MCP devem chamar exclusivamente essa porta — nunca `execute`.

Dois cuidados herdados:

- **`audit/` estreia aqui, e com ele o primeiro `logging` do projeto.** Ate
  hoje nenhum modulo importa `logging`, e `tests/test_leakage.py` varre `src/`
  inteiro para garantir isso (D-012). Esse teste precisara ser reescrito para
  permitir log APENAS de metadata, sem afrouxar a garantia.
- `MaskedResult.truncated` precisa chegar ao cliente MCP: uma IA que nao saiba
  que o resultado foi cortado tirara conclusoes erradas.

## 11. O que NAO foi implementado

- MCP Server (Fase 5) — nao existe `maskgw/mcp/`
- `gateway/` e `audit/` (Fase 5); nenhum modulo importa `logging`
- testes adversariais end-to-end (Fase 6)

Fora do escopo do MVP, em `docs/FUTURE-HARDENING.md`: bloqueio de WHERE /
ORDER BY / GROUP BY sobre dados sensiveis, supressao de agregacoes, controle de
cardinalidade, RBAC, column-level GRANT automatico, JSONB deep inspection,
transformers Python customizados, multi-tenant e default deny.

Regra do projeto: nao avancar de fase sem aprovacao, nem com teste falhando.
