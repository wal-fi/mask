# W1 Oracle — ponte duplex mínima do host e portas injetadas (v2)

2026-11-10. Proposta somente documental e read-only (`MASKGW-DUPLEX-REVISION-ONLY-20261110-V2`), sob a delegação vigente do usuário. Elaborada por Gemini 4 Argon (High), esforço high — **não** por Claude2. O usuário autorizou expressamente o uso dos pacotes públicos necessários pelo Gemini enquanto a quota do Claude2 (`sessão 51ea0d85`, `claude-opus-5-5`, medium) permanece interrompida por erro 429 até 19h30 São Paulo / 22h30 UTC de 2026-11-10. Esta v2 fecha integralmente os itens `R1`–`R6` da revisão técnica do root (`REVISION-REQUEST.md`) sobre a v1 (`7cba610d`, 352 linhas / 40485 B), que fica preservada como histórico. Não reivindica autoria do Claude, aprovação individual do usuário nem prova nativa.

Base pública: código `7ecf056`, checkpoint documental `cad2edf`. Nada foi executado, gerado ou editado: nenhum teste, comando, processo, socket, thread, loop de eventos, guard, sinal, Docker, PostgreSQL, SQL, raiz operacional, nonce, credencial ou estado. Os resultados verdes históricos (`1215` relacionados, `366` próprios e `18` sondas independentes) não foram repetidos nesta leitura e não fecham nenhum gate nativo ou de produto.

## 1. Escopo mínimo, insumos imutáveis e exclusão de limpeza física (`R2`, `R4`)

O **único** objeto deste desenho é o módulo de definições `docs/poc/oracle9_w1_duplex_bridge.py`: uma ponte síncrona mínima que conduz uma instância fresca do `HostReactor` puro (`e86f8e32`) através de portas síncronas específicas e determinísticas, representando um único processo futuro de CLI do container gateway (`stdin=PIPE`, `stdout=PIPE`, `stderr=DEVNULL`) e as seis ações fechadas do host.

| Insumo público imutável | Pin / Tamanho | Papel e restrição |
|---|---|---|
| `docs/poc/oracle9_w1_host_reactor.py` | `e86f8e32` (38610 B / 1104 linhas) | Único decisor de protocolo, sequência, veredictos e cerca de `T6`; injetado já carregado pelo chamador |
| `tests/test_oracle9_w1_host_reactor.py` | `f177102a` (77736 B / 2144 linhas) | Oráculo congelado `H1`–`H17` + `R1` do reator; inalterado |
| `deploy/oracle9_w1_main.py` | `89c99c65` (46787 B) | `HostLink` (`<= 512` B com `LF`, `56` linhas), códigos `64`–`70` e `HOLD` |
| `deploy/oracle9_w1_driver.py` | `b54a8a94` (51913 B) | Eventos canônicos, fases/razões de `ABORT`, `load_pure` |
| `deploy/oracle9_w1_controller.py` | `4c155d76` (22453 B) | `decode_init`, `decode_control`, `ControlMachine`, constantes |
| `docs/poc/oracle9_w1_expect.py` | `ce6ff389` (22114 B) | Gera o pacote `LAB_INIT` fora da ponte; não importado |

**Fronteiras fechadas desta v2:**
- `HOST-TEST-REVIEW` e `HOST-SOURCE-REVIEW` prevalecem sobre qualquer ambiguidade anterior do `HOST-DESIGN` (`aed85ad4`). O teto antigo de `256` linhas do `NATIVE-PLAN` v4 está superado por `56` linhas (`54` normais + `2` para `ABORT`/`TERMINAL`) e `<= 512` B por linha incluindo `LF`, mantida a exceção da 57ª linha recusada com `HostRefusal("LINE")` antes de `ORDER` ou parse.
- `w1_bootstrap_channel.py` é apenas referência conceitual histórica; é **proibido importá-lo** (wire, limites e pins incompatíveis).
- **Corte estrito de limpeza e tickets (`R2`):** ficam **removidos** deste módulo `quiesce()`, `close()`, `assert_released()`, `BridgeQuiesced`, `BridgeAbsent`, geração de `nonce`, `issue_ticket` e flags de `released`/`cleanup`. A instância de `DuplexBridge` é criada e retida fortemente pelo chamador **antes** de `run()` e conserva permanentemente todos os seus slots e referências incertas. `Done` (inclusive `COMPLETE_CANDIDATE`) é apenas candidato de protocolo. Matar ou colher a saída do processo CLI do gateway **não** encerra nem aquieta ações de `ActPort` (que no lote nativo terão processos/conexões e owners próprios). O contrato de quiescência, limpeza física e prova de ausência por CID pertence a lote futuro separado, antes de ligar o SO real.
- Os `124` insumos do pacote (`123` caminhos + `pyproject.toml`), o `source20`/`estado16` e a tentativa consumida `3f12dc584c29` (`FAILED_ONLY_OPERATOR_ABORT`) permanecem fixos.

## 2. Injeção do módulo do reator e semânticas de runtime (`R4`)

A ponte **não** importa `docs.poc.oracle9_w1_host_reactor` automaticamente nem usa `runpy`/`importlib`. O chamador carrega o módulo do reator por caminho pinado e injeta na ponte tanto o namespace `reactor_mod: types.ModuleType` quanto uma instância fresca `reactor: HostReactor`.

- **Verificação no construtor (`_trusted_reactor_binding`):**
  - `type(reactor_mod) is types.ModuleType`;
  - presença das classes exatas `HostReactor`, `HostRefusal`, `HostPolicy`, `HostStatus`, `Line`, `Delivered`, `ActDone`, `Exited`, `Send`, `Act`, `Wait`, `Done`, `TerminateFacts`, `PauseFacts`, `RestoreFacts`, `ObserveFacts`, `ZeroFacts`, `KillFacts` e dos enums `Delivery`, `ActStatus`, `ExitStatus`, `Purpose`, `Verdict`, `Outcome`, `HostPhase`, `ActKind`;
  - `type(reactor) is reactor_mod.HostReactor`;
  - `reactor.status()` devolve `HostStatus` com `phase is reactor_mod.HostPhase.AWAIT_GUARD`, `lines == 0`, `controls_sent == 0`, `last_at is None`, `pending is None`, `orphan is None`, `orphan_receipt is None` e `refusal is None`.
  - A validação de forma não autentica a origem do arquivo; o pin de origem é responsabilidade do chamador. Qualquer divergência levanta `BridgeRefusal(BridgeFault.REACTOR)` sem criar instância.
- **Execução síncrona sem loop nativo nos primeiros testes (`R4`):** `DuplexBridge` é inteiramente síncrona (`run() -> BridgeRunResult`), avançando apenas por chamadas a `ClockPort.poll(deadline)` sobre slots de operação explícitos. Nos testes iniciais não há `asyncio`, `ProactorEventLoop`, socket, thread, subprocesso ou relógio do SO. Na futura ligação ao Windows CPython 3.11.3 (`BLOCK_NATIVE`), o adaptador nativo implementará essas mesmas portas sobre o Proactor mantendo as restrições documentadas (sem `communicate()`, `stderr=DEVNULL`, sem depender de `wait_for` cancelado para prazo nem de `is_closing()` como prova).

## 3. API exata, DTOs fechados, slots de operação e portas (`R1`, `R4`, `R6`)

Módulo proposto: `docs/poc/oracle9_w1_duplex_bridge.py` (somente definições; sem efeitos no import). Todos os DTOs usam `@dataclass(frozen=True, slots=True)`. Os carriers (`DuplexBudget`, `SpawnOutcome`, `ReadOutcome`, `WriteOutcome`, `ActOutcome`, `WaitOutcome`) não levantam exceção em `__init__`; toda validação ocorre nos métodos da ponte. `ReadOutcome` e `BridgeStatus` têm `__repr__` redigido que nunca expõe bytes brutos de `stdout` ou `Send.payload`.

### 3.1 Enums, exceção fechada e DTOs públicos

```python
class BridgePhase(enum.Enum):
    NEW = "NEW"
    STARTING = "STARTING"
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    DONE = "DONE"
    HELD = "HELD"
    REFUSED = "REFUSED"

class BridgeFault(enum.Enum):
    REACTOR = "REACTOR"
    BUDGET = "BUDGET"
    PORT = "PORT"
    REENTRY = "REENTRY"
    SPAWN = "SPAWN"
    STDOUT_LIMIT = "STDOUT_LIMIT"
    SILENCE = "SILENCE"
    OVERALL_DEADLINE = "OVERALL_DEADLINE"
    REACTOR_REFUSAL = "REACTOR_REFUSAL"
    CONTROL = "CONTROL"

class BridgeRefusal(Exception):
    """Exceção fechada: args == (category.value,), sem __cause__, __context__ ou valor bruto."""
    def __init__(self, category: BridgeFault, reactor_refusal: str | None = None) -> None:
        self.category = category
        self.reactor_refusal = reactor_refusal
        super().__init__(category.value)
```

```python
@dataclass(frozen=True, slots=True)
class DuplexBudget:
    spawn_s: float        # 0 < spawn_s <= 30.0
    silence_s: float      # 0 < silence_s <= 60.0
    drain_s: float        # 0 < drain_s <= 30.0
    overall_s: float      # max(spawn_s, silence_s, drain_s) < overall_s <= 300.0

@dataclass(frozen=True, slots=True)
class SpawnOutcome:
    ok: bool
    process: object | None

@dataclass(frozen=True, slots=True, repr=False)
class ReadOutcome:
    ok: bool
    data: bytes
    def __repr__(self) -> str:
         size = len(self.data) if type(self.data) is bytes else -1
        return f"ReadOutcome(ok={self.ok!r}, len={size})"

@dataclass(frozen=True, slots=True)
class WriteOutcome:
    delivery: object      # reactor_mod.Delivery: NOT_SENT | SENT | UNKNOWN
    bytes_written: int    # int exato: 0 para NOT_SENT; len(payload) para SENT; 0..len para UNKNOWN

@dataclass(frozen=True, slots=True)
class ActOutcome:
    status: object        # reactor_mod.ActStatus: OK | FAILED | UNKNOWN
    facts: object | None  # TerminateFacts | PauseFacts | RestoreFacts | ObserveFacts | ZeroFacts | KillFacts | None

@dataclass(frozen=True, slots=True)
class WaitOutcome:
    status: object        # reactor_mod.ExitStatus: EXITED | NO_EXIT | UNKNOWN
    code: int | None      # int exato 0..255 sse EXITED, senão None
    reaped: bool          # bool exato; True somente com EXITED e reap confirmado pela porta

@dataclass(frozen=True, slots=True)
class SlotView:
    name: str
    occupied: bool
    op: object | None
    done: bool

@dataclass(frozen=True, slots=True)
class BridgeStatus:
    phase: BridgePhase
    fault: BridgeFault | None
    reactor_refusal: str | None
    reactor_status: object               # reactor_mod.HostStatus
    attempt_consumed: bool
    retained: bool
    process: object | None
    total_stdout_bytes: int
    queued_lines: int
    partial_bytes: int
    overflow: bool
    trailing_partial: bool
    stdout_eof: bool
    reaped: bool
    exit_code: int | None
    slots: tuple[SlotView, ...]          # ordem fixa: ("spawn", "read", "write", "act", "wait")

@dataclass(frozen=True, slots=True)
class BridgeRunResult:
    done: object                         # reactor_mod.Done (apenas candidato de protocolo)
    status: BridgeStatus
```

### 3.2 `OperationSlot` e protocolo `begin_*_into` (posse antes do efeito, `R1`)

Para impedir que uma exceção após alocar/agendar deixe recurso fora do owner, a ponte pré-aloca cinco instâncias de `OperationSlot` no seu `__init__` (`"spawn"`, `"read"`, `"write"`, `"act"`, `"wait"`) e **nunca** recebe handles por retorno tardio:

```python
class OperationSlot:
    __slots__ = ("_name", "_op")
    def __init__(self, name: str) -> None: ...
    @property
    def name(self) -> str: ...
    @property
    def op(self) -> object | None: ...
    @property
    def occupied(self) -> bool: ...
    def bind(self, op: object) -> None: ...
```

**Regras obrigatórias de `OperationSlot` e `PortOp` (`R1`, `R6`):**
1. **Assinatura de `PortOp`:** qualquer operação vinculada a um slot deve expor `done() -> bool` (devolvendo `bool` exato) e `outcome() -> SpawnOutcome | ReadOutcome | WriteOutcome | ActOutcome | WaitOutcome`.
2. **Reserva no slot original antes do efeito:** todo método de partida das portas recebe o `slot: OperationSlot` correspondente (`begin_spawn_into(slot, eff_deadline)`, `begin_read_into(slot, max_bytes)`, `begin_write_into(slot, payload, eff_deadline)`, `begin_act_into(slot, act, eff_deadline)`, `begin_wait_into(slot, eff_deadline)`). A porta **deve** chamar `slot.bind(op)` com o objeto de operação inerte **antes** de criar processo, agendar I/O ou tocar no ambiente simulado/real, e só então iniciar o efeito em `op`.
3. **Proibição de sobrescrita:** se `slot.occupied` já é `True`, tantar iniciar nova operação nesse slot ou chamar `slot.bind(...)` uma segunda vez sem colheita legítima levanta `BridgeRefusal(BridgeFault.PORT)` com `_retained = True` e `_phase = BridgePhase.HELD`, preservando o `_op` original intacto no slot.
4. **Colheita e retenção em falha/prazo:**
   - Uma operação que ainda não terminou no prazo (`op.done() is False`) ou que terminou com efeito incerto (`Delivery.UNKNOWN`, `ActStatus.UNKNOWN`, `ExitStatus.UNKNOWN`) **permanece retida no seu `OperationSlot` original** (`slot.occupied` continua `True`). O slot nunca é limpo nem reutilizado.
   - **Adoção de spawn tardio (`_harvest_spawn`):** antes de qualquer limpeza do slot `"spawn"` e em toda fronteira de inspeção/erro/término, se `_slots["spawn"].op` existe e `op.done() is True` com `SpawnOutcome(ok=True, process=proc)` onde `proc` é um `GatewayProcess` válido, a ponte adota `self._process = proc` **antes** de liberar o slot `"spawn"`. Se `SpawnOutcome.ok is False` ou `proc` ainda está anexado a um erro parcial, `_slots["spawn"]` permanece ocupado com `op` retido.
   - `op.done() is True` significa apenas que a chamada local da porta encerrou; **não** atesta término físico no SO nem limpeza de processos auxiliares.

### 3.3 Portas síncronas injetadas (`ClockPort`, `GatewayPort`, `GatewayProcess`, `ActPort`)

Conferidas por forma no `__init__` da ponte (e `GatewayProcess` ao ser adotado); ausência de método `callable` levanta `BridgeRefusal(BridgeFault.PORT)`:

1. **`ClockPort`:**
   - `now() -> float`: devolve instante monotônico `int | float` exato (`bool` e subclasses recusados), finito e `>= 0`, não decrescente em relação a `_last_clock` do owner (violação levanta `BridgeRefusal(BridgeFault.PORT)`).
   - `poll(deadline: float) -> float`: recebe `deadline` (`int | float` finito `>= _last_clock`), avança as operações pendentes até no máximo `deadline` (retornando antes assim que qualquer `OperationSlot` ocupado passar a `done() is True`) e devolve o novo `now()`.
2. **`GatewayPort` e `GatewayProcess`:**
   - `GatewayPort.begin_spawn_into(slot: OperationSlot, deadline: float) -> None`.
   - `GatewayProcess.begin_read_into(slot: OperationSlot, max_bytes: int) -> None` (`1 <= max_bytes <= 4096`).
   - `GatewayProcess.begin_write_into(slot: OperationSlot, payload: bytes, deadline: float) -> None`.
   - `GatewayProcess.begin_wait_into(slot: OperationSlot, deadline: float) -> None`.
3. **`ActPort`:**
   - `ActPort.begin_act_into(slot: OperationSlot, act: Act, deadline: float) -> None`: aceita exclusivamente `act` do tipo `reactor_mod.Act` com um dos seis `ActKind` fechados e recebe o prazo efetivo `deadline = min(act.deadline, _overall_deadline)`.

### 3.4 Classe `DuplexBridge`

```python
class DuplexBridge:
    def __init__(
        self,
        reactor_mod: types.ModuleType,
        reactor: object,
        clock: ClockPort,
        gateway: GatewayPort,
        acts: ActPort,
        budget: DuplexBudget,
    ) -> None: ...

    def status(self) -> BridgeStatus: ...
    def run(self) -> BridgeRunResult: ...
```

**Validação no `__init__` (antes de criar instância):**
1. `_trusted_reactor_binding(reactor_mod, reactor)` → senão `BridgeRefusal(BridgeFault.REACTOR)`.
2. `_budget_ok(budget)` (`type(budget) is DuplexBudget`, 4 campos `int | float` exatos e finitos respeitando `0 < spawn_s <= 30`, `0 < silence_s <= 60`, `0 < drain_s <= 30` e `max(spawn_s, silence_s, drain_s) < overall_s <= 300`) → senão `BridgeRefusal(BridgeFault.BUDGET)`.
3. Forma de `clock`, `gateway` e `acts` → senão `BridgeRefusal(BridgeFault.PORT)`.
4. Aloca todos os slots (`_slots = {name: OperationSlot(name) for name in ("spawn", "read", "write", "act", "wait")}`, `_line_queue = deque()`, `_partial_buf = bytearray()`, `_process = None`, `_attempt_consumed = False`, `_retained = False`, `_phase = BridgePhase.NEW`).

## 4. Política única e finita de `stdout` (`R3`)

Constantes exatas da ponte:
- `_READ_CHUNK: Final = 4096`
- `_LINE_CAP: Final = 512` (máximo de bytes de uma linha válida incluindo `\n`)
- `_DIAG_LINE_CAP: Final = 513` (`_LINE_CAP + 1`, amostra máxima para diagnóstico de linha longa)
- `_QUEUE_CAP: Final = 57` (`56` linhas de protocolo + `1` slot para a 57ª linha de recusa `LINE`)
- `_MAX_STDOUT_BYTES: Final = 28672` (`56 * 512` bytes admitidos; a leitura admite no máximo `+1` byte de detecção de overflow, totalizando no máximo `28673` bytes lidos).

**Regras fechadas de leitura, montagem e enfileiramento (`R3`):**
1. **Cálculo de `read_size` antes de cada leitura:**
   - Só inicia nova leitura em `_slots["read"]` quando `_process is not None`, `not _ slots["read"].occupied`, `not _stdout_eof` e `not _overflow`.
   - Calcula `remaining = _MAX_STDOUT_BYTES - _total_stdout_bytes` (sempre `>= 0` antes do overflow) e `read_size = min(_READ_CHUNK, remaining + 1)` (`1 <= read_size <= 4096`).
   - Chama `_process.begin_read_into(_slots["read"], read_size)`.
2. **Colheita do `ReadOutcome`:**
   - Quando `_slots["read"].op.done() is True`, colhe `out = op.outcome()`.
   - Se `type(out) is not ReadOutcome`, `type(out.ok) is not bool`, `type(out.data) is not bytes` ou `len(out.data) > read_size` (ou `not out.ok` com `out.data != b""`): mantém o slot ou marca `_retained = True`, `_phase = BridgePhase.HELD` e recusa `BridgeRefusal(BridgeFault.PORT)`.
   - Se `out.ok is False`: mantém a operação falha retida em `_slots["read"]`, marca `_retained = True`, `_phase = BridgePhase.HELD` e recusa `BridgeRefusal(BridgeFault.PORT)`.
   - Se `out.ok is True`: limpa `_slots["read"]` após copiar `chunk = out.data`.
   - Se `chunk == b""`: marca `_stdout_eof = True`. Se `len(_partial_buf) > 0`, marca `_trailing_partial = True`, `_retained = True`, extrai `raw = bytes(_partial_buf)`, limpa `_partial_buf` e chama `self._enqueue_line(raw)`.
   - Se `len(chunk) > 0`: soma `_total_stdout_bytes += len(chunk)`. Se `_total_stdout_bytes > _MAX_STDOUT_BYTES` (atingiu `28673` B), marca `_overflow = True`, `_retained = True`, `_phase = BridgePhase.HELD` e levanta imediatamente `BridgeRefusal(BridgeFault.STDOUT_LIMIT)`.
3. **Montagem sem concatenação grande (`_partial_buf <= 513` B):**
   - Percorre `chunk` com índice `pos = 0`:
     - Procura `nl = chunk.find(b"\n", pos)`.
     - **Com `\n` (`nl != -1`):** `seg_len = nl + 1 - pos` e `total_len = len(_partial_buf) + seg_len`. Sem concatenar `_partial_buf + chunk[pos:nl+1]`, calcula `take = min(seg_len, _DIAG_LINE_CAP - len(_partial_buf))`, executa `_partial_buf.extend(chunk[pos : pos + take])`, extrai `raw = bytes(_partial_buf)` (`<= 513` B), limpa `_partial_buf`, avança `pos = nl + 1` e chama `self._enqueue_line(raw)`. Se `total_len > _LINE_CAP` (`len(raw) == 513`), marca `_overflow = True` e `_retained = True` e interrompe o consumo do restante de `chunk`.
     - **Sem `\n` (`nl == -1`):** `rem_len = len(chunk) - pos`, calcula `take = min(rem_len, _DIAG_LINE_CAP - len(_partial_buf))` e executa `_partial_buf.extend(chunk[pos : pos + take])`. Se `len(_partial_buf) == _DIAG_LINE_CAP` (`513` B sem `\n`), extrai `raw = bytes(_partial_buf)`, limpa `_partial_buf`, marca `_overflow = True` e `_retained = True`, chama `self._enqueue_line(raw)` e para de iniciar novas leituras.
4. **Verificação central de enfileiramento (`_enqueue_line` com teto 57):**
   - Toda inserção em `_line_queue` (linha normal terminada em `\n`, fatia diagnóstica de `513` B ou linha parcial de `EOF`) passa **obrigatoriamente** por `_enqueue_line(raw: bytes)`.
   - Se `len(_line_queue) >= _QUEUE_CAP` (`57`): marca `_overflow = True`, `_retained = True`, `_phase = BridgePhase.HELD` e levanta `BridgeRefusal(BridgeFault.STDOUT_LIMIT)` antes de anexar.
   - Caso contrário, executa `_line_queue.append(raw)`.
   - Quando a ponte entra em `HELD` por `STDOUT_LIMIT`, encerra imediatamente com falha fechada e slots conservados; **não** promete dreno infinito nem ausência de bloqueio de pipe após `HELD`.

## 5. Escrita (`Send`), ações (`Act`), prazos efetivos e serialização (`R5`, `R6`)

### 5.1 Prazo global (`_overall_deadline`) e janelas capturadas uma única vez (`R5`)

1. **Início único em `run()`:** se `_attempt_consumed is True` ou `_phase is not BridgePhase.NEW`, levanta `BridgeRefusal(BridgeFault.REENTRY)` sem alterar nenhum slot. Caso contrário, lê `t0 = _now()`, marca `_attempt_consumed = True`, `_overall_deadline = t0 + _budget.overall_s`, `_phase = BridgePhase.STARTING` e inicia `gateway.begin_spawn_into(_slots["spawn"], min(t0 + _budget.spawn_s, _overall_deadline))`.
2. **Prazo efetivo em todas as portas (`eff_deadline`):** toda operação com prazo recebe `eff_deadline = min(target_deadline, self._overall_deadline)`.
3. **Vencimento de `_overall_deadline`:** sempre que `_now() >= self._overall_deadline` antes de concluir `Done`:
   - A ponte colhe nos slots quaisquer operações cujo `done() is True` (adotando `_process` se `"spawn"` concluiu e registrando observações reais de leitura/saída sem inventar `UNKNOWN` para operação já concluída), mantém nos slots originais quaisquer operações com `done() is False`, **não** alimenta nenhum recibo `SENT`/`OK` nem nova `Line` que avance o `HostReactor`, marca `_retained = True`, `_phase = BridgePhase.HELD` e levanta `BridgeRefusal(BridgeFault.OVERALL_DEADLINE)`.
4. **Âncora de silêncio (`_silence_deadline`):** quando `reactor.status().pending is None`, `_line_queue` está vazia e a fase do reator é `AWAIT_GUARD`, `AWAIT_INIT_OK` ou `RUNNING`, se `_silence_deadline is None` a ponte captura **uma vez** `_silence_deadline = min(_overall_deadline, _now() + _budget.silence_s)`. Leituras parciais sem `\n` ou retornos de `poll()` sem linha completa **nunca** renovam `_silence_deadline`; ele só volta a `None` quando uma `Line` completa é retirada de `_line_queue` e entregue a `reactor.feed(...)`. Se `_now() >= _silence_deadline` (com `_now() < _overall_deadline`) sem saída do processo e sem linha completa, marca `_retained = True`, `_phase = BridgePhase.HELD` e levanta `BridgeRefusal(BridgeFault.SILENCE)`.
5. **Prazo de dreno terminal (`_drain_deadline` capturado uma única vez):** na **primeira** entrada em `HostPhase.DRAINING`, `HostPhase.ENDING` ou na coleta de saída após `ActDone(KILL_GATEWAY)`, se `_drain_deadline is None`, a ponte captura **uma única vez** `_drain_deadline = min(_overall_deadline, _now() + _budget.drain_s)`. Linhas `ABORT`/`TERMINAL` ou wakeups subsequentes **nunca** recalculam nem estendem `_drain_deadline`.

### 5.2 Escritas (`Send`) e recibos fechados (`NOT_SENT` / `SENT` / `UNKNOWN`, `R6`)

Quando `reactor.feed(...)` devolve `Send(token, purpose, payload, issued_at, deadline)`:
1. O owner lê `pre = _now()` (garantindo `pre >= issued_at` e `pre >= reactor.status().last_at`).
2. Chama `_process.begin_write_into(_slots["write"], payload, min(send.deadline, _overall_deadline))` e avança `clock.poll(...)` (drenando `stdout` em `_line_queue` enquanto aguarda) até `_slots["write"].op.done() is True` ou até `eff_deadline = min(send.deadline, _overall_deadline)`.
3. Se `_now() >= _overall_deadline` e a operação não concluiu antes de `_overall_deadline`: aplica a regra 5.1.3 (`OVERALL_DEADLINE`, mantendo `send` como `pending` no reator e a operação (ou resultado colhido) no owner).
4. Se `_slots["write"].op.done() is False` em `send.deadline` (com `_now() < _overall_deadline`):
   - A operação viva **permanece retida em `_slots["write"]`** (slot ocupado, nunca reutilizado);
   - Marca `_retained = True`, lê `post = _now()` e alimenta `Delivered(token, Delivery.UNKNOWN, pre, post)` no `HostReactor` (que entra em `DRAINING`).
5. Se `_slots["write"].op.done() is True`: colhe `out = op.outcome()`:
   - Valida `type(out) is WriteOutcome`, `type(out.delivery) is reactor_mod.Delivery` e `type(out.bytes_written) is int`:
     - `Delivery.NOT_SENT` exige `out.bytes_written == 0` (única prova aceita de zero bytes enviados);
     - `Delivery.SENT` exige `out.bytes_written == len(payload)`;
     - `Delivery.UNKNOWN` exige `0 <= out.bytes_written <= len(payload)`.
     - Qualquer violação de tipo/domínio levanta `BridgeRefusal(BridgeFault.PORT)` com `_retained = True` e `_phase = BridgePhase.HELD`.
   - Limpa `_slots["write"]` somente se `out.delivery in (Delivery.SENT, Delivery.NOT_SENT)`; se `out.delivery is Delivery.UNKNOWN`, mantém a operação retida em `_slots["write"]` e marca `_retained = True`.
   - Lê `post = _now()` e alimenta `Delivered(token, out.delivery, pre, post)` no `HostReactor` (se `post >= send.deadline`, o próprio reator trata `SENT` como tardio e vai para `DRAINING`).
   - Qualquer exceção levantada pela porta durante `begin_write_into` ou `outcome()` **nunca** é tratada como `NOT_SENT`: marca `_retained = True`, `_phase = BridgePhase.HELD` e fecha com `BridgeRefusal(BridgeFault.PORT)` (ou relança `BaseException` de controle).

### 5.3 Ações (`Act`), serialização de timestamps e ordenação de `T6` (`R5`, `R6`)

1. **Execução de `Act(token, kind, case, issued_at, deadline)`:**
   - Inicia `acts.begin_act_into(_slots["act"], act, min(act.deadline, _overall_deadline))` e avança `clock.poll(...)` (drenando `stdout` em `_line_queue`) até `_slots["act"].op.done() is True` ou `eff_deadline = min(act.deadline, _overall_deadline)`.
   - Se vencer `_overall_deadline`, aplica a regra 5.1.3 (`OVERALL_DEADLINE`).
   - Se `_slots["act"].op.done() is False` em `act.deadline` (com `_now() < _overall_deadline`): mantém a operação viva retida em `_slots["act"]`, marca `_retained = True`, lê `at = _now()` e alimenta `ActDone(token, kind, ActStatus.UNKNOWN, None, at)` no `HostReactor` (que marca o caso `FAIL` e entra em `DRAINING` — ou, para `KILL_GATEWAY`, retém falha de `T6` e aguarda `Exited`).
   - Se `done() is True`: colhe `ActOutcome(status, facts)`. Limpa `_slots["act"]` somente se `status in (ActStatus.OK, ActStatus.FAILED)`; se `status is ActStatus.UNKNOWN`, retém em `_slots["act"]` e marca `_retained = True`. Lê `at = _now()` e alimenta `ActDone(token, kind, status, facts, at)` (facts incoerentes geram `HostRefusal("RECEIPT")`, convertida em `BridgeRefusal(BridgeFault.REACTOR_REFUSAL, "RECEIPT")` com `_retained = True`).
2. **Serialização sem retrodatação:** enquanto `_slots["write"]` ou `_slots["act"]` aguarda conclusão para o `pending` atual do reator, o owner **nunca** desenfileira `Line` de `_line_queue` nem entrega `Exited`. Primeiro entrega `Delivered` ou `ActDone`; só quando `reactor.status().pending is None` desenfileira cada `raw` de `_line_queue` com timestamp pós-observação fresco `at = _now() >= reactor.status().last_at`.
3. **Ordenação de `T6` e limite de causalidade:** para `Act(KILL_GATEWAY, 25)` (cujo `deadline` é a `fence` calculada pelo reator a partir do `Delivered.pre` do `GO{25}`, jamais estendida pela ponte), o recibo `ActDone(KILL_GATEWAY)` é sempre entregue ao `HostReactor` **antes** de colher/entregar `Exited`. Se `Exited(EXITED, code != 69, eof=True, reaped=True)` devolver `Act(ZERO_BACKENDS, 25)`, `_slots["act"]` (já livre após `KILL_GATEWAY` `OK`) executa `ZERO_BACKENDS` até `min(act.deadline, _overall_deadline)`. Se `ActDone(KILL_GATEWAY)` terminou `UNKNOWN` com `_slots["act"]` ocupado, o reator nunca pede `ZERO_BACKENDS` (encerra em `T6_FAILED` / `ENDED_UNKNOWN`), preservando `_slots["act"]` intocado. Essa ordem de mensagens satisfaz o modelo, mas **não prova causalidade do kill nativo** (que caberá ao `ActPort` nativo provar por CID/inspect).

### 5.4 Primeiro `fault` pegajoso e primeiro `BaseException` de controle (`R6`)

- `self._fault` é pegajoso: uma vez definido, nenhuma falha posterior o sobrescreve.
- Qualquer `HostRefusal(cat)` do reator define `_reactor_refusal = cat`, `_set_fault(BridgeFault.REACTOR_REFUSAL)`, `_retained = True`, `_phase = BridgePhase.REFUSED` e levanta `BridgeRefusal(BridgeFault.REACTOR_REFUSAL, cat) from None`.
- Se um `BaseException` de controle (`not isinstance(exc, Exception)`, como `KeyboardInterrupt` ou `SystemExit`) ocorrer em qualquer ponto: a ponte colhe apenas eventual `GatewayProcess` já pronto em `_slots["spawn"]` para não perder a referência, registra `_set_fault(BridgeFault.CONTROL)`, `_retained = True` e `_phase = BridgePhase.HELD`, **não** limpa slots nem inicia I/O em `finally`, e relança a **mesma instância** `exc`.

## 6. Oráculos dos primeiros testes (`tests/test_oracle9_w1_duplex_bridge.py`, RED-first)

O próximo incremento após aprovação desta v2 pelo root é **somente** `tests/test_oracle9_w1_duplex_bridge.py` em estado RED (`docs/poc/oracle9_w1_duplex_bridge.py` ausente), usando apenas portas falsas síncronas e relógio diádico lógico.

| Grupo | Oráculo obrigatório nos primeiros testes (sem SO, loop nativo, socket, thread ou subprocesso) |
|---|---|
| `D1` | **Injeção do reator, DTOs e posse antes de efeito (`R1`, `R4`):** recusa `REACTOR`, `BUDGET` e `PORT` no construtor; verificação de `OperationSlot.bind` antes de iniciar efeito em `spawn`/`read`/`write`/`act`/`wait`; exceção lançada após `slot.bind(op)` conserva `op` e o recurso alocado no slot original com `retained=True` e `phase=HELD`; tentativa de sobrescrever slot ocupado recusa `PORT`; colheita de `spawn` tardio adota `_process` antes de limpar o slot; segunda chamada a `run()` recusa `REENTRY` |
| `D2` | **Caminho feliz completo e serialização FIFO de timestamps:** `54` linhas, `50` controles e `58` saídas `Send`/`Act` até `COMPLETE_CANDIDATE` sobre o `HostReactor` real (`e86f8e32`); linhas lidas do `stdout` durante `write` ou `act` aguardam como `bytes` brutos em `_line_queue`; o recibo (`Delivered`/`ActDone`) é entregue primeiro com `pre`/`post`/`at` reais, e as linhas enfileiradas recebem timestamps pós-observação não decrescentes do owner |
| `D3` | **Escritas e ações incertas, prazos e retenção no slot original (`R6`):** `WriteOutcome(NOT_SENT, 0)` → `DRAINING` e slot limpo; exceção na porta de escrita → `PORT`/`HELD` (nunca `NOT_SENT`); escrita parcial ou viva em `send.deadline` → `Delivered(UNKNOWN)`, operação viva retida permanentemente em `_slots["write"]`, `retained=True`, `DRAINING`, sem segundo recibo se concluir depois; o mesmo para os 6 `ActKind` em `_slots["act"]`, invalidando `RESULT PASS` anterior em `21`/`24` |
| `D4` | **Política única de `stdout`, teto 57 e `EOF` parcial (`R3`):** `read_size = min(4096, remaining + 1)`; montagem de linhas sem concatenação `> 513` B; linha de `513` B com ou sem `\n` enfileira amostra diagnóstica de `513` B, marca `overflow=True`/`retained=True` e dispara `HostRefusal("LINE")` (ou `ORDER` se pendente `< 56`); 57ª linha entregue ao reator recusa `LINE` antes de `ORDER`; 58ª tentativa de enqueue ou byte `28673` falha fechado com `STDOUT_LIMIT` e `phase=HELD`; `EOF` com bytes sem `\n` marca `trailing_partial=True` e recusa `LINE` |
| `D5` | **Prazo global (`overall_s`), silêncio (`silence_s`) e dreno único (`drain_s`) (`R5`):** todas as portas recebem `min(deadline, _overall_deadline)`; vencimento de `_overall_deadline` colhe observações concluídas sem inventar `UNKNOWN`, não avança o reator e recusa `OVERALL_DEADLINE` mantendo `pending` original; `_silence_deadline` não se renova por wake espúrio ou chunk parcial e recusa `SILENCE`; `_drain_deadline` é capturado uma única vez e ao vencer sem saída entrega `Exited(NO_EXIT)` → `RETAINED`/`ENDED_UNKNOWN` |
| `D6` | **Ordenação de `T6`, primeiro `fault`/`BaseException` e estáticos AST (`R2`, `R6`):** `ActDone(KILL_GATEWAY)` entregue antes de `Exited`; `fence` por `Delivered.pre` do `GO{25}` sem extensão; orçamento `< t6_kill_min_s` devolve `Done(T6_FAILED)` sem chamar `KILL_GATEWAY`; primeiro `KeyboardInterrupt`/`SystemExit` preserva slots/`_process`, marca `CONTROL`/`HELD` e relança a mesma instância; ausência de métodos/tipos de cleanup (`quiesce`/`close`/`BridgeQuiesced`/`BridgeAbsent`) e AST sem `os`/`subprocess`/`socket`/`threading`/`asyncio`/`w1_bootstrap_channel` |

## 7. Próximo incremento e gates abertos

- **Próximo passo único após revisão desta v2 pelo root:** criar apenas `tests/test_oracle9_w1_duplex_bridge.py` e medir o RED congelado antes de implementar `docs/poc/oracle9_w1_duplex_bridge.py`.
- **`NOT_PREPARED`:** contrato separado de cleanup/quiescência/ausência por CID, adaptador nativo Windows Proactor, pins de CLI/Desktop/stdlib/relógio, raiz, task, nonce, estado operacional, rede, PG16 e credenciais.
- **Gates nativos e de produto abertos (`BLOCK_NATIVE` / produto):** `T5` físico, `T2`/`T4`/`T6` nativos no Oracle Linux 9.8 (`621cc7f7`) com PG16 isolado, `B-1`, `B-2`, `D-090` gate 2, `C1`/`D-119`, TLS upstream, patches e ingressos `PGWire`/`MCP`/`Admin`/`IDE`. Gateway indisponível; SQL `PGWire` recusada.
