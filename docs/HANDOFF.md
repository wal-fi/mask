# Handoff

Estado do projeto ao final da sessao que implementou a **Fase 2**.
Documento de entrada para a proxima sessao.

Leitura obrigatoria antes de continuar: `CLAUDE.md`, `docs/ARCHITECTURE.md`,
`docs/SECURITY.md`, `docs/MASKING-SPEC.md`, `docs/ROADMAP.md`,
`docs/DECISIONS.md`.

---

## 1. Fases concluidas

**FASE 1 — Config Loader + Masking Engine puro.** Concluida.
**FASE 2 — PostgreSQL Adapter + ResultSet Masking.** Concluida e verificada
contra PostgreSQL real.

As Fases 3 a 6 **nao foram iniciadas**.

Entregue na Fase 2:

- `PostgresAdapter`: conexao psycopg3, execucao de consulta, leitura em lotes
- extracao de `output_name` a partir de `cursor.description`
- aplicacao do Masking Engine sobre o result set
- sanitizacao de erros do PostgreSQL
- canonicalizacao deterministica de valores por tipo, com falha fechada
- 241 testes novos (497 no total)

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

`pglast` continua **nao** instalado: pertence a Fase 4.

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
   (Fase 5)                (Fase 4)     (Fase 4)          (Fase 2)
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

**Na Fase 2 `origin_name` e sempre `None`**: o matching usa somente
`output_name`. Lineage e a Fase 3.

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
  db/                    <- Fase 2
    columns.py           describe_columns: cursor.description -> ColumnDescriptor
    result.py            MaskedResult
    sanitize.py          psycopg.Error -> DatabaseError generico
    postgres.py          PostgresAdapter

tests/
  conftest.py              fixtures, DSN e dublês de conexao/cursor
  test_config_loader.py     35     test_canonical.py         52
  test_matching.py          38     test_db_columns.py        13
  test_transformers.py      94     test_db_masking.py        47
  test_engine.py            36     test_db_errors.py         37
  test_purity.py            32     test_db_leakage.py        41
  test_leakage.py           13     test_db_integration.py    51
  test_config_hazards.py     8
```

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

## 6. Resultado das verificacoes

Com `MASKGW_TEST_DSN` apontando para PostgreSQL 16 em Docker:

```text
pytest   497 passed
ruff     All checks passed
ruff     40 files already formatted
mypy     Success: no issues found in 40 source files  (strict)
```

Sem `MASKGW_TEST_DSN`: `447 passed, 50 skipped`.

## 7. Lacuna da Fase 2, deliberada

`SELECT cpf AS documento` passa **em claro**. Sem lineage o adapter so conhece
o alias, e `documento` nao casa nenhuma regra.

Fixado por `TestPhaseTwoAliasGap`, em `tests/test_db_masking.py` e em
`tests/test_db_integration.py`. **Esses testes devem ser invertidos na Fase 3.**

## 8. Sondagem para a Fase 3 (medida, nao suposta)

`docs/ARCHITECTURE.md` afirmava que `table_oid` e `table_column` sao expostos
por psycopg3 em `cursor.description`. **Nao sao** (psycopg 3.3.4): o `Column`
oferece apenas `name`, `type_code`, `display_size`, `internal_size`,
`precision`, `scale` e `null_ok`. Os campos existem em
`cursor.pgresult.ftable(i)` e `cursor.pgresult.ftablecol(i)`. O documento ja
foi corrigido.

Medicao por cenario, contra PostgreSQL 16:

| cenario | `ftable` | origem resolvivel? |
|---|---|---|
| `SELECT cpf` | oid da tabela | sim |
| `SELECT cpf AS documento` | oid da tabela | **sim** |
| `SELECT *` | oid da tabela, por coluna | sim |
| JOIN | oid da tabela de cada coluna | sim |
| subquery | oid da tabela | sim |
| `SELECT d FROM (SELECT cpf AS d ...)` | oid da tabela | **sim** |
| CTE | oid da tabela | sim |
| view | **oid da VIEW**, nao da tabela base | parcial — ver abaixo |
| `cpf::text` | oid da tabela | sim |
| **UNION ALL** | **0** | **nao** |
| `md5(cpf)` | 0 | nao (esperado) |
| `substr(cpf,1,3) AS x` | 0 | nao (esperado) |
| literal | 0 | nao (esperado) |

Dois achados que o design da Fase 3 precisa tratar:

- **UNION perde a proveniencia.** `SELECT cpf FROM a UNION ALL SELECT cpf FROM b`
  devolve `ftable = 0`. Hoje o `output_name` ainda salva o caso, mas
  `SELECT cpf AS documento FROM a UNION ALL ...` nao teria nem nome nem origem.
- **View resolve para a coluna da view, nao da tabela base.** Uma view
  `SELECT cpf AS documento FROM cliente` daria `origin_name = "documento"`.
  Resolver ate a tabela base exigiria percorrer `pg_rewrite`.

A cobertura por alias e melhor do que `docs/THREAT-MODEL.md` supunha: alias em
subquery preserva a origem.

## 9. Sondagem para a Fase 4

`SELECT 1 AS a; SELECT 2 AS b` **e aceito** pelo psycopg3 quando a consulta nao
leva parametros: o protocolo simples permite multiplos statements, `fetchall()`
devolve o primeiro result set e `nextset()` retorna `True`. Com parametros o
protocolo estendido rejeita (`cannot insert multiple commands into a prepared
statement`).

Ou seja: **o bloqueio de multiplos statements da Fase 4 e obrigatorio** e nao
pode depender do driver. Ate la o adapter e componente interno, sem superficie
MCP.

## 10. Fase 3 — objetivo e criterios

**FASE 3 — Column provenance/lineage e protecao contra alias.**

Escopo (`docs/ROADMAP.md`): resolucao de `origin_name` via `table_oid` +
`table_column` cruzados com `pg_attribute`; `ColumnDescriptor` completo;
matching por `output_name` OR `origin_name`; exceptions avaliadas contra os
dois nomes.

O ponto de extensao ja existe: `maskgw/db/columns.py::describe_columns`. Hoje
ele devolve `origin_name=None` para toda coluna.

Criterios de aceite:

1. `SELECT cpf AS documento` retorna mascarado.
2. Alias em JOIN, subquery, CTE, UNION e view retornam mascarados.
3. Expressao (`table_oid = 0`) nao quebra o pipeline: `origin_name` e `None` e
   o matching recai sobre `output_name`.
4. Os testes de lacuna da Fase 2 sao invertidos.

Cuidados ja identificados: o custo de consultar `pg_attribute` por consulta
(cache por `(oid, attnum)`), e os dois achados da secao 8.

## 11. O que NAO foi implementado

- resolucao de proveniencia / lineage de coluna (Fase 3)
- SQL parser e query validator com pglast (Fase 4)
- conexao read-only, `statement_timeout`, limite de linhas (Fase 4)
- bloqueio de multiplos statements (Fase 4)
- MCP Server (Fase 5)
- `gateway/` e `audit/` (Fases 4 e 5); nenhum modulo importa `logging`
- testes adversariais end-to-end (Fase 6)

Fora do escopo do MVP, em `docs/FUTURE-HARDENING.md`: bloqueio de WHERE /
ORDER BY / GROUP BY sobre dados sensiveis, supressao de agregacoes, controle de
cardinalidade, RBAC, column-level GRANT automatico, JSONB deep inspection,
transformers Python customizados, multi-tenant e default deny.

Regra do projeto: nao avancar de fase sem aprovacao, nem com teste falhando.
