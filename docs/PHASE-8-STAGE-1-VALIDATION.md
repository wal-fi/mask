# Fase 8 — evidência da Etapa 1

**Estado:** aprovada; Etapa 1 concluída. **Data:** 2026-09-09.
Entrega exclusivamente documental, vinculada à [especificação integral
aprovada](PHASE-8-SPEC.md) e à [matriz normativa](PHASE-8-TRACEABILITY.md).
A Etapa 2 e qualquer implementação funcional não foram iniciadas.

## Checkpoint anterior à primeira alteração

| Item | Observado |
|---|---|
| Branch | master |
| HEAD | 27d92bd580875e9eb2abb04db102eb98af2054fe |
| origin/master local | 27d92bd580875e9eb2abb04db102eb98af2054fe |
| Ahead / behind | 0 / 0 |
| Working tree | Limpa |

Nenhum fetch, reset, checkout, alteração de dependência ou ajuste do produto
foi necessário. origin/master é a referência local conferida; não se presume
estado remoto novo nem se faz push nesta rodada.

## Ambiente e execução real

Windows; Python da `.venv` existente. PostgreSQL **16.15** confirmado por
`SHOW server_version` e `SHOW server_version_num`, da imagem local já presente
`postgres:16-alpine`. Contêiner de teste isolado e descartável, banco
`maskgw_test`, porta publicada somente em **127.0.0.1**, sem download de imagem.
Senha aleatória e `MASKGW_TEST_DSN` transmitidos apenas pelo ambiente dos
processos de teste, sem registrar credenciais neste documento ou no Git.
O contêiner e seu volume descartável foram removidos após a suíte.

A suíte inteira foi executada com o ajuste temporário documentado de pilha
**64 MiB por thread**, sem modificar código ou testes. Comando efetivo, com
`CAMINHO_TEMPORARIO` representando o relatório XML fora do repositório:

```text
.venv/Scripts/python.exe -c "import threading, pytest; threading.stack_size(64 * 1024 * 1024); raise SystemExit(pytest.main(['-q', '-ra', '--junitxml=CAMINHO_TEMPORARIO/pytest.xml']))"
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/python.exe -m ruff format --check src tests
.venv/Scripts/python.exe -m mypy --strict src tests
```

Sem `--deselect`, `-k`, `-m integration` ou filtro equivalente nesta reprodução.
Não foi executada uma segunda seleção de integração; números históricos dessa
seleção permanecem identificados como históricos nos outros documentos.

| Gate | Resultado efetivamente medido |
|---|---|
| Pytest completo | **2312 coletados; 2304 aprovados; 8 skips; 0 falhas; 0 erros; 0 deselected**; exit 0 |
| Ausência de DSN | **0 skips** por ausência de MASKGW_TEST_DSN |
| Plataforma | **8 skips POSIX**: 5 de fsync de diretório e 3 de bits de modo POSIX |
| Avisos pytest | **1 PytestWarning** preexistente sobre `match` vazio em test_admin_http_lifecycle; não é skip/xfail ou falha |
| Duração pytest | **405.515 s** no JUnit; **414.84 s** de processo medidos pelo lançador |
| Ruff check | `All checks passed!`; exit 0 |
| Ruff format check | `121 files already formatted`; exit 0 |
| mypy strict | `Success: no issues found in 121 source files`; exit 0 |
| git diff --check / git diff --cached --check | Sem erros; exit 0; inclui os 11 documentos, inclusive os novos |

As contagens foram apuradas nos 2312 elementos testcase do JUnit e conferidas
com seus totais: errors 0, failures 0, skipped 8, tests 2312. Não há xfail ou
finding convertido em skip. A suíte Python permaneceu intacta.

Após pytest retornar **0**, o lançador temporário encontrou um
`UnicodeEncodeError` ao imprimir a cauda do log em console cp1252. O XML e o
resultado do subprocesso já estavam gravados; o cleanup do contêiner ocorreu.
O problema foi somente da apresentação do lançador, não do pytest ou produto.
Ruff, format e mypy ainda não tinham iniciado; foram executados separadamente
e todos retornaram 0. Não foi necessário repetir a suíte nem alterar testes.

## Skips condicionais identificados no JUnit

| Teste | Condição |
|---|---|
| tests.test_admin_adversarial.TestLeakageNasFalhasDeEscrita::test_durability_error_depois_do_replace_nao_vaza | fsync de diretório POSIX |
| tests.test_admin_http_audit.TestDurabilidade::test_durability_error_publica_com_revision_after | fsync de diretório POSIX |
| tests.test_admin_http_writes.TestDurabilidade::test_fsync_de_diretorio_falho_publica_com_applied_true | fsync de diretório POSIX |
| tests.test_admin_service.TestDurability::test_real_directory_fsync_failure_is_post_commit_on_posix | fsync de diretório POSIX |
| tests.test_config_filesystem.TestDurability::test_directory_fsync_failure_is_post_commit | fsync de diretório POSIX |
| tests.test_config_filesystem.TestValidation::test_group_writable_config_is_rejected_on_posix | bits de modo POSIX |
| tests.test_config_filesystem.TestValidation::test_world_writable_parent_is_rejected_on_posix | bits de modo POSIX |
| tests.test_config_filesystem.TestValidation::test_reused_lock_must_be_mode_0600_on_posix | bits de modo POSIX |

Os ramos POSIX continuam condicionais; este host Windows não os executou.
A reprodução não encerra o risco conhecido de pilha do payload gigante nem
altera os findings aceitos nas revisões de segurança anteriores.

## Revisão documental e segurança

A especificação foi transcrita integralmente da última proposta revisada
aprovada, preservando seções, tabelas, contratos, versões, limites, testes e
critérios. As únicas mudanças nela são o título/estado, a confirmação das
quatro aprovações e o limite explícito de execução à Etapa 1; espaços finais
foram normalizados para o gate de whitespace. Não houve redução normativa.

D-061: entrega embarcada/opt-in/mesma origem e rollback. D-062: interpretador
fechado público/privado, custo e exposição residual. D-063: operações
granulares, reorder só de regras, SQL aditivo e sem PUT /config pela UI.
D-064: memória volátil, recuperação humana e gates reais. A matriz F8-001 a
F8-065 cobre todas as subseções normativas e as vincula às Etapas 2–9,
componentes previstos e contraprovas/gates. Ela não alega testes UI entregues.

A busca completa anterior à edição percorreu os Markdown do repositório,
seguida de conferência de todas as referências a Fase 7/Etapa 11 e nova busca
após a edição. Foram corrigidos:

- ROADMAP: Fase 7 marcada em andamento/Etapas 1–6; ausência atual de escritas,
  validate, adoção e AdminAudit recontextualizada como histórico da Etapa 7.
- ARCHITECTURE: Fase 7 em implementação e Etapa 11 ainda não iniciada.
- DECISIONS: cabeçalho em andamento, introdução desatualizada sobre FastAPI e
  alcance dos registros posteriores a D-054; o histórico técnico foi mantido.
- TEST-PLAN: cabeçalho da Fase 7 limitado às Etapas 1–6, embora as onze já
  estivessem concluídas. Contagens históricas das etapas foram preservadas.
- CLAUDE/HANDOFF/ROADMAP: estado de Fase 8 não iniciada e próximos passos,
  quantidade de decisões e checklist antigo de 2121/486 testes no handoff.
- HANDOFF: nove skips de medição anterior explicitamente rotulados como
  históricos; evidência atual registra os oito observados nesta rodada.
- HANDOFF/ROADMAP/SECURITY: afirmações genéricas de ausência de porta de rede
  ou autenticação diferenciadas entre MCP stdio e Admin API HTTP local.
- AGENTS: exceção de interface limitada à UI administrativa local e opt-in
  da especificação aprovada, sem autorização para antecipar a Etapa 2.

Requisitos históricos/normativos corretos da Fase 7, seu bloqueio atual por
presença de Origin/Referer e as exclusões do produto permanecem preservados.
SECURITY-REVIEW, THREAT-MODEL, FUTURE-HARDENING e PHASE-7-SPEC não precisaram
ser alterados. A política futura do navegador está claramente identificada
como aprovada, ainda sem implementação. Não há frontend MCP, SQL, auditoria
consultável, expansão de rede, token persistente ou flexibilização genérica
de CORS aprovada por esta rodada documental.

## Limite da entrega

Somente Markdown de especificação, decisões, matriz, evidência e estado.
Nenhum package.json, lockfile, configuração TypeScript, JS/CSS/HTML, asset,
manifesto, flag, rota, header, schema ou código funcional foi criado/alterado.
Nenhuma dependência instalada; nenhum ajuste de skip/xfail, produto, runtime,
persistência ou MCP. Não foram executados gates frontend nem se declara
cobertura de navegador ainda inexistente nesta etapa.

Os gates e a revisão documental/de segurança passaram antes de alterar o
estado para Etapa 1 concluída. A conferência do índice incluiu exatamente os
11 documentos autorizados, nenhum arquivo funcional. A especificação integral
e a numeração D-001 a D-064/F8-001 a F8-065 foram conferidas.

Entrega preparada para o único commit local, com autor/committer
w.filho <w.filho@live.com> e trailer
Co-Authored-By no padrão do projeto, identificando Codex como coautor desta
rodada. Após o commit, conferir árvore limpa e exatamente 1 ahead / 0 behind
em relação à referência origin/master preservada. **Parar antes da Etapa 2;
nenhum push ou publicação.**
