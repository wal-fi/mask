# W1 Oracle — desenho do driver do controlador (v3, para revisão)

2026-11-06. Somente desenho, escrito pelo Claude2 (sessão
51ea0d85-05bb-4d24-ba9a-c9627c3f832f, claude-opus-5-5, esforço medium).
Decisões técnicas sob a delegação vigente; nenhuma aprovação individual do
usuário é inventada. Nenhum código, teste ou efeito: sem Docker, PostgreSQL,
SQL, guard real, processo, socket ou thread. Não autoriza execução.

Fixos e inalterados: núcleo puro `deploy/oracle9_w1_controller.py`
4c155d76, teste 084d62cd, app124 instalado, source20, estado16, tentativa
consumida. APIs públicas de captura/owner usadas como estão.

## 1. Fontes relidas para este desenho

- `runtime/worker_session.py`: `WorkerProfile`, construtor, `open`, `query`,
  `send_result_to`, `_cleanup`, `close`.
- `runtime/budget.py`: `reserve_candidate`, `publish`, `reserve_session`,
  `adopt_session`, `begin_output`, `end_output`, `retain`, `release`,
  `status` (propriedade).
- `runtime/worker_protocol.py`: `SessionKey`, `WireFailure`, `Kind`.
- `pgwire/result_receiver.py`: `ResultReceiver`, `ResultSummary`.
- `pgwire/result_frame.py`: `ResultLimits`, `ValidatedResult.iter_chunks`.
- `runtime/linux_guard.py`: `protect_process`; `tests/test_worker_session.py`.

Fatos usados:

- `WorkerSession(ledger, token, *, lock, key, limits, profile, guard)` exige
  tipos exatos (`lock` é `LockType`), Linux e `GuardFacts` CONTROLLER com
  `pid == getpid() == 1`. O construtor não adota nada.
- `open(snapshot: bytes)` adota exatamente uma vez, sob o lock comum, no
  início de `_open`. Falha antes da adoção: `_cleanup` devolve HELD sem tocar
  o ledger e `state` continua `NEW`. `close()` exige `_adopted`.
- `query(sql: bytes)`, 1..64 KiB. Devolve `ErrorReply` (e já faz cleanup se
  `can_continue` é False) ou `None` somente depois do DONE (estado RESULT).
  Outras falhas fazem cleanup e levantam `WorkerSessionError` JOB.
- `send_result_to(channel)` só em RESULT; devolve
  `ResultSummary(columns, rows, truncated)`; libera o pin. Não renova o
  `idle_end` interno.
- `iter_chunks` começa em `_HEADER.size` = 76: o canal recebe só o **corpo**
  D-113, no máximo F−76 bytes.
- O pin é `begin_output(session, frame_bytes=max_frame_bytes,
  overhead_bytes=…)` e exige `2F + overhead <= parent_bytes`.
- `retain(token)` põe a reserva em HELD sem confirmação. `release` exige
  DRAINING/HELD e confirmação completa; senão HELD.

## 2. Separação de arquivos e carga

- `deploy/oracle9_w1_controller.py`: núcleo puro, inalterado.
- Novo `deploy/oracle9_w1_driver.py`: único entry point. Contém loader,
  orquestração com portas injetáveis e, só no D2, o binding físico.
- O loader executa **código-fonte confiável e fixado**, não dado inerte:
  lê `PURE_PATH` limitado a 64 KiB, confere `PURE_BYTES` e `PURE_SHA`,
  cria `types.ModuleType` com nome privado, registra em `sys.modules` e
  executa os mesmos bytes conferidos. Loader de propósito único; sem
  `sys.path`, sem import implícito de vizinho, sem framework.
- Emenda prospectiva ao plano §4: **dois binds RO de arquivo único**
  (`/opt/maskgw/lab/oracle9_w1_driver.py` e
  `/opt/maskgw/lab/oracle9_w1_controller.py`) mais os tmpfs declarados.
  Comando: `python -I -B /opt/maskgw/lab/oracle9_w1_driver.py`.

## 3. Ordem de início

| passo | ação | falha |
|---|---|---|
| 0 | `Owner()` com slots pré-alocados; objeto puro | — |
| 1 | `protect_process(role=CONTROLLER, address_limit_bytes=384 MiB)` | resultado `GUARD_FAILED`; nada lido |
| 2 | loader do núcleo puro (depois do guard) | `ABORT{phase:LOAD}` |
| 3 | evento `GUARD` | `ABORT{reason:OUTPUT}` |
| 4 | `read_init` (10 s), `decode_init` | `ABORT{phase:INIT}` |
| 5 | `capture(init, 1)` e `capture(init, 2)` | `ABORT{phase:CAPTURE}` |
| 6 | ledger, lock, `reserve_candidate`/`publish` de G1 | `ABORT{phase:LEDGER}` |
| 7 | evento `INIT_OK`, depois os casos | — |

Única exceção à regra "guard antes de tudo": os imports do próprio driver
(stdlib e `maskgw` instalado), puros e sem segredo, como no worker.

## 4. Valores prospectivos fechados (lógicos, sem alegação física)

- `ResultLimits(max_rows=1000, max_frame_bytes=F)`, F = 16 MiB.
- `WorkerProfile(address_bytes=256 MiB, idle_ms=30000 (T3: 1000),
  statement_timeout_ms=1000 em G1 / 30000 em G2,
  output_overhead_bytes=1 MiB)`.
- `BudgetLimits(total_bytes=512 MiB, base_bytes=128 MiB,
  headroom_bytes=64 MiB, entries=4, sessions=1, workers=1, candidates=1,
  generations=2, auxiliaries=1)`; `DatasourceCapacity(sessions=1,
  candidates=1)`; `shared_bytes=1 MiB` por geração; W = 256 MiB;
  P = 2·16 + 1 = 33 MiB.
- Aritmética medida pelo root via API pública (só aritmética):
  `status.reserved_bytes` (já inclui base e headroom) = 483 MiB,
  `available_bytes` = 29 MiB, pin adquirido, segunda reserva CAPACITY.
- G1 fica DRAINING após `publish(replacing=G1)` e não é liberada: não há
  fato de cleanup a confirmar.
- Nenhum limite é aumentado para obter verde.

## 5. Posse, locks e alocações

- `ledger_lock = threading.Lock()` único para driver, `WorkerSession` e
  `ResultReceiver`. O driver só o segura em volta de chamadas ao ledger,
  com aquisição em fatias de 0,25 s até 3 s. **Nunca** durante `query`,
  envio, leitura do host ou join.
- `call_lock` próprio e curto, só para `call_active` em T4.
- Regra de alocação: todo objeto ou fd devolvido com sucesso vai primeiro
  para uma variável local e, antes de qualquer passo falível seguinte, para
  o slot pré-alocado do owner. Se a criação falha com efeito desconhecido
  (pode ter criado algo), o slot vira `UNKNOWN` e o resultado é RETAINED.
- Threads: porta separa `create(target, name) -> handle` (alocado e
  registrado no owner, sem iniciar) de `handle.start() -> bool`. Falha ou
  exceção em `start` retém o handle (pode ter iniciado) e dá RETAINED.
- O owner fecha só endpoints próprios e só depois de join verificado. Sem
  join verificado, mantém endpoints e handle: RETAINED. Nunca há limpeza
  declarada sem fato.

### Sessões

1. `token = ledger.reserve_session(gen, worker_bytes=W, parent_bytes=P)`
   sob `ledger_lock`; `owner.session_token = token`.
2. `session = factory.create(ledger, token, lock=ledger_lock, key=…,
   limits=…, profile=…, guard=…)`; `owner.session = session`.
3. `session.open(snapshot)`: a própria sessão adota. O driver **nunca**
   adota antes.

| falha | ação |
|---|---|
| `create` falha | token RESERVED, não adotado: `ledger.retain(token)`; nunca `close`; ABORT retido |
| `open` falha e `state` é NEW | `ledger.retain(token)`; nunca `close`; ABORT retido |
| `open` falha com HELD/CLOSED | a sessão fez cleanup; se HELD, um `close()` (só repete cleanup físico); persistindo HELD, ABORT retido |
| `close()` HELD ou exceção | ABORT retido; nenhum `reserve` posterior; nunca `CleanupConfirmation` inventada |

Ordem serial: P (G1, jobs 1–19), T1, T2, T3 (G1); `reserve_candidate` +
`publish(replacing=G1)`; T4 e T6 (G2). Cada sessão termina em `close()`
RELEASED ou ALREADY_RELEASED antes da seguinte. T5 não usa sessão (§10).

Contagens: 6 `WorkerSession` (P, T1, T2, T3, T4, T6) + 1 sonda T5
separada; 19 jobs persistentes + 4 chamadas `query` (T1–T4, a de T3 falha
localmente antes do fio); 50 frames aceitos do host, até o GO de T6.

### SessionKey por caso

Sem campo novo no LAB_INIT nem API de produção:
`SessionKey(session_id=ids.session_id(), datasource_id=bytes.fromhex(
DATASOURCE_ID[4:]), generation=1|2, record_revision=RECORD_REVISION)`.
`session_id` vem da porta `ids` (D2: 16 bytes de `os.urandom`; D1: fake
determinística), um por sessão, nunca emitido. A identidade bate com o
snapshot porque o worker recompila com `key.datasource_text()`, geração e
revisão.

## 6. Janela de idle (agregada e conservadora)

O idle do filho começa quando ele termina de responder, sempre depois de
o pai começar a chamada. `send_result_to` não renova o `idle_end`. Sem ler
`_idle_end`:

- Antes de `open` e de cada `query`, o driver grava `t0 = clock.monotonic()`.
- Limite inferior de vida do filho: `t0 + idle_s`. Prazo absoluto da
  próxima transferência: `D = t0 + idle_s − 2 s` (margem fixa).
- Todas as esperas até a próxima `query` (envio do resultado, join do sink,
  eventos, ACK, READY, GO) usam `min(cap_da_fase, D − agora − 1 s)`.
- Se o restante for ≤ 1 s, ou se `D` vencer antes da próxima `query`: falha
  fechada `IDLE_WINDOW`, sem próxima query, e ABORT.

Caps por fase: GO e ACK 20 s; ACK de T1/T2 (sessão já fechada pelo fatal)
90 s, sem `D`. T3 é expirado de propósito e fica isento. T4 termina em
fatal e não tem próxima query. Em P, o job16 pode gastar até 11 s, o que
deixa cerca de 17 s para o resto: o host tem de responder rápido, e não
cumprir é FAIL fechado, nunca aumento de idle.

## 7. Sink por resultado

Somente depois de `query()` devolver `None` (DONE):

1. `a, b = pair.create()`; ambos em local e depois no owner.
2. `h = threads.create(sink(b, …), "sink")`; handle no owner; `h.start()`.
3. `summary = session.send_result_to(RawChannel(a, …))`.
4. `a.shutdown_write()`.
5. `h.join(min(t_send + 33 s, D − 1 s))`.
6. Só com join verificado o owner fecha `a` e `b`.

O sink é uma função pura sobre uma leitura limitada: blocos de no máximo
64 KiB, SHA-256 incremental, contagem e prazo absoluto. Teto
`cap = F − 76 = 16 777 140`. Ao passar do teto ele **para imediatamente**,
sem drenar o resto, e reporta `count = cap + 1` (sentinela). Vereditos
fechados: `OK`, `MISMATCH`, `OVERRUN`, `NO_EOF`, `IO`, `TIMEOUT`.

Passa só com sink `OK` em EOF, contagem e SHA iguais a `bytes`/`sha256`
esperados, e `summary.rows` e `summary.truncated` iguais ao esperado
(`truncated` True só no job9). Qualquer outra coisa (divergência, overrun,
erro, stop ou falha de envio) é ABORT: sem próxima query, sem reuso do
stream. Join falho é RETAINED.

`bytes`/`sha256` cobrem só o corpo D-113, sem o cabeçalho de 76 bytes. O
schema congelado aceita `bytes` até F; valores acima de F−76 nunca batem.
Limitação registrada, sem mudar o teste.

## 8. T4: watcher

Ordem exata (a máquina pura exige ARMED antes de `handoff`):

1. `machine.emit("ARMED", 23)`: transição interna, devolve 46.
2. `seq = machine.handoff()`: 46.
3. `w = threads.create(watch(link, seq, deadline, session, call_state))`;
   handle no owner; `w.start()`.
4. Escreve o evento `ARMED{case:23, next_seq:46}`.
5. Sob `call_lock`: `call_active = True`. Fora do lock:
   `session.query(HEAVY_SQL bytes)`. Sob `call_lock`: `call_active = False`.
6. `w.join(prazo do job G2 + 3 s = 43 s)`.
7. Só com join verificado: `machine.join(obs.raw)`.

Watcher: lê exatamente um frame (`read_control`), decodifica com o
`decode_control` puro e não toca a máquina. Só chama `request_stop()` se o
kind for STOP, o case for 23, o seq for **exatamente 46** e `call_active`
estiver ligado sob `call_lock`. Guarda uma observação imutável: bytes
brutos ou `None`, kind ou `None`, `stop_applied`.

PASS exige `stop_applied=True` e JOB fatal. STOP tardio, NOSTOP ou frame
inválido dão FAIL. Join não verificado dá RETAINED.

## 9. T6, retenção e resultado terminal

- T6 (G2): `SUMMARY` → open → `READY{25}` → GO (cap e `D`) →
  `machine.emit("ARMED", 25)` → evento
  `ARMED{case:25, next_seq:51, live_window_ms}`, com
  `live_window_ms = floor((D − agora) * 1000)`, entre 1000 e 30000; abaixo
  disso, FAIL antes do ARMED.
- O host só pode matar o container dentro dessa janela e só depois de
  provar de forma independente que o worker ou backend está vivo (por
  exemplo, backend do papel em `pg_stat_activity`); sem essa prova, T6 FAIL.
- O driver não aceita frame algum depois do ARMED. Ao fim da janela, o
  resultado é `T6_UNKILLED`, que é FAIL. Nunca há PASS global no driver.

Resultado terminal D1, finito e imutável:

```text
DriverResult(outcome, verdicts, owner)
  outcome:  GUARD_FAILED | ABORTED | RETAINED | T6_UNKILLED
  verdicts: tuple[CaseVerdict, ...]   (25 entradas: PASS, FAIL ou NOT_RUN)
  owner:    referência forte ao Owner se RETAINED; senão None
```

No D1 o RETAINED é só um **valor** que mantém o owner vivo enquanto o
teste o segura. O D2 precisa de uma retenção física: o PID1 nunca volta
para uma saída operacional com recurso vivo incerto, e por exemplo
bloqueia até o host matar o container. Essa estratégia está **pendente** e
não existe antes do D2. Nenhum teste unitário roda sem fim.

## 10. T5

No D1 o caso 24 é `RESULT{verdict:FAIL, kind:PENDING, reason:T5_PENDING}`,
sem ledger nem processo. Nenhum resultado booleano de sonda é aceito como
prova física.

O D3 tem desenho próprio obrigatório: `reserve_session` e `adopt_session`
sob o lock comum, dono enraizado na principal, todos os fds antes do
`Popen`, codec público e o mesmo ambiente do filho, saída natural com
returncode 0 e `release` só com fatos reais de reap.

## 11. Eventos stdout (fechados)

JSON ASCII canônico (chaves ordenadas, sem espaços), uma linha por evento,
no máximo 512 bytes por linha e 56 linhas no total (limite do canal: 256).
Sem string livre nem conteúdo de exceção.

| evento | campos (valores) |
|---|---|
| GUARD | `as` 402653184; `dumpable` 0; `pdeathsig` 0; `pid` 1 |
| INIT_OK | — |
| READY | `case` 1..25; `next_seq` 1..50 |
| ARMED | `case` 23 ou 25; `next_seq` 46 ou 51; `live_window_ms` null (23) ou 1000..30000 (25) |
| RESULT | `case` 1..24; `next_seq` 2..49; `verdict` PASS/FAIL; `kind` RESULT/ERROR/FATAL/PENDING; `rows` 0..1000 ou null; `truncated` bool ou null; `bytes` 0..16777141 ou null; `sink` enum ou null; `reason` enum ou null; `release` RELEASED/ALREADY_RELEASED/HELD ou null; `stop_applied` bool ou null |
| SUMMARY | `failed` lista ordenada e única em 1..24, sempre contém 24; `global_pass` false; `prefix_cases` 24 |
| ABORT | `case` 0..25; `phase` LOAD/INIT/CAPTURE/LEDGER/CASE/CLEANUP; `reason` enum; `retained` bool |
| TERMINAL | `outcome` ABORTED/RETAINED/T6_UNKILLED |

`next_seq = 51` aparece só no ARMED de T6, como metadado pós-último-frame;
nenhum frame é aceito.

Enums:

- `sink`: OK, MISMATCH, OVERRUN, NO_EOF, IO, TIMEOUT.
- `reason` em RESULT: os nomes de `WireFailure` (QUERY, TIMEOUT, TYPE,
  LIMIT, MEMORY, RESOURCE, CONNECTION, INTERNAL, PROTOCOL, DEADLINE); OPEN,
  JOB, OUTPUT, CLEANUP, STATE (de `SessionFailure`); IDLE_WINDOW;
  EXPECTATION; STOP_LATE; T5_PENDING.
- `reason` em ABORT: INIT, CONTROL, PHASE, SQL, CAPTURE, DESTINATION (as
  categorias de `LabRefusal`); EOF, TIMEOUT, IDLE_WINDOW, SESSION, SINK,
  WATCHER, LEDGER, LOAD, EXPECTATION, JOIN, OUTPUT.

`SUMMARY.failed` é a união dos FAIL de caso do driver com
`machine.summary().failed_cases`. Como T5 é sempre PENDING/FAIL, a lista
nunca é vazia e nenhum caminho fake imprime um verde de produção.

## 12. D1: API estável mínima e escopo dos testes

API do driver no D1:

- `load_pure(reader, *, path, sha256, size) -> namespace`
- `run(ports, *, pure) -> DriverResult`
- `Ports(clock, link, guard, ids, factory, pair, threads)`, todas
  injetáveis.
- Funções puras testáveis: `sink_drain(read, *, cap, chunk, deadline)` e
  `watch_once(read, *, expected_seq, decode, call_state)`.

Escopo do primeiro teste: **portas determinísticas sem efeito**.

- Real: o `BudgetLedger`, os codecs e a captura do núcleo puro, `SessionKey`,
  `ResultLimits`, `WorkerProfile` e `GuardFacts` (como valor).
- Fake: uma porta de sessão confiável que emula o contrato da
  `WorkerSession` sobre o ledger real (`open` adota via
  `adopt_session(token)` sob o lock; `close` faz `begin_drain` e `release`
  com fatos roteirizados), e também relógio, link, threads e pares.
- Não há socketpair real, thread, subprocess, guard real, Linux, PG ou
  rede. O D1 **não** prova threads nem tempo de vida.
- Uma integração posterior e separada pode reusar a `WorkerSession` real
  com SO simulado (padrão de `tests/test_worker_session.py`).

Testes finitos do D1:

| # | teste |
|---|---|
| D1-1 | loader: SHA, tamanho, ausência e excesso dão `ABORT{LOAD}` depois do guard, sem ler o INIT; bytes corretos dão namespace funcional |
| D1-2 | ordem: owner, guard, load, GUARD, `read_init`; guard falho termina em `GUARD_FAILED` sem leitura |
| D1-3 | caminho completo com STOP: 50 frames, 6 sessões, 23 queries, 13 sinks OK, 6 ERROR recuperáveis, T3 local, T5 PENDING, SUMMARY com `failed ⊇ {24}`, resultado `T6_UNKILLED` |
| D1-4 | NOSTOP: T4 FAIL, nenhum `request_stop`, `failed ⊇ {23, 24}` |
| D1-5 | STOP com `call_active` desligado, seq ≠ 46 ou case ≠ 23: sem `request_stop`, FAIL ou ABORT |
| D1-6 | join do watcher falho: RETAINED com o owner retido, sem `machine.join` |
| D1-7 | `sink_drain` puro: OK, MISMATCH, OVERRUN com parada imediata e sentinela, NO_EOF, IO, TIMEOUT |
| D1-8 | sink divergente: ABORT, sem próxima query, endpoints fechados só depois do join; join falho dá RETAINED |
| D1-9 | `start` de thread falho: handle retido, RETAINED |
| D1-10 | criação de par falha com efeito desconhecido: slot UNKNOWN, RETAINED |
| D1-11 | `create` falha: `retain` sem `close`; `open` NEW: `retain`; `open` HELD/CLOSED respeitado |
| D1-12 | `close()` HELD: ABORT retido, sem reserva posterior |
| D1-13 | janela de idle: ACK/GO além de `D` dão IDLE_WINDOW e ABORT; T3 isento |
| D1-14 | T6: `live_window_ms` dentro da faixa; frame depois do ARMED não é aceito; janela vencida dá `T6_UNKILLED` |
| D1-15 | locks: `ledger_lock` nunca seguro durante query ou I/O fake; `call_lock` só em volta de `call_active` |
| D1-16 | eventos: chaves e enums exatos, ≤512 B, ≤56 linhas, varredura de senha, HMAC e canários |
| D1-17 | ledger: valores de §4 via `status`, pin exato, segunda reserva CAPACITY, G2 substitui G1 |
| D1-18 | refusal da máquina ou EOF: ABORT com cleanup, sem leitura posterior |

## 13. Bloqueadores separados (não são verdes falsos)

1. Gerador das expectativas exatas (corpo D-113 por job a partir da
   fixture, da chave HMAC e do encoder; canário não numérico para o job13).
2. D2: bindings físicos (fd 0/1 com prazo absoluto, guard real, factory
   real, pares e threads reais) e a estratégia física de retenção do PID1.
3. D3: a sonda T5 física.
4. D4: a ponte duplex do host, a fixture, o perfil PG, a trava de frescor e
   a prova de vida antes do kill em T6.
5. Readmissão nativa da candidata 621cc7f7 e uma única invocação revista.

## 14. Pendências honestas

- Base, headroom, overhead, margem de idle e caps são escolhas sob
  delegação, não medições.
- A margem de 2 s pressupõe o mesmo CLOCK_MONOTONIC no pai e no filho,
  como o código já exige; não foi medida.
- A estratégia de retenção física do D2 está ausente.
- A prova de vida do worker antes do kill de T6 depende do host (D4).
