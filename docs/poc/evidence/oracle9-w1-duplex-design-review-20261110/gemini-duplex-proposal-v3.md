# W1 Oracle — ponte duplex mínima do host e portas injetadas (v3)

2026-11-10. Proposta somente documental e read-only (`MASKGW-DUPLEX-FINAL-PRECISIONS-ONLY-20261110-V3`), sob a delegação vigente do usuário. Elaborada por Gemini 4 Argon (High), esforço high — **não** por Claude2. O usuário autorizou expressamente o uso dos pacotes públicos necessários pelo Gemini enquanto a quota do Claude2 (`sessão 51ea0d85`, `claude-opus-5-5`, medium) permanece interrompida por erro 429 até 19h30 São Paulo / 22h30 UTC de 2026-11-10. Esta v3 aplica as emendas mínimas de fechamento `R7` (`R7.1`–`R7.4` de `FINAL-PRECISIONS.md`) sobre a v2 (`6dbb0ce5`, 303 linhas / 32190 B), preservando a v1 (`7cba610d`) e a v2 como histórico. Não reivindica autoria do Claude, aprovação individual do usuário nem prova nativa.

Base pública: código `7ecf056`, checkpoint documental `cad2edf`. Nada foi executado, gerado ou editado: nenhum teste, comando, processo, socket, thread, loop de eventos, guard, sinal, Docker, PostgreSQL, SQL, raiz operacional, nonce, credencial ou estado. Os resultados verdes históricos (`1215` relacionados, `366` próprios e `18` sondas independentes) não foram repetidos nesta leitura e não fecham nenhum gate nativo ou de produto.

## 1. Escopo mínimo, insumos imutáveis e exclusão de limpeza física (`R2`, `R4`, `R7`)

O **único** objeto deste desenho é o módulo de definições `docs/poc/oracle9_w1_duplex_bridge.py`: uma ponte síncrona mínima que conduz uma instância fresca do `HostReactor` puro (`e86f8e32`) através de portas síncronas específicas e determinísticas, representando um único processo futuro de CLI do container gateway (`stdin=PIPE`, `stdout=PIPE`, `stderr=DEVNULL`) e as seis ações fechadas do host.

| Insumo público imutável | Pin / Tamanho | Papel e restrição |
|---|---|---|
| `docs/poc/oracle9_w1_host_reactor.py` | `e86f8e32` (38610 B / 1104 linhas) | Único decisor de protocolo, sequência, veredictos e cerca de `T6`; injetado já carregado pelo chamador |
| `tests/test_oracle9_w1_host_reactor.py` | `f177102a` (77736 B / 2144 linhas) | Oráculo congelado `H1`–`H17` + `R1` do reator; inalterado |
| `deploy/oracle9_w1_main.py` | `89c99c65` (46787 B) | `HostLink` (`<= 512` B com `LF`, `56` linhas), códigos `64`–`70` e `HOLD` |
| `deploy/oracle9_w1_driver.py` | `b54a8a94` (51913 B) | Eventos canônicos, fases/razões de `ABORT`, `load_pure` |
| `deploy/oracle9_w1_controller.py` | `4c155d76` (22453 B) | `decode_init`, `decode_control`, `ControlMachine`, constantes |
| `docs/poc/oracle9_w1_expect.py` | `ce6ff389` (22114 B) | Gera o pacote `LAB_INIT` fora da ponte; não importado |

**Fronteiras fechadas:**
- `HOST-TEST-REVIEW` e `HOST-SOURCE-REVIEW` prevalecem sobre qualquer ambiguidade anterior do `HOST-DESIGN` (`aed85ad4`). O teto antigo de `256` linhas do `NATIVE-PLAN` v4 está superado por `56` linhas (`54` normais + `2` para `ABORT`/`TERMINAL`) e `<= 512` B por linha incluindo `LF`, mantida a exceção da 57ª linha recusada com `HostRefusal("LINE")` antes de `ORDER` ou parse.
- `w1_bootstrap_channel.py` é apenas referência conceitual histórica; é **proibido importá-lo** (wire, limites e pins incompatíveis).
- **Corte estrito de limpeza e tickets (`R2`):** ficam **removidos** deste módulo `quiesce()`, `close()`, `assert_released()`, `BridgeQuiesced`, `BridgeAbsent`, geração de `nonce`, `issue_ticket` e flags de `released`/`cleanup`. A instância de `DuplexBridge` é criada e retida fortemente pelo chamador **antes** de `run()` e conserva permanentemente todos os seus slots e referências incertas. `Done` (inclusive `COMPLETE_CANDIDATE`) é apenas candidato de protocolo. Matar ou colher a saída do processo CLI do gateway **não** encerra nem aquieta ações de `ActPort` (que no lote nativo terão processos/conexões e owners próprios). O contrato de quiescência, limpeza física e prova de ausência por CID pertence a lote futuro separado, antes de ligar o SO real.
- Os `124` insumos do pacote (`123` caminhos + `pyproject.toml`), o `source20`/`estado16` e a tentativa consumida `3f12dc584c29` (`FAILED_ONLY_OPERATOR_ABORT`) permanecem fixos.

## 2. Injeção do módulo do reator e semânticas de runtime (`R4`, `R7.4`)

A ponte **não** importa `docs.poc.oracle9_w1_host_reactor` automaticamente nem usa `runpy`/`importlib`. O chamador carrega o módulo do reator por caminho pinado e injeta na ponte tanto o namespace `reactor_mod: types.ModuleType` quanto uma instância fresca `reactor: HostReactor`.

- **Verificação no construtor (`_trusted_reactor_binding`, `R7.4`):**
  - `type(reactor_mod) is types.ModuleType`;
  - presença das classes exatas (`isinstance(cls, type)`) `HostReactor`, `HostRefusal`, `HostPolicy`, `HostStatus`, `Line`, `Delivered`, `ActDone`, `Exited`, `Send`, `Act`, `Wait`, `Done`, `TerminateFacts`, `PauseFacts`, `RestoreFacts`, `ObserveFacts`, `ZeroFacts`, `KillFacts` e dos enums `Delivery`, `ActStatus`, `ExitStatus`, `Purpose`, `Verdict`, `Outcome`, `HostPhase`, `ActKind`;
  - `type(reactor) is reactor_mod.HostReactor`;
  - `reactor.status()` devolve `s` com `type(s) is reactor_mod.HostStatus`, `s.phase is reactor_mod.HostPhase.AWAIT_GUARD`, `_same_int(s.lines, 0)`, `_same_int(s.controls_sent, 0)`, `s.last_at is None`, `s.pending is None`, `s.orphan is None`, `s.orphan_receipt is None`, `s.refusal is None` e `s.verdicts == (reactor_mod.Verdict.NOT_RUN,) * 25`.
  - A validação de forma não autentica a origem do arquivo; o pin de origem é responsabilidade do chamador. Qualquer divergência levanta `BridgeRefusal(BridgeFault.REACTOR)` sem criar instância.
- **Execução síncrona sem loop nativo nos primeiros testes (`R4`, `R7.2`):** `DuplexBridge` é inteiramente síncrona (`run() -> BridgeRunResult`), avançando apenas por chamadas a `ClockPort.poll(watched, deadline)` sobre slots de operação explícitos. Portas e relógio falsos são contratos lógicos determinísticos: não medem preempção ou latência do SO. Na futura ligação ao Windows CPython 3.11.3 (`BLOCK_NATIVE`), o adaptador nativo implementará essas mesmas portas sobre o Proactor mantendo as restrições documentadas (sem `communicate()`, `stderr=DEVNULL`, sem depender de `wait_for` cancelado para prazo nem de `is_closing()` como prova).

## 3. API exata, DTOs fechados, slots de operação e portas (`R1`, `R4`, `R6`, `R7`)

Módulo proposto: `docs/poc/oracle9_w1_duplex_bridge.py` (somente definições; sem efeitos no import). Todos os DTOs usam `@dataclass(frozen=True, slots=True)`. Os carriers (`DuplexBudget`, `SpawnOutcome`, `ReadOutcome`, `WriteOutcome`, `ActOutcome`, `WaitOutcome`) aceitam qualquer valor em `__init__` sem levantar exceção; toda validação ocorre nos métodos da ponte.

### 3.1 Enums, exceção fechada e DTOs públicos com `__repr__` redigido (`R7.4`)

Como carriers e vistas podem receber objetos arbitrários antes da validação (ou reter handles/outcomes), **todos** os DTOs que contêm `object` ou `bytes` usam `repr=False` e implementam `__repr__` seguro que **jamais** chama `repr()` ou `str()` sobre `bytes`, `process`, `op`, `facts` ou objetos injetados arbitrários (exibindo apenas tipos/enums fechados conhecidos, booleanos/inteiros exatos ou `<redacted>`/`<object>`).

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
    """Exceção fechada: args == (category.value,), levantada fora de handler sem __cause__/__context__."""
    def __init__(self, category: BridgeFault, reactor_refusal: str | None = None) -> None:
        self.category = category
        self.reactor_refusal = reactor_refusal
        super().__init__(category.value)
```

```python
@dataclass(frozen=True, slots=True)
class DuplexBudget:
    spawn_s: float        # 0 < spawn_s <= 30.0 (domínio prospectivo de teste; operacional é NOT_PREPARED)
    silence_s: float      # 0 < silence_s <= 60.0
    drain_s: float        # 0 < drain_s <= 30.0
    overall_s: float      # max(spawn_s, silence_s, drain_s) < overall_s <= 300.0 (não é o freshness de 300s)

@dataclass(frozen=True, slots=True, repr=False)
class SpawnOutcome:
    ok: bool
    process: object | None
    def __repr__(self) -> str:
        ok_s = repr(self.ok) if type(self.ok) is bool else "<invalid>"
        proc_s = "None" if self.process is None else "<object>"
        return f"SpawnOutcome(ok={ok_s}, process={proc_s})"

@dataclass(frozen=True, slots=True, repr=False)
class ReadOutcome:
    ok: bool
    data: bytes
    def __repr__(self) -> str:
        ok_s = repr(self.ok) if type(self.ok) is bool else "<invalid>"
        size = len(self.data) if type(self.data) is bytes else -1
        return f"ReadOutcome(ok={ok_s}, len={size})"

@dataclass(frozen=True, slots=True, repr=False)
class WriteOutcome:
    delivery: object      # reactor_mod.Delivery: NOT_SENT | SENT | UNKNOWN
    bytes_written: int    # int exato: 0 para NOT_SENT; len(payload) para SENT; 0..len para UNKNOWN
    def __repr__(self) -> str:
        d_s = self.delivery.name if isinstance(self.delivery, enum.Enum) else "<invalid>"
        n_s = repr(self.bytes_written) if type(self.bytes_written) is int else "<invalid>"
        return f"WriteOutcome(delivery={d_s}, bytes_written={n_s})"

@dataclass(frozen=True, slots=True, repr=False)
class ActOutcome:
    status: object        # reactor_mod.ActStatus: OK | FAILED | UNKNOWN
    facts: object | None  # TerminateFacts | PauseFacts | RestoreFacts | ObserveFacts | ZeroFacts | KillFacts | None
    def __repr__(self) -> str:
        st_s = self.status.name if isinstance(self.status, enum.Enum) else "<invalid>"
        f_s = "None" if self.facts is None else "<facts>"
        return f"ActOutcome(status={st_s}, facts={f_s})"

@dataclass(frozen=True, slots=True, repr=False)
class WaitOutcome:
    status: object        # reactor_mod.ExitStatus: EXITED | NO_EXIT | UNKNOWN
    code: int | None      # int exato 0..255 sse EXITED, senão None
    reaped: bool          # bool exato; True somente com EXITED e reap confirmado pela porta
    def __repr__(self) -> str:
        st_s = self.status.name if isinstance(self.status, enum.Enum) else "<invalid>"
        c_s = repr(self.code) if type(self.code) is int or self.code is None else "<invalid>"
        r_s = repr(self.reaped) if type(self.reaped) is bool else "<invalid>"
        return f"WaitOutcome(status={st_s}, code={c_s}, reaped={r_s})"

@dataclass(frozen=True, slots=True, repr=False)
class SlotView:
    name: str
    occupied: bool
    op: object | None
    done: bool
    outcome: object | None
    def __repr__(self) -> str:
        return f"SlotView(name={self.name!r}, occupied={self.occupied!r}, done={self.done!r})"

@dataclass(frozen=True, slots=True, repr=False)
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
    def __repr__(self) -> str:
        f_s = None if self.fault is None else self.fault.name
        return f"BridgeStatus(phase={self.phase.name}, fault={f_s!r}, retained={self.retained!r}, <redacted>)"

@dataclass(frozen=True, slots=True, repr=False)
class BridgeRunResult:
    done: object                         # reactor_mod.Done (apenas candidato de protocolo)
    status: BridgeStatus
    def __repr__(self) -> str:
        return f"BridgeRunResult(phase={self.status.phase.name}, retained={self.status.retained!r})"
```

### 3.2 `OperationSlot`, colheita única em cache e `_clear_known_positive` (`R1`, `R7.1`)

A ponte pré-aloca cinco instâncias de `OperationSlot` em `__init__` (`"spawn"`, `"read"`, `"write"`, `"act"`, `"wait"`). `OperationSlot` expõe publicamente **apenas** `name`, `op`, `occupied` e `bind(op)` — portas e fakes não possuem método para limpar o slot:

```python
class OperationSlot:
    def __init__(self, name: str) -> None: ...
    @property
    def name(self) -> str: ...
    @property
    def op(self) -> object | None: ...
    @property
    def occupied(self) -> bool: ...
    def bind(self, op: object) -> None: ...
    def __repr__(self) -> str: ...
```

**Regras de reserva, colheita única em cache e limpeza exclusiva pela ponte (`R7.1`):**
1. **`bind(op)` antes do efeito:** todo método `begin_*_into(slot, ...)` da porta **deve** chamar `slot.bind(op)` com o handle inerte (`callable(getattr(op, "done", None))` e `callable(getattr(op, "outcome", None))`) **antes** de criar processo, agendar I/O ou alterar estado. Se `slot.occupied` já for `True` ou `op` não tiver a forma exigida, `slot.bind(op)` levanta `BridgeRefusal(BridgeFault.PORT)` sem sobrescrever o `_op` original.
2. **Colheita única em cache (`_harvest_slot(slot)`):**
   - Cada operação vinculada em `slot` é inspecionada por `op.done()` apenas enquanto ainda não foi colhida/reportada (`not harvested`). `op.done()` deve devolver `bool` exato; qualquer outro retorno ou exceção marca o slot como reportado/quarentenado, define `_retained = True`, `_phase = BridgePhase.HELD` e levanta `BridgeRefusal(BridgeFault.PORT)`.
   - Quando `op.done() is True`, a ponte marca imediatamente o slot como colhido/reportado (`harvested = True`, `done_cached = True`) e chama `op.outcome()` **uma única vez**, salvando o objeto retornado em `outcome_cached` (ou a exceção capturada) **antes** de qualquer validação de domínio. Operações com `harvested is True` (ou quarentenadas por prazo/erro/`UNKNOWN`) **nunca** têm `done()` ou `outcome()` chamados novamente e **nunca** voltam a entrar na tupla `watched` de `clock.poll(...)`.
3. **Limpeza privada exclusiva (`DuplexBridge._clear_known_positive(slot)`):**
   - Somente o método privado `self._clear_known_positive(slot)` da ponte pode esvaziar `slot` (`slot.op -> None`, `slot.occupied -> False`, limpando o cache transitório do slot), e **somente** após validar e absorver um resultado positivo/determinado:
     - `"spawn"`: `SpawnOutcome(ok=True, process=proc)` com `proc` válido, após `self._process = proc`;
     - `"read"`: `ReadOutcome(ok=True, data=chunk)` válido e absorvido sem overflow;
     - `"write"`: `WriteOutcome` válido com `delivery in (Delivery.SENT, Delivery.NOT_SENT)`;
     - `"act"`: `ActOutcome` válido com `status in (ActStatus.OK, ActStatus.FAILED)` **depois** que `reactor.feed(ActDone(...))` aceitou o recibo sem levantar `HostRefusal`;
     - `"wait"`: `WaitOutcome(status=ExitStatus.EXITED, code=0..255, reaped=True)` válido, após copiar para `_wait_cache`.
   - Em qualquer resultado `UNKNOWN`, `NO_EXIT`, `ok=False`, `facts`/recibo recusado pelo reator, erro de porta ou operação viva no prazo (`done_cached is False`), `_clear_known_positive` **não** é chamado: `slot.op` e `SlotView.outcome` (em cache) permanecem retidos no slot original (`slot.occupied is True`).
4. **Adoção de `process` mesmo em `SpawnOutcome` falho:** sempre que `"spawn"` é colhido e `type(outcome_cached) is SpawnOutcome` com `outcome_cached.process is not None`, a ponte retém `self._process = outcome_cached.process` **antes** de validar `ok` ou a forma de `process` e antes de levantar `SPAWN` ou `PORT`.
5. **`status()` é leitura pura de cache (`R7.1`):** `bridge.status()` **nunca** chama `op.done()`, `op.outcome()`, `clock.now()`, `clock.poll()` nem colhe spawn tardio; lê exclusivamente os valores já em cache na ponte (`SlotView.done` e `SlotView.outcome` refletem apenas o cache colhido).

### 3.3 Portas síncronas injetadas (`ClockPort`, `GatewayPort`, `GatewayProcess`, `ActPort`, `R7.2`)

Conferidas por forma no `__init__` da ponte (e `GatewayProcess` ao ser validado em `"spawn"`); ausência de método `callable` levanta `BridgeRefusal(BridgeFault.PORT)`:

1. **`ClockPort`:**
   - `now() -> float`: devolve instante monotônico `int | float` exato (`bool` e subclasses recusados), finito e `>= 0`, não decrescente em relação a `_last_clock` (violação levanta `BridgeRefusal(BridgeFault.PORT)`).
   - `poll(watched: tuple[OperationSlot, ...], deadline: float) -> float`: recebe a tupla não vazia `watched` contendo **apenas** `OperationSlot`s ocupados e ainda não colhidos/reportados, e `deadline` (`int | float` finito `>= _last_clock`). Deve retornar `t_now` (`_last_clock <= t_now <= deadline` ou `>= _last_clock`) quando pelo menos um slot de `watched` concluir (`done() is True`) ou quando o relógio atingir `deadline`. **Proibição de busy-loop:** se após colher `watched` nenhum slot de `watched` tiver concluído (`done() is True`) **e** `t_now < deadline` **e** `t_now == _last_clock` (retorno no mesmo instante sem nova conclusão), a ponte marca `_retained = True`, `_phase = BridgePhase.HELD` e recusa com `BridgeRefusal(BridgeFault.PORT)`.
2. **`GatewayPort` e `GatewayProcess`:**
   - `GatewayPort.begin_spawn_into(slot: OperationSlot, deadline: float) -> None`.
   - `GatewayProcess.begin_read_into(slot: OperationSlot, max_bytes: int, deadline: float) -> None` (`1 <= max_bytes <= 4096`, `deadline = _overall_deadline`).
   - `GatewayProcess.begin_write_into(slot: OperationSlot, payload: bytes, deadline: float) -> None`.
   - `GatewayProcess.begin_wait_into(slot: OperationSlot, deadline: float) -> None`.
3. **`ActPort`:**
   - `ActPort.begin_act_into(slot: OperationSlot, act: Act, deadline: float) -> None`: aceita `act` (`reactor_mod.Act`) dos seis `ActKind` fechados com `deadline = min(act.deadline, _overall_deadline)`.

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

## 4. Política única e finita de `stdout` (`R3`, `R7.4`)

Constantes exatas da ponte: `_READ_CHUNK = 4096`, `_LINE_CAP = 512`, `_DIAG_LINE_CAP = 513`, `_QUEUE_CAP = 57`, `_MAX_STDOUT_BYTES = 28672` (`56 * 512` B admitidos + no máximo `1` B de detecção de overflow = `28673` B).

1. **Armar leitura (`_arm_read`):** somente quando `_process is not None`, `not _slots["read"].occupied`, `not _stdout_eof` e `not _overflow`, calcula `remaining = _MAX_STDOUT_BYTES - _total_stdout_bytes` e `read_size = min(_READ_CHUNK, remaining + 1)` (`1 <= read_size <= 4096`), chamando `_process.begin_read_into(_slots["read"], read_size, _overall_deadline)`.
2. **Colheita e validação de `ReadOutcome`:**
   - Quando `_slots["read"]` é colhido em `_harvest_slot`, valida `type(out) is ReadOutcome`, `type(out.ok) is bool`, `type(out.data) is bytes` e `len(out.data) <= read_size` (e se `not out.ok`, `out.data == b""`). Qualquer violação ou `out.ok is False` mantém `_slots["read"]` ocupado com `op` e `out` em cache, marca `_retained = True`, `_phase = BridgePhase.HELD` e levanta `BridgeRefusal(BridgeFault.PORT)`.
   - Se `out.ok is True` e `out.data == b""`: chama `_clear_known_positive(_slots["read"])`, marca `_stdout_eof = True` e, se `len(_partial_buf) > 0`, marca `_trailing_partial = True`, `_retained = True`, extrai `raw = bytes(_partial_buf)`, limpa `_partial_buf` e chama `self._enqueue_line(raw)`.
   - Se `out.ok is True` e `len(out.data) > 0`: soma `_total_stdout_bytes += len(out.data)`. Se `_total_stdout_bytes > _MAX_STDOUT_BYTES` (`28673` B), mantém `_slots["read"]` ocupado com `out` em cache, marca `_overflow = True`, `_retained = True`, `_phase = BridgePhase.HELD` e levanta `BridgeRefusal(BridgeFault.STDOUT_LIMIT)`. Caso contrário, chama `_clear_known_positive(_slots["read"])` e processa `chunk = out.data`.
3. **Montagem sem concatenação grande (`_partial_buf <= 513` B):**
   - Percorre `chunk` com `pos = 0` procurando `nl = chunk.find(b"\n", pos)`:
     - **Com `\n` (`nl != -1`):** `seg_len = nl + 1 - pos`, `total_len = len(_partial_buf) + seg_len`, `take = min(seg_len, _DIAG_LINE_CAP - len(_partial_buf))`. Executa `_partial_buf.extend(chunk[pos : pos + take])`, extrai `raw = bytes(_partial_buf)` (`<= 513` B), limpa `_partial_buf`, avança `pos = nl + 1` e chama `self._enqueue_line(raw)`. Se `total_len > _LINE_CAP` (`len(raw) == 513`), marca `_overflow = True`, `_retained = True` e interrompe a varredura de `chunk`.
     - **Sem `\n` (`nl == -1`):** `rem_len = len(chunk) - pos`, `take = min(rem_len, _DIAG_LINE_CAP - len(_partial_buf))`, executa `_partial_buf.extend(chunk[pos : pos + take])`. Se `len(_partial_buf) == _DIAG_LINE_CAP` (`513` B sem `\n`), extrai `raw = bytes(_partial_buf)`, limpa `_partial_buf`, marca `_overflow = True`, `_retained = True` e chama `self._enqueue_line(raw)`.
4. **Enfileiramento central (`_enqueue_line` com teto 57):** se `len(_line_queue) >= _QUEUE_CAP` (`57`), marca `_overflow = True`, `_retained = True`, `_phase = BridgePhase.HELD` e levanta `BridgeRefusal(BridgeFault.STDOUT_LIMIT)` antes de anexar. Caso contrário, `_line_queue.append(raw)`. Após `HELD`, a ponte não promete dreno adicional nem pipe livre.

## 5. Algoritmo normativo do loop principal, `Send`/`Act`, `Wait`/`EOF`/`Exited` e `T6` (`R5`, `R6`, `R7.2`–`R7.4`)

### 5.1 Partida, `_overall_deadline` absoluto e colheita de I/O em cada `poll`

1. **Reserva da tentativa antes do primeiro callback (`R7.2`):** no início de `run()`, se `_attempt_consumed is True` ou `_phase is not BridgePhase.NEW`, levanta `BridgeRefusal(BridgeFault.REENTRY)` sem tocar em nenhum slot. Caso contrário, define **imediatamente** `_attempt_consumed = True` e `_phase = BridgePhase.STARTING` **antes** da primeira chamada a `clock.now()` ou `gateway.begin_spawn_into(...)`.
2. **Spawn e armamento inicial (`R7.3`):**
   - Lê `t0 = _now()`, fixa `_overall_deadline = t0 + _budget.overall_s` e `spawn_deadline = min(t0 + _budget.spawn_s, _overall_deadline)`.
   - Chama `gateway.begin_spawn_into(_slots["spawn"], spawn_deadline)` (exigindo `_slots["spawn"].occupied is True`).
   - Enquanto `_slots["spawn"]` não foi colhido e `_now() < spawn_deadline`, chama `_poll_and_harvest((_slots["spawn"],), spawn_deadline)`.
   - Se `_now() >= _overall_deadline`, aplica a regra 5.1.3 (`OVERALL_DEADLINE`).
   - Se `"spawn"` não concluiu até `spawn_deadline` ou concluiu com `ok is False` (retendo `out.process` em `self._process` se não nulo, conforme 3.2.4), marca `_retained = True`, `_phase = BridgePhase.HELD` e levanta `BridgeRefusal(BridgeFault.SPAWN)` (ou `PORT` se tipo/forma inválidos).
   - Com `SpawnOutcome(ok=True, process=proc)` válido: adota `self._process = proc`, chama `_clear_known_positive(_slots["spawn"])`, muda `_phase = BridgePhase.ACTIVE` e arma imediatamente `_arm_read()` em `_slots["read"]` e `_process.begin_wait_into(_slots["wait"], _overall_deadline)` em `_slots["wait"]`.
3. **Regra invariável de `_overall_deadline` e `_poll_and_harvest(watched, deadline)` (`R5`, `R7.3`, `R7.4`):**
   - Em todo passo de espera, a ponte chama `now = clock.poll(watched, min(deadline, _overall_deadline))` e colhe uma vez (`_harvest_slot`) cada slot de `watched` cujo `op.done()` seja `True`.
   - **Sem exceção após `_overall_deadline` (`R7.4`):** somente o instante `now` observado pelo owner governa. Se `now >= _overall_deadline`, a ponte apenas retém no cache os outcomes/processos já colhidos (sem alimentar recibo, linha ou `Exited` no `HostReactor`), marca `_retained = True`, `_phase = BridgePhase.HELD` e levanta `BridgeRefusal(BridgeFault.OVERALL_DEADLINE)`.
   - Quando `now < _overall_deadline`: se `_slots["wait"]` foi colhido, valida `WaitOutcome` (para `EXITED`, `code` int `0..255` e `reaped is True` → salva em `_wait_cache` e chama `_clear_known_positive(_slots["wait"])`; para `NO_EXIT` ou `UNKNOWN`, `code is None` e `reaped is False` → salva em `_wait_cache`, marca `_retained = True` e mantém `_slots["wait"]` ocupado/quarentenado; qualquer outra forma levanta `PORT`). Se `_slots["read"]` foi colhido, processa os bytes/EOF conforme a Seção 4 e, se `_slots["read"]` foi limpo por `_clear_known_positive` e `not _stdout_eof and not _overflow`, rearma `_arm_read()` imediatamente.

### 5.2 Execução de `Send` e `Act`, verificação pré-partida de `EOF`/saída e exceção `ZERO_BACKENDS(25)` (`R6`, `R7.3`, `R7.4`)

1. **Verificação antes de iniciar NOVO `Send` ou `Act` nativo (`R7.3`):**
   - Quando `reactor.feed(...)` devolve um novo `Send` ou `Act` (que passa a ser `reactor.status().pending`, ainda sem operação iniciada em `_slots["write"]` ou `_slots["act"]`):
   - **Exceção explícita para `Act(kind=ActKind.ZERO_BACKENDS, case=25)`:** como `ZERO_BACKENDS(25)` é emitido pelo `HostReactor` exatamente em resposta ao `Exited` válido pós-`KILL_GATEWAY`, ele **deve** ser iniciado em `_slots["act"]` mesmo com `_stdout_eof is True` e `_wait_cache` já preenchido.
   - **Para todos os demais `Send` e `Act`:** se `self._stdout_eof is True` ou `self._wait_cache is not None` antes de iniciar a operação na porta, a ponte **não** inicia escrita/ação desnecessária nem fabrica `Delivered(NOT_SENT)`. Em vez disso, entra no dreno terminal (5.3.2), consome eventuais linhas `ABORT`/`TERMINAL` da `_line_queue` e entrega `Exited` conservador ao `HostReactor`, que transforma `pending` em `orphan` e conclui com `Done`.
2. **Escrita (`Send`) em voo (`R6`):**
   - Verifica `_slots["write"].occupied is False` (senão `PORT`), lê `pre = _now()`, chama `_process.begin_write_into(_slots["write"], send.payload, min(send.deadline, _overall_deadline))` e executa `_poll_and_harvest` (incluindo `_slots["write"]` e slots elegíveis de `"read"`/`"wait"`, drenando `stdout` para `_line_queue` sem alimentar o reator) até `_slots["write"]` ser colhido ou `_now() >= min(send.deadline, _overall_deadline)`.
   - Se `_slots["write"]` não concluiu até `send.deadline` (`_now() < _overall_deadline`): marca `_slots["write"]` como quarentenado (permanece ocupado em `_slots["write"]`, fora de futuros `watched`), marca `_retained = True`, lê `post = _now()` e alimenta `Delivered(send.token, Delivery.UNKNOWN, pre, post)` (entrando em `DRAINING`).
   - Se concluiu: valida `WriteOutcome(delivery, bytes_written)` (`NOT_SENT` exige `bytes_written == 0`; `SENT` exige `bytes_written == len(send.payload)`; `UNKNOWN` exige `0 <= bytes_written <= len(send.payload)`; senão `PORT`). Chama `_clear_known_positive(_slots["write"])` somente para `SENT` ou `NOT_SENT` (para `UNKNOWN`, mantém ocupado e `_retained = True`), lê `post = _now()` e alimenta `Delivered(send.token, out.delivery, pre, post)` **antes** de qualquer `Line` ou `Exited`.
3. **Ação (`Act`) em voo (`R6`, `R7.4`):**
   - Verifica `_slots["act"].occupied is False` (senão `PORT`), chama `acts.begin_act_into(_slots["act"], act, min(act.deadline, _overall_deadline))` e executa `_poll_and_harvest` até `_slots["act"]` ser colhido ou `_now() >= min(act.deadline, _overall_deadline)`.
   - Se não concluiu até `act.deadline` (`_now() < _overall_deadline`): quarentena `_slots["act"]` (permanece ocupado), marca `_retained = True`, lê `at = _now()` e alimenta `ActDone(act.token, act.kind, ActStatus.UNKNOWN, None, at)`.
   - Se concluiu: valida `type(out) is ActOutcome` e `type(out.status) is reactor_mod.ActStatus` (senão mantém em `_slots["act"]`, `_retained = True` e recusa `PORT`). Lê `at = _now()` e chama `reactor.feed(ActDone(act.token, act.kind, out.status, out.facts, at))` **antes** de limpar o slot: se `reactor.feed` aceitar e `out.status in (ActStatus.OK, ActStatus.FAILED)`, chama `_clear_known_positive(_slots["act"])` (para `UNKNOWN`, mantém ocupado e `_retained = True`); se `reactor.feed` levantar `HostRefusal("RECEIPT")` por `facts` incoerentes, `_slots["act"]` permanece ocupado com `op` e `out` retidos!

### 5.3 Consumo da `_line_queue`, algoritmo de `Wait`/`EOF`/`Exited` e ordenação de `T6` (`R7.3`)

Quando não há operação nativa de `write` ou `act` em voo (`reactor.status().pending is None` ou dreno pré-efeito da regra 5.2.1):

1. **Fila FIFO de linhas antes de `Exited`:**
   - Enquanto `reactor.status().pending is None` e `len(_line_queue) > 0`:
     - Retira `raw = _line_queue.popleft()`, reseta `_silence_deadline = None`, lê `at = _now()` (pós-observação `>= reactor.status().last_at`) e chama `step = reactor.feed(Line(raw=raw, at=at))`.
     - Se `step` for `Done`, define `_phase = BridgePhase.HELD if (_retained or step.controller_retained) else BridgePhase.DONE` e retorna `BridgeRunResult(done=step, status=self.status())`.
     - Se `step` for `Send` ou `Act`, executa a Seção 5.2 **antes** de retirar outra linha de `_line_queue`.
2. **Coleta de dreno terminal e emissão de `Exited` com fatos reais em cache:**
   - Entra em modo de dreno quando `reactor.status().phase in (HostPhase.DRAINING, HostPhase.ENDING)`, ou após entregar `ActDone(KILL_GATEWAY)`, ou quando `_stdout_eof is True` ou `_wait_cache is not None`.
   - Na **primeira** vez que entra em modo de dreno, captura **uma única vez** `_drain_deadline = min(_overall_deadline, _now() + _budget.drain_s)` (jamais renovado por linhas ou wakeups).
   - Se `_wait_cache` tem `EXITED` mas `not _stdout_eof`, ou se `_stdout_eof is True` mas `_wait_cache is None`, ou se ambos ainda aguardam em `DRAINING`/`ENDING`/pós-`KILL_GATEWAY`: enquanto `(not _stdout_eof or _wait_cache is None)` e `_now() < _drain_deadline` e existir slot elegível (`"read"` ou `"wait"`), chama `_poll_and_harvest(watched, _drain_deadline)` e, se novas linhas entraram em `_line_queue` (inclusive parcial de `EOF`) enquanto `pending is None`, retorna ao passo 5.3.1 para alimentá-las antes de `Exited`.
   - Quando `(_stdout_eof and _wait_cache is not None)` ou `_now() >= _drain_deadline` (com `_line_queue` vazia ou `pending` aguardando `orphan` por 5.2.1):
     - Se `_wait_cache is not None`: usa os fatos reais em cache `status = _wait_cache.status`, `code = _wait_cache.code`, `reaped = _wait_cache.reaped` e `eof = self._stdout_eof` (mesmo que `eof` seja `False`). Se `status is not ExitStatus.EXITED` ou `not eof` ou `not reaped`, marca `_retained = True`.
     - Se `_wait_cache is None` (o prazo `_drain_deadline` venceu e `"wait"` permaneceu pendente sem retornar `WaitOutcome`, logo sem prova positiva de `EXITED` nem de `NO_EXIT`): quarentena `_slots["wait"]` (permanece ocupado), marca `_retained = True` e usa `status = ExitStatus.UNKNOWN`, `code = None`, `eof = self._stdout_eof`, `reaped = False`. (`ExitStatus.NO_EXIT` só é usado quando a porta concluiu `"wait"` devolvendo positivamente `WaitOutcome(status=ExitStatus.NO_EXIT, code=None, reaped=False)`).
     - Entrega `step = reactor.feed(Exited(at=_now(), status=status, code=code, eof=eof, reaped=reaped))`: se devolver `Act(ZERO_BACKENDS, 25)`, executa-o por 5.2; se devolver `Done`, define `_phase = BridgePhase.HELD if (_retained or step.controller_retained) else BridgePhase.DONE` e retorna `BridgeRunResult(done=step, status=self.status())`.
3. **Espera normal por linha (`silence_s`):**
   - Quando não está em modo de dreno, `pending is None` e `_line_queue` está vazia: se `_silence_deadline is None`, captura **uma vez** `_silence_deadline = min(_overall_deadline, _now() + _budget.silence_s)` (nunca renovado por chunk parcial sem `\n`). Se `_now() >= _silence_deadline`, marca `_retained = True`, `_phase = BridgePhase.HELD` e levanta `BridgeRefusal(BridgeFault.SILENCE)`. Caso contrário, chama `_poll_and_harvest(watched, _silence_deadline)` e repete 5.3.

### 5.4 Primeiro `fault` pegajoso e handler de `BaseException` sem callbacks novos (`R6`, `R7.1`)

- `_fault` é pegajoso: definido apenas se ainda `None`. `HostRefusal(cat)` define `_reactor_refusal = cat`, `_set_fault(BridgeFault.REACTOR_REFUSAL)`, `_retained = True`, `_phase = BridgePhase.REFUSED` e levanta `BridgeRefusal(BridgeFault.REACTOR_REFUSAL, cat) from None`.
- Se um `BaseException` de controle (`not isinstance(exc, Exception)`) ocorrer: o handler **não faz nenhum callback novo** (não chama `done()`, `outcome()` nem `clock.now()`); apenas adota `outcome_cached.process` se já estiver em cache no slot `"spawn"`, marca `_set_fault(BridgeFault.CONTROL)`, `_retained = True`, `_phase = BridgePhase.HELD` e relança a **mesma instância** `exc`.

## 6. Oráculos dos primeiros testes (`tests/test_oracle9_w1_duplex_bridge.py`, RED-first)

O próximo incremento após revisão desta v3 pelo root é **somente** `tests/test_oracle9_w1_duplex_bridge.py` em estado RED (`docs/poc/oracle9_w1_duplex_bridge.py` ausente), testando exclusivamente a API pública e a identidade dos objetos com portas falsas síncronas.

| Grupo | Oráculo obrigatório nos primeiros testes (sem SO, loop nativo, socket, thread ou subprocesso) |
|---|---|
| `D1` | **Binding do reator, DTOs/repr redigidos e colheita única (`R1`, `R4`, `R7.1`, `R7.4`):** recusas `REACTOR` (incluindo contadores `!= 0` ou `verdicts != (NOT_RUN,)*25`), `BUDGET` e `PORT`; `attempt_consumed=True` antes do primeiro `clock.now()`; `slot.bind` antes de efeito; `done()`/`outcome()` chamados uma única vez; `status()` puro sem chamar portas/relógio; adoção de `process` mesmo em `SpawnOutcome(ok=False, process=proc)`; `repr` redigido em todos os DTOs sem invocar `repr` de objetos arbitrários; segunda chamada a `run()` recusa `REENTRY` |
| `D2` | **Caminho feliz completo e serialização FIFO de timestamps:** `54` linhas, `50` controles e `58` saídas `Send`/`Act` até `COMPLETE_CANDIDATE` sobre o `HostReactor` real (`e86f8e32`); bytes de `stdout` lidos durante `write` ou `act` entram em `_line_queue` sem timestamp; recibo (`Delivered`/`ActDone`) entregue primeiro, seguido das linhas com timestamps pós-observação não decrescentes do owner |
| `D3` | **Escritas/ações incertas, quarentena de slot e validação de `ActOutcome` (`R6`, `R7.1`, `R7.4`):** `NOT_SENT` exige `bytes_written == 0`; `UNKNOWN` ou prazo vencido mantém `op` e `outcome` em cache no slot original (`occupied=True`), nunca reobservado em `watched` nem gerando segundo recibo; `ActOutcome` inválido ou recusado por `RECEIPT` no reator preserva slot ocupado e `retained=True`; falha de ação invalida `RESULT PASS` anterior em `21`/`24` |
| `D4` | **Política única de `stdout`, teto 57 e `EOF` parcial (`R3`):** `read_size = min(4096, remaining + 1)`; linha de `513` B sem concatenação grande; 57ª linha entregue ao reator recusa `LINE` antes de `ORDER`; 58ª linha ou byte `28673` falha fechado com `STDOUT_LIMIT` e `HELD`; `EOF` com bytes sem `\n` marca `trailing_partial=True` e recusa `LINE` |
| `D5` | **Algoritmo `Wait`/`EOF`/`Exited`, pré-cheque de `EOF`/saída e prazos (`R5`, `R7.2`–`R7.4`):** `poll` sem progresso recusa `PORT`; `_overall_deadline` sempre recusa `OVERALL_DEADLINE` antes de qualquer avanço do reator; `_silence_deadline` e `_drain_deadline` capturados uma vez sem rebase; `wait` `EXITED` aguarda `EOF` até `_drain_deadline` e usa `eof` real; `wait` pendente no fim do dreno gera `ExitStatus.UNKNOWN` (e `NO_EXIT` só com prova positiva da porta); `EOF`/saída em cache antes de iniciar novo `Send`/`Act` entrega `Exited` e transforma `pending` em `orphan` (exceto `ZERO_BACKENDS(25)`, que executa após `Exited`) |
| `D6` | **Ordenação de `T6`, primeiro `fault`/`BaseException` sem callbacks e estáticos AST (`R2`, `R6`, `R7.1`):** `ActDone(KILL_GATEWAY)` entregue antes de `Exited`; `fence` por `Delivered.pre` do `GO{25}` sem extensão; primeiro `KeyboardInterrupt`/`SystemExit` não invoca novos callbacks, preserva slots/`_process` já em cache e relança a mesma instância; ausência de APIs de cleanup (`quiesce`/`close`/`BridgeQuiesced`/`BridgeAbsent`) e AST sem `os`/`subprocess`/`socket`/`threading`/`asyncio`/`w1_bootstrap_channel` |

## 7. Próximo incremento e gates abertos

- **Próximo passo único após revisão desta v3 pelo root:** criar apenas `tests/test_oracle9_w1_duplex_bridge.py` e medir o RED congelado antes de implementar `docs/poc/oracle9_w1_duplex_bridge.py`.
- **`NOT_PREPARED`:** contrato separado de cleanup/quiescência/ausência por CID, adaptador nativo Windows Proactor, pins de CLI/Desktop/stdlib/relógio, raiz, task, nonce, estado operacional, rede, PG16 e credenciais.
- **Gates nativos e de produto abertos (`BLOCK_NATIVE` / produto):** `T5` físico, `T2`/`T4`/`T6` nativos no Oracle Linux 9.8 (`621cc7f7`) com PG16 isolado, `B-1`, `B-2`, `D-090` gate 2, `C1`/`D-119`, TLS upstream, patches e ingressos `PGWire`/`MCP`/`Admin`/`IDE`. Gateway indisponível; SQL `PGWire` recusada.
