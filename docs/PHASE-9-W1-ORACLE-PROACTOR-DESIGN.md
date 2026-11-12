# W1 Oracle: adaptador Proactor do `Pump` — desenho P3

2026-11-12. Somente desenho, sob delegação. Autor: Claude2, sessão
51ea0d85-05bb-4d24-ba9a-c9627c3f832f, claude-opus-5-5/medium. Não é código,
teste, prova nativa, runbook nem aprovação do usuário.

A P3 é uma correção estreita da P2 (49f00da9) e fecha R5–R7 de
`PHASE-9-W1-ORACLE-PROACTOR-REVIEW.md`. A P1 (f3cba358) está preservada em
`evidence/oracle9-w1-proactor-design-review-20261112/c2-design-v1-preserved.md`
apenas como evidência. Este documento é autocontido e normativo.

Ficam fixos:
- owner `a5d233ae`;
- testes `e85f8b53`/`f86f54aa`;
- os DTOs, enums e API desses arquivos;
- PORT-DESIGN/CONTRACT;
- 15 arquivos upstream/ponte, app124, estado16 e tentativa consumida.

`docs/poc/oracle9_w1_proactor_pump.py` e o teste novo continuam AUSENTES
até oráculos revistos e RED medido e congelado.

Fontes v3.11.3, lidas só como texto em `public-sdk-context/`, sem executar
nem importar:
[base_events](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/base_events.py),
[base_subprocess](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/base_subprocess.py),
[proactor_events](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/proactor_events.py),
[windows_events](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/windows_events.py),
[events](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/events.py),
[windows_utils](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/windows_utils.py),
[subprocess](https://github.com/python/cpython/blob/v3.11.3/Lib/subprocess.py),
[protocols](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/protocols.py),
[transports](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/transports.py),
[tasks](https://github.com/python/cpython/blob/v3.11.3/Lib/asyncio/tasks.py).

A ordem interna do SDK citada aqui é leitura de fonte, não medição; volta
no gate nativo (§15). O pump nunca lê atributos privados, filas nem o heap
do SDK.

## 0. Deltas

| Achado | Resolução |
|---|---|
| R1–R4 (P2) | Preservados: `run_until` executável, handler fechado, fases de partida, retenção honesta, EOF pausado, `close` idempotente |
| R5 | Todo teste de latch usa `is not None`, nunca a veracidade do objeto. Só entra em `_ctl` uma BaseException que não é Exception. O contexto do handler é lido só como `dict` exato. Barreira de latch/stop depois de cada evento diferido e antes de qualquer segmento (§4, §5) |
| R6 | Gate local irrevogável por entrada (OPEN → SPENT, ou OPEN → CLOSED). Qualquer falha de `call_at` ou `create_task`, antes ou depois da inserção, fecha o gate. Um callback tardio nunca autoriza nada, e `not_started` diferido é fato verdadeiro. `record_id` nunca é reutilizado; retenção limitada (§6) |
| R7 | API, seam, construtor e mapeamentos normativos reincorporados (§2, §7, §8). `ident()` com falha fechada. Handle válido dentro dos callbacks. Limites de escrita só com `stdin_pipe=True`. Falha de limites persistente: `write_limits()` passa a devolver `(-1, -1)` (§3, §7, §8) |

## 1. K1–K6 (decididas pelo root, prospectivas)

- **K1**:
  - o construtor `ProactorEventLoop()` cria o self-pipe (`socket.socketpair`);
  - na thread principal, chama `signal.set_wakeup_fd`; o pump detém o
    wakeup fd durante a vida do loop;
  - fd anterior livre é precondição confiável do chamador, não certificada;
  - `close()` põe `-1`.
- **K2**: `run_forever` instala o running loop e os hooks de asyncgen e, no
  `finally`, zera o running loop e restaura os hooks. Exige não existir loop
  rodando. Não se afirma restauração de loop anterior.
- **K3**: `run_forever` + `loop.stop()`. O pump cancela só os próprios
  `TimerHandle`, nunca Task/Future. Cancelar não prova cleanup.
- **K4**: DISPOSE explícito (owner/pump) é distinto do cleanup automático do
  SDK:
  - `BaseSubprocessTransport.__init__`: falha de `_start` → `close()`;
  - `_make_subprocess_transport`: falha do waiter → `close()` + `_wait()`;
  - `__del__` dos transportes e de `Popen`.

  Nenhum automatismo prova liberação.
- **K5**: o primeiro controle é preservado por identidade (§4–§5).
- **K6**:
  - exit fora de 0..255 é limite do owner fixo: CALLBACK, OPEN retido;
  - `Popen.terminate` usa `TerminateProcess(handle, 1)`;
  - sem normalização.

## 2. Módulo, API pública, ligação confiável e seam

`docs/poc/oracle9_w1_proactor_pump.py`, módulo único:
- não importa `asyncio`, `subprocess`, `signal`, `socket`, `threading`,
  `logging`, `warnings` nem `gc` no topo;
- os imports de `asyncio`, `subprocess`, `sys` e `threading` só ocorrem
  dentro de `bind_proactor_pump`;
- não importa o owner nem `docs.poc.*`;
- não lê ambiente, configuração nem `sys.flags`;
- não instala hook de auditoria, filtro de warnings, handler de sinal nem
  handler de log.

```text
class PumpFault(Exception)               # args == (); sempre levantada fora de except
class ProactorPump:                       # implementa o Pump do owner (PORT §2.2)
    def __init__(self, *, loop: LoopSeam, pipe: int, devnull: int,
                 ident: Callable[[], int], max_starts: int = 512) -> None
    def now(self) -> float
    def schedule_start(self, request: StartRequest) -> None
    def run_until(self, target: float, stop: Callable[[], bool]) -> float
    def close(self) -> bool               # True fechado; False recusado com tudo retido
    __repr__ -> "ProactorPump(<redacted>)"
def bind_proactor_pump() -> ProactorPump  # ligação confiável real
```

Seam mínimo (`typing.Protocol`), só com métodos públicos do SDK:

```text
LoopSeam: time() -> float; call_at(when, cb, *args) -> TimerSeam;
  create_task(coro) -> TaskSeam; run_forever() -> None; stop() -> None;
  is_running() -> bool; is_closed() -> bool; close() -> None;
  get_debug() -> bool; set_debug(enabled: bool) -> None;
  get_task_factory() -> object; set_exception_handler(h) -> None;
  get_exception_handler() -> object;
  subprocess_exec(factory, *argv: str, stdin: int, stdout: int, stderr: int)
    -> Awaitable[tuple[TransportSeam, object]]
TimerSeam: cancel() -> None              TaskSeam: done() -> bool
TransportSeam (SubprocessTransport): get_pid(); get_returncode();
  get_pipe_transport(fd: int) -> PipeSeam | None; is_closing() -> bool;
  close() -> None; kill() -> None
PipeSeam (WriteTransport/ReadTransport): write(data: bytes);
  get_write_buffer_size() -> int; get_write_buffer_limits() -> tuple[int, int];
  set_write_buffer_limits(high: int, low: int) -> None; is_closing() -> bool;
  pause_reading() -> None; resume_reading() -> None
```

O construtor, sem nenhuma chamada nativa própria:
1. exige `max_starts` int exato em 1..512, `pipe`/`devnull` int exatos e
   distintos, e `ident` chamável;
2. faz `me = ident()` via §3; o resultado vira a thread dona;
3. confere `loop.is_running() is False`, `loop.is_closed() is False` e
   `loop.get_task_factory() is None`;
4. chama `loop.set_debug(False)` e
   `loop.set_exception_handler(self._on_sdk_error)`;
5. relê `get_debug() is False` e `get_exception_handler() == self._on_sdk_error`
   (bound method).

Qualquer Exception levanta `PumpFault()`. Um controle atravessa como o mesmo
objeto. Depois de construído, o pump nunca expõe o loop.

`bind_proactor_pump()`:
1. faz os imports;
2. exige `sys.platform == "win32"` e
   `threading.current_thread() is threading.main_thread()`;
3. confere que `asyncio.get_running_loop()` levanta RuntimeError;
4. cria `loop = asyncio.ProactorEventLoop()` e exige
   `type(loop) is asyncio.ProactorEventLoop`;
5. constrói `ProactorPump(loop=loop, pipe=subprocess.PIPE,
   devnull=subprocess.DEVNULL, ident=threading.get_ident)`.

Se o passo 5 falhar, faz um único `loop.close()` (ainda sem processo) e
levanta `PumpFault`; um controle atravessa. A ligação nunca usa política,
`get_event_loop`, `set_event_loop`, `asyncio.run` nem `set_task_factory`. Ela
não prova proveniência: o pin dos bytes é do chamador, como na ponte.

Estado:
- `_state` ∈ {OPEN, CLOSED, BROKEN};
- `_in_run`, `_in_stop` (bool);
- `_gen` (int);
- `_ctl: BaseException | None`;
- `_fault: bool`;
- contadores saturados em 2**63-1: `_faults`, `_ctl_dropped`,
  `_dropped_events`, `_stale_callbacks`;
- `_entries: dict[int, _Start]`;
- `_deferred: deque[_Start]` com no máximo `max_starts` itens;
- `_last_time: float | None`.

## 3. Fronteira dos métodos públicos

`_ident_ok()` chama o seam `ident()` dentro de `try`:
- Exception, ou resultado diferente de int exato → `PumpFault()` levantada
  depois do `try`;
- controle → atravessa com o mesmo objeto, via `raise` simples no `except`
  de BaseException que não é Exception;
- resultado diferente da thread dona → `PumpFault()`.

Essa consulta não grava latch nem muda estado.

`_gate(reentry_ok)`, nesta ordem:
1. `_ident_ok()`;
2. `_state is not OPEN` → `PumpFault()`;
3. `not reentry_ok and _in_run` → `PumpFault()`.

O gate não consome latch; um latch pendente sai na próxima fronteira válida.

| Método | Gate |
|---|---|
| `now()` | `_gate(reentry_ok=True)`, depois `_time()`; falha → `PumpFault`; controle do `time()` atravessa |
| `schedule_start` | `_gate(reentry_ok=True)`: o owner agenda filhos dentro de eventos |
| `run_until` | `_gate(reentry_ok=False)` |
| `close` | só `_ident_ok()`; o resto em §12 |

`_time()`:
- `v = loop.time()`;
- exige `type(v) in (int, float)`, valor finito, `v >= 0` e
  `v >= _last_time`; então atualiza `_last_time`;
- senão: fault (dentro de `run_until`) ou `PumpFault` (em `now()`).

Os métodos do `_Handle` (§8) **não** passam por `_gate`. O owner os chama
dentro dos próprios callbacks (por exemplo, `started` lê `pid` e
`write_limits`, e `data` chama `pause_reading`) e também fora do loop (as
chamadas diretas). Eles só exigem `_state is OPEN` e o transporte da
entrada; senão levantam `PumpFault()`.

`_invariants_ok()`, na entrada de `run_until`, usa `_guard` sobre
`is_running() is False`, `is_closed() is False`, `get_debug() is False`,
`get_exception_handler() == self._on_sdk_error` e
`get_task_factory() is None`. Qualquer divergência ou falha → latch.

## 4. Latches, precedência e handler (R2, R5)

```text
_latch(e):
    if isinstance(e, Exception):        _fault = True; _faults += 1
    elif isinstance(e, BaseException):
        if _ctl is None:                _ctl = e          # identidade; nunca bool(e)
        else:                           _ctl_dropped += 1
    else:                               _fault = True; _faults += 1   # não é exceção
    if _in_run and not _stopping_latch:
        _stopping_latch = True
        try: loop.stop()
        except BaseException as e2: _latch_nostop(e2)  # mesma classificação, sem stop
        finally: _stopping_latch = False

_guard(fn, *a) -> (ok: bool, value):
    try: return True, fn(*a)
    except BaseException as e: _latch(e); return False, None

_pending() -> bool:  return _ctl is not None or _fault is True

_report():
    if _ctl is not None: c = _ctl; _ctl = None; raise c     # fora de except
    if _fault is True:   _fault = False; raise PumpFault()
```

Nenhum ponto avalia `bool(_ctl)` ou `_ctl or …`. Subclasses de BaseException
com `__bool__` falso ou explosivo passam pelo pump sem que seu `__bool__`
seja chamado. Precedência: controle pendente > fault pendente > retorno
normal. Latches são pegajosos: só são limpos pelo `_report`, nunca por
entrada nem por `finally`.

Handler `_on_sdk_error(loop, context) -> None`:

```text
try:
    exc = None
    if type(context) is dict:                 # exato: get/__contains__ de dict não são substituíveis
        exc = dict.get(context, "exception")
    if (exc is not None and isinstance(exc, BaseException)
            and not isinstance(exc, Exception)):
        _latch(exc)                           # controle real encaminhado por Handle._run
    else:
        _latch(_FAULT)                        # Exception, não-exceção, ausente ou contexto malformado
except BaseException as e:
    _latch(e)
return None
```

`_FAULT` é um sentinela privado do módulo que não é exceção. Com ele,
`_latch` registra só fault.

- Um contexto que não é `dict` exato nunca tem método chamado.
- O handler nunca deixa nada escapar. Por isso `call_exception_handler` não
  aciona `default_exception_handler`, que formataria o contexto.
- O handler não guarda `context`, não chama `repr`/`str`/`format` e não
  chama close, kill, abort ou cancel.
- Fora de `run_until`, o handler só registra latch; `loop.stop` exige
  `_in_run`.

Limite: um KeyboardInterrupt assíncrono depois do `except` e antes do
`return` escapa. `call_exception_handler` o relança (não o envia ao fallback)
e ele vira controle cru do segmento (§5). Ausência de handler de sinal
customizado é precondição NOT_PREPARED.

## 5. `run_until` executável (R1, R5)

```text
run_until(target, stop):
  _gate(reentry_ok=False)
  if _pending(): _report()                     # latch de fora: relatado sem conduzir
  t = target se type(target) in (int, float) e finito, senão raise PumpFault()
  _in_run = True; _gen += 1; _stop = stop
  try:    result = _drive(t)
  except BaseException as e: _latch(e); result = None   # defesa contra bug do pump
  _in_run = False; _stop = None
  if _pending(): _report()
  return result

_drive(t):
  if not _invariants_ok(): return None
  if _pending(): return None
  if _eval_stop(): return _time()
  now = _time();  if now is None: return None
  if now >= t: return now                      # alvo atingido: sem loop, sem partida, sem diferidos
  _flush_deferred()                            # §6
  if _pending(): return None                   # barreira R5: nada roda antes do relato
  if _eval_stop(): return _time()
  idle = 0
  loop:
    seg0, d0 = now, _delivered
    _segment(t)
    if _pending(): return None
    if _eval_stop(): return _time()
    now = _time(); if now is None: return None
    if now >= t: return now
    idle = idle + 1 if (_delivered == d0 and now == seg0) else 0
    if idle >= IDLE_SEGMENTS_MAX (64): _latch(_FAULT); return None

_flush_deferred():
  while _deferred:
    e = _deferred.popleft()
    _deliver(e.events.not_started); e.events = None; e.phase = NOT_STARTED
    if _pending() or _stop_requested: break    # o restante fica para a próxima condução

_segment(t):
  ok, timer = _guard(loop.call_at, t, _wake, _gen)
  if not ok: return
  try:    loop.run_forever()
  except BaseException as raw: _latch(raw)     # controle cru registrado ANTES do cancel
  finally: _guard(timer.cancel)                # nunca levanta e não substitui o latch

_wake(gen): if gen == _gen and _in_run: _guard(loop.stop)

_eval_stop():
  if _in_stop: _latch(_FAULT); return True     # recursão é violação
  _in_stop = True
  try:    ok, r = _guard(_stop)
  finally: _in_stop = False
  if not ok: return True
  if type(r) is not bool: _latch(_FAULT); return True
  return r is True

_deliver(fn, *args):                           # só eventos do owner
  if not _in_run or _in_stop: _latch(_FAULT); _dropped_events += 1; return
  ok, _ = _guard(fn, *args); _delivered += 1
  if not ok: return                            # o latch já pediu stop
  if _eval_stop(): _stop_requested = True; _guard(loop.stop)
```

`_stop_requested` é zerado a cada entrada de `run_until`.

Regras:
- **Retorno.** Só com `stop()` verdadeiro, com `now >= t` ou levantando. A
  checagem PUMP do owner vale.
- **Fatos depois de `stop()`.** O SDK executa o resto da iteração ("every
  callback already scheduled will still run"). Esses eventos chegam ao owner
  no mesmo `run_until`. Fato nunca é adiado nem perdido.
- **Sem progresso.** Um segmento sem evento entregue e sem avanço de tempo é
  ocioso. 63 voltas ociosas consecutivas são aceitas; a 64ª dá fault. O
  valor é do modelo, não medido (N13).
- **Entrega fora do loop.** Pela fonte, callbacks só rodam em `_run_once`;
  `pause_writing` é síncrono, mas não é entregue. Uma entrega fora de
  `run_until` dá fault e o fato é descartado; o registro fica retido.
- **Limpeza.** O único cleanup do segmento é `cancel` do próprio timer de
  espera; `_gen` neutraliza um timer cujo `cancel` falhou. Isso não é
  cleanup físico.

## 6. Partida: gate local, fases e donos (R3, R6)

`_Start` contém:
- `record_id`, `phase`;
- `gate` ∈ {OPEN, SPENT, CLOSED};
- `stdin_pipe`;
- `request` (forte até a fase terminal), `events`;
- `timer`, `coro`, `task`, `protocol`, `transport`;
- as flags `started`, `limits_failed`, `lost`, `explicit_close_ok` e
  `closed_delivered`.

**Contrato único do gate (R6).** O gate pertence só ao pump e não depende
do estado de protocolo do owner.
- Só `_start` chama `authorize`, e só se encontrar `gate is OPEN`. Antes da
  chamada, troca para SPENT. Assim, cada entrada autoriza no máximo uma vez.
- Qualquer falha de agendamento troca OPEN → CLOSED, de forma irrevogável.
- Callback ou passo que encontre o gate diferente de OPEN termina sem
  efeito e sem evento (`_stale_callbacks += 1`). Isso vale para `_due` com
  timer inserido apesar da falha e para o passo de uma Task criada apesar da
  falha.
- Com o gate CLOSED, nenhum caminho deste pump chama `authorize` nem
  `subprocess_exec` para a entrada. Por isso `not_started()` diferido é fato
  verdadeiro, mesmo que `call_at`/`create_task` tenham inserido algo antes
  de falhar.

**`record_id`.** `schedule_start` recusa com `PumpFault`, sem tocar a
entrada existente, todo `record_id` já presente em `_entries`, em qualquer
fase. As entradas nunca são removidas durante a vida do pump. Isso dá no
máximo `max_starts` (≤512) entradas e `_deferred` ≤ `max_starts`.

**Retenção das entradas terminais.** Uma entrada NOT_STARTED solta
`request`, `events`, `timer` e `task`. Ela retém `coro` só no caso S2
(abaixo), até `close()`. Um callback inserido apesar da falha mantém a
entrada viva pelo SDK até disparar ou até `loop.close()` esvaziar as filas.

| Fase | Retém | Falha (Exception ou controle) | Registro / evento | Condução seguinte / `close` |
|---|---|---|---|---|
| S0 validação em `schedule_start` | nada | forma inválida (`record_id` int exato 1..2**31-1; `argv` tupla de str com 1..64 itens; `stdin_pipe` bool exato; `not_before` finito; `authorize` chamável; os 8 métodos de `events`), teto ou id repetido → `PumpFault` | nenhuma entrada | owner PUMP |
| S1 `call_at(not_before, _due, entry)` | `entry.request`; o SDK pode reter a entrada | **antes ou depois da inserção, sem distinguir**: gate → CLOSED; `request = None`; a entrada vai a `_deferred`. Exception → `PumpFault()` de `schedule_start`; controle → o mesmo objeto atravessa | `not_started()` diferido na próxima condução com alvo futuro | depois NOT_STARTED, quiescente; `_due` tardio é callback velho |
| S2 `_due(entry)` (callback no loop, protegido) | `coro = _start(entry)`, ainda não iniciada | `create_task` falha (antes ou depois de agendar o passo): gate → CLOSED; latch (Exception = fault, controle = `_ctl`); `entry.coro` retida; vai a `_deferred` | `not_started()` diferido | o passo, se rodar, encontra CLOSED e termina. Em `close()`, depois de `loop.close()` com sucesso, chama `coro.close()` só nessas coroutines do próprio pump, para não deixar coroutine sem fim |
| S3 passo inicial de `_start` | Task e coroutine | gate diferente de OPEN → termina sem efeito; senão gate → SPENT e `_guard(authorize)`; resultado `is not True`, Exception ou controle (latch) | `_deliver(not_started)`; nenhuma chamada nativa | NOT_STARTED; `request` liberado |
| S4 `await subprocess_exec(factory, *argv, stdin=pipe if stdin_pipe else devnull, stdout=pipe, stderr=devnull if stdin_pipe else pipe)`, no mesmo passo de S3 | frames de `subprocess_exec`/`_make_subprocess_transport` com `program`/`args`; no SDK: transporte, `Popen` com `args`, Task `_connect_pipes` e o futuro de `wait_for_handle` | ver abaixo | ver abaixo | ver abaixo |
| S5 `connection_made(t)` | `entry.transport = t`, protocolo | — | §7 | §11 |
| S6 `connection_lost` | — | — | `closed()`; `lost = True` | — |

Resultados de S4, todos dentro da coroutine, que captura tudo:
- **Retorno `(t, p)`**: exige `entry.started is True` e `t is entry.transport`.
  Sem isso: fault, nenhum evento extra.
- **Exception antes de `started`**: `start_failed()`; fase START_FAILED.
  Possíveis efeitos:
  - `windows_utils.pipe`/`Popen` falhou; o pipe do stdin é criado fora do
    `try`, e um vazamento de handle sem processo é possível;
  - `CreateProcess` falhou;
  - o SDK chamou `close()` → `kill` em `_start` ou no waiter.

  O registro fica UNKNOWN sem handle, nunca NOT_STARTED.
- **Exception depois de `started`**: `start_failed()`; OPEN com handle.
- **Controle antes de `started`**: latch e `start_failed()`. Depois de
  `started`: só o latch.
- **Pendente para sempre**: no caminho de falha do waiter, `_wait()` depende
  de `_call_connection_lost`, que fica em `_pending_calls`. Fase EXEC; Task
  e frames retidos; `close()` False.
- **Fase terminal de S4**: `entry.request = None`; a Task termina com `None`
  e `entry.task = None`. O pump nunca chama `Task.cancel`. `coro.close()`
  ocorre só no caso S2.

Authorize e Popen ocorrem no mesmo passo da Task, sem iteração do loop entre
eles. A `factory` devolve o `_PumpProtocol(entry)` pré-criado uma vez; uma
segunda chamada levanta `PumpFault`.

## 7. Protocolo e mapeamento

`_PumpProtocol(entry)` implementa `asyncio.SubprocessProtocol` por
duck-typing, sem herdar. Cada evento passa por `_deliver`.

| Callback SDK | Ação do pump | Evento do owner |
|---|---|---|
| `connection_made(t)` | `entry.transport = t`; **só se `entry.stdin_pipe is True`**: `p0 = t.get_pipe_transport(0)`; se `p0 is None` → `limits_failed = True`; senão `ok, _ = _guard(p0.set_write_buffer_limits, 0, 0)` com `high=0, low=0`, e `limits_failed = not ok`. Helpers sem stdin nunca consultam o fd 0 | `started(_Handle(entry))`, sempre depois da configuração |
| `pipe_data_received(fd, d)` | `bytes(d)` | `data(fd, chunk)` |
| `pipe_connection_lost(fd, exc)` | `failed = exc is not None`; `exc` descartado | `pipe_lost(fd, failed)` |
| `process_exited()` | `code = t.get_returncode()` | `exited(code)` |
| `pause_writing()` | só a flag; síncrono dentro de `write` | nenhum |
| `resume_writing()` | — | `write_resumed()` |
| `connection_lost(exc)` | `lost = True`; `exc` descartado | `closed()` |

Sem reordenar, deduplicar ou filtrar. A cada evento, o owner relê `now()`,
que é `loop.time()` validado.

Ordem pela fonte: `_connect_pipes` agenda `connection_made`, depois os
`_pending_calls` (dados, perdas, exit e `_call_connection_lost`), e só então
resolve o waiter. Fatos podem chegar antes de `subprocess_exec` retornar.

## 8. `_Handle(entry)` 1:1

`t` é o transporte da entrada e `p0 = t.get_pipe_transport(0)`.

| Método do owner | Ação |
|---|---|
| `pid()` | `t.get_pid()` |
| `returncode()` | `t.get_returncode()` |
| `write_limits()` | se `entry.limits_failed is True` → `(-1, -1)` constante, **sem reler o SDK**; senão `p0.get_write_buffer_limits()` (`(low, high)`); sem stdin → `PumpFault` |
| `write(b)` | `p0.write(b)` |
| `buffer_size()` | `p0.get_write_buffer_size()` |
| `is_closing()` | `t.is_closing() or p0.is_closing()`; sem stdin, só `t.is_closing()` |
| `pause_reading(fd)` / `resume_reading(fd)` | `t.get_pipe_transport(fd).pause_reading()` / `.resume_reading()`; pipe ausente → `PumpFault` |
| `close()` | `t.close()`; se retornar normalmente, `entry.explicit_close_ok = True` |
| `kill()` | `t.kill()` |

- `(-1, -1)` difere de `(0, 0)` e não é um valor possível do SDK, que exige
  `high >= low >= 0`. Uma falha de configuração continua falha para o owner
  mesmo que o SDK tenha ajustado os valores para zero antes de levantar:
  - `started` dá WRITE_LIMITS, spawn não ok, handle retido;
  - escritas ficam NOT_SENT.
- Uma Exception do SDK vira `PumpFault()` fora do `except`, sem mensagem nem
  cadeia.
- Um controle atravessa como o mesmo objeto: dentro de evento, o owner
  relança e `_deliver` registra; fora do loop, chega direto ao owner.
- Nada chama close/kill por conta própria.

## 9. Escrita, leitura e prazos

- Conclusão síncrona: `_pending_write` igual a 0, buffer 0, SENT local
  (handoff ao WriteFile, não ack).
- Overlapped pendente: `pause_writing` (no-op); na conclusão,
  `resume_writing` → `write_resumed`; o owner relê buffer 0 e `is_closing`
  False.
- `_fatal_error`/`_force_close`: buffer 0 com `is_closing` True e
  `pipe_lost(0, True)`; nunca SENT. `write` sobre `_conn_lost` descarta em
  silêncio, também com `is_closing` True.

Os quatro casos tardios medidos (handoff, data, EOF e write síncrono que
atravessa o prazo) dependem de `now()` novo a cada evento e depois de
chamada direta; isso é preservado. O prazo do SPAWN não limita a sessão.

## 10. Retenção honesta

O argv é retido:
- pelo `CliPlan` do owner (vida inteira);
- por `entry.request` até a fase terminal de S1–S4;
- pela coroutine/Task e pelos frames enquanto S4 está suspensa;
- pelo SDK em `Popen.args`, inclusive via `get_extra_info('subprocess')`,
  enquanto o transporte existir;
- por hooks de `sys.audit("subprocess.Popen", …)`, se existirem
  (precondição NOT_PREPARED).

`Popen.__repr__` inclui `args`, truncado em 80 caracteres. A closure
`authorize` vive na `request`.

Um controle registrado preserva `__traceback__` com frames e locais até ser
reportado; o owner guarda `first_control`. Não se sobrescreve traceback nem
se promete apagar memória. Promete-se apenas:
- `repr` constante;
- `PumpFault` sem `args`;
- nenhuma cópia ou formatação de argv, bytes, mensagens ou contexto;
- remoção das próprias referências nas fases terminais.

## 11. Posse, overhead e pausa de leitura (R4)

| Objeto | Dono | Liberação |
|---|---|---|
| loop, IOCP, self-pipe, wakeup fd | pump | `close()` quiescente |
| `_entries` (≤512) | pump | nunca removidas; ficam leves no estado terminal |
| timer de partida | `entry.timer` | dispara uma vez; em falha, o gate fechado o neutraliza |
| timer de espera | local ao segmento | `cancel` protegido |
| Task | `entry.task` | solta quando termina |
| coro de S2 | `entry.coro` | `coro.close()` depois de `loop.close()` |
| transporte e protocolo | `entry` e o `_Handle` do owner | solto pelo pump após `lost`, `explicit_close_ok` e `closed` entregue |

Overhead do SDK fora do teto do owner:
- `bytearray(65536)` por pipe de leitura, ≈17 MiB no pior caso de P1 retido;
- uma cópia por bloco;
- `_pending_calls` sem limite exposto antes de `connection_made`;
- a cópia do payload no overlapped.

**Limite R4.** O owner fixo chama `pause_reading(1)` quando
`accepted_total == cap` (28673 no gateway, 4096 por filho) e nunca retoma a
leitura. O EOF fica em `_pending_data_length`, sem `pipe_connection_lost`.
Então:
1. o registro nunca chega a SETTLED_RETAINED, e o pai do filho não
   decodifica;
2. sem `connection_lost`, não há `closed`;
3. `kill` gera exit mas não entrega o EOF, e TERMINATE depois do exit é
   recusado;
4. CLOSE_HANDLE é recusado (STATE);
5. `pump.close()` fica False, e owner e pump ficam retidos.

O caminho positivo fica abaixo do cap. O plano nativo precisa tratar esse
risco antes de alegar recuperação (N14). O FakeLoop nunca fabrica EOF com a
leitura pausada.

## 12. Disposição, automatismos e `close()` idempotente

- **CLOSE_HANDLE** (o owner exige alvo SETTLED_RETAINED e `returncode` int):
  `t.close()` não mata, porque pela fonte `_returncode` está definido e
  `_proc` é None depois de `_call_connection_lost`. DONE_OBSERVED =
  `connection_lost` observado + `close()` explícito retornado. Não é
  fechamento de handle no SO.
- **TERMINATE** → `t.kill()` → `Popen.terminate` (`TerminateProcess(1)`);
  assenta só por exit e pipes.
- **Automatismos do SDK** (K4): o pump retém referências fortes para que
  nenhum finalizador dispare por perda de referência. Descartar pump ou
  owner é proibido.

`close() -> bool`, depois de `_ident_ok()`:

| Estado / condição | Resultado |
|---|---|
| CLOSED | `True`, sem chamada ao seam |
| BROKEN | `False`, sem chamada |
| `_in_run` | `False` |
| `_pending()` | `False`; o latch deve ser relatado via `run_until` |
| alguma entrada não quiescente ou `_deferred` não vazio | `False`, tudo retido |
| quiescente | `loop.close()` uma vez → CLOSED; `coro.close()` das coroutines S2; solta as próprias referências; `True` |
| `loop.close()` levanta Exception | BROKEN, `False`; nunca repete |
| `loop.close()` levanta controle | BROKEN; o mesmo objeto atravessa |

Entrada quiescente:
- NOT_STARTED já entregue, com Task concluída ou ausente; ou
- `started`, `lost`, `explicit_close_ok`, `closed` entregue e Task
  concluída.

Não são quiescentes: START_FAILED sem `started`, EXEC e timer de partida com
gate OPEN. `IocpProactor.close` espera overlapped cancelados, sem limite
garantido (N8). Depois de CLOSED, `now`, `schedule_start` e `run_until`
levantam `PumpFault`.

## 13. Sigilo e diagnósticos

- Debug fica desligado desde o construtor; não há `execute program %r`.
- O handler fechado garante que o fallback que formata o contexto nunca
  roda.
- Logs remanescentes do SDK, sem argv nem dados:
  - `Using proactor` (DEBUG, no construtor);
  - `socket.send() raised exception.` (WARNING);
  - progresso de `IocpProactor.close` (DEBUG);
  - `ResourceWarning` com pid, só se houver perda de referência, que o pump
    evita.
- A ausência de log não prova nada (N9).

## 14. Oráculos determinísticos (primeiro lote; owner e testes intocados)

Arquivo novo `tests/test_oracle9_w1_proactor_pump.py`. `FakeLoop`:
- relógio diádico roteirizável (inválido e regressivo);
- heap de timers;
- lote de prontos por iteração e `stop` ao fim do lote;
- `create_task` que avança coroutines por `send(None)`;
- `call_exception_handler` com a precedência do SDK, registrando qualquer uso
  do fallback;
- `call_at` e `create_task` roteirizáveis para falhar **antes** ou **depois**
  da inserção, com Exception ou controle;
- `subprocess_exec` com `_pending_calls` antes do waiter.

`FakeTransport`/`FakePipe` com trace e pausa real: EOF retido quando pausado.
`ident` falso roteirizável. Requests e events falsos com `__weakref__`.
Integração com owner, ponte e reator publicados. Nenhum asyncio, loop,
thread, processo, socket, sinal ou DLL reais. `bind_proactor_pump` nunca é
chamado.

### Positivos (Q1–Q5)

- **Q1**: P1 completo abaixo do cap → `quiet_scoped` True e `close()` True.
- **Q2**: authorize e `subprocess_exec` no mesmo passo; limites antes de
  `started`; helper sem stdin → zero chamadas a `get_pipe_transport(0)`.
- **Q3**: SENT síncrono e via `resume_writing`.
- **Q4**: ordens de data, exit e perdas, inclusive tudo em `_pending_calls`.
- **Q5**: os quatro casos tardios.

### R1 (preservados)

- **R1-a**: controle cru em `run_forever` → mesmo objeto (`is`), um
  `cancel`, próxima condução normal.
- **R1-b**: `c1` de evento e depois `k2` cru → `c1`.
- **R1-c/d**: `cancel` levanta Exception ou controle.
- **R1-e/f**: `time()` inválido ou regressivo; `call_at` do timer de espera
  falha.
- **R1-g**: `stop()` levanta, devolve não-bool, e mede profundidade 1.
- **R1-h**: alvo atingido.
- **R1-i**: 64 segmentos ociosos.
- **R1-j**: disparo precoce.
- **R1-k**: fronteiras sem consumir latch.

### R2 / R5

- **R5-a**: `class FalseCtl(BaseException): __bool__ → False`, levantado
  num evento → `run_until` levanta o mesmo objeto (`is`); o `__bool__`
  instrumentado nunca é chamado.
- **R5-b**: `class BoomCtl(BaseException): __bool__ → raise AssertionError`
  → idem, em evento, em `stop()`, em `cancel` e no handler.
- **R5-c**: com `FalseCtl` já registrado, um segundo controle não é
  levantado e `_ctl_dropped` vale 1. O relato limpa o latch, e a condução
  seguinte é normal.
- **R5-d**: handler com `{"exception": 7}`, `{"exception": object()}`,
  `{"exception": ValueError()}`, `{}` e `{"exception": None}` → só fault
  (`PumpFault`), nunca TypeError, nunca `_ctl`.
- **R5-e**: handler com `dict` exato contendo `C(BaseException)` → o mesmo
  objeto é levantado na fronteira.
- **R5-f**: handler com contexto subclasse de `dict` cujo `get`,
  `__getitem__` e `__contains__` falham o teste → nenhum é chamado; só
  fault.
- **R5-g**: dentro de `run_until`, o handler recebe uma Exception e o
  `loop.stop` roteirizado levanta KeyboardInterrupt `k` → zero fallbacks e
  `k` levantado (`is`). Com controle prévio, `k` é descartado e o anterior é
  levantado.
- **R5-h**: os valores do `context` têm `__repr__`/`__str__` que falham o
  teste, e um weakref de valor morre ao sair do handler.
- **R5-i** (diferido): uma falha de S1 deixa um `not_started` diferido, e o
  `not_started` do owner falso levanta Exception (ou controle `FalseCtl`).
  Uma segunda partida está devida no FakeLoop. A condução seguinte entrega o
  diferido e retorna com `PumpFault` (ou o mesmo controle), com **zero**
  `call_at` de espera, `run_forever`, `create_task` e `authorize` da
  segunda partida. A próxima condução válida então inicia a segunda.
- **R5-j**: dois diferidos; o primeiro deixa `stop()` verdadeiro → só ele é
  entregue; o segundo sai na condução seguinte.
- **R2-d** (mantido): handler fora de `run_until` duas vezes → um
  `PumpFault` na entrada, sem conduzir; a condução seguinte é normal.

### R6

- **R6-a**: `call_at` de partida levanta Exception **antes** da inserção →
  `PumpFault`; um `not_started` diferido; NOT_STARTED; weakref da request
  morto; zero `authorize`.
- **R6-b**: Exception **depois** da inserção → idem. O `_due` tardio
  dispara: zero `create_task`, zero `authorize`, `_stale_callbacks` igual a
  1, nenhum evento extra.
- **R6-c/d**: controle (`FalseCtl`) antes ou depois da inserção → o mesmo
  objeto atravessa `schedule_start`; depois, igual a R6-a/b. O owner falso
  com protocolo UNKNOWN não é usado como trava: o teste usa authorize falso
  que devolveria True e prova que ele nunca é chamado.
- **R6-e**: `create_task` falha antes ou depois de agendar o passo
  (Exception ou controle) → `not_started` diferido. Se o passo rodar, termina
  sem `authorize`. Depois de `close()` True, `coro.close()` foi chamado uma
  vez e não há RuntimeWarning "never awaited" (warnings registrados pelo
  teste).
- **R6-f**: `record_id` repetido em qualquer fase (QUEUED, NOT_STARTED,
  STARTED ou com gate CLOSED) → `PumpFault`, entrada original intacta.
  `max_starts` + 1 → `PumpFault`.
- **R6-g**: um passo duplicado roteirizado da mesma Task → um único
  `authorize` (gate SPENT).

### R7

- **R7-a**: `ident` levanta Exception → `PumpFault` em `now`,
  `schedule_start`, `run_until` e `close`, sem latch nem mudança de estado.
  `ident` levanta controle → o mesmo objeto. `ident` devolve bool, str ou
  outra thread → `PumpFault`. Construtor com `ident` falho → `PumpFault`,
  com zero `set_debug`/`set_exception_handler`.
- **R7-b**: dentro de `started`, o owner real consulta `pid()` e
  `write_limits()`, e dentro de `data` chama `pause_reading` → funcionam
  durante `run_until` (sem REENTRY/`PumpFault`).
- **R7-c**: helper `stdin_pipe=False` → `connection_made` não chama
  `get_pipe_transport(0)` nem `set_write_buffer_limits`; `started` é
  entregue; o filho assenta normalmente.
- **R7-d**: `set_write_buffer_limits` do FakePipe ajusta os limites para
  `(0, 0)` e depois levanta Exception (ou controle `FalseCtl`) →
  `write_limits()` devolve `(-1, -1)`, sem nova consulta ao SDK; o SPAWN fica
  UNKNOWN com fault WRITE_LIMITS e handle retido; o slot recebe
  `SpawnOutcome(ok=False)`; nenhuma escrita é chamada. No caso de controle,
  ele também é levantado na fronteira.
- **R7-e**: `stdin_pipe=True` com `get_pipe_transport(0)` None → mesmo
  resultado de R7-d.
- **R7-f**: AST — `_gate` chama `ident`; o handle não chama `_gate`.

### R3 / R4 / X (preservados)

- **R3-d**: authorize devolve `1`/`None` ou levanta → `not_started`.
- **R3-e**: exec falha antes de `started` → `start_failed`; `started`
  tardio.
- **R3-f**: exec pendente para sempre → `close()` False.
- **R3-g**: controle no exec.
- **R3-h**: transporte divergente.
- **R4-a/b**: cap atingido → EOF retido → disposições e `close` recusados.
- **R4-c/d/e**: `close` idempotente, BROKEN e dentro de `run_until`.
- **X5**: `_force_close` falso.
- **X12**: canários ausentes de `repr`/`args`/`__context__`/trace.
- **X13**: AST de imports, nenhum atributo privado do seam, nenhuma API
  proibida, `cancel` só em timer.
- **X14**: exit 300 e `-1`.

Esses oráculos não constituem prova nativa.

## 15. Gate nativo futuro (separado, NOT_PREPARED)

Exige plano, destino e admissão explícitos e helper benigno revisto; nunca
Docker/PG/SQL. Medir por identidade e fatos, nunca por bools True ou
ausência de mensagem:

- **N1**: ordem de `connection_made`/`_pending_calls`/retorno.
- **N2**: nenhum callback entre authorize e `CreateProcess`.
- **N3**: escrita síncrona × pendente com `high=0`.
- **N4**: EOF pausado.
- **N5**: fechamento de pipes e handle do processo.
- **N6**: `close` assentado não mata; código 1.
- **N7**: falhas de partida, inclusive vazamento parcial de pipe.
- **N8**: `loop.close` quiescente sem bloqueio; wakeup fd; ausência de
  executor.
- **N9**: logs.
- **N10**: exits maiores que 255.
- **N11**: KeyboardInterrupt real.
- **N12**: memória.
- **N13**: voltas ociosas.
- **N14**: estratégia para cap/pausa.
- **N15**: hooks de auditoria e de sinal.
- **N16**: inserção parcial real de `call_at`/`create_task` (não injetável
  publicamente; o contrato do gate não depende dela).

## 16. Limites e itens em aberto

1. **R4, pausa.** Processo, registro e loop podem ficar retidos sem
   recuperação pública.
2. **Partida sem handle.** Partida UNKNOWN sem handle e S4 pendente para
   sempre retêm sem recuperação (PORT §12.3).
3. **Callback velho.** Um callback velho inserido pelo SDK apesar da falha
   mantém a entrada viva até disparar ou até `loop.close`; nunca autoriza
   nada.
4. **K6 e bloqueio em close.** Exits maiores que 255; bloqueio sem limite
   em `IocpProactor.close`.
5. **Precondições não certificadas.** Ambiente herdado, canal de segredo,
   hooks de auditoria e de sinal, e wakeup fd.
6. **Valores de modelo.** `IDLE_SEGMENTS_MAX`, `max_starts` e o limite de
   `_deferred` são valores de modelo.

Política Senff: desenho e código derivados por IA exigem revisão humana e de
segurança antes do merge.
