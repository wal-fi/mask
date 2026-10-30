# Fase 9 — Etapa 8 — B-1: equivalência observável em outro processo

**Estado (2026-10-19): incremento de testes implementado localmente, revisão
técnica concluída e lote aprovado explicitamente pelo usuário. Sem código de
produção novo, commit ou push. Não fecha B-1 fim a fim, B-2 ou D-090 gate 2;
SQL de cliente continua recusado.**

## 1. Autorização e checkpoint

Após aprovar o núcleo B-1 e a D-111, o usuário respondeu **"sim"** ao lote
proposto: comprovar equivalência do snapshot em processo isolado, sem SQL
de cliente nem integração operacional, com revisão pelo Claude2, localmente
e sem commit/push. Não é autorização de worker ou supervisor de produção.

Checkpoint: `master`, HEAD `4a5e5560abb495898c9e1b8ca44ac2d155681015`;
referência local `origin/master` em
`5d173ea938eb12db33bc880bf67a2e81a208fd5e`, 1 ahead/0 behind. Sem fetch.
O working tree já estava modificado: preservados o núcleo B-1, a tipagem
anterior, documentação e arquivos pessoais não rastreados. Foi tomado um
freeze de **435 arquivos** em `src`, `tests`, `docs`, AGENTS/CLAUDE,
`pyproject.toml` e `.venv/pyvenv.cfg`, antes deste incremento.

Conferência final contra esse freeze: sete documentos existentes alterados,
dois arquivos de testes e esta evidência adicionados, nenhum removido.
Todos os arquivos em `src`, as dependências e `.venv/pyvenv.cfg` continuaram
com os mesmos hashes, inclusive as alterações preexistentes do usuário.

## 2. Entrega somente em testes

- `tests/snapshot_child_probe.py`: helper autossuficiente, somente stdlib e
  `maskgw.*`. Não importa `tests.*`. Importá-lo no pytest não instala hook;
  o entry point instala a guarda somente no filho, antes de importar produto.
- `tests/test_runtime_snapshot_process.py`: **35 casos novos**, com processo
  real iniciado por `sys.executable -I -B`, cwd temporário fora do checkout,
  ambiente restrito e sem shell. A instalação editável já existente permite
  importar `maskgw` pelo site-packages; não há ajuste de `sys.path` nem
  dependência de `PYTHONPATH` para isso.

O snapshot canônico existente é enviado **somente por stdin**. Argumentos
contêm apenas o caminho fixo do probe, identidade pública esperada e seletor
fechado de fixture. Nenhum snapshot ou segredo é escrito em arquivo. Somente
credenciais, chaves e linhas **sintéticas** são usadas.

O filho usa `recompile_snapshot`, loader e engine existentes. Recebe no máximo
`MAX_SNAPSHOT_BYTES + 1`, permitindo recusar excesso. O JSON de observações
tem teto de 16 KiB verificado antes de ser emitido e após a coleta pelo pai.
Não contém linhas, conninfo ou chaves: só digests agregados de fixtures,
booleans, PID, identidade pública e categorias fechadas.

**Limites da prova:** fingerprints SHA-256 iguais demonstram equivalência
observável sob essas entradas, não comparação literal byte a byte nem
autenticação. Incluem material derivado de chaves sintéticas; não são formato
ou canal autorizados para dados reais. A estrutura de observações é só do
harness, **não** um codec de resultados do produto. Coleções não ordenadas da
política SQL são ordenadas explicitamente; `PYTHONHASHSEED` é ignorado por
`-I` e não serve para obter igualdade artificial.

## 3. Casos medidos

| Grupo | Prova |
|---|---|
| Determinísticos | Nove configurações, 15 valores/tipos e nove descritores por configuração; fingerprints tipados, decisões, parâmetros, NULL e erro de aridade. |
| Matching | Aliases, exceptions autoritativas, prioridade de derivados, default ALLOW, ordem, exact/contains e case sensitivity. |
| AST | Quatro SELECTs constantes somente analisados, sem execução SQL; mesmos índices de sensibilidade. |
| Configuração | Limites efetivos, extensões SQL aditivas, alvo com `hostaddr` e identidade explícita. |
| Random | Cinco configurações; entropia controlada só em contexto de teste, restaurada no pai e no filho, mais invariantes de alfabeto/comprimento com entropia real. |
| HMAC | Geração antiga continua equivalente após mudar o ambiente do pai e compilar uma nova; os resultados das duas gerações diferem. Filho com HMAC/chave-mestra/PGHOST/PYTHONPATH sintéticos divergentes não altera o resultado. |
| Provider exato | Provider customizado devolve espaços preservados no snapshot; resultado difere do provider que normaliza a mesma chave. |
| Isolamento Python | PID diferente do pai; flags `isolated`, `ignore_environment`, `no_user_site`; módulo `maskgw` adversarial no cwd não é importado. |
| Recusas | Entradas vazias, ASCII inválido, NaN, duplicata, profundidade/tamanho, truncamento, forma não canônica, versão, política, segredo ausente/desconhecido e datasource/geração/revisão divergentes ou tipo bool. |
| Guardas do harness | Hook só no filho nega eventos de socket/subprocesso e `os.system`; autocontraprovas de eventos recusados. `EnvSecretProvider.get` é substituído por recusa durante recompilação/observação. Sem stderr nem chave/conninfo nos argumentos ou saída. |

As guardas são **instrumentação do teste**, não sandbox de SO nem fronteira
de segurança de produção. Não se afirma bloqueio de toda forma possível de
I/O nativo. `subprocess.run(timeout=15)` recolhe o probe confiável e finito;
não é o supervisor aprovado para workers, nem demonstra teto de memória ou
cleanup sob falhas de SO. O limite de saída não foi testado contra um filho
malicioso que contorne o próprio harness.

## 4. Gates medidos neste incremento

Windows nativo, CPython **3.11.3** já existente; nenhuma instalação ou
recriação da `.venv`. Sem PostgreSQL, Docker, rede ou banco do usuário nos
testes. A rede foi usada somente para a revisão solicitada no Claude2.

- Seleção consolidada: **286 passed**, zero falhas/erros/skips, exit 0:
  201 do núcleo B-1, 35 do processo e 50 de pureza/separação de planos.
  Resumo pytest: **35,08 s**; XML: **31,970 s** no escopo da suíte.
- Estabilidade: **três repetições integrais dos 35 casos de processo**,
  todas com 35 passed, zero falhas/erros/skips e exit 0; tempos de
  **26,69 s**, **26,74 s** e **28,09 s**. Sem fixar hash seed do filho.
- Ruff check `src tests` e format: aprovados, **229 arquivos**.
- Mypy strict `src tests`, alvos **3.11 e 3.14**: aprovados,
  **229 arquivos** cada, executados pelo interpretador 3.11.3.
  Não é execução no CPython 3.14.
- Suíte integral, PostgreSQL real, pacotes instalados, frontend/browsers e
  POSIX: **não repetidos neste incremento somente de testes**. Os números
  do lote anterior permanecem históricos, não evidência desta árvore.

Comando da seleção: `.venv\Scripts\python.exe -I -B -m pytest -o
addopts=--strict-markers -q -p no:cacheprovider --tb=short
tests/test_runtime_snapshot.py tests/test_runtime_snapshot_process.py
tests/test_purity.py tests/test_plan_separation.py`.

Primeira rodada: **31 passed, 1 failed**; o teste esperava `INVALID` para um
transformer desconhecido e o contrato existente retorna `POLICY`. Corrigida
a expectativa, não o produto. Os erros iniciais de tipagem ficaram restritos
ao harness e foram corrigidos. A rodada intermediária de 236 passou, mas a
checagem final do provider exato foi reforçada depois; os 286 acima já usam
esse reforço. Não houve skip, xfail ou deselect para contornar falha.

JUnit temporário, fora do checkout:
`%LOCALAPPDATA%\Temp\maskgw-b1-process-20261019-focused.xml`.
SHA-256: `9c1c1c936ca5394736dfea4433c4bfc0cb469dc74f1ebf3d5f4542ebb055133f`.

Fontes medidos (SHA-256):

- probe: `6c1c8c2c6322aebcdf3c3a8bbe4e447a06d046a218f9215915c2b3aab7621708`;
- testes: `0c7d05f9c6b23a92de22e113a0c023f94674cf0df1d03eb44ca3b544e38e9e61`.

## 5. Revisão e pendências

Claude2 revisou o plano em modo somente leitura. A implementação mantém o
probe autossuficiente e fora do padrão `test_*.py`, hook exclusivo do filho,
ordem explícita das coleções e fingerprints agregados de dados sintéticos.
A revisão final do código e desta evidência não apontou bloqueador no escopo
estreito. O revisor destacou que o patch escopado da entropia também afeta o
módulo `secrets` compartilhado durante a chamada: o harness roda serialmente,
restaura o patch e não introduz esse mecanismo em produto. Os resultados das
três repetições foram conferidos pelo implementador; o revisor não executou
os testes nem confirmou os tempos de execução.

Depois dos gates só documentos foram ajustados para registrar resultados e
revisão. Os dois hashes de testes da §4 permaneceram iguais; não se repetiram
as suítes por essas alterações exclusivamente editoriais. `git diff --check`,
UTF-8 estrito e whitespace dos dez arquivos do incremento foram conferidos.

**B-1 fim a fim continua aberto:** não há captura real de lease, vínculo de
geração no ingresso, nonce/tag de handshake ou worker integrado. A passagem
de bytes aqui usa pipes privados do teste, não transporte operacional.
**B-2 e D-090 gate 2 continuam abertos**; a falha agregada anterior de memória
continua reprovada. Não há cursor novo, orçamento de memória/admissão,
supervisor, codec de resultado, bootstrap/registry/driver/MCP/Admin/UI novos.
PGWire continua recusando SQL de cliente com `0A000`; nenhuma liberação de
produção, commit ou push foi feita ou está implícita neste incremento.

## 6. Aprovação do incremento

Em 2026-10-19, depois do relatório dos resultados e limites deste lote, o
usuário respondeu **"aprovado"**. A aprovação abrange somente o incremento
de testes de equivalência observável em outro processo. Não fecha B-1 fim a
fim, B-2 ou D-090 gate 2 e não autoriza worker, integração operacional,
SQL de cliente, commit, push ou produção.

O registro da aprovação alterou somente documentos. Código, testes, hashes,
resultados e limitações foram preservados; as suítes não foram repetidas
para esse fechamento exclusivamente editorial.
