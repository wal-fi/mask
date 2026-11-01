# Controle nativo benigno do chamador de admissão — desenho revisado

Data: 2026-11-01, America/Sao_Paulo. Sob delegação vigente; decisões técnicas
do programador, não aprovações individuais do usuário. O desenho inicial foi
seguido pelo adaptador e pelo orquestrador privados, ambos com testes
simulados, descritos nas notas finais. Não há CLI, consumidor, comando, raiz,
nonce operacional, execução ou chamada nativa neste lote. As notas preservam
a ordem dos incrementos; medições do revisor estão na validação do runner.
Fontes congeladas: backend `pg16_shell_admission_win32.py` 10c9058f, chamador
`pg16_shell_admission_host.py` dfcc4ed6, sonda/preparador/entrada e estado de
16 campos. Este desenho não autoriza efeito nativo: procedimento, comando e
raiz exatos ainda exigem proposta e revisão próprias.

Referências primárias Microsoft (citadas, não consultadas pelo programador):
[UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute),
[Nested jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs),
[Job objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects),
[The Old New Thing, 2023-02-09](https://devblogs.microsoft.com/oldnewthing/20230209-00/?p=107812).
Distinção: jobs aninhados existem a partir do Windows 8; o atributo
`PROC_THREAD_ATTRIBUTE_JOB_LIST` a partir do Windows 10. O artigo de 2023
explica que os jobs da lista são atribuídos na ordem dada antes da thread
inicial executar; essa leitura foi conferida pelo revisor, não pelo programador.

## 1. Objetivo e três casos fixos

Provar com o mesmo launcher pinado (`.venv/Scripts/python.exe`, bfff5171) e
argv fixo `(launcher, "-I", "-B", "-c", LITERAL)` que a contenção funciona:

1. **NORMAL**: `print("MASKGW-NATIVE-CONTROL-NORMAL")`, sai 0.
2. **TERMINATE**: `SLEEP` abaixo, terminado à força pelo orçamento.
3. **LAST_CLOSE**: `SLEEP`, encerrado só por fechar o último handle de um job
   `KILL_ON_JOB_CLOSE`, sem nenhum `TerminateJobObject`/`TerminateProcess`.

`SLEEP = 'import time;print("MASKGW-NATIVE-CONTROL-READY",flush=True);time.sleep(120)'`
(120 s > 60 + 10 de decisão e limpeza). Só stdlib; nunca sonda, runner ou
worker. Literais, launcher, os dez nomes de ambiente do chamador e limites são
constantes; não há executável, código, argv, ambiente, prazo ou callback de
entrada.

## 2. Por que dois jobs e o que é observado

O `Owner` aceito retém o único handle do seu job e `close()` recusa job vivo;
fechar `ledger["job"]` por fora mutaria estado aceito, e qualquer handle
retido do job kill-on-close anularia o teste. Solução aceita:

- **OUTER**: job observador e de contenção, retido até o fim.
- **INNER**: job `KILL_ON_JOB_CLOSE` cujo único handle (próprio, não herdável,
  nunca duplicado nem passado ao filho) é o objeto do teste.
- O filho nasce membro de ambos com `PROC_THREAD_ATTRIBUTE_JOB_LIST`
  exatamente `[outer, inner]`, na ordem, na criação suspensa. Filhos do filho
  herdam os dois por padrão (sem breakaway em nenhum). INNER fica aninhado em
  OUTER. Lista recusada, aninhamento não suportado ou ordem divergente é
  `LAUNCH_FAILED` do caso, sem fallback de atribuição posterior.
- Fechar INNER enquanto OUTER está aberto é observação em **outro** job: as
  contas e a lista de PIDs de OUTER cobrem todos os membros, inclusive um
  interpretador base criado pelo launcher e qualquer membro criado depois de
  um snapshot, sem `OpenProcess` e sem handles por PID.
- OUTER também é `KILL_ON_JOB_CLOSE`, `ActiveProcessLimit=2`, sem breakaway:
  rede de segurança se o processo de controle cair.

## 3. Reuso mínimo: subclasse só de controle

Módulo novo `docs/poc/pg16_shell_native_control_win32.py` carrega o backend
10c9058f por SHA num namespace próprio e define `NestedJobOwner(Owner)`, uma
subclasse explícita construída nova; nunca monkeypatch de globais/assinaturas
aceitas nem instâncias vivas emprestadas. A subclasse só altera o próprio
estado. Herdados sem cópia (correção: `_call` **não** está nesta lista, é
sobrescrito como descrito abaixo): construtor base, `_start`, `_ok/_error/
_fail/_hold/_expect/_close`, `_guarded/_interrupt/_contain_job/_abort/_quarantine`,
`_wait/_peek`, consultas de OUTER (`_config/_accounting/_members`, que usam
`ledger["job"]` = OUTER), `setup()`/`start()` públicos e todas as primitivas
de supervisão.

Sobrescritos, com justificativa (correção da revisão: o `_start` herdado
**não** é copiado; ele já despacha por `self._ok` → `self._call`, inclusive
para `UpdateProcThreadAttribute` e `ResumeThread`, e esse é o ponto de
extensão):

- `_setup`: chama `super()._setup()` (OUTER, NUL, pipe, herança conferida) e,
  ainda dentro do mesmo `_guarded`, cria INNER (`CreateJobObjectW`), registra
  `inner` no ledger logo após sucesso coerente (saída inválida, alias ou
  exceção: quarentena/HELD como no backend), aplica e relê a mesma
  configuração e confere INNER não herdável. O proxy de auditoria (§5) é
  instalado logo após o setup herdado, antes de criar INNER. Setup não cria
  processo.
- `_call` (único despacho alterado; demais nomes repassados sem mudança a
  `super()._call`):
  - `UpdateProcThreadAttribute` com atributo `JOB_LIST`: valida que o buffer
    recebido é exatamente `(HANDLE*1)` com `ledger["job"]` e tamanho 8; cria
    `(HANDLE*2)(outer, inner)`, guarda em `self._keep` até o fim e delega com
    tamanho 16. Qualquer divergência devolve resultado de falha sem delegar,
    e o `_start` herdado segue o caminho de falha de atributo já aceito.
  - `ResumeThread`: antes de delegar, verifica INNER com chamadas diretas a
    `super()._call` por um auxiliar fixo que recebe o handle explicitamente
    (`IsProcessInJob(process, inner)` verdadeiro, configuração de INNER
    relida, contas (1,1), lista `[pid]` com tamanho validado). Falha: não
    delega e devolve resultado de exceção; o `_start` herdado faz
    `_abort("WIN32_RESUME", in_job=True)` sobre OUTER, que contém os mesmos
    processos, e o owner registra `inner_verified=False` à parte.
  - Nunca troca `ledger["job"]`, globais aceitas ou assinaturas; não se
    auto-intercepta (os auxiliares usam `super()._call`).
  - Todo o resto do `_start` herdado permanece: quarentena, alias, PI,
    ciclo da lista de atributos, `_abort` e HELD.
  - Invariante que impediria esse reuso: só se o backend deixasse de usar
    `self._call` nesses dois pontos; isso é verificado por teste AST sobre a
    fonte pinada 10c9058f, e divergência bloqueia.
- `close` (correção da revisão): exige os mesmos estados permitidos do
  original; se houve processo, prova quietude **antes** de tocar INNER:
  launcher sinalizado (`_wait(0)`), OUTER com zero ativos e lista vazia,
  cópias de stdio do pai fechadas e EOF observado, pelos primitivos herdados.
  Ainda vivo: `WIN32_NOT_QUIESCENT` sem fechar INNER; não comprovado: HELD
  com INNER retido. Só depois fecha INNER (falha → HELD) e chama
  `super().close()`, que revalida e fecha o resto; nenhum `CLOSED` com INNER
  aberto ou forjado.
- Sem processo criado: se `CreateProcessW` nunca foi chamado (setup falho ou
  falha de atributo), nenhum membro é possível; se foi chamado e falhou de
  forma limpa, o `_start` herdado já provou OUTER (0,0) e lista vazia, o que
  cobre INNER por ser aninhado; criação incerta já é HELD herdado. Só então
  os handles extras são fechados.
- Novo `close_inner()`: única operação intencional de fechar job vivo; só em
  `RUNNING`, exige `inner` no ledger, roda sob o `_guarded` herdado e usa
  `_close("inner")` (sai do ledger só após sucesso). Falha: contenção com
  `TerminateJobObject(outer)` enquanto ainda `RUNNING`, depois `_hold`;
  `BaseException`: o `_interrupt` herdado contém OUTER e mantém HELD. Nunca
  contorna guarda de HELD.

Não há framework geral, controle de processos por PID nem `TerminateProcess`
fora do `_abort` herdado.

## 4. Orquestrador `docs/poc/pg16_shell_native_control.py`

API privada única `run(nonce)`; sem `__main__`, CLI ou consumidor. O nonce
(32 hex minúsculo) é só identificador de frescor e consumo: não é credencial,
aprovação nem permissão. Chamar `run` é efeito nativo que continua exigindo
procedimento, comando e raiz próprios e revisados; testes usam nonces
fictícios, caminhos redirecionados e owners falsos.

Fontes por SHA completo, leitura limitada e namespaces novos (correção da
revisão do plano): chamador
dfcc4ed6be3ea8ab47b7a38ca8a9d4bfa00b3c75cda41c365be3dd5b1aa3dac7, adaptador
eaebedd6ac36602ba30cb51a4c30a2a93737f1127c23cdc4ebb8ae8cf9246407 e o backend
10c9058f… **apenas** pelo `definitions()` do adaptador. Uma única identidade de
backend: `Request`, `Owner`, `NestedJobOwner` e `Win32Error` vêm todos dessa
cópia; `_load_backend` do chamador nunca é usado (uma segunda cópia trocaria a
classe de erro e `_attempt` transformaria todo código em `INTERNAL`).

Do chamador só auxiliares genéricos, inalterados, sem mutar limites nem
globais: `_Clock`, `_attempt`, `_new_facts`, `_supervise`, `write_new`,
`strict`, `encoded`, `sha`, `absent`, `real_directories`, `listing`,
`_environment`, `_runtime`, `_launcher_pin` e constantes (`PYTHON`,
`PYTHON_SHA`, prazos, turnos, `RETAIN_BYTES`, `WAIT_MS`, `COMMAND_LIMIT`,
`ENVIRONMENT_NAMES`). Não usados: `run`, `_run`, `_lifecycle`,
`_close_unstarted`, `_held`, `_interrupted` e `_record_held` (mutam
`_HELD_REASONS` e gravariam o kind da admissão), `_project`, `_summary`,
`_publish`, `_sources`, `_load_backend`, sonda, `prepare`, entrada e `drive`.
Prazos 60/10 s e 1200/200 turnos permanecem. Testes só substituem seams nas
cópias em memória.

Registro `_LIVE` e registro HELD próprios do módulo: owner registrado antes de
`setup` e removido só quando provado `CLOSED`; um owner não provado sobrevive
a `run` que levanta e recusa nova `run` antes de qualquer artefato. Contrato
de uma thread. Import e construtores não leem configuração/binários de
runtime nem acionam os controles nativos; há metadados comuns de fonte.

Áreas: privada `Temp/maskgw-pg16-native-control-v1-<nonce>/case-N/` e pública
`docs/poc/evidence/pg16-native-control-<nonce12>/`; ocupante prévio recusa.
Requests e linhas de comando são validados antes de criar a área privada; a
partir daí o nonce está consumido. Ordem fixa 1→2→3; o primeiro caso reprovado
encerra o lote e os demais ficam `NOT_RUN`.

Por caso: `invocation.json` (xb/fsync/releitura, argv privado, nomes de
ambiente sem valores) antes do lançamento; pin do launcher; `_Clock` novo cuja
leitura inicial inválida recusa antes de criar owner (`CONTROL_CLOCK`); owner
registrado; `setup`; relógio inválido ou orçamento de 60 s esgotado depois do
setup impede `start` (fecha sem filho); `start`. Saídas de owner são
comparadas com tipos estritos (`int` que não é `bool`, `tuple`, `bytes`), sem
aceitar valor apenas verdadeiro.

## 5. Ledger de chamadas auditado (caso 3)

Depois de `super()._setup()` a subclasse substitui `self._api` por um proxy
cujo `k` registra cada nome de função antes de chamar a real. É o único ponto
de auditoria: cobre o despacho de `_call` e o `TerminateJobObject` direto do
`_interrupt` herdado. Setup não tem caminho de terminate.

- Finito: no máximo 512 entradas. Estouro ou `Exception` ao registrar marca
  `audit_valid=False` de forma permanente; a chamada real continua, preservando
  a contenção e a limpeza. `BaseException` marca inválido e propaga antes da
  chamada real; nunca se lança ou resume depois de engolir uma interrupção.
- Snapshots imutáveis (tuple substituído) gravados em privado com a flag de
  integridade; nunca se fabrica ledger completo.
- Aprovar o caso 3 exige `audit_valid=True` e nenhum `TerminateJobObject` ou
  `TerminateProcess` em nenhuma fase, incluindo fallback e limpeza.
- Chamada de terminate bem-sucedida nunca é tratada como colheita: a prova de
  recursos continua sendo contas/lista de OUTER, EOF, sinal e `CLOSED`.
- Se a falha de auditoria coincidir com limpeza que não se prova, o owner
  fica retido em HELD; nada de segurança ou posse é descartado.

## 6. Sequências

READY (casos 2 e 3): laço cooperativo próprio com contadores independentes
(`ready_turns`, ≤200, e ≤10 s desde a sua primeira leitura do mesmo `_Clock`),
cada turno `read()` (≤4096) e `wait(50)`; retém ≤1024 bytes nos mesmos fatos;
exige a linha exata `MASKGW-NATIVE-CONTROL-READY` com LF ou CRLF. Motivos:
`READY_MISSING` (ausência por turnos ou tempo), `READY_MISMATCH` (bytes que
não são prefixo da linha), `READY_EARLY_EXIT` (launcher sinalizado antes),
`OUTPUT_OVERFLOW` e `CALLER_CLOCK`. Todo motivo segue para o `_supervise`, que
termina e prova a árvore; nunca há árvore `RUNNING` abandonada nem aprovação.
Leitura/espera falha ou malformada é HELD. O laço nunca toca
`facts["turns"]` (permanece 0), preservando bytes e histórico do relógio.

1. NORMAL (`Owner` aceito, um job): `_supervise` desde o início do caso, depois
   `close`. Aprova com motivo `None`, exit 0 repassado, stdout exatamente a
   linha com LF ou CRLF (framing registrado), total 1 ou 2, EOF, sinalizado,
   zero ativos, lista vazia e `CLOSED`.
2. TERMINATE (`Owner` aceito): READY; `_supervise` com o início do caso; o
   orçamento de 60 s força terminate. Aprova só com READY observado, motivo
   `DEADLINE`, terminate bem-sucedido, exit 1, total 1 ou 2, prova completa de
   recursos e `CLOSED`.
3. LAST_CLOSE (`NestedJobOwner`): READY; snapshot de OUTER pelos métodos
   públicos exige total `int` 1 ou 2, ativos iguais ao total e ao número de
   PIDs, INNER no ledger e `inner_verified is True` (senão `SNAPSHOT_INVALID`);
   `close_inner()` bem-sucedido com `inner_closed is True` (senão
   `CLOSE_INNER_FAILED` se ainda `RUNNING`, HELD caso contrário);
   `_supervise` com início igual à leitura do relógio logo após o fechamento.
   A auditoria é capturada **uma única vez, depois de `CLOSED`**: uma leitura
   de `audit` e uma de `audit_valid`; íntegra só com `audit_valid is True` e
   tupla de `str` (1–64) com no máximo 512 itens. Aprovação, `audit.json` e
   resumo derivam dessa mesma tupla imutável e do mesmo bool. Auditoria
   inválida ou estourada é rejeição própria `AUDIT_INVALID`; o limite 512 do
   adaptador nunca é elevado. Aprova só com INNER fechado, zero terminate,
   OUTER com zero ativos e lista vazia, EOF, launcher sinalizado com exit lido
   (registrado, não previsto) e `CLOSED`. Terminate depois de INNER fechado
   (por exemplo pelo prazo) torna o caso `FAILED_LAST_CLOSE`; sem prova, HELD.

## 7. Persistência, interrupção e publicação

Tudo privado e durável antes da projeção, inclusive em casos `CLOSED`
reprovados: `invocation.json`, `supervision.json`, `local-stdout.bin` e, no
caso 3, `audit.json` e `snapshot.json` (no fluxo normal, esses brutos seguem
`CLOSED`; a invocação o antecede). Em HELD, falha ou
interrupção com owner não provado: owner retido, no máximo um terminate
guardado só se `RUNNING`, e registro HELD próprio e finito (`held.json` com
kind do controle e `local-stdout.bin`, xb, uma única vez, nunca sobrescrito,
removido ou repetido); a exceção original propaga por identidade e falhas ou
segunda interrupção na limpeza/registro não a substituem. Num caminho HELD sem
exceção prévia, uma interrupção chegada durante o registro propaga (não é
engolida). Owner que comprovadamente chegou a `CLOSED` sai do registro mesmo
se a interrupção vier depois. HELD nunca publica. Limite herdado explícito:
segunda interrupção durante o terminate de contenção do `_interrupt` do
backend substitui a primeira.

Pública: `summary.json` com campos fechados por caso (desfecho, rejeição,
exit, framing, total, terminated, ready, inner_closed, integridade e tamanho
da auditoria, contagem de terminate, segundos informativos) e
`transport.json` ligando tamanho/SHA de todo bruto privado e do resumo.
Bytes e valor de retorno são preparados antes; só há publicação com registro
vazio. Antes do rename final, falha ou interrupção pode deixar diretório
público parcial ou `.next`: fica consumido, sem remoção nem retry; o que se
garante é a ausência de `transport.json` final válido. O rename não
sobrescrevente é a última operação tentada: depois da tentativa não há I/O
nem em sucesso nem em exceção. Se o rename levanta, o efeito pode ter
ocorrido; o resultado é `CONTROL_COMMIT_INDETERMINATE` (levantado fora do
`except`, sem `__context__`/`__cause__`), nunca "não publicado"; interrupção
na tentativa propaga por identidade.

## 8. Matriz de testes com fakes

`NestedJobOwner` com o kernel falso do backend estendido a dois jobs: AST da
fonte pinada confirma que `_start` usa `self._ok`/`self._call` para
`UpdateProcThreadAttribute` e `ResumeThread`; `_start` herdado é o mesmo
objeto (não sobrescrito); buffer de um job inesperado recusado sem delegar;
verificação de INNER antes do resume real, falha sem chamar `ResumeThread`;
`close` vivo ou não comprovado não toca INNER; ledger com estouro ou falha de
registro invalida aprovação e ainda repassa terminate; ordem e
conteúdo exato de `JOB_LIST=[outer,inner]` (16 bytes) e `HANDLE_LIST`; INNER
não herdável e configurado; membro de só um job recusado antes do resume;
falha/alias/exceção na criação de INNER; `close_inner` ok, falso (contenção
enquanto RUNNING e HELD), exceção e interrupção; `close` fecha INNER antes do
`CLOSED`; ledger auditado inclui o terminate direto do `_interrupt`; nenhum
`OpenProcess`.

Orquestrador com owners falsos e cópias por SHA do chamador e do adaptador:
identidade única do backend e `_load_backend` nunca usado; limites e globais
do chamador inalterados; nonce inválido, fonte divergente, registro retido e
áreas ocupadas recusados antes de artefato; ordem fixa e parada no primeiro
reprovado; NORMAL com framing/exit/total/sobra errados; TERMINATE sem READY,
com sobra, saída precoce ou exit ≠1; LAST_CLOSE com terminate na auditoria,
auditoria inválida/estourada/malformada/não-bool, snapshot vazio ou com
`bool`, INNER ausente, não verificado ou `close_inner` sem efeito; captura
única da auditoria após `CLOSED`; relógio inválido e orçamento esgotado sem
`start`; interrupção em cada fase com a mesma exceção, owner retido e
registro HELD; segunda interrupção sem substituir; interrupção durante a
publicação sem owner retido; rename que efetua e levanta, rename
interrompido e sucesso, todos sem I/O depois da tentativa; transporte
recomputado arquivo a arquivo; nenhum valor de ambiente gravado; bans de
`ctypes.WinDLL`, `Popen`, `os.system`, `Thread.start` e de leitura em `.venv`.

## 9. Limites honestos

- Atribuir a morte ao fechamento de INNER é inferência: um membro pode morrer
  por outra causa na mesma janela; registrado, não provado.
- "Último handle" só vale para os handles deste processo: o mesmo usuário ou
  um administrador pode duplicar o handle de INNER a partir de fora
  (`DuplicateHandle` com acesso ao processo de controle), e o kernel pode
  manter referências próprias; nesse caso o fechamento não mata a árvore e o
  caso reprova pelo prazo. Não há prova universal de último handle.
- Semântica nativa de `JOB_LIST` com dois jobs e aninhamento sob um job da
  ferramenta só será observada na execução; se recusada, o caso reprova.
- Exit code após kill-on-close é registrado, não previsto.
- Chamadas síncronas do SO não têm limite; orçamentos são verificados entre
  chamadas, sem prazo absoluto de parede.
- O agente não faz leituras explícitas de runtime/config/binários agora, mas
  a partida futura do CPython/venv lê `pyvenv.cfg`, `site`, DLLs e stdlib
  implicitamente; não há promessa de partida sem configuração. Só o launcher
  é pinado.
- Um literal benigno, uma amostra: não certifica contenção de árvore
  arbitrária, memória, C1/B1/B2/D090 nem libera produção.

O adaptador `NestedJobOwner` e o `run(nonce)` privado estão implementados com
fakes, conforme as notas seguintes. Próximo passo: procedimento e proposta
exatos dos controles, sob revisão antes de qualquer efeito nativo. Não há
`__main__` ou consumidor. Gateway, B1/B2/D090/C1/SQL e produção seguem abertos.

## Notas de implementação — adaptador aninhado (primeiro incremento)

Registro histórico do incremento publicado em c03fd10, anterior ao runner
descrito na seção seguinte; a ausência do orquestrador abaixo vale para aquela
rodada, não para o estado atual.

2026-11-01, America/Sao_Paulo, sob delegação vigente. Só
`docs/poc/pg16_shell_native_control_win32.py` e
`tests/test_pg16_shell_native_control_win32.py`; o orquestrador
`pg16_shell_native_control.py`, `__main__`, consumidor, raiz, comando e
execução nativa **não** existem. Nenhum teste executado pelo programador.
Backend 10c9058f e chamador dfcc4ed6 inalterados.

- Carga preguiçosa explícita: import e construtores não leem nada; só
  `definitions()` lê o backend por SHA (leitura limitada, sem reparse),
  confere por AST o invariante de reuso (`_start` usa `self._ok` para
  `UpdateProcThreadAttribute`, `self._call` para `ResumeThread`, e `_ok`
  usa `self._call`), executa num namespace privado novo e constrói a
  subclasse. Falha: `ControlError("CONTROL_SOURCE")`.
- Sobrescritos exatamente: `__init__` (só telemetria própria: `inner_verified`,
  `inner_closed`, `audit`, `audit_valid`, `_pair`), `_setup`, `_call`,
  `close`, `close_inner`, e auxiliares próprios (`_entry`, `_record`,
  `_query`, `_job_config`, `_job_accounting`, `_job_members`,
  `_expand_job_list`, `_verify_inner`, `_close_inner`, `_close_extra`). `_start`, `start`,
  `_abort`, `_interrupt`, `_guarded` e primitivas de supervisão são os mesmos
  objetos do backend (teste de identidade).
- `_call` delega tudo sem mudança, exceto: atualização `JOB_LIST` validada
  (buffer `(HANDLE*1)` exato com OUTER, tamanho 8, flags 0, sem retorno
  anterior, par ainda inexistente) vira `(HANDLE*2)(outer, inner)` mantido em
  `_keep`; caso contrário devolve falha sem delegar. `ResumeThread` só é
  delegado depois de INNER verificado (membro, configuração, contas (1,1),
  lista `[pid]` com cabeçalho e tamanho validados), por `super()._call` com o
  handle explícito; falha devolve resultado de exceção e o `_start` herdado
  aborta sobre OUTER.
- `close` comum prova quietude (sinalizado, OUTER zero ativos e lista vazia,
  cópias de stdio fechadas, EOF) antes de soltar INNER; vivo/não comprovado
  não toca INNER. Criação limpa falha prova OUTER (0,0) e lista vazia antes;
  sem `CreateProcessW` tentado, nenhum membro é possível. INNER sai antes de
  o `close` herdado declarar `CLOSED`.
- `close_inner` só em `RUNNING`, sob `_guarded`; falha contém OUTER ainda em
  `RUNNING` e depois HELD com INNER retido.
- Auditoria: proxy instalado após o setup herdado; máximo 512 entradas;
  snapshots imutáveis; estouro ou `Exception` ao registrar marcam
  `audit_valid=False` para sempre e a chamada real segue (limpeza preservada).
  `BaseException` ao registrar marca inválido e **propaga antes** da chamada
  real: nunca lança `CreateProcessW` nem `ResumeThread` depois de uma
  interrupção; o `_guarded` herdado fica HELD e contém OUTER pelo
  `_interrupt`, cujo terminate direto também é auditado.
- Limite herdado: se uma segunda interrupção chegar durante o terminate de
  contenção do `_interrupt` herdado, ela propaga no lugar da primeira; o
  backend aceito não promete preservar o primeiro sinal nesse ponto.

### Correções após revisão de e7ccc759 (achados do revisor)

Revisão independente reproduziu dois P2 com o kernel falso (registro do
revisor; regressões formais escritas antes da correção, não executadas pelo
programador):

- P2-A: `_call("UpdateProcThreadAttribute", ...)` com `JOB_LIST` em `args[2]`
  mas aridade diferente de 7 escapava da expansão e chegava ao nativo. Agora
  qualquer aridade diferente de 7 nessa API é recusada antes de delegar, para
  qualquer atributo; `JOB_LIST` exige `int` exato e passa pela validação de 7
  argumentos; `HANDLE_LIST` válido continua repassado sem mudança.
- P2-B: a transição do recurso extra no `close` comum ficava fora do guard
  herdado; uma interrupção vinda da auditoria no `CloseHandle` de INNER deixava
  o estado `RUNNING`. Agora todo o trecho (prova de quietude, cópias de stdio,
  EOF e fechamento de INNER) roda sob `_guarded`: recusa conhecida
  (`WIN32_NOT_QUIESCENT`) passa sem efeito; exceção comum (por exemplo
  alocação) vira HELD `WIN32_INTERNAL` com contenção de OUTER; interrupção de
  controle vira HELD `WIN32_INTERRUPTED`, contém OUTER e repropaga. INNER fica
  retido e nunca há `CLOSED` com ele aberto. O `close` comum nunca chama
  `close_inner`. A parte herdada de `super().close()` (depois de INNER solto)
  mantém o comportamento aceito do backend.
- Removido o `noqa: C901` desnecessário do PoC.

## Notas de implementação — orquestrador privado (segundo incremento)

2026-11-01, America/Sao_Paulo, sob delegação vigente, com as correções do
revisor ao plano incorporadas nas seções 4, 6, 7 e 8. Só
`docs/poc/pg16_shell_native_control.py` e
`tests/test_pg16_shell_native_control.py`; adaptador eaebedd6, backend
10c9058f, chamador dfcc4ed6 e estado de 16 campos inalterados. Sem
`__main__`, CLI, consumidor, raiz, comando ou execução nativa. Nenhum teste
executado pelo programador; medições do revisor estão em
`PHASE-9-W1-PG16-SHELL-NATIVE-CONTROL-VALIDATION.md`.

- Seams (só nas cópias privadas, só em testes): no orquestrador `TEMP`,
  `EVIDENCE` e `_owner_class`; na cópia do chamador `_environ`,
  `_monotonic`, `_sleep`, `_launcher_pin` e `sys`; `os.rename` e
  `write_new` envolvidos para provocar falhas. Os testes banem
  `ctypes.WinDLL`, `Popen`, `os.system`, `Thread.start` e leitura sob `.venv`.
- Códigos fechados `CONTROL_*`; `RunError` levantado fora de `except`.
- Limite: o teto 512 da auditoria é menor que o pior caso de chamadas
  permitido pelos orçamentos (READY 200 turnos e supervisão 1200 turnos,
  2–3 chamadas cada; estimativa por leitura de código, não medida). Falha
  fechada como `AUDIT_INVALID`, nunca aprovação falsa; elevar o teto exigiria
  mudar o adaptador e nova revisão.
- Limite: pin do launcher e criação do processo não são atômicos; a
  auditoria não cobre as chamadas do setup herdado anteriores ao proxy (sem
  caminho de terminate nesse trecho, pela leitura da fonte).

### Achados da revisão do orquestrador 0dfcd0f4 (regressões antes da correção)

Revisão independente só com fakes reproduziu três P2; o orquestrador foi
rejeitado e não publicado. Instantâneos rejeitados preservados em
`docs/poc/evidence/native-control-review-20261101`. Nesta etapa só foram
escritas regressões em `tests/test_pg16_shell_native_control.py`, não
executadas pelo programador; nessa rodada o orquestrador ficou intacto até o
revisor medir o vermelho.

- A: leitura final do relógio inválida (NaN, regressiva ou não-float) era
  ignorada quando já havia motivo esperado (`DEADLINE` no caso 2), que era
  aprovado com `seconds` nulo. Exigido: rejeição `CALLER_CLOCK` mantendo a
  prova de limpeza e os bytes privados.
- B: após falha comum, uma interrupção de controle chegada no terminate de
  contenção ou na gravação do registro HELD era descartada e `run` devolvia
  `CONTROL_INTERNAL`. Exigido: essa interrupção propaga por identidade, owner
  retido, nada publicado.
- C: falha na fronteira do auxiliar de retenção (por exemplo `MemoryError`
  ou nova interrupção) substituía a interrupção original. Exigido: a original
  propaga por identidade; registro retido salvo owner provado `CLOSED`; sem
  evidência pública confirmada.

Correções (depois do RED medido pelo revisor; só no orquestrador; nenhum
teste executado pelo programador, verde não reivindicado):

- A: `_finish` valida a leitura final sempre. Inválida e motivo ainda
  esperado (nenhum, ou `DEADLINE` no TERMINATE) vira `CALLER_CLOCK`, com
  `seconds` nulo; demais motivos já rejeitam e ficam como estão. Owner já
  `CLOSED`, prova de limpeza e brutos privados preservados; caso e lote
  rejeitados, casos seguintes `NOT_RUN`. TERMINATE com relógio válido segue
  aprovando pelos critérios existentes. O `supervision.json` registra então
  `CALLER_CLOCK` no lugar do `DEADLINE` esperado (`terminated` mantém o fato
  do terminate).
- B/C: a chamada de retenção inteira fica sob `_contain`: falha comum na
  fronteira (inclusive alocação) é absorvida; a primeira interrupção nova,
  devolvida por `_retain` ou levantada na fronteira, é devolvida. Com falha
  comum ativa, essa interrupção propaga por identidade, levantada fora do
  `except`; sem interrupção, segue `CONTROL_INTERNAL` saneado. Com
  `BaseException` original ativa, nada na retenção a substitui. O registro é
  reconciliado à parte: owner já `CLOSED` sai mesmo se a retenção falhou antes
  de soltá-lo; owner não provado continua retido; nada é fabricado.
- Limites: a interrupção nova de B pode carregar no `__context__` a falha
  comum que estava sendo tratada quando chegou (encadeamento automático do
  Python; o objeto não é alterado). Segue explícito o limite herdado do
  backend sobre segunda interrupção no terminate de contenção do
  `_interrupt`.

### Achado da revisão de 31fd2ead: retenção reentrante (regressões antes da correção)

Os três achados anteriores ficaram limpos, mas o revisor reproduziu o limite
reentrante declarado no relatório do programador, contrário ao contrato
aceito de no máximo um terminate guardado na retenção. Exemplo: leitura comum
falha no READY do TERMINATE (HELD `READY`, owner `RUNNING`); `_held` chama
`_retain` (um terminate) e a gravação de `held.json` recebe uma interrupção; `_held` a
levanta, `_case` a captura e `_contain` chama `_retain` de novo, que tenta um
segundo terminate porque o registro gravado só é conferido depois do
terminate. Instantâneos em `docs/poc/evidence/native-control-review-20261101`.

Regressões escritas antes da correção (não executadas pelo programador):
retenção repetida faz no máximo um terminate de emergência, preserva a
identidade da interrupção, mantém o owner não resolvido e não repete gravações
xb; o mesmo vale se a interrupção chega durante o primeiro terminate de
retenção. O terminate de decisão do supervisor herdado é política separada e
não consome a tentativa de emergência (teste com exatamente duas chamadas:
uma do supervisor, uma da retenção).

RED medido pelo revisor antes da correção, com a fonte 31fd2ead inalterada:
as duas regressões de reentrada falharam e o controle de separação do
supervisor passou (2 falhas, 1 aprovado, 80 desmarcados).

Correção (só no orquestrador; testes inalterados; nenhum teste executado pelo
programador): cada episódio de retenção tem duas reservas próprias do caso,
feitas antes do efeito: `contained` para o único terminate guardado de
emergência (só com owner `RUNNING`) e `recorded` para o único registro HELD
finito. Uma reentrada após interrupção, tentativa falha ou tentativa
interrompida não repete o terminate nem as gravações xb. O terminate de
decisão do `_supervise` herdado não usa nem consome essa reserva. Identidade
da interrupção original, propagação da primeira interrupção nova,
reconciliação do registro (`CLOSED` sai, não resolvido fica) e ausência de
publicação em HELD permanecem como antes. O limite de dupla retenção deixa de
existir na implementação atual; fica só este registro histórico.

Gateway, B1/B2/D090/C1/SQL e produção seguem abertos.
