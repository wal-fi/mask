# Fase 9 — validação da Etapa 4 (Admin API v2 de datasources)

**Data:** 2026-09-24
**Base:** `402969c617791cd9d9f3dced20e8eb2569551aab` (Etapa 3), `master`, um
commit à frente de `origin/master` (`b368da38d81f2dd019cf713a1b41172d9ca560ac`),
sem alterações rastreadas no início; `.codex/` e `systeminfo` não rastreados e
preservados.
**Escopo autorizado:** somente `/admin/v2` de datasources conforme a §8 e o
limite efetivo de resolução DNS exigido pela §11/D-090. UI v2, PGWire, variável
de ambiente nova, bind externo, extensão da tool MCP, push e Etapa 5 ficaram
fora.

Este documento registra somente o que foi medido nesta sessão. Gate não
executado aparece como não executado.

## 1. Decisões apresentadas antes do código

| ponto | escolha aprovada | decisão |
|---|---|---|
| limite de DNS sem abandonar thread | resolução em processo filho descartável, prazo de 5 s, `kill` + recolhimento | D-092 |
| ativação e superfície | v2 só com `datasource_catalog` e `admin_http` no composition root; inventário literal | D-093 |
| concorrência otimista | revision por datasource; criação pela revision do catálogo | D-094 |
| vocabulário de erro e auditoria | enum, schemas e `DatasourceAdminAudit` próprios; v1 intacta | D-095 |
| default do MCP | adiado para a Etapa 11 (exige campo novo no catálogo autenticado) | D-096 |

Medição que motivou D-092: `socket.getaddrinfo("example.invalid")` em processo
levou 11,08 s neste host; no filho, a mesma resolução foi cortada em 5,0 s. Uma
resolução real num filho custou cerca de 0,2 s. O psycopg 3.3.4 instalado pula
a resolução quando `hostaddr` está preenchido (`_conninfo_attempts.py`), e
`build_conninfo` sempre o preenche; o único ponto de DNS é `resolve_destination`.

## 2. O que foi implementado

| arquivo | conteúdo |
|---|---|
| `src/maskgw/datasource/resolver.py` | resolver com prazo em processo filho `-I -S`: host por `stdin`, JSON limitado, `stderr` descartado, ambiente sem segredo, semáforo de 4 |
| `src/maskgw/datasource/destination.py` | o resolver default passa a ser o limitado |
| `src/maskgw/runtime/candidate.py` | `verify_policy`: compila a política pelo mesmo caminho do candidato, sem conectar |
| `src/maskgw/runtime/datasource_service.py` | revision por datasource, mutação e confirmação sob o lock, `DatasourceWriteProbe`, erros próprios (não encontrado, alias, conflito com revision, desabilitado), teste de desabilitado recusado, política nova de desabilitado compilada |
| `src/maskgw/admin/http/v2/` | `errors.py`, `schemas.py`, `operations.py`, `audit.py`, `routes.py` |
| `src/maskgw/audit/datasource.py` e `audit/log.py` | `DatasourceAdminAudit` fechado e `AuditLog.record_datasource_admin` |
| `src/maskgw/admin/http/app.py`, `bootstrap/application.py` | parâmetro `datasources` com import tardio da v2 |
| `pyproject.toml` | `S608` ignorado só no novo arquivo de integração (SQL de constantes do próprio teste) |

Inventário v2: `GET|HEAD` `/admin/v2/status`, `/admin/v2/datasources`,
`/admin/v2/datasources/{id}`, `/admin/v2/datasources/{id}/policy`; `POST`
`/datasources`, `/datasources:test`, `/datasources/{id}:test`,
`/datasources/{id}:rotate-credential`, `/datasources/{id}:enable`,
`/datasources/{id}:disable`; `PUT /datasources/{id}`;
`DELETE /datasources/{id}`; `PUT /datasources/{id}/policy`. Nenhuma rota de SQL,
DSN, segredo, chave-mestra, auditoria ou default do MCP.

## 3. Testes novos

| arquivo | testes | cobre |
|---|---:|---|
| `test_datasource_resolver.py` | 18 | prazo efetivo, filho recolhido, sem neto órfão do launcher do venv (com contraprova), ambiente sem segredo, host fora de `argv`, falhas fixas, `stdout`/`stderr` limpos, semáforo, default de `resolve_destination`, candidato `DESTINATION` no prazo |
| `test_datasource_service_v2.py` | 9 | revision por datasource, mutação e confirmação sob lock, probe, teste de desabilitado, política compilada, desabilitar sem depender da política, corrida de um vencedor, falha certa bloqueando |
| `test_admin_v2_http.py` | 52 | inventário literal, v1 byte a byte (sonda a sonda com e sem v2), v1 sem importar a v2, fronteira (401 antes de 422, 400, 403, 413, 415, 405, 404), schema fechado sem eco, leituras sem segredo, criar/editar/rotacionar/testar/habilitar/desabilitar/remover/política, destinos proibidos, DNS trocado, falhas de persistência certa e incerta, busy, indisponível, cadeia de exceção, canários em respostas e auditoria, `repr` sem senha |
| `test_admin_v2_audit.py` | 28 | paridade de vocabulário, desfecho × status, v1 intocada, registro fechado e recusas de construção, logger falho contido, `audit/datasource.py` sem `logging` |
| `test_admin_v2_concurrency.py` | 5 | um vencedor por revision pela porta HTTP, datasources distintos sem conflito, criação concorrente, mistura de testes/leituras/escritas, escritas paralelas pela tradução |
| `test_admin_v2_lifecycle.py` | 3 | shutdown com DNS lento em voo termina no prazo sem thread/filho, composition root com v2 e sem v2, porta e locks liberados |
| `test_admin_v2_integration.py` | 4 | PostgreSQL 16 real, resolver de produção e adapters reais: criação que mascara, credencial errada sem efeito nem vazamento, teste sem efeito, rotação/desabilitar/habilitar/política/remoção |

São 119 testes novos; 4 usam PostgreSQL real. Nenhum `skip`, `xfail` ou
`deselect` foi introduzido.

## 4. Revisão adversarial

| id | achado | tratamento | prova |
|---|---|---|---|
| A-1 | depois de falha de persistência o store recusa também leituras (D-081); as leituras v2 sairiam como `CATALOG_WRITE_ERROR` | leituras com catálogo já bloqueado respondem `503 CATALOG_BLOCKED`; `/admin/v2/status` continua em modo degradado (`catalog_available: false`) | `test_write_failure_before_replace_blocks_writes_and_the_catalog` |
| A-2 | o `repr` de um corpo Pydantic mostraria a senha upstream | `Field(repr=False)` na senha | `test_request_models_never_show_the_password_in_repr` |
| A-3 | no Windows o `python.exe` do venv é um launcher que cria o interpretador como neto; `kill` no launcher poderia deixar o neto órfão | medido: o neto morre junto (job object); teste de regressão com contraprova de detecção | `test_killing_the_child_leaves_no_interpreter_behind` |
| A-4 | compilar a política ao desabilitar faria a desabilitação depender, por exemplo, da chave HMAC | só política NOVA é compilada; desabilitar nunca depende dela | `test_disabling_never_depends_on_the_policy_still_compiling` |
| A-5 | o coordenador da Etapa 3 testava datasource desabilitado, contra a §6.1 | recusa com `409 DATASOURCE_DISABLED`, sem adapter | `test_testing_a_disabled_or_unknown_datasource_is_refused` |
| A-6 | o gerador da UI v1 lê `AdminErrorCategory`, `AdminOperationName` e `admin/http/schemas.py`; estender mudaria a v1 | vocabulário, schemas e auditoria próprios (D-095) | `test_v1_enums_and_schema_module_are_unchanged` |
| A-7 | o teste de isolamento só importava módulos; um mutante que registrava a v2 sem catálogo sobreviveu | o teste passou a construir um app v1 real no subprocesso | mutantes da §5 |

Mutantes: cada um remove uma garantia numa cópia descartável da árvore e roda
os testes correspondentes. **23 de 23 foram detectados** (21 na primeira rodada,
com um sobrevivente — A-7 —, e os dois de registro sem catálogo depois do
reforço). Garantias cobertas: kill no prazo, ambiente do filho, host fora de
`argv`, semáforo, revision do datasource, revision do catálogo no lugar da do
datasource, teste de desabilitado, compilação de política de desabilitado,
desabilitar sem compilar, `allowed_pg_functions`, allowlist preservada, alias
imutável, confirmação de remoção, cadeia de exceção, leitura bloqueada,
senha no `repr`, habilitar ocioso sem gravar, pin DNS, registro sem catálogo
(isolamento e inventário), mutação fora da seção crítica, auditoria na recusa e
teste de rascunho que publicaria.

## 5. Gates

### 5.1. Ambiente

Windows 11 Pro 10.0.26200, Python **3.11.3 nativo** do Windows no venv do
projeto; a suíte integral rodou pelo comando documentado, com pilha de thread
de 64 MiB. PostgreSQL **16.15** real em contêiner descartável da imagem local
`postgres:16-alpine`, publicado somente em `127.0.0.1`, com senha aleatória
gerada nesta sessão, guardada em arquivo privado temporário e nunca impressa;
`MASKGW_TEST_DSN` apontava para ele. Nenhum banco existente foi tocado.
Versões: pytest 9.1.1, psycopg 3.3.4 (libpq 18.3), pydantic 2.13.5, fastapi
0.141.1, uvicorn 0.52.4, mcp 2.1.1, pglast 8.4, cryptography 50.0.1, Ruff
0.16.5, mypy 2.3.1.

### 5.2. Resultados

| gate | resultado |
|---|---|
| suíte Python integral final, sem deselect, PostgreSQL 16.15 real | **4.155 testes: 4.147 aprovados, 0 falhas, 0 erros, 8 skips**; JUnit 553,3 s |
| testes da Etapa 4 | **119/119 aprovados**, nenhum skip |
| testes marcados `integration` | 575 selecionados, todos executados com DSN na suíte integral |
| primeira rodada integral (antes dos ajustes A-2, A-3 e A-7) | 4.153 testes: 4.145 aprovados, 0 falhas, 0 erros, 8 skips; 552,6 s |
| Ruff check (`src` + `tests`) | aprovado |
| Ruff format `--check` | aprovado; 172 arquivos |
| mypy strict (`src` + `tests`), plataforma `win32` | aprovado; 172 arquivos sem erros |
| `git diff --check` (inclusive arquivos novos, via staging) | aprovado |
| mutantes | 23/23 detectados (§4) |
| regressão byte a byte da v1 | aprovada: todas as sondas da v1 idênticas com e sem v2 |

Os 8 skips são condicionais de plataforma POSIX neste host Windows e são os
mesmos da base: quatro de `fsync` de diretório (auditoria de durabilidade,
escrita administrativa, serviço administrativo e leakage adversarial), três de
bits de modo POSIX e um de `fsync` de diretório do filesystem. **Nenhum skip
por ausência de DSN.**

## 6. Limitações e riscos reais

- **O event loop administrativo fica ocupado durante uma operação v2**, como na
  v1 (D-059): uma escrita com candidato resolve o DNS duas vezes (candidato e
  revalidação no store, até 5 s cada) e conecta com `connect_timeout=10` por
  endereço resolvido (até 64). Leituras administrativas esperam nesse intervalo.
- **Verificação pós-conexão sem teto do lado do cliente — risco NÃO
  corrigido.** Verificado no código: `PostgresAdapter.connect()` chama
  `psycopg.connect()` (limitado pelo `connect_timeout`) e, depois de autenticar,
  `_verify_session()` e `check_provenance_capability()`, cujas consultas
  dependem apenas do `statement_timeout` do próprio servidor. Os handlers v2 são
  `async` e executam esse trabalho síncrono no event loop: um upstream que
  autentica e para de responder prende o handler, a fronteira administrativa e o
  shutdown. O limite de DNS (D-092) não cobre esse trecho. É gate próprio:
  limite efetivo **antes da ativação da Admin API v2 pelo operador, prevista para
  a Etapa 7** — distinto do limite de validação e masking locais, exigido antes
  dos ingressos PGWire e MCP multi-datasource (Etapas 8 e 11). Nenhuma solução
  pode abandonar thread, processo ou conexão. Hoje a v2 só existe pelo parâmetro
  interno do composition root, somente em loopback e com token.
- **Refixar DNS com o mesmo destino não é possível pela v2.** Com o mesmo host e
  porta, o conjunto persistido é exigido (D-084); uma mudança legítima de DNS é
  recusada até trocar o destino. Também o startup falha fechado nesse caso
  (Etapa 3).
- **`last_test` não é atualizado.** Testes não têm efeito (D-091, F9-026), e as
  escritas o redefinem; a "última verificação" da §6.1 fica para a UX/decisão
  posterior.
- **Oráculo de rede para o administrador.** As categorias de falha do candidato
  distinguem destino recusado, conexão falha e capability ausente; quem tem o
  token pode sondar a rede privada — o mesmo principal que já cadastra destinos.
- **Semáforo do resolver esgotado** vira `DATASOURCE_DESTINATION_REJECTED`, não
  `DATASOURCE_BUSY`; com os limites de candidato (D-089) não é alcançável pelo
  HTTP.
- **Ativação só pelo composition root.** Sem variável de ambiente nova, a v2 não
  é alcançável por um operador até a ativação por settings (Etapa 7).
- **Não executados nesta etapa:** ramo POSIX do teste de neto órfão (sem WSL
  neste host), Node/browsers (a UI não mudou) e pacote instalado (Etapa 12).
- O default do MCP não existe (D-096).
