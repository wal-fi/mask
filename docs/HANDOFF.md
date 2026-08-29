# Handoff

Estado do projeto ao final da sessao que implementou a Fase 1.
Documento de entrada para a proxima sessao.

Leitura obrigatoria antes de continuar: `CLAUDE.md`, `docs/ARCHITECTURE.md`,
`docs/SECURITY.md`, `docs/MASKING-SPEC.md`, `docs/ROADMAP.md`,
`docs/DECISIONS.md`.

---

## 1. Fase concluida

**FASE 1 — Config Loader + Masking Engine puro.** Concluida e verificada.

Os 17 criterios de aceite da Fase 1 (`docs/ROADMAP.md`) estao cobertos por
teste. As Fases 2 a 6 nao foram iniciadas.

Entregue:

- Config Loader com validacao Pydantic e comportamento fail-closed
- Modelos de configuracao imutaveis
- Matcher e Exception Matcher, ambos avaliando `output_name` e `origin_name`
- Transformer Registry extensivel
- Transformers: md5, sha256, sha512, hmac_sha256, regex, random, fixed, truncate
- Masking Engine puro (sem I/O)
- 252 testes automatizados

## 2. Stack e dependencias

Python 3.11.3. Ambiente em `.venv/` na raiz (ignorado pelo git).

| Pacote | Versao instalada | Uso |
|---|---|---|
| pydantic | 2.13.5 | validacao de configuracao |
| PyYAML | 6.0.3 | leitura do `masking.yaml` |
| pytest | 9.1.1 | testes |
| ruff | 0.16.5 | lint + format |
| mypy | 2.3.1 | type-check strict |

Ainda **nao** instalados, por pertencerem a fases futuras: `psycopg3` (Fase 2)
e `pglast` (Fase 4).

Configuracao em `pyproject.toml`. Nao ha instalacao editavel: o pytest resolve
o pacote via `pythonpath = ["src"]`.

Comandos:

```bash
.venv/Scripts/python.exe -m pytest
```

```bash
.venv/Scripts/python.exe -m ruff check src tests && .venv/Scripts/python.exe -m ruff format --check src tests
```

```bash
.venv/Scripts/python.exe -m mypy src tests
```

A chave HMAC vem da variavel de ambiente `MASKGW_HMAC_KEY` (minimo 32
caracteres). Sem ela, qualquer configuracao que use `hmac_sha256` nao carrega.

## 3. Arquitetura consolidada

```text
AI Client -> MCP Server -> Gateway -> Query Validator -> DB Adapter -> PostgreSQL
                                                              |
                                              Result Set + Column Metadata
                                                              |
                                MaskingEngine (Exception -> Masking -> Original)
                                                              |
                                                        MCP Response
```

Pipeline por coluna, com default **ALLOW**:

```text
EXCEPTION MATCH -> ORIGINAL
MASKING MATCH   -> TRANSFORMER
NO MATCH        -> ORIGINAL
```

Peca central: o `ColumnDescriptor`, que carrega os dois nomes.

```text
ColumnDescriptor
  output_name    nome devolvido ao cliente (o alias)
  origin_name    nome real da coluna de origem, quando determinavel
```

O matching aplica a regra se **qualquer um** dos nomes casar. E isso que
neutraliza o bypass por alias (`SELECT cpf AS documento`). Na Fase 1
`origin_name` e sempre fornecido por quem chama; a resolucao automatica a
partir do PostgreSQL e o objeto da Fase 3.

Exceptions tem prioridade absoluta e sao avaliadas contra os mesmos dois nomes.

## 4. Decisoes D-001 a D-014

Detalhamento completo em `docs/DECISIONS.md`.

| # | Decisao |
|---|---|
| D-001 | Codigo em `src/maskgw/`; `config/` na raiz permanece diretorio de dados |
| D-002 | Chave HMAC na env `MASKGW_HMAC_KEY`, nome fixo no codigo |
| D-003 | `regex` sem correspondencia devolve `[REDACTED]`, nunca o original |
| D-004 | Conflito entre regras: vence a primeira do arquivo |
| D-005 | `random` usa `secrets` (CSPRNG), nao o modulo `random` |
| D-006 | Chave HMAC exige >= 32 caracteres; vazia ou so espacos conta como ausente |
| D-007 | `hmac_sha256` nao aceita nenhum parametro no YAML |
| D-008 | Lista global de parametros proibidos (`key`, `secret`, `salt`, ...) em qualquer transformer |
| D-009 | `random` exige `strategy` explicita; `length` obrigatorio sse `preserve_length: false` |
| D-010 | `truncate` devolve `value[:length]`, sem sufixo |
| D-011 | Valores nao-string sao convertidos com `str()`; NULL nunca e convertido |
| D-012 | Fase 1 nao registra log; `audit/` so na Fase 5 |
| D-013 | Transformers nao expoem atributo `name`; a chave do registry e a fonte da verdade |
| D-014 | Riscos de configuracao (H-1 a H-4): documentar e fixar em teste, nao bloquear no loader |

## 5. Estrutura dos modulos

```text
src/maskgw/
  errors.py              ConfigError, TransformerError
  secretsource.py        SecretProvider, EnvSecretProvider, MappingSecretProvider
  config/
    models.py            modelos Pydantic (extra="forbid", frozen)
    loader.py            load_config, load_config_text, parse_config
  masking/               <- nucleo PURO: sem banco, MCP, rede ou psycopg
    descriptor.py        ColumnDescriptor
    rules.py             MatchMode, MatchSpec, MaskingRule, MaskingException, MaskingPolicy
    matcher.py           RuleMatcher, ExceptionMatcher
    engine.py            Action, Decision, MaskingEngine
    transformers/
      base.py            Transformer (apply trata NULL), REDACTED
      params.py          validacao de parametros, FORBIDDEN_PARAMS
      registry.py        TransformerRegistry, build_default_registry
      hashes.py          md5, sha256, sha512, hmac_sha256
      regex_transformer.py
      randomize.py       random
      simple.py          fixed, truncate

tests/
  conftest.py
  test_config_loader.py    35
  test_matching.py         38
  test_transformers.py     94
  test_engine.py           36
  test_purity.py           28
  test_leakage.py          13
  test_config_hazards.py    8
```

A pureza de `masking/` e verificada automaticamente por `test_purity.py`, que
analisa os imports por AST e confirma em subprocesso que importar
`maskgw.masking` nao carrega banco, MCP, rede, yaml nem pydantic.

Modulos ainda inexistentes, previstos pela arquitetura: `maskgw/db/`,
`maskgw/sql/`, `maskgw/gateway/`, `maskgw/mcp/`, `maskgw/audit/`.

## 6. Resultado das verificacoes

Executadas ao final da Fase 1, todas verdes:

```text
pytest   252 passed
ruff     All checks passed
ruff     28 files already formatted
mypy     Success: no issues found in 28 source files  (strict)
```

## 7. Riscos conhecidos H-1 a H-4

Confirmados por sondagem na revisao de seguranca da Fase 1. **Nenhum e defeito
do engine**: em todos o pipeline se comporta como especificado, e quem abre a
porta e o `masking.yaml`. Fixados em `tests/test_config_hazards.py`.

| # | Configuracao | Efeito |
|---|---|---|
| H-1 | `exceptions: - match: cpf` sem `mode` (default e `contains`) | Desliga a regra `cpf` inteira, em silencio |
| H-2 | `regex` com pattern `(.*)` e replacement `\1` | Devolve o valor original |
| H-3 | `truncate` com `length` maior que o valor | Devolve o valor original |
| H-4 | `random` com `preserve_length: true` | Publica o comprimento do valor original |

H-1 e o mais relevante: o `config/masking.yaml` do repositorio usa
`mode: exact` na exception, mas o default e `contains`. Uma exception escrita
sem `mode` pode anular a regra correspondente sem nenhum sinal.

Evolucao possivel registrada em `docs/FUTURE-HARDENING.md`: um `--check` de
configuracao que avise nesses casos.

## 8. Decisoes que ainda precisam de revisao

Tres decisoes da Fase 1 afetam configuracao existente e merecem confirmacao
explicita do responsavel pelo projeto:

- **D-003** — `regex` sem correspondencia devolve `[REDACTED]` em vez do valor
  original. Mais seguro, porem altera o comportamento natural de `re.sub`.
- **D-006** — chave HMAC exige no minimo 32 caracteres. Pode recusar uma chave
  ja em uso.
- **D-009** — `strategy` passou a ser obrigatoria em `random`. Foi o que
  motivou a unica alteracao funcional em `config/masking.yaml`.

Alem disso, permanece em aberto a proposta de tratar H-1 alterando o default de
`mode` para exceptions, ou recusando exception cujo padrao seja substring do
padrao de uma regra. Nao foi implementado por ser mudanca de semantica.

## 9. Fase 2 — objetivo e criterios

**FASE 2 — PostgreSQL Adapter + ResultSet Masking.**

Objetivo: ligar o Masking Engine a um banco real, aplicando a politica sobre
result sets obtidos via psycopg3. Nesta fase o matching usa **somente**
`output_name`: a resolucao de `origin_name` e da Fase 3.

Escopo:

- conexao via psycopg3
- execucao de SELECT
- extracao de `output_name` a partir de `cursor.description`
- aplicacao do Masking Engine sobre o result set
- sanitizacao de erros do PostgreSQL

Criterios de aceite:

1. `SELECT cpf FROM cliente` retorna valor mascarado.
2. `SELECT *` mascara todas as colunas que casam regra.
3. `SELECT cpf, email` aplica transformers distintos por coluna.
4. NULL permanece NULL no result set real.
5. Nenhum erro do PostgreSQL chega ao chamador com o texto original.
6. Nenhum valor sensivel aparece em log.

Ponto de atencao registrado no roadmap: nesta fase `SELECT cpf AS documento`
**passa em claro**, porque nao ha lineage. Essa lacuna deve ser coberta por um
teste que documenta o comportamento, e esse teste sera invertido na Fase 3.

Ja existe teste equivalente no engine:
`tests/test_engine.py::TestAliasProtection::test_alias_without_origin_passes`.

## 10. O que NAO foi implementado

Nao existe nenhuma linha de codigo para:

- PostgreSQL e psycopg3 (Fase 2)
- resolucao de proveniencia / lineage de coluna (Fase 3)
- SQL parser e query validator com pglast (Fase 4)
- conexao read-only, `statement_timeout`, limite de linhas (Fase 4)
- MCP Server (Fase 5)
- `gateway/` e `audit/` (Fases 4 e 5)
- testes adversariais end-to-end (Fase 6)

Fora do escopo do MVP, documentado em `docs/FUTURE-HARDENING.md`: bloqueio de
WHERE / ORDER BY / GROUP BY sobre dados sensiveis, supressao de agregacoes,
controle de cardinalidade, RBAC, column-level GRANT automatico, JSONB deep
inspection, transformers Python customizados, multi-tenant e default deny.

Regra do projeto: nao avancar de fase sem aprovacao, nem com teste falhando.
