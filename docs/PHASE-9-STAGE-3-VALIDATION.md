# Fase 9 — validação da Etapa 3 (registry multi-datasource e lifecycle)

**Data:** 2026-09-23
**Base:** `b368da38d81f2dd019cf713a1b41172d9ca560ac` (Etapa 2), `master`, igual a
`origin/master`, sem alterações rastreadas no início.
**Escopo autorizado:** registry por alias e generation, acquire/release,
refcount, aposentadoria e fechamento único, isolamento, limites globais e por
datasource, drain em desabilitação/remoção, startup fail-closed, teste de
candidato sem publicação e modo legado intacto. Admin API v2, UI v2, PGWire,
rota nova, variável de ambiente nova e extensão da tool MCP ficaram fora.

Este documento registra somente o que foi medido nesta sessão. Gate não
executado aparece como não executado.

## 1. Decisões apresentadas antes do código

A especificação não fixava quatro pontos; eles foram apresentados e aprovados
pelo usuário antes de qualquer código (D-087–D-089):

| ponto | escolha aprovada |
|---|---|
| ativação | só pelo parâmetro interno `build_application(datasource_catalog=...)`; `main()` e o ambiente intactos até a Etapa 7 |
| MCP com catálogo ativo | runtime legado inalterado até a Etapa 11 |
| `policy.database` × `limits` | o mais restritivo dos dois (mínimo) |
| limites | por datasource `limits.max_sessions`, 1 aposentada e 1 candidato; globais 32 sessões, 4 aposentadas e 2 candidatos |

D-090 (drenagem e shutdown) e D-091 (coordenador, candidato e falhas) são
escolhas de implementação dentro do contrato. A revisão posterior identificou
o limite de D-090 registrado na §7: os timeouts de libpq e PostgreSQL não
constituem um teto total de espera.

## 2. O que foi implementado

| arquivo | conteúdo |
|---|---|
| `src/maskgw/runtime/candidate.py` | candidato imutável: destino revalidado contra o DNS persistido, policy compilada, limites efetivos, alvo libpq por `hostaddr` e conexão de verificação sempre fechada; falhas em quatro categorias fixas |
| `src/maskgw/runtime/datasources.py` | `DatasourceRegistry`: geração por alias, sessão com conexão própria, refcount, aposentadoria, descarte único, reservas, limites, retirada e shutdown em duas fases |
| `src/maskgw/runtime/datasource_service.py` | `open_datasource_runtime` (passos 3–7 da §11, fail-closed) e `DatasourceRuntimeService` (teste sem efeito; criar, atualizar, rotacionar, habilitar/desabilitar, remover) |
| `src/maskgw/gateway/datasources.py` | sessão de consulta por alias sobre o mesmo pipeline do MCP |
| `src/maskgw/gateway/service.py` | `run_audited`/`to_query_result` extraídos de `Gateway.query`, sem mudança de comportamento |
| `src/maskgw/bootstrap/application.py` | parâmetro `datasource_catalog`, import tardio, ordem de startup e shutdown, fechamentos encadeados |
| `src/maskgw/db/postgres.py` | `PostgresAdapter.cancel()` para o shutdown; entrou na API pública fechada de `test_db_leakage.py` |
| `src/maskgw/datasource/store.py` | propriedade somente leitura `requires_reopen` (o bloqueio de D-081 já existente) |

Nenhuma variável de ambiente é lida pela capacidade nova; `MASKGW_PGWIRE_ENABLED`
continua sem leitor. O MCP `query_database(sql)` não mudou. Sem o parâmetro,
nenhum módulo de `maskgw.datasource`, `maskgw.runtime.candidate`,
`maskgw.runtime.datasource*` ou `maskgw.gateway.datasources` é importado —
medido em subprocesso na suíte e no pacote instalado.

## 3. Testes novos

| arquivo | testes | cobre |
|---|---:|---|
| `test_datasource_registry.py` | 29 | gerações, erro fixo de alias, troca com sessão admitida, descarte único, retirada/drenagem, isolamento, limites e reservas, falhas parciais (connect, construção de adapter), shutdown em duas fases, recancelamento, sessão em `connect`, candidatos em voo, `close` concorrente, estresse concorrente e `repr` |
| `test_datasource_runtime_service.py` | 42 | limites efetivos, pinning DNS, categorias sanitizadas, teste sem efeito, ordem candidato → persistência → publicação, busy antes do candidato, rename, conflito, bloqueio por falha de persistência (inclusive não `CatalogWriteError`), resultado incerto, desabilitar sem DNS, `cancel` do adapter e startup fail-closed |
| `test_datasource_runtime_integration.py` | 8 | PostgreSQL 16 real: masking por alias no mesmo pipeline, escrita recusada pelo validator e pelo PostgreSQL, uma conexão por sessão, troca de policy com sessão admitida, drenagem, credencial errada sem efeito, startup com senha errada e cancelamento real no shutdown |
| `test_datasource_bootstrap.py` | 13 | legado sem módulo de catálogo e com `repr` igual, nada publicado com datasource inválido, ordem de startup, admissão parada antes de esperar o HTTP, consulta em voo cancelada no `close`, falha do legado sem prender datasources nem locks, falha tardia fechando tudo e subprocesso real válido/inválido |

São 92 testes; 10 usam PostgreSQL real (os 8 de integração e os 2 de
subprocesso). Nenhum `skip`, `xfail` ou `deselect` foi introduzido.

## 4. Revisão independente

Um revisor separado, sem ter escrito o código, examinou o diff contra o
contrato. Não encontrou P1. Achados e tratamento:

| id | achado | correção | prova |
|---|---|---|---|
| P2-1 | desabilitar dependia de DNS: com DNS fora do ar ou adulterado, o store recusava a desabilitação | com o mesmo destino, o conjunto persistido é reapresentado ao store; reabilitar continua exigindo candidato | `test_disable_never_depends_on_dns` |
| P2-2 | falha ao construir o adapter em `open_session` deixava a sessão contada | adapter construído antes de qualquer contador | `test_adapter_construction_failure_leaves_no_admission_counted` |
| P3-3 | shutdown não esperava teste de conexão em voo | `close()` espera sessões e candidatos | `test_shutdown_waits_for_candidate_in_flight` |
| P3-4 | falha de persistência que não é `CatalogWriteError` envenenava o store sem bloquear o coordenador | bloqueio pela condição do store (`requires_reopen`) | `test_any_failure_that_poisons_the_store_blocks_the_service`, `test_refusals_before_commit_do_not_block` |
| P3-5 | cancelamento único podia chegar antes de o statement existir | fase 2 repete o cancelamento a cada segundo enquanto a sessão está ocupada | `test_shutdown_waits_for_query_finishing_between_check_and_release` |
| P3-6 | `cancel_safe` exige psycopg ≥ 3.2, e o `pyproject` aceita ≥ 3.1 | fallback para `cancel()` sem mudar dependência | `test_adapter_cancel_is_a_noop_without_connection_and_never_raises` |
| P3-7 | uma falha no fechamento do legado pulava o fechamento dos datasources e dos stores | fechamentos encadeados em `try/finally`, depois da barreira do HTTP | `test_legacy_close_failure_still_closes_datasources_and_catalog` e mutantes de §5 |

## 5. Mutantes

Cada mutante remove uma garantia de uma cópia descartável da árvore; a suíte
sem banco da etapa (`test_datasource_registry.py`,
`test_datasource_runtime_service.py`, `test_datasource_bootstrap.py`) roda com
`-x`. **35 de 35 foram detectados.** Na primeira rodada, cinco sobreviveram
por falta de teste observável (fechamento sem marcar `closed`, admissão em
geração aposentada ainda publicada, shutdown sem esperar releases, sessão
marcada que não fecha ao sair de `use()` e `close()` que não para a admissão
antes de esperar o HTTP); os testes correspondentes foram acrescentados e a
rodada final os detectou. Dois mutantes de shutdown travavam o processo de
teste; os testes passaram a liberar o lock em `finally` e usar threads daemon,
e os dois falham sem travar.

Garantias cobertas: fechamento na própria troca, marca `closed`, admissão só
na geração publicada, cada limite (sessões por datasource e global, ordem
global antes do alias, candidato, aposentadas), as duas fases do shutdown,
cancelamento, recancelamento, espera de releases e de candidatos, contador
depois do adapter, liberação em falha de `connect`, fechamento na saída de
`use()`, candidato antes da persistência, bloqueio por falha, bloqueio pela
condição do store, retirada em resultado incerto, rename, teste sem
publicação, fechamento do registry no startup, datasource desabilitado não
aberto, limites pelo mínimo, conexão de verificação fechada, pinning por
`hostaddr`, comparação do DNS persistido, erro sem contexto, catálogo antes do
legado, admissão parada no início do `close()` e fechamentos encadeados no
`close()` e na falha parcial de startup.

## 6. Gates desta versão

### 6.1. Ambiente

Ambiente Linux descartável (x86_64, Python 3.11.15), executado como usuário
sem privilégio com `umask 022`; a suíte integral rodou numa thread com pilha
de 64 MiB. PostgreSQL **16.13** descartável: `initdb` com `--no-locale`,
`UTF8`, SCRAM-SHA-256, `TimeZone=UTC`, somente `127.0.0.1` em porta
temporária, senha aleatória só em arquivo privado do ambiente. Nenhum banco
existente do usuário foi tocado. Versões: psycopg 3.3.6 (libpq 18.6),
pytest 9.1.1, pydantic 2.13.5, mcp 2.2.0, fastapi 0.141.1, uvicorn 0.53.0,
pglast 8.4, cryptography 50.0.1, Ruff 0.16.8, mypy 2.3.1.

### 6.2. Resultados

| gate | resultado |
|---|---|
| suíte Python integral, sem deselect, PostgreSQL 16.13 real | **4.036 testes: 4.028 aprovados, 4 falhas ambientais, 0 erros, 4 skips**; **nenhum skip por DSN**; JUnit 251,5 s |
| testes da Etapa 3 | **92/92 aprovados** na suíte integral |
| catálogo da Etapa 2 (`test_datasource_catalog.py`) | **114/114 aprovados** |
| Ruff check | aprovado |
| Ruff format `--check` | aprovado; 156 arquivos |
| mypy strict (`src` + `tests`), plataforma `win32` | aprovado; 156 arquivos sem erros |
| mypy strict (`src` + `tests`), plataforma nativa Linux | 1 erro preexistente em `tests/test_browser_harness.py:27` (`winerror` só existe no typeshed do Windows); nenhum erro em arquivo alterado |
| `git diff --check` | aprovado |
| mutantes | 35/35 detectados (§5) |
| wheel e sdist | construídos fora do checkout; wheel `bc11ca191ea49b52714b2c5991fe1763354e53493404bdc1edbe3b3a3df9cc77`, sdist `bb7499cb56d96adf56a88da2976ec9ccf37938db72b0c111e0d4218b4859f4b1` |
| pacote instalado | wheel e sdist instalados em ambientes separados, executados com `python -I` fora do checkout: quatro recursos da UI, zero módulos de catálogo carregados pelo bootstrap legado, startup do catálogo, sessão, shutdown e liberação dos locks aprovados nos dois |

Depois da execução integral, a única mudança foi a anotação de tipos de um
dublê em `test_datasource_registry.py`, exigida pelo mypy; o arquivo foi
reexecutado (29/29). Os pacotes foram construídos da mesma árvore `src/`
medida, conferida arquivo a arquivo.

Os 4 skips são exclusivos do Windows (omissão de `fsync` de diretório e
limitação de modo). As 4 falhas são ambientais deste Linux e foram
reproduzidas idênticas em `b368da3`, sem a Etapa 3, no mesmo ambiente:

| teste | causa |
|---|---|
| `test_admin_http_lifecycle.py::TestBindReal::test_bind_em_ipv6_loopback` | o ambiente não tem IPv6 (`Address family not supported by protocol`) |
| `test_admin_http_mcp_coexistence.py::TestSessaoMcpComAdminAtivo::test_o_processo_encerra_sem_deixar_a_porta_aberta` | porta em `TIME_WAIT` logo após o encerramento (`Address already in use`) |
| `test_admin_ui_startup.py::test_exact_raw_flag[True-1\x00]` | `environ` POSIX não aceita byte NUL |
| `test_admin_ui_startup.py::test_process_uses_raw_flag_without_querying_secret_provider[1\x00]` | idem |

A primeira execução integral, antes da revisão, também acusou
`test_db_leakage.py::TestPublicApiSurface::test_adapter_exposes_only_the_allowed_names`:
`cancel` ampliava a API pública fechada do adapter. A ampliação é deliberada
(D-090) e foi registrada no próprio teste.

### 6.3. Medição posterior no Windows

Na revisão posterior, o teste de subprocesso falhou em dois cenários porque
comparava `stderr` com `\n` literal; o subprocesso nativo do Windows emitia
`\r\n`. O teste agora normaliza exclusivamente CRLF para LF antes de conferir
o mesmo texto fixo e a ausência do canário. Nenhum erro de produto foi
reproduzido nessa falha. O lote direcionado da Etapa 3 e do catálogo da
Etapa 2 passou: **206/206**, sem skips, em 62,134 s.

A suíte integral desta correção foi executada em Python nativo do Windows,
com PostgreSQL 16.15 descartável e pilha de thread de 64 MiB; o resultado
foi **4.036 coletados, 4.028 aprovados, 8 skips exclusivos de POSIX, 0 falhas,
0 erros, 0 deselects e nenhum skip por DSN**, em 780,862 s. Os skips foram
cinco de `fsync` de diretório e três de bits de modo POSIX. O banco só ouviu
em loopback, com credencial temporária. Nenhum banco existente foi tocado.

### 6.4. Não executado nesta revisão

- **Gates Node, build do frontend e browsers.** A etapa não altera o frontend
  nem os recursos embarcados; não foram executados e não são declarados
  aprovados.

## 7. Limitações conhecidas

- A capacidade só é ligada pelo composition root. A prova de F9-023 em
  subprocesso usa um driver que chama `build_application`; a ativação por
  settings de processo e a prova pelo entrypoint real pertencem à Etapa 7.
- Nenhuma fronteira externa consome o registry: PGWire (Etapas 7–10) e o MCP
  multi-datasource (Etapa 11) ainda não existem. A sessão de
  `gateway/datasources.py` é o plano de dados mínimo para prova.
- Drenagem por desabilitação ou remoção não força término: a sessão admitida
  termina sob seus próprios limites. O idle timeout e clientes lentos são da
  Etapa 7.
- O shutdown espera sem timeout (D-057/D-090). `connect_timeout` não cobre
  resolução DNS anterior à libpq; cancelamento e `statement_timeout` não cobrem
  validação nem masking locais. Portanto não há teto total garantido nesta
  etapa. Isso é aceito apenas enquanto a capacidade nova depende do parâmetro
  interno `datasource_catalog`. Antes de expor candidatos pela Admin API v2
  (Etapa 4), a resolução DNS precisa de limite efetivo; antes de expor
  consultas por PGWire (Etapa 8) ou MCP multi-datasource (Etapa 11), o
  processamento local também precisa de limite efetivo, sem abandonar threads
  ou conexões.
- `verify-full` usa a raiz de confiança padrão da libpq; o modelo não tem campo
  de CA. Configurar CA específica é decisão futura.
- Em subprocesso sem o `main()`, o uvicorn da Admin HTTP escreve em `stderr`
  "Shutting down" e "Finished server process [pid]" ao encerrar. O
  comportamento é preexistente, foi medido também em `b368da3` e não carrega
  dado.
- O gate de frontend não foi repetido nesta revisão da Etapa 3 (§6.4).

## 8. Resultado

A Etapa 3 está implementada localmente dentro do escopo autorizado. Ruff,
format, mypy, `git diff --check`, mutantes e pacote instalado passaram. A
medição inicial em Linux teve quatro falhas ambientais preexistentes,
reproduzidas sem a etapa. A revisão posterior corrigiu somente a expectativa
de quebra de linha em dois cenários do teste de subprocesso e fechou o gate
integral no Windows com PostgreSQL 16.15 real: **4.028 aprovados, oito skips
POSIX, zero falhas ou erros**, sem excluir testes. A limitação de D-090 fica
aceita apenas no opt-in interno da Etapa 3 e condiciona as próximas fronteiras
externas (§7). Os PostgreSQL descartáveis foram parados e removidos depois de
cada medição. Não houve push, e a Etapa 4 não foi iniciada.
