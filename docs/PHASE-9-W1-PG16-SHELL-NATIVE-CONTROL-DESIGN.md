# Controle nativo benigno do chamador de admissão — desenho revisado

Data: 2026-11-01, America/Sao_Paulo. Sob delegação vigente; decisões técnicas
do programador, não aprovações individuais do usuário. O desenho inicial foi
seguido apenas pelo adaptador privado e seus testes com fakes, descritos nas
notas finais. Não há orquestrador, comando, raiz, nonce operacional, execução
ou chamada nativa neste lote.
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

API privada única `run(nonce)` (32 hex minúsculo); sem `__main__`, CLI ou
consumidor. Carrega o chamador dfcc4ed6 por SHA e usa só definições genéricas
como objetos imutáveis: `_Clock`, `_attempt`, `_new_facts`, `_supervise`,
`write_new`, `strict`, `encoded`, `sha`, `regular`, `absent`,
`real_directories`, `_environment`, `_runtime`, `_launcher_pin`. Nunca chama
`run`, sonda, `prepare`, entrada ou `drive`, e nunca altera globais da cópia
para encurtar prazos (60/10 s e 1200/200 turnos permanecem). Testes só
substituem seams na sua própria cópia em memória.

Registro `_LIVE` próprio do módulo: owner registrado antes de `setup`,
removido só após `CLOSED`; sobrevive a `run` que levanta; owner retido recusa
nova `run` antes de qualquer artefato. Contrato de uma thread, sem promessa de
concorrência. Import e construtores não tocam runtime nem APIs nativas além de
metadados comuns de fonte.

Áreas: privada `Temp/maskgw-pg16-native-control-v1-<nonce>/case-N/` e pública
`docs/poc/evidence/pg16-native-control-<nonce12>/`; qualquer ocupante prévio
consome. Ordem fixa 1→2→3; o primeiro caso não aprovado encerra o lote.

Por caso: `invocation.json` (xb/fsync/releitura, argv privado, nomes de
ambiente sem valores) antes do lançamento; pin do launcher; relógio `_Clock`;
owner registrado; `setup`/`start` com `_attempt`.

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

READY (casos 2 e 3): laço cooperativo próprio, ≤10 s e ≤200 turnos, cada
turno `read()` (≤4096) e `wait(50)` ou pausa; retém ≤1024 bytes nos fatos;
exige a linha exata `MASKGW-NATIVE-CONTROL-READY` com LF ou CRLF. Ausência,
sobra ou estouro define `facts["reason"]="READY_MISSING"` e o `_supervise`
conduz terminate e prova; nunca aprovado. Antes do supervisor zera-se
explicitamente `facts["turns"]`, preservando bytes, fatos e histórico do relógio.

1. NORMAL (`Owner` aceito, um job): `_supervise` desde o início do caso, depois
   `close`. Aprova com motivo `None`, exit 0 repassado, stdout exatamente a
   linha com LF ou CRLF (framing registrado), total 1 ou 2, EOF, sinalizado,
   zero ativos, lista vazia e `CLOSED`.
2. TERMINATE (`Owner` aceito): READY; `_supervise` com o início do caso; o
   orçamento de 60 s força terminate. Aprova só com READY observado, motivo
   `DEADLINE`, terminate bem-sucedido, exit 1, total 1 ou 2, prova completa de
   recursos e `CLOSED`.
3. LAST_CLOSE (`NestedJobOwner`): READY; snapshot de OUTER exige total 1 ou 2,
   ativos iguais ao total e lista não vazia, com INNER presente; `close_inner()`
   bem-sucedido; `_supervise` com início igual à leitura do relógio no fechamento.
   Aprova só com INNER fechado, ledger sem terminate, OUTER com zero ativos e
   lista vazia, EOF, launcher sinalizado com exit lido (registrado, não
   previsto) e `CLOSED`. Prazo que leva ao terminate de OUTER torna o caso
   `FAILED_LAST_CLOSE`; sem prova, HELD; nunca aprovado.

## 7. Persistência, interrupção e publicação

Tudo privado e durável antes da projeção: `invocation.json`,
`supervision.json`, `local-stdout.bin` e, no caso 3, `audit.json` e
`snapshot.json`. Em interrupção ou falha: owner retido, até um terminate
guardado só se `RUNNING`, registro HELD e bytes parciais por melhor esforço
(`_interrupted`/`_record_held` do chamador, com o diretório do caso), e
repropagação da exceção original; falhas ou segunda interrupção na limpeza não
a substituem. Nada é publicado.

Pública: `summary.json` com campos fechados por caso (desfecho, exit,
framing, total, terminated, inner_closed, contagem de terminate, segundos
informativos) e `transport.json` ligando tamanho/SHA de todo bruto privado e
do resumo. Um único rename final não sobrescrevente é a última operação;
sem I/O depois, sem retry ou remoção.

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

Orquestrador com owners falsos e cópia do chamador: ordem fixa e parada no
primeiro reprovado; NORMAL com framing/exit/total errados; TERMINATE sem READY
ou exit ≠1; LAST_CLOSE com terminate no ledger, snapshot sem membros, INNER
ausente ou close falho; interrupção em cada fase com registro retido e nova
`run` recusada; invocação antes do lançamento; falhas de persistência;
transporte recomputado arquivo a arquivo; nenhum valor de ambiente gravado;
bans de `ctypes.WinDLL`, `Popen` e `Thread.start`.

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

O adaptador `NestedJobOwner` e seus fakes estão implementados nas notas
seguintes. Próximo incremento: apenas `run(nonce)` privado e seus fakes, sem
`__main__` ou consumidor, sob revisão própria. Gateway, B1/B2/D090/C1/SQL e
produção seguem abertos.

## Notas de implementação — adaptador aninhado (primeiro incremento)

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

Gateway, B1/B2/D090/C1/SQL e produção seguem abertos.
