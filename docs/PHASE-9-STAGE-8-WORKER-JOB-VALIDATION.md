# Worker — composição privada de um job

**2026-10-23 — implementada sob delegação; código e evidência final revistos
pelo Claude2 sem bloqueador.** D-118 é escolha delegada, não aprovação individual.
B-1 fim a fim, B-2 e D-090 gate2 continuam abertos; SQL PGWire recusada.
Não há worker integrado ou chamador operacional deste corpo.

## Escopo e checkpoint

HEAD4a5e5560abb495898c9e1b8ca44ac2d155681015, origin/master em cache
5d173ea938eb12db33bc880bf67a2e81a208fd5e,0behind/1ahead. Não houve fetch,
commit/push/escrita .git ou segundo escritor. Baseline632 arquivos e
.venv/pyvenv.cfg em docs/poc/evidence/worker-job-source-baseline-20261023.json,
SHAa16e502ee59787df17aa4e8d1e6acb29b442813a8356bd7d5839118aeeb6ab6d.
Arquivos/capturas/evidências anteriores preservados.

Só um arquivo **novo de produto**, runtime/worker_job.py; nenhum arquivo
anterior de produto alterado. Dois testes estruturais anteriores agora
permitem somente esse consumidor privado do encoder/frame. O frame continua
recusando qualquer consumidor novo do receiver. Testes próprios verificam
que nenhum módulo operacional importa worker_job, com contraprovas de
imports absolutos/relativos; não é prova contra toda reflexão Python.

| Fonte final | SHA256 |
| --- | --- |
| runtime/worker_job.py |e93e3c3e38aeeb212c0bca5d5ab6f961eb5c7df1ee37aafb70bc8498bf5758a8|
| tests/test_worker_job.py |b5b4089d9719bc6ff502fc7f52706b80c28eb107229d1a141dfa21ce9d6f03e2|
| tests/test_result_encoder.py |585324b38dbcbd120c9920bfcc72b42a9187d26cf8a7d3a6ca2d352767487893|
| tests/test_result_frame.py |ef776988809d117cde7344696d1219eb4ea749335f7612914c0ca2b8717a95fa|

## Contrato implementado

run_job recebe adapter exato já conectado/dono exclusivo, SQL str exata e
ResultIdentity/ResultLimits/ResultDeadline exatos. Revalida estruturas,
limita SQL a64KiB UTF8 (len antes de contar blocos4KiB, sem NUL/surrogate),
exige max_rows int exato igual ao setting lido uma vez no adapter.
Não verifica vínculo da identidade à geração/lease: isso cabe ao dono.

Deadline/saúde antes da execução, depois e após encoding; relógio absoluto
nunca renovado. Só uma _execute_typed_validated e um encode_result usando
o pipeline existente, sem cópia do parser/proveniência/masking. O encoder
autovalida D-113; o job confere também forma/tamanho contra o limite recebido.
Só frame completo é devolvido, nunca TypedMaskedResult/linhas/parcial.
Deadlines aqui são cooperativos; dependem do supervisor futuro para impor
prazo de chamada/CPU/nativo bloqueados. Não é contenção de memória.

JobOutcome frozen/repr redigido, bool implícito recusado; só frame bytes
no sucesso ou categoria enum no erro. Construção local confiável não é
autenticador de frame/decoder IPC ou sandbox contra reflexão. O máximo
estrutural16MiB repete D-113; o sucesso também exige o limite específico da
chamada, evitando aceitar saída maior por divergência entre constantes.

Classificação por **identidade de tipo**, sem ler mensagem/SQLSTATE/diag:
- InvalidQuery/QueryRejected exatos → QUERY; tipo não representável → TYPE;
  D-117 QUERY/TIMEOUT e encoder TYPE/LIMIT só são candidatos;
- candidato requer saúde positiva pós-settle e tempo restante no momento
  de formar resultado. Saúde perdida → CONNECTION, prazo/clock → DEADLINE;
- RESOURCE/CONNECTION/INTERNAL, MemoryError, integridade, erro genérico,
  subclasses não listadas, grupos e interrupções são fatais, sem frame;
- J6: KeyboardInterrupt/SystemExit/GeneratorExit viram INTERNAL **fatal**,
  não sinal propagado nem cancelamento recuperável. Futuro dono deve parar
  e recolher em todo fatal; não usar este módulo como middleware de shutdown.

Depois do handler só categoria/booleans persistem; resultado/frame local
descartados e frames inativos limpos quando possível. Falha na limpeza é
INTERNAL fatal. Não promete apagar RAM, GC imediato, frames ativos de
caller/debugger ou objetos nativos/grupos que outro dono retenha. OOM ao
construir o próprio outcome não tem garantia de recuperação neste processo.

Não cria/conecta/fecha/cancela adapter nem faz rollback próprio (o adapter
mantém settle), lê ambiente/secret, log, spawn/thread, transporte ou fila.
Não libera crédito mesmo no fatal. Dono futuro continua responsável por
fatal persistente, ID monotônico, um job em voo, geração/lease, domínio
físico, pin/HELD/reap e canal quieto. Não houve integração desses requisitos.

## Revisões e resultados iniciais preservados

Claude2 sessão51ea0d85 revisou plano antes de código sem bloqueador após
J1–J6: tipos exatos/ordem, lenSQL antes de encode, max_rows exato, checagens
por fase, correlação a cargo do dono e interrupção explícita. J6 escolheu
a alternativa fatal admitida pelo revisor, por sigilo do protocolo interno.

Testes vieram primeiro: coleta falhou por módulo ausente. Primeiras rodadas
detectaram duas fixtures usando row_count em vez de rows, IDs de teste
com payloads enormes causando erros de setup e classificação de surrogate
como INTERNAL. IDs curtos e fixtures corrigidos; Unicode inválido agora
é PROTOCOL sem execução. Um patch intermediário colocou retorno de sucesso
antes da execução (42 falhas/26 passed), corrigido para após encode/saúde;
nenhuma dessas rodadas é apresentada como gate aprovado.68 passaram então.
Uma fixture de exception usou YAML inválido; corrigida sem tocar o loader.
Ruff/mypy novos também apontaram anotações/estilo, corrigidos antes dos gates.

Seleção relacionada inicial:1.405 passed/2 failed/116,04s. Ambos eram os
guards históricos que recusavam qualquer consumidor do encoder/frame.
Admitido só worker_job.py, mantendo guard operacional separado. A rodada
seguinte passou1.409/109,94s, antes da regressão J7 abaixo.

Primeira revisão do código sem bloqueador para composição privada; notas:
conferir tamanho contra limits.max_frame_bytes e repetir obrigação J6 no
registro de decisão. Incorporadas. Uma regressão de saída do encoder acima
do limite foi adicionada e passou.

**J7, regressão própria antes do fix:** comparação de classes via `in`
aceitava metaclass.__eq__ customizado como se fosse InvalidQuery, dando
QUERY/can_continue=True para erro opaco. O teste falhou primeiro com esse
resultado; correção usa somente `is`/`or`, sem igualdade de classe.
104 testes focados passaram depois. Não era ingresso exposto; o contrato
interno de tipo exato agora vale também nesse caso adversarial.

| Gate final | Resultado medido |
| --- | --- |
| Casos próprios |104 passed/0,84s|
| Seleção após J7, primeira rodada |1.409 passed/1 failed/129,73s; deadline Unicode40s|
| Mesmo caso Unicode isolado, sem mudar teto/código |1 passed/30,38s; chamada30,25s|
| Repetição relacionada final, sem workloads paralelos próprios |1.410 passed/107,11s;0 falhas/erros/skips|
| Ruff src/tests |aprovado|
| Format src/tests |267 arquivos conformes|
| mypy strict alvos3.11 e3.14 |267 arquivos, ambos sem erro|
| Runtime executado |somente Windows3.11.3|

O deadline Unicode40s pertence a teste anterior do encoder, cujo código
não mudou neste lote. A falha da rodada após J7 fica preservada; houve
build/checks próprios paralelos, mas isso **não comprova causa**. A rodada
anterior verde e o caso isolado verde também não descartam defeito de teste
ou disponibilidade. Causa permanece indeterminada. Repetição relacionada
serial não amplia prazo, cota, skip/xfail nem deseleciona o caso. O episódio
fica como **observação aberta** de disponibilidade do teste denso, próximo
ao próprio deadline; futuras calibrações não devem apagá-lo ou presumir
causa já demonstrada. Não se introduz CI ou aumento de teto neste lote.
Terminal real/exit0 da sessão50258 preservado em
docs/poc/evidence/worker-job-tests-terminal-20261023.json; só fragmento
terminal, não cópia da saída integral. Zero falhas/erros/skips é inferido da
linha de resumo pytest que só imprime1.410 passed, não de arquivo JUnit.
O revisor não executou nem recontou testes.

Seleção relacionada: test_worker_job, test_db_execution_error,
test_db_typed_result, test_result_encoder, test_result_frame,
test_result_receiver, test_result_receive_primitives, test_runtime_snapshot,
test_runtime_snapshot_process, test_runtime_budget, test_runtime_domain,
test_result_budget, test_purity e test_plan_separation. Sem deselect interno.
Fakes para conexão/cursor, parser/engine/adapter/encoder/validator reais.
Provas de máscara antes do frame, exceção autoritativa/alias/derivada,
truncamento, mesma conexão/uma execução/sem fallback, recusa real TYPE/LIMIT,
SQL UTF8 exato/+1, saúde/deadline por fase, subclasses/grupos/controle,
sigilo/console, forma do outcome, guarda estrutural e J7. Seleções se
sobrepõem; não somar104 ao total relacionado.

Nenhum PG/DockerCLI novo ou carga física, listener, worker processual,
ingresso SQL, dependência/setting/porta ou mudança UI. Subprocessos dos
testes anteriores de snapshot/import não são worker integrado. A suíte
PG16 de D-117 não é evidência de execução deste módulo contra PG real.
Não houve nova suíte integral/browsers sem caminho operacional alterado.

## Pacotes

Rodada A em %LOCALAPPDATA%/Temp/maskgw-job-package-20261023-eac45765:
wheel/sdist com44 módulos carregados iguais aos fontes; job em adapter
fechado recusou CONNECTION sem frame/continuidade. Ambos perfis C1 NOT_READY,
stale worker_job e checkout recusados. Esse sucesso é histórico **anterior
ao fix J7**; seus arquivos não foram sobrescritos nem declarados finais.

Rodada B em raiz nova maskgw-job-package-20261023-a078f697, após J7. Build
inicial exit0 (chamada40614c), anterior ao checker/lista commands. Sem
rede/build isolation; checker faz wheel do sdist fora do checkout, valida
caminhos/tipos/tamanho de148 membros antes de extrair; wheel122 entradas.
Todos os .py maskgw de ambos wheels comparados com src. Dependências vêm
do interpretador existente, não isoladas. Sonda -I -B com cwd externo e
targets separados --no-index/--no-deps/--no-compile; sem PYTHONPATH/secrets.
Asserts do checker ativos, sem -O e com -I ignorando PYTHONOPTIMIZE.

Resultado B terminal/exit0;44 módulos carregados de cada target, iguais aos
fontes. Job em adapter fechado → CONNECTION sem frame/continuidade e C1
continua com dois NOT_READY. Build-sdist (wheel reconstruído), instalações
e sondas exit0; duas contraprovas stale/checkout exit1 esperado. Programa,
resultados e quatro logs de cada rodada estão preservados em
docs/poc/evidence/worker-job-package-20261023.json,
41.319bytes/SHA97e6acd26b1d68cf77d0d8f087f98c1002e37b75add223f1fee9b49a74001867.
Cópia distingue hashes do módulo A (77d2bdd1...) e final B (e93e3c3e...),
sem reclassificar A como produto final. Logs completos do build inicial
permanecem externos com hash/tamanho identificados na cópia; não estão na
lista commands do checker. Nenhuma alegação de determinismo entre wheels.

| Artefato B final | SHA256 |
| --- | --- |
| wheel |96d78001108e7b22f1c31870a83d337b4f7a0db7e622bbaaa5bd447079bfc018|
| sdist |8894e650824ef54035ce490e844c5f08b26f800ad5958180a71c4a4973255fda|
| wheel reconstruído |85e0e0f335ec6ad582f9b500a366b5ea22a05840e2606531c8a8a3a0cfd741ed|

Sonda testa import/origem/bytes e recusa com adapter fechado; **não** executa
job saudável, PG, aplicação instalada completa, IPC ou imposição de SO.
Teste de execução saudável foi somente no pytest com conexão fake.

## Fechamento

Claude2 sessão51ea0d85/handle35436 terminal: rerevisão de J7, guards
estreitos, tamanho do frame, D-118, resultado B e evidência sem bloqueador
para fechar composição isolada. Duas notas documentais incorporadas acima:
Unicode40s como observação aberta e zero falhas inferido do resumo, não de
JUnit. Só documentos mudaram depois dos gates; não se repetiram as suítes.
Auditoria final dos632 arquivos: somente oito documentos e dois testes
estruturais anteriores mudaram; nenhum arquivo anterior de produto. Reverter
só as duas exceções estreitas nos guards recupera seus bytes/hashes anteriores
exatos. Capturas e .venv/pyvenv.cfg preservados. Raw A/B coincide com externos
e hashes/tamanhos; fonte do job final coincide com B. Registro em
docs/poc/evidence/worker-job-source-audit-20261023.json,
SHA4f6eab205048eb41c39bdb624c520101eeb933cd908c062deb48227887e381a8.
git diff --check limpo, só avisos LF/CRLF; HEAD inalterado e0behind/1ahead
contra referência em cache. Nenhuma cota observada ou job agendado novo.
Sem inferir B-1 fim a fim,
B-2 ou D-090 gate2. SQL PGWire continua0A000, C1 NOT_READY e destino real
ainda não identificado. Não houve commit/push/deploy ou mudança de recursos
anteriores para fazer os gates passarem.
