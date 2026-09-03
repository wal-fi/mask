# Handoff

**Documento de entrada. Comece por aqui.**

Estado do projeto ao final da Etapa 8 da Fase 7. O MVP esta completo, as
Etapas 1–8 da Fase 7 estao concluidas e a suite esta verde contra PostgreSQL 16
real. A proxima tarefa e a Etapa 9 — rotas de escrita e adocao com backup —,
ainda nao iniciada (secao 10).

Antes de comecar qualquer fase, confira `git status --short`: a arvore precisa
estar limpa. **Confira, nao presuma** — este documento nao pode afirmar o
estado do working tree no momento em que voce o le.

Ordem de leitura sugerida:

| documento | para que |
|---|---|
| `CLAUDE.md` | invariantes e pipeline; carregado em toda sessao |
| **este arquivo** | estado, como rodar, o que fazer a seguir |
| `docs/ARCHITECTURE.md` | modulos e responsabilidades |
| `docs/SECURITY.md` | invariantes de seguranca e o que exigir antes de expor |
| `docs/SECURITY-REVIEW.md` | 11 findings do red team, seis fechados |
| `docs/DECISIONS.md` | D-001 a D-057, com o motivo de cada uma |
| `docs/MASKING-SPEC.md` | semantica exata do pipeline |
| `docs/TEST-PLAN.md` | o que cada camada de teste cobre |
| `docs/THREAT-MODEL.md` | cenarios de ataque e o resultado medido |
| `docs/FUTURE-HARDENING.md` | propostas avaliadas, com custo e impacto |
| `docs/ROADMAP.md` | historico das seis fases |

---

## 1. Fases concluidas

**FASE 1 — Config Loader + Masking Engine puro.** Concluida.
**FASE 2 — PostgreSQL Adapter + ResultSet Masking.** Concluida.
**FASE 3 — Column provenance / lineage.** Concluida.
**FASE 4 — SQL validation + execution safety.** Concluida.
**FASE 5 — Gateway + MCP Server.** Concluida.
**FASE 6 — Security red team + hardening.** Concluida.
**FASE 6.1 — Fechamento dos bypasses criticos.** Concluida.

**As fases historicas 1–6.1 estao concluidas.**

Entregue na Fase 6.1:

- `sql/sensitivity.py`: analise de sensitividade por AST, uma vez por consulta
- F-01 (expressoes), F-02 (UNION + alias) e F-08 (exception via alias) FECHADOS
- H-1 corrigido: `mode` default das exceptions passou a `exact`
- 96 testes novos (1304 no total)

Andamento da Fase 7:

| etapa | estado | commit |
|---|---|---|
| 1 — IDs e revision no modelo do arquivo | concluida | `053cf66` |
| 2 — `RuntimeRegistry` | concluida | `3114c14` |
| 3 — runtime adquirido/liberado por query | concluida | `3c8de4c` |
| 4 — composition root e lifecycle | concluida | `7c06132` |
| 5 — filesystem seguro: verificações, lock exclusivo, escrita atômica, digest e limpeza de temporários | concluida | `d651fe0` |
| 6 — secao critica administrativa e fluxo completo de escrita/reload | concluida | `git log -- src/maskgw/admin` |
| 7 — aplicacao HTTP: auth, bind, anti-CSRF, headers, limites, handlers, rotas de leitura | concluida | `git log -- src/maskgw/admin/http` |
| 8 — `POST /admin/v1/config:validate` | concluida | `git log -- src/maskgw/admin/http/validate.py` |
| 9 — rotas de escrita e adocao com backup | proxima, nao iniciada | — |

O estado atual deve ser conferido com `git status --short --branch` e
`git rev-list --left-right --count origin/master...HEAD` antes de continuar;
nao o presuma a partir deste documento versionado.

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
| mcp | SDK MCP oficial, linha v2 (testado em 2.1.1) | Fase 5 |
| fastapi | fronteira HTTP administrativa (testado em 0.141.1) | Fase 7, Etapa 7 |
| uvicorn | servidor ASGI da Admin API (testado em 0.52.4) | Fase 7, Etapa 7 |

FastAPI e uvicorn sao usados **exclusivamente** pelo plano administrativo. O
MCP continua stdio only (D-036), e nenhuma porta e aberta sem
`MASKGW_ADMIN_ENABLED=1`.

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
| `MASKGW_DATABASE_DSN` | DSN do PostgreSQL do Gateway | sim |
| `MASKGW_CONFIG` | outro `masking.yaml` (default: `config/masking.yaml`) | nao |
| `MASKGW_TEST_DSN` | DSN do PostgreSQL dos testes de integracao | nao; sem ela os testes `integration` dao SKIP |
| `MASKGW_ADMIN_ENABLED` | `1` habilita a Admin API; **qualquer outro valor nao habilita** | nao; default desligado |
| `MASKGW_ADMIN_TOKEN` | token administrativo, minimo 32 caracteres | sim, se a Admin API estiver habilitada |
| `MASKGW_ADMIN_BIND` | `127.0.0.1` (default), `::1` ou `localhost` — **so loopback** | nao |
| `MASKGW_ADMIN_PORT` | porta da Admin API, 1..65535 (default `8765`) | nao |

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
   (stdio)                                (Fase 4)          (Fase 2)
                                                              |
                                              Result Set + Column Metadata
                                                              |
                       MaskingEngine (Derived -> Exception -> Masking -> Original)
                                                              |
                                                        MaskedResult
```

Pipeline por coluna, default **ALLOW**:

```text
DERIVED (a AST provou dependencia sensivel) -> TRANSFORMER
EXCEPTION (pelo nome autoritativo)           -> ORIGINAL
MASKING (por output_name ou origin_name)     -> TRANSFORMER
NO MATCH                                     -> ORIGINAL
```

Desde a Fase 3 o matching avalia `output_name` OR `origin_name`, com
`origin_name` resolvido a partir da metadata do PostgreSQL. Desde a Fase 6.1,
uma dependencia sensivel provada pela AST vem antes das exceptions; fora desse
ramo, o default ALLOW e a prioridade das exceptions sobre masking permanecem.

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
  sql/                   <- Fases 4 e 6.1
    parser.py            pglast; um statement executavel
    validator.py         allowlist de nos da AST
    policy.py            politica de funcoes e de relacoes
    sensitivity.py       dependencia sensivel por posicao  (Fase 6.1)
  gateway/               <- Fase 5
    models.py            QueryResult, QueryColumn, ErrorCategory, GatewayError
    service.py           Gateway.query: a fachada publica
  runtime/               <- Fase 7, Etapas 2 e 3
    registry.py          RuntimeRegistry: acquire/release, retired, close unico
  admin/                 <- Fase 7, Etapa 6; a secao critica, SEM HTTP
    errors.py            AdminError e as categorias fechadas (10.2 + D-056)
    document.py          MaskingFileConfig <-> bytes YAML, round-trip conferido
    service.py           AdminConfigService: a secao critica e a secao 7.4
    http/                <- Fase 7, Etapas 7 e 8; leitura + config:validate
      settings.py        enable, token, bind e porta: o passo 1 do startup
      middleware.py      Host, Origin, limite de corpo (413 autoritativo), auth, CT
      responses.py       forma unica de erro; categoria -> status HTTP
      schemas.py         modelos de resposta e de request, extra="forbid"/frozen
      views.py           respostas de leitura a partir de UM snapshot (D-057)
      validate.py        config:validate: valida e compila, SEM efeito (Etapa 8)
      app.py             oito rotas de leitura, config:validate e os handlers
      server.py          uvicorn em thread nao-daemon, com bind confirmado
  bootstrap/             <- Fase 7, Etapas 4, 6 e 7; composition root
    application.py       construcao e lifecycle ordenado dos dois planos
    main.py              entrypoint compartilhado, stderr sanitizado
  __main__.py            python -m maskgw -> bootstrap
  mcp/                   <- Fase 5
    server.py            build_mcp_server; a tool query_database
    __main__.py          python -m maskgw.mcp -> bootstrap
  audit/                 <- Fase 5
    log.py               QueryAudit, AuditLog; UNICO modulo que importa logging

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
                                 test_gateway.py               46
                                 test_mcp_server.py            54
                                 test_mcp_integration.py       43
                                 test_audit.py                 19

  test_sensitivity.py       54   <- Fase 6.1

  test_config_ids.py             <- Fase 7, Etapa 1
  test_runtime_registry.py       <- Fase 7, Etapa 2
  test_gateway_runtime.py        <- Fase 7, Etapa 3
  test_bootstrap.py              <- Fase 7, Etapas 4 e 6
  test_plan_separation.py        <- Fase 7, Etapas 4 e 6
  test_config_filesystem.py      <- Fase 7, Etapa 5
  test_admin_service.py     47   <- Fase 7, Etapa 6

  admin_http_support.py          <- Fase 7, Etapa 7 (apoio, nao e teste)
  test_admin_http_settings.py    51
  test_admin_http_boundary.py    88
  test_admin_http_surface.py    108
  test_admin_http_reads.py       64
  test_admin_http_lifecycle.py   35
  test_admin_http_leakage.py     20
  test_admin_http_mcp_coexistence.py  5  (integration)

  security/                      <- Fases 6 e 6.1, 209 testes adversariais
    test_attack_expressions.py        55
    test_attack_union_views.py        29
    test_attack_functions_catalog.py  29
    test_attack_oracle_errors.py      23
    test_attack_protocol.py           73
```

Os testes de protocolo MCP usam o cliente in-memory do SDK
(`mcp.Client(server)`), nunca a funcao Python decorada.

`tests/test_pgresult_metadata.py` nao testa codigo do Gateway: mede o que o
PostgreSQL e o psycopg devolvem. Se uma versao futura mudar esse contrato, ele
quebra antes do resto.

`masking/` continua puro: `test_purity.py` verifica por AST e em subprocesso
que importar `maskgw.masking` nao carrega `maskgw.db` nem psycopg, e a
contraprova confirma que `maskgw.db` de fato depende de psycopg.

Todos os modulos previstos ate a Etapa 6 existem: `masking/`, `config/`, `db/`,
`sql/`, `gateway/`, `runtime/`, `admin/`, `bootstrap/`, `mcp/` e `audit/`.

`gateway/factory.py` foi removido: construcao e lifecycle pertencem somente ao
composition root `bootstrap/`. A Etapa 5 adicionou `config/filesystem.py`, sem
HTTP: validacao fail-closed, lock sidecar pelo lifecycle, digest exato, escrita
atomica e limpeza seletiva de temporarios. A Etapa 6 adicionou `maskgw/admin/`,
tambem sem HTTP: a secao critica administrativa e o fluxo de escrita/reload.

A Etapa 7 adicionou `maskgw/admin/http/`, **somente leitura**: as oito rotas
`GET`/`HEAD` sob `/admin/v1`, autenticacao por bearer token, bind so em
loopback, anti-CSRF, limite de corpo, headers e os tres handlers de erro.
FastAPI e uvicorn entraram no `pyproject.toml` **agora**, e sao usados so ali.

O confinamento e estrutural e e teste com contraprova: importar `maskgw.admin`
**nao** carrega FastAPI, e importar `maskgw.admin.http` carrega. A secao critica
continua utilizavel — e testavel — sem servidor.

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
| D-033 | Proveniencia nao sai para o cliente MCP |
| D-034 | Uma conexao, aberta no startup; sem pool; consultas serializadas |
| D-035 | Auditoria por `request_id`; digest da SQL descartado (oraculo) |
| D-036 | Somente stdio; nenhuma porta de rede |
| D-037 | Argumentos extras sao IGNORADOS pelo SDK, nao recusados |
| D-038 | Erro do MCP: categoria fixa, mensagem curta, sem encadeamento |
| D-039 | Relacoes de estatistica (`pg_stats`) bloqueadas no validator |
| D-040 | Falha de resolucao rejeita a consulta; `DERIVED` nao. Emenda D-025 |
| D-041 | Bypass conhecido vira teste que o AFIRMA, nunca `skip` |
| D-042 | Exception responde pelo nome AUTORITATIVO; alias nao cria excecao |
| D-043 | Sensitividade por AST aplicada ao resultado da expressao; ambiguidade recusa |
| D-044 | Serializacao de linha inteira (`row_to_json`) e recusada |
| D-045 | `mode` default das exceptions passa a `exact`. Corrige H-1 |
| D-046 | Um passo entre niveis: nomes exportados por CTE e subquery |

D-047 a D-054 foram aprovadas antes da Fase 7; comportamento das Etapas 8–11
continua ausente. D-055 registra escolhas de implementacao da Etapa 6, D-056 as
da Etapa 7, e D-057 as duas correcoes exigidas na revisao da Etapa 7:

| # | Estado na Etapa 7 |
|---|---|
| D-047 | `LoadedConfig` preserva juntos o modelo validado do arquivo e os objetos runtime compilados; o admin so escreve a partir do modelo validado |
| D-048 | Fluxo completo implementado: validar, construir, conectar, persistir, trocar — com as semanticas dos dois lados do `os.replace` |
| D-049 | Separacao de planos imposta e verificada por AST; `admin/` nao executa SQL e nao conhece `gateway/` nem `mcp/` |
| D-050 | Protecoes estruturais preservadas; nao ha superficie que as edite |
| D-051 | IDs estaveis implementados; com `revision >= 1`, ID ausente falha no carregamento |
| D-052 | Secao critica administrativa implementada: adocao, `expected_revision`, digest, limite de aposentados, persistencia e swap sob um lock |
| D-053 | `enabled` continua ausente |
| D-054 | `RuntimeRegistry` implementa refcount, `retired` e fechamento unico; o fluxo administrativo respeita os tres |
| D-055 | Runtime candidato construido do documento reparseado dos bytes que serao persistidos; callback e leitura administrativa recebem copia profunda, nunca o documento do runtime publicado; vocabulario de erro proprio do admin; `admin_enabled` como parametro de composicao |
| D-056 | Escolhas da fronteira HTTP: cinco categorias de erro novas, ordem dos middlewares, contencao da excecao por fora do Starlette, bind na thread chamadora, parametros de transformer no registry e contadores de `/status`. Aprovada como decisao de contrato na revisao da Etapa 7 |
| D-057 | Snapshot administrativo coerente (`AdminSnapshot`, uma leitura por resposta); shutdown SEM timeout, com `join` integral da thread HTTP; referencia do servidor adotada antes de `start()`; `_closing` permanente, que impede `run()` e nunca se apresenta como `ready` |
| D-058 | Contrato de `config:validate` (Etapa 8): request e o documento candidato na raiz com schema HTTP proprio; `expected_revision` no corpo -> `422 SCHEMA_INVALID`; resposta de sucesso sao quatro booleanos; falha de compilacao -> `CONFIG_INVALID`; sem efeito, provado por contadores estruturais; correcao do `BodyLimitMiddleware` para cortar em `413` autoritativamente sob o roteador do FastAPI |

## 6. Resultado das verificacoes

Medido ao final da Etapa 5, com `MASKGW_TEST_DSN` apontando para PostgreSQL
16.15 descartavel:

```text
pytest   1418 passed, 8 skipped condicionais de plataforma (1426 coletados)
pytest    408 passed, 1018 deselected  (-m integration)
          405 testes dependentes de DSN executados; nenhum skip por falta de DSN
pytest    209 passed  (tests/security)
```

Medido ao final da Etapa 6, com `MASKGW_TEST_DSN` apontando para um
PostgreSQL 16.15 descartavel em Docker:

```text
pytest   1485 passed, 9 skipped  (1494 coletados)
         suite INTEIRA: nenhum deselect, nenhum skip por ausencia de DSN
           9 skips condicionais de plataforma
pytest    410 passed, 0 skipped  (-m integration)
pytest      2 passed  (TestRealReload, o reload contra banco real)
pytest     93 passed, 1 skipped  (admin + bootstrap + plan separation)
           repetido 10 vezes sem intermitencia
pytest     16 testes de concorrencia, isolamento e reload real repetidos 15
           vezes, sem intermitencia
ruff     All checks passed
ruff     93 files already formatted  (src + tests)
mypy     Success: no issues found in 93 source files  (strict, mypy 2.3.1)
git      diff --check sem erros
```

Medido ao final da Etapa 7, com `MASKGW_TEST_DSN` apontando para um
PostgreSQL 16.15 descartavel em Docker:

```text
pytest   1871 passed, 9 skipped  (1880 coletados)
         suite INTEIRA: nenhum deselect, nenhum skip por ausencia de DSN
           os MESMOS 9 skips condicionais de plataforma do baseline
pytest    415 passed, 0 skipped  (-m integration)
pytest    371 testes novos da Etapa 7
           os arquivos HTTP repetidos 9+ vezes sem intermitencia
ruff     All checks passed
ruff     109 files already formatted  (src + tests)
mypy     Success: no issues found in 109 source files  (strict, mypy 2.3.1)
git      diff --check sem erros
```

Medido ao final da Etapa 8 (ja com a correcao de D-058 — adotado sem ID como
`SCHEMA_INVALID` e escalares estritos), contra PostgreSQL 16.15 descartavel:

```text
pytest   1986 passed, 9 skipped  (1995 coletados)
         suite INTEIRA: nenhum deselect, nenhum skip por ausencia de DSN
           os MESMOS 9 skips condicionais de plataforma do baseline
pytest    415 passed, 0 skipped  (-m integration)
pytest     80 testes de config:validate (61 da entrega + 19 da correcao D-058)
ruff     All checks passed
ruff     112 files already formatted  (src + tests)
mypy     Success: no issues found in 112 source files  (strict, mypy 2.3.1)
git      diff --check sem erros
```

**A suite integral exigiu pilha ampliada neste host.** Com a pilha default do
Windows, `test_large_query_payload_does_not_crash` — a consulta com 100.000
termos somados — estoura a pilha da thread no walk recursivo da AST e derruba o
interpretador com `Windows fatal exception: stack overflow`. Nao e regressao:
reproduz identicamente no commit `d276c22`, anterior a Etapa 6. Nunca havia
aparecido aqui porque, sem DSN, esse teste dava SKIP.

O gate foi fechado rodando o processo de teste com pilha de thread de
**64 MiB**, valor que bastou. Nada foi deselecionado, pulado ou alterado no
teste, e **nenhuma correcao de producao foi feita**: a limitacao continua
aberta, na secao 11 e em `docs/SECURITY-REVIEW.md`.

```bash
.venv/Scripts/python.exe -c "import threading, pytest; threading.stack_size(64 * 1024 * 1024); raise SystemExit(pytest.main(['-q']))"
```

Os nove skips condicionais do host Windows sao quatro criacoes de symlink sem
privilegio, tres verificacoes de bits POSIX e dois `fsync` de diretorio POSIX
(um do filesystem, um do fluxo administrativo). Os testes Windows reais,
inclusive `msvcrt` entre processos e a omissao de `fsync` de diretorio,
passaram.

Nao ha distribuicao WSL neste host; os ramos POSIX permanecem na suite
condicional para execucao nativa em POSIX.

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

## 8. Proveniencia: o que o PostgreSQL informa, e o que resta aberto

Medidas, nao supostas (`tests/test_pgresult_metadata.py`).

| cenario | `ftable` | efeito |
|---|---|---|
| coluna direta, alias, `SELECT *`, JOIN | oid da relacao | origem resolvida |
| subquery, alias em subquery, CTE, cast | oid da relacao | origem resolvida |
| view | **oid da VIEW** | origem e a coluna DA VIEW |
| **UNION** | **0** | sem origem |
| expressao, literal, agregado | 0 | sem origem (esperado) |

A tabela acima descreve o que o PostgreSQL informa, e continua valendo. O que
mudou e o que o Gateway FAZ quando ele nao informa nada:

- **UNION e expressoes deixaram de vazar.** A analise de AST da Fase 6.1
  (`sql/sensitivity.py`) cobre os dois casos: `SELECT substr(cpf,1,3) AS x` e
  `SELECT cpf AS documento FROM a UNION ALL SELECT 'x'` saem mascarados
  (D-043). Ambiguidade entre regras e serializacao de linha inteira sao
  rejeitadas.
- **View que renomeia continua aberta.** `CREATE VIEW v AS SELECT cpf AS
  documento FROM cliente` da `origin_name = "documento"`, e a definicao da view
  nao esta na arvore da consulta. Nem a AST nem a proveniencia enxergam `cpf`.
  Sem lineage recursivo por `pg_get_viewdef` (D-022, F-03).
- **Falha de catalogo em runtime REJEITA a consulta.** Nao e mais tolerante:
  D-040 emendou D-025. Havia proveniencia que deveria ser resolvivel, e
  devolver o resultado assim entregaria em claro uma coluna que deveria estar
  mascarada. `DERIVED` (`ftable = 0`) continua sendo estado legitimo e segue o
  fluxo normal; falha operacional levanta `CapabilityError`, que chega ao
  cliente como `CONFIGURATION_ERROR` sanitizado. O check de startup (D-026)
  cobre a instalacao; este cobre o runtime.

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

## 9b. Como subir o servidor MCP

```bash
export MASKGW_HMAC_KEY="<chave com ao menos 32 caracteres>"
export MASKGW_DATABASE_DSN="host=... dbname=... user=... password=..."
python -m maskgw.mcp
```

`MASKGW_CONFIG` aponta outro `masking.yaml` (default: `config/masking.yaml`).

Transporte de dados: **stdio**. Falha em qualquer passo do startup termina o
processo com codigo 1, e o servidor nunca fica disponivel parcialmente
funcional.

**Sem `MASKGW_ADMIN_ENABLED=1`, nenhuma porta e aberta** — o processo e
exatamente o de antes da Etapa 7: nenhuma thread nova, nenhum lock de arquivo e
nenhum caminho de escrita.

### 9b.1 Como subir tambem a Admin API (opcional, Etapa 7)

```bash
export MASKGW_ADMIN_ENABLED=1
export MASKGW_ADMIN_TOKEN="<token com ao menos 32 caracteres>"
python -m maskgw.mcp
```

`MASKGW_ADMIN_BIND` (default `127.0.0.1`) aceita **so** `127.0.0.1`, `::1` e
`localhost`; `MASKGW_ADMIN_PORT` default `8765`. Bind fora de loopback, token
ausente ou curto, porta invalida e porta ocupada **impedem o startup** — e o
MCP nunca fica disponivel.

Leitura, com o token no header e so nele:

```bash
curl -H "Authorization: Bearer $MASKGW_ADMIN_TOKEN" http://127.0.0.1:8765/admin/v1/status
```

As oito rotas sao `GET`/`HEAD`: `status`, `config`, `rules`, `rules/{id}`,
`exceptions`, `exceptions/{id}`, `transformers` e `protected`. **Nao ha escrita
nesta etapa**, nao ha `/docs` e nao ha CORS. Token em query string ou cookie
nunca e aceito, e `Origin`/`Referer` presentes recusam a requisicao com `403`.

O startup anuncia host e porta em `stderr`; `stdout` continua exclusivamente
com o protocolo MCP.

## 9c. Postura de seguranca (leia antes de expor)

`docs/SECURITY-REVIEW.md` traz os 11 findings: **seis corrigidos**, cinco
aceitos. Os tres bypasses de uma linha de SQL foram fechados na Fase 6.1.

**Obrigatorio antes de expor:** revogar `EXECUTE` das funcoes de usuario para a
role do Gateway. `EXECUTE` e concedido a `PUBLIC` por padrao, e uma funcao
pre-existente que leia coluna sensivel devolve o valor sob o nome dela (F-04).

```sql
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
```

**Permanece aceito e nao fechado:**

- oraculo por predicado reconstroi um CPF em 11 consultas (F-07), fora do
  escopo do MVP
- view que renomeia coluna sensivel expoe o valor (F-03)
- default ALLOW: coluna sensivel com nome fora do padrao passa em claro

Conclusao: com o `EXECUTE` revogado e o oraculo aceito, **uso interno com
cliente semi-confiavel**. Nao adequado a exposicao externa — o transporte de
dados e stdio e nao ha autenticacao nele.

**A Admin API da Etapa 7 nao muda essa conclusao.** Ela e loopback-only, sem
TLS, com um token estatico e um unico papel; autentica o plano administrativo,
e nao o plano de dados. Antes de habilita-la:

- o token e um segredo de verdade: 32+ caracteres, de `MASKGW_ADMIN_TOKEN`, e
  nunca em linha de comando, onde apareceria em `ps`;
- quem alcanca `127.0.0.1` alcanca a porta. Numa maquina multiusuario, isso
  inclui outros usuarios locais;
- rotacao e trocar a variavel e reiniciar. Nao ha endpoint que rotacione
  secret, e nao havera.

## 9d. Mudancas de comportamento da Fase 6.1

Tres, todas documentadas e cobertas por teste:

1. **Exception nao e mais alcancavel por alias** (D-042). `SELECT cpf AS
   tipo_cpf` passou de original para mascarado. `SELECT tipo_cpf` nao mudou.
2. **Expressoes sobre coluna sensivel sao mascaradas ou recusadas** (D-043).
   `concat(cpf, email)` e `row_to_json(c)` passaram a ser recusadas.
3. **`mode` default das exceptions e `exact`** (D-045). Configuracao que
   dependa de exception por substring precisa declarar `mode: contains`.

## 9e. Mudancas de comportamento da Etapa 7

Uma so, e ela e opcional:

1. **Existe uma porta de rede, quando pedida.** Com `MASKGW_ADMIN_ENABLED=1` o
   processo passa a abrir um socket em loopback e a manter uma thread HTTP
   nao-daemon. **Sem a variavel, nada muda** — nenhuma porta, nenhuma thread,
   nenhum lock de arquivo —, e isso e teste, inclusive num processo real.

Mudancas internas que nao alteram comportamento observavel do MCP:

- `TransformerRegistry.register` aceita os nomes dos parametros de cada
  transformer, para que `GET /admin/v1/transformers` os publique a partir de uma
  fonte unica (D-056). Chamadas existentes continuam validas;
- `RuntimeRegistry` conta aquisicoes, e `AdminConfigService` conta operacoes
  administrativas, para os contadores de `/status`. Sao inteiros em memoria, nao
  historico, e **nao** antecipam `AdminAudit`;
- `AdminConfigService.snapshot()` devolve `AdminSnapshot` — `revision`,
  documento e `SqlPolicy` de UMA leitura do runtime publicado — e as funcoes de
  `views.py` passam a receber esse snapshot em vez do servico (D-057). As
  propriedades `revision`, `adopted`, `document` e `sql_policy` continuam
  existindo para leitura avulsa; o que nao se pode e combinar duas delas na
  mesma resposta;
- `AdminHttpServer.stop()` **bloqueia ate a thread HTTP terminar**: nao ha mais
  `shutdown_timeout`, e o limite passou para o `timeout_graceful_shutdown` do
  uvicorn, que encerra requisicoes arrastadas para que a thread sempre chegue ao
  fim (D-057). No caminho normal nada muda;
- o composition root adota a referencia do servidor ANTES de `start()`
  (`_build_admin_http` constroi sem iniciar), e `Application` ganhou `_closing`
  permanente: `run()` recusa uma aplicacao em desmontagem e `repr()` reporta
  `closing` em vez de `ready` (D-057);
- piso do uvicorn subiu para `>=0.29`, versao em que
  `timeout_graceful_shutdown` existe.

## 10. Como continuar

A Fase 7 esta em andamento, com as Etapas 1–8 concluidas. A proxima tarefa e
**exclusivamente a Etapa 9** — rotas de escrita e adocao com backup —, ainda nao
iniciada. A regra de nao avancar de etapa sem aprovacao continua valendo.

### A. Endurecer o que resta (inventario preservado; nao e a proxima etapa)

Os dois findings HIGH abertos nao precisam de codigo:

- **F-04** — revogar `EXECUTE` das funcoes de usuario para a role do Gateway.
  E operacional, e esta na secao 9c. Deveria ser feito antes de qualquer uso
  real, e nao depende de mais nenhuma fase.
- **F-07** — decidir formalmente se o oraculo por predicado e aceitavel para o
  contexto de uso, ou restringir o uso.

Os que precisam de codigo, com custo em `docs/FUTURE-HARDENING.md`:

| item | esforco | observacao |
|---|---|---|
| F-03 lineage de view por `pg_get_viewdef` | medio | exige reparsear a definicao e mapear posicoes |
| F-04 resolver `FuncCall` em `pg_proc` | medio | gestao de funcoes do PostgreSQL |
| `unmatched_policy: allow \| mask \| deny` | pequeno | evolucao natural do default ALLOW; muda a filosofia, precisa de aprovacao |
| F-07 controle de inferencia | grande | e outro produto |

### B. Fase 7 — Admin API

```text
Fase em andamento:
Fase 7 — Admin API, Etapas 1–7 concluidas

Proxima tarefa:
Etapa 9 — rotas de escrita e adocao com backup — NAO INICIADA
```

A Etapa 5 concluiu os primitivos de filesystem seguro em
`config/filesystem.py`: arquivo/diretorio/lock verificados, lock exclusivo
mantido aberto, SHA-256 dos bytes exatos, duas verificacoes de digest, escrita
atomica e limpeza estrita de orfaos.

A Etapa 6 criou `maskgw/admin/` — `errors.py`, `document.py` e `service.py` — e
com ele a secao critica administrativa. `AdminConfigService.apply` executa os
onze passos da secao 7.4 sob **um** lock por processo, e o composition root
passa a adquirir o `ConfigFileStore` quando o admin esta habilitado, mantendo-o
ate o shutdown. O runtime inicial e construido dos bytes do snapshot lido sob o
lock, para que o digest de referencia corresponda ao runtime publicado.

A Etapa 7 criou `maskgw/admin/http/` e a fronteira de rede: as oito rotas de
leitura, autenticacao por bearer token em header, bind so em loopback, as
quatro camadas anti-CSRF, o limite de 1 MiB que corta streaming, os headers
obrigatorios e os tres handlers de erro. O admin passa a ser habilitado por
`MASKGW_ADMIN_ENABLED=1`, e nao mais so por parametro de composicao.

`build_application` tem agora **dois** parametros administrativos, e a
distincao importa: `admin_enabled` compoe a secao critica — lock e caminho de
escrita —, e `admin_http` acrescenta a fronteira HTTP — thread, socket e rotas.
O segundo implica o primeiro, nunca o contrario. `resolve_admin_settings()` le
o ambiente e e o passo 1 do startup, antes de qualquer arquivo ser aberto.

O que as Etapas 7 e 8 deliberadamente **nao** fizeram, e nao deve ser presumido
pronto:

- as rotas de escrita, a operacao `config:adopt` completa (IDs aleatorios,
  `confirm_comment_loss` e backup dos bytes originais) e o backup — Etapa 9.
  O que existe e a **pre-condicao assimetrica** do passo 1, que e parte da
  secao critica: `AdminOperation.ADOPT` exige estado nao adotado e
  `expected_revision: 0`; as demais escritas exigem estado adotado;
- `AdminAudit` — Etapa 10. `admin/` nao importa `logging`, e isso e teste. Os
  contadores de `/status` sao inteiros em memoria, nao historico;
- a suite adversarial HTTP — Etapa 11.

**`IMMUTABLE_FIELD` nao foi declarada** (D-056): ela so e alcancavel por rota de
escrita com corpo, e declara-la agora fixaria o status HTTP de uma operacao da
Etapa 9. A Etapa 9 a acrescenta.

A especificacao aprovada esta em `docs/PHASE-7-SPEC.md`.
Ela cobre endpoints, autenticacao, bind e CORS, schemas, IDs e migracao,
revision e 409, persistencia atomica, lifecycle dos runtimes, sanitizacao de
erro, secrets, protecoes read-only, testes exigidos e escopo de auditoria.

As quatro questoes que estavam abertas foram decididas (secao 14.1 da spec):

| questao | decisao |
|---|---|
| `allowed_pg_functions` | somente leitura na Admin API; loader nao muda nesta fase |
| runtimes aposentados | limite 1; `409 RELOAD_BUSY` antes de construir o candidato |
| porta default | 8765 |
| comentarios do YAML | perda aceita, com backup dos bytes originais |

Dez bloqueios da revisao tambem foram corrigidos na especificacao, entre eles: `config:reload`
removido da primeira versao, `409 CONFIG_OUT_OF_SYNC` antes de toda escrita,
`CONFIG_DURABILITY_ERROR` com `applied: true` para falha de `fsync` depois do
`replace`, lock exclusivo de arquivo contra um segundo processo, bind so em
loopback, e uma composition root em `bootstrap/` que e o unico modulo autorizado
a conhecer os dois planos. A composition root foi implementada na Etapa 4, o
filesystem na Etapa 5, a serializacao com as duas verificacoes de digest e a
semantica de durabilidade na Etapa 6, e os itens de HTTP — bind so em loopback,
porta e autenticacao — na Etapa 7.

As Etapas 8–11 ainda nao foram iniciadas.

Objetivo: superficie administrativa separada do MCP para gerenciar
configuracao, policies, status e auditoria sem editar arquivo a mao.

**Principios ja aprovados** — decididos antes de qualquer codigo, registrados
em D-047 a D-054 com o motivo de cada um:

- Admin API **completamente separada** do MCP: planos distintos, sem handler e
  sem schema compartilhado
- Admin API **nao executa SQL**. Nao havera `/query`, `/sql` nem `/execute`
  (D-049)
- **MCP continua sendo o unico caminho de query**, e nunca altera configuracao
- **Secrets nunca retornados**, nem parcialmente mascarados: so `configured` /
  `missing`
- **A fonte administrativa persistida e o arquivo de configuracao validado**,
  nao os objetos runtime compilados (D-047)
- **Mudanca constroi runtime novo por inteiro** (D-048)
- **Runtime nunca e alterado parcialmente**: a query ve o antigo inteiro ou o
  novo inteiro
- **Persistencia atomica** e **troca de runtime atomica**, nesta ordem:
  validar → construir runtime → conectar e verificar → persistir → trocar
  (D-048). As duas sao atomicas **separadamente**: nao ha atomicidade conjunta
  entre filesystem e memoria
- **Depois do `rename` o arquivo ja e o novo**, e nao ha rollback de arquivo.
  Falha da persistencia preserva o arquivo anterior; falha antes dela preserva
  arquivo e runtime (D-048)
- **Janela de crash entre persistir e trocar**: se o processo morrer nela, o
  disco tem a configuracao nova — ja validada e ja comprovada conectavel — e o
  proximo start sobe com ela. Uma operacao que nao retornou sucesso pode ter
  tomado efeito no restart (D-048)
- **O DSN nao e campo administrativo**: credenciais, host e banco continuam
  vindo so de secret/env. A reconexao do candidato existe porque
  `statement_timeout_ms` viaja em `options` do DSN (D-028, D-048)
- **Ciclo de vida do runtime por refcount + `retired`** (D-054): o reload nao
  bloqueia esperando queries antigas; o runtime antigo e aposentado no swap; o
  ultimo release o fecha exatamente uma vez; se ja nao houver usuarios no
  swap, e fechado ali mesmo; e nenhuma query adquire um runtime aposentado
- **`revision` + `expected_revision`** para controle otimista de concorrencia,
  verificados **dentro de uma secao critica administrativa serializada**: duas
  requisicoes com o mesmo `expected_revision` nao vencem ambas (D-052)
- **Protecoes estruturais nao sao editaveis** — `denied_relations` com
  `pg_stats` e o caso concreto (D-050)
- IDs administrativos estaveis para rules e exceptions; a ordem continua
  semanticamente relevante (D-051)
- `enabled` fica fora da primeira versao (D-053)
- bind HTTP futuro em **`127.0.0.1`** por default, **sem CORS wildcard**
- **sem front-end** nesta fase

### C. Fase 8 — Front-end · NAO INICIADA

Depende da Fase 7. Sem Admin API nao ha o que consumir.

### D. Fase 9 — Deployment · NAO INICIADA

Streamable HTTP, autenticacao, OAuth. Hoje so ha stdio, e a ausencia de porta
de rede e uma **decisao de seguranca** (D-036), nao uma lacuna. Trocar o
transporte exige um modelo de sessao e de autenticacao; nao e trocar um
parametro.

### Fora do escopo, inalterado

RBAC, OAuth/OIDC, LDAP/SSO, multi-tenant, multi-database, MySQL, pool de
conexoes, `resources`/`prompts` MCP, schema discovery, JSONB deep inspection,
lineage completo, transformers Python customizados, column-level GRANT
automatico, banco de configuracao, Redis, background workers.

### Antes de iniciar a proxima etapa

- `git status --short` vazio: a arvore precisa estar limpa
- suite verde: **1995 testes coletados**, 1986 passed e 9 skips condicionais
  de plataforma; `ruff check`, `ruff format --check` e `mypy --strict` sem erros
- PostgreSQL real disponivel via `MASKGW_TEST_DSN`: 415 testes marcados como
  integracao, todos executando, sem skip por ausencia dele
- neste host Windows, rode o pytest com pilha de thread ampliada (64 MiB), ou o
  teste de payload gigante derruba o processo. Nunca o transforme em `skip`
  (D-041); a limitacao esta na secao 11

## 11. Riscos conhecidos que atravessam qualquer fase seguinte

1. **Default ALLOW.** Coluna sensivel com nome fora do padrao passa em claro.
   E consequencia direta do modelo, nao um defeito, e a protecao depende da
   qualidade do `masking.yaml`.
2. **Funcao de usuario pre-existente** que leia coluna sensivel devolve o valor
   sob o nome dela (F-04). Mitigacao e privilegio, nao codigo.
3. **View que renomeia coluna sensivel** expoe o valor (F-03).
4. **Oraculo por predicado** reconstroi um CPF em 11 consultas (F-07).
5. **Cache de proveniencia por conexao** fica obsoleto apos `RENAME COLUMN`
   (D-021). O Gateway e read-only sobre schema estavel; nao ha invalidacao.
6. **Argumentos extras do MCP sao ignorados, nao recusados** pelo SDK 2.1.1
   (D-037). Nao alteram nada; a expectativa de recusa e que nao se cumpre.
7. **`audit/` e in-memory-free**: escreve via `logging`, sem storage proprio.
   Nao ha historico consultavel — qualquer feature que precise disso comeca do
   zero.
8. **Consulta com dezenas de milhares de termos pode derrubar o processo.** A
   analise da AST e recursiva, e uma expressao com 100.000 somas estoura a
   pilha da thread antes de qualquer limite do produto. **Nao existe controle
   no Gateway** que limite o tamanho da consulta ou a profundidade da
   expressao: quem decide o desfecho e o tamanho de pilha disponivel. Com a
   pilha default deste host Windows o processo cai; com 64 MiB por thread o
   mesmo caso passa — foi assim que a suite integral fechou, e isso e
   propriedade do AMBIENTE DE TESTE, nunca uma protecao do produto.
   Nao e regressao da Fase 7 — reproduzido em `d276c22` — e **continua sem
   correcao**. Uma correcao real seria limitar o tamanho da consulta na
   fronteira, ou tornar o walk iterativo; as duas mudam comportamento ja
   entregue e precisam de aprovacao propria.

## 12. Armadilhas ja pisadas (nao repita)

Registradas porque custaram tempo e foram descobertas por teste, nao por
revisao:

- **`raise ... from None` nao basta.** Zera `__cause__`, mas o interpretador
  ainda pendura a excecao original em `__context__` quando o `raise` ocorre
  dentro de um handler ativo. Levante FORA do handler. Aconteceu duas vezes
  (D-017 na Fase 2, e de novo na Fase 6 em `provenance.py`).
- **`SELECT 1 INTO nova` parseia como `SelectStmt` e cria uma tabela.** Raiz
  SELECT nao basta (D-031).
- **`str()` sobre `memoryview` embute o endereco do objeto** e quebra o
  determinismo do HMAC em silencio (D-015).
- **Multiplos comandos com parametros** sao recusados pelo protocolo estendido
  do psycopg. Separe o DDL do INSERT parametrizado nas fixtures.
- **Descer a arvore inteira em cada nivel** tornou a analise de AST quadratica
  e travou o processo com 200 subqueries aninhadas (D-046). Use `Skip`.
- **`bool` e subclasse de `int`; `datetime` e subclasse de `date`.** A ordem
  dos `isinstance` na canonicalizacao importa (D-015).
- **Nomes de coluna duplicados sao validos.** Nunca indexar linhas por nome.

Regra do projeto: nao avancar de fase ou etapa sem aprovacao, nem com teste
falhando.
