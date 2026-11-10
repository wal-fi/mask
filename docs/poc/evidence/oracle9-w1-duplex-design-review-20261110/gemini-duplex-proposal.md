# W1 Oracle — ponte duplex mínima do host e portas injetadas (v1)

2026-11-10. Proposta somente documental e read-only (`MASKGW-DUPLEX-PUBLIC-DESIGN-20261110-V1`), sob a delegação vigente do usuário. Elaborada por Gemini 4 Argon (High), esforço high — **não** por Claude2. O usuário autorizou expressamente o fallback ao Gemini com os pacotes públicos necessários quando a quota do Claude2 (`sessão 51ea0d85`, `claude-opus-5-5`, esforço medium) parou com erro 429 na CLI 65449 antes de qualquer edição (reset informado para 19h30 São Paulo / 22h30 UTC de 2026-11-10, não observado). O root recuperou a sessão antes de edições, com zero escritor ativo concorrente. Este documento não reivindica autoria do Claude, aprovação individual do usuário nem prova nativa.

Base pública: código `7ecf056`, checkpoint documental `cad2edf`. Nada foi executado, gerado ou modificado para redigir este desenho: nenhum teste, comando, processo, socket, thread, loop de eventos, guard, sinal, Docker, PostgreSQL, SQL, raiz operacional, nonce, credencial ou estado. Os resultados históricos (`1215` testes relacionados, `366` próprios e `18` sondas independentes verdes) não foram repetidos nesta leitura e não fecham nenhum gate nativo ou de produto.

## 1. Escopo, insumos imutáveis e precedência documental

O **único** objeto deste desenho é a ponte duplex mínima e específica do host (`docs/poc/oracle9_w1_duplex_bridge.py`) que conduz o `HostReactor` puro já validado, conectando-o por portas injetadas a um único processo futuro de CLI do container gateway e ao executor fechado das seis ações do host.

| Insumo público | Pin / Identidade | Papel neste desenho |
|---|---|---|
| `docs/poc/oracle9_w1_host_reactor.py` | `e86f8e325410a26efeb47de1c4e349e9099673de612c028eb30e01ceea5d91ae` (38610 B / 1104 linhas) | Único decisor de protocolo, sequência, veredictos e cerca de `T6`; **imutável** |
| `tests/test_oracle9_w1_host_reactor.py` | `f177102a1ea55e9c6a32d1fcd863f18a2c04800588bddeeab8ee0eb192816613` (77736 B / 2144 linhas) | Oráculo congelado `H1`–`H17` + `R1` do reator; **imutável** |
| `deploy/oracle9_w1_main.py` | `89c99c65` (46787 B) | `HostLink` (`<= 512` B com `LF`, `56` linhas), códigos `64`–`70` e `HOLD`; **imutável** |
| `deploy/oracle9_w1_driver.py` | `b54a8a94` (51913 B) | Eventos canônicos, fases/razões de `ABORT`, `load_pure`; **imutável** |
| `deploy/oracle9_w1_controller.py` | `4c155d76` (22453 B) | `decode_init`, `decode_control`, `ControlMachine`, constantes; **imutável** |
| `docs/poc/oracle9_w1_expect.py` | `ce6ff389` (22114 B) | Construtor do pacote `LAB_INIT`; não importado pela ponte; **imutável** |

**Regras de fronteira e precedência:**
- `HOST-TEST-REVIEW` e `HOST-SOURCE-REVIEW` prevalecem sobre qualquer ambiguidade anterior do `HOST-DESIGN` (`aed85ad4`).
- O limite antigo de `256` linhas mencionado no `NATIVE-PLAN` v4 está **superado** pelo contrato implementado em `e86f8e32`: no máximo `56` linhas no protocolo (`54` normais + `2` para `ABORT`/`TERMINAL`) e até `512` bytes por linha incluindo o `LF` final (`\n`), preservada a exceção explícita da 57ª linha recusada com `HostRefusal("LINE")` antes de `ORDER` ou parse.
- `w1_bootstrap_channel.py` (`ManagedBootstrap`) é **apenas referência conceitual histórica** (uso único, retenção de tasks/handles, `Delivery`, `Quiesced` e `Absent`). É **proibido importá-lo**: seu wire de frame único + trailer, linha `READY`, limite de `32768` bytes acumulados e pins fixos no topo são incompatíveis.
- A ponte **não** reimplementa `ControlMachine`, não recalcula `next_seq`, veredictos ou `fence` de `T6`, não cria camada genérica de SO/processos, não cria novo sistema de proveniência e não é o programa coordenador completo do host.
- Os `124` insumos do pacote (`123` caminhos + `pyproject.toml`), o `source20`/`estado16` e a tentativa consumida `3f12dc584c29` (`FAILED_ONLY_OPERATOR_ABORT`) permanecem fixos e intocados.

## 2. Reuso estrito do `HostReactor` e separação de responsabilidades

A ponte importa e reutiliza diretamente do módulo `docs/poc/oracle9_w1_host_reactor.py` os tipos revisados, sem duplicá-los nem envolvê-los em espelhos paralelos:

- **Carriers de entrada para `reactor.feed(item)`:** `Line(raw, at)`, `Delivered(token, delivery, pre, post)`, `ActDone(token, kind, status, facts, at)`, `Exited(at, status, code, eof, reaped)`.
- **Facts fechados por `ActKind`:** `TerminateFacts`, `PauseFacts`, `RestoreFacts`, `ObserveFacts`, `ZeroFacts`, `KillFacts`.
- **Saídas de decisão de `reactor.feed(item)`:** `Send(token, purpose, payload, issued_at, deadline)`, `Act(token, kind, case, issued_at, deadline)`, `Wait()`, `Done(outcome, verdicts, controller_retained, orphan)`.
- **Vista e exceção:** `HostStatus`, `HostPolicy`, `HostRefusal` e os enums fechados `Delivery`, `ActStatus`, `ExitStatus`, `Purpose`, `Verdict`, `Outcome`, `HostPhase`, `ActKind`.

**Invariantes de divisão entre reator e ponte:**
1. O `HostReactor` decide **qual** efeito (`Send` ou `Act`) deve ocorrer, seu `token` e seu `deadline` absoluto, ou quando aguardar (`Wait`) ou concluir o modelo (`Done`).
2. A ponte executa no máximo o único `Send` ou `Act` pendente por vez através das portas injetadas, drena o `stdout` concorrentemente em fila FIFO finita de bytes brutos sem bloqueio de pipe, serializa os timestamps monotônicos do owner e alimenta `reactor.feed(...)`.
3. `Done` (inclusive `Outcome.COMPLETE_CANDIDATE`) é apenas candidato de protocolo para auditoria futura: **nunca** autoriza limpeza física, descarte de referências retidas, `kill` implícito ou marcação de recursos como fechados.

## 3. Semânticas verificadas do Python 3.11 vs. garantias das portas

Conforme verificado pelo root na documentação oficial do Python 3.11 (3.11.18), nenhuma primitiva de `asyncio`/stdlib isolada atesta limites de kernel ou término físico:

| Semântica oficial Python 3.11 | Risco na ponte | Regra obrigatória do desenho |
|---|---|---|
| `Process.wait()` pode travar com pipes cheios | Deadlock se o container escrever no `stdout`/`stderr` enquanto o host espera escrita, ação ou saída | `stderr=DEVNULL` obrigatório; task leitora de `stdout` drena continuamente (inclusive em modo de descarte após overflow) enquanto `writer`, `act` ou `wait` aguardam |
| `Process.communicate()` acumula na memória; `limit` de `StreamReader` não é teto global | Exaustão de memória por linha sem `LF` ou flood contínuo | `communicate()` e `readline()` ilimitados são proibidos; leitura em blocos `<= 4096` B com tetos verificados **durante** a leitura (`513` B por linha, `57` linhas na fila, `32768` B totais) |
| `asyncio.wait_for()` aguarda o cancelamento da task e pode exceder o timeout | Bloqueio além do `deadline` se a corrotina/SO ignorar cancelamento | Proibido depender do término de cancelamento para cumprir prazo; a ponte aguarda até o prazo em task monitorada, retém a referência viva se não concluir e emite recibo `UNKNOWN` |
| Event loop guarda apenas referência fraca de tasks | Task coletada pelo GC em meio a I/O ou espera | O owner registra referência forte em `self._tasks[name]` **antes** de qualquer `await` e nunca remove entrada de task não concluída |
| `StreamWriter.drain()` é apenas controle de fluxo local | Confundir retorno de `drain()` com recebimento pelo PID 1 no container | `Delivery.SENT` significa exclusivamente que o pipe local da CLI aceitou todos os bytes dentro do prazo |
| `is_closing()` não prova handle fechado; `wait_closed()` pode tentar flush pendente | Falso positivo de limpeza ou bloqueio ao fechar `stdin` antes da morte do processo | Nunca usar `is_closing()` como prova; nunca fechar `stdin` para forçar término antes de `kill`/reap; `BridgeQuiesced` exige reap + confirmação explícita de pipes fechados pela porta |

Quando o SO, o loop ou a CLI não cooperam até o prazo, a ponte **não** fabrica sucesso nem força desligamento cego: marca `_retained = True`, transita para `BridgePhase.HELD` e preserva todas as referências para inspeção e limpeza externa.

## 4. API prospectiva, DTOs fechados, erros e slots de ownership

Módulo proposto: `docs/poc/oracle9_w1_duplex_bridge.py` (somente definições; sem efeitos no import, sem leitura de ambiente/arquivos/relógio global e sem import de `subprocess`/`os`/`socket`/`threading`/`w1_bootstrap_channel`).

### 4.1 Enums, exceção fechada e DTOs imutáveis

Todos os DTOs usam `@dataclass(frozen=True, slots=True)`. Qualquer DTO que possa conter bytes ou referências sensíveis implementa `__repr__` redigido. Os carriers (`DuplexBudget`, `ActResult`, `WaitOutcome`, `BridgeQuiesced`, `BridgeAbsent`) não levantam exceção no construtor; toda validação ocorre nos métodos da ponte.

```python
class BridgePhase(enum.Enum):
    NEW = "NEW"
    STARTING = "STARTING"
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    QUIESCING = "QUIESCING"
    QUIESCED = "QUIESCED"
    HELD = "HELD"
    CLOSED = "CLOSED"
    REFUSED = "REFUSED"

class BridgeFault(enum.Enum):
    BUDGET = "BUDGET"
    PORT = "PORT"
    REENTRY = "REENTRY"
    SPAWN = "SPAWN"
    WRITE = "WRITE"
    READ = "READ"
    STDOUT_LIMIT = "STDOUT_LIMIT"
    ACTION = "ACTION"
    SILENCE = "SILENCE"
    OVERALL_DEADLINE = "OVERALL_DEADLINE"
    EXIT = "EXIT"
    REACTOR_REFUSAL = "REACTOR_REFUSAL"
    CONTROL = "CONTROL"
    HELD = "HELD"

class BridgeRefusal(Exception):
    """Exceção fechada: apenas BridgeFault; sem causa, contexto, cadeia ou valor bruto."""
    def __init__(self, category: BridgeFault, reactor_refusal: str | None = None) -> None: ...
```

```python
@dataclass(frozen=True, slots=True)
class DuplexBudget:
    spawn_s: float        # 0 < spawn_s <= 30.0
    silence_s: float      # 0 < silence_s <= 60.0
    drain_s: float        # 0 < drain_s <= 30.0
    overall_s: float      # max(spawn_s, silence_s, drain_s) < overall_s <= 300.0
    quiesce_s: float      # 0 < quiesce_s <= 30.0

@dataclass(frozen=True, slots=True)
class BridgeQuiesced:
    target_id: str        # identificador opaco não vazio (ex.: CID na futura ligação nativa)
    nonce: str            # 32 hex minúsculos injetados pela porta de ticket/clock
    issued_at: float      # instante monotônico finito >= 0 após coleta de todos os recursos CLI

@dataclass(frozen=True, slots=True)
class BridgeAbsent:
    ticket: BridgeQuiesced
    observed_at: float    # instante monotônico finito >= ticket.issued_at

@dataclass(frozen=True, slots=True)
class BridgeStatus:
    phase: BridgePhase
    fault: BridgeFault | None
    reactor_refusal: str | None
    reactor_status: HostStatus
    attempt_consumed: bool
    retained: bool
    total_stdout_bytes: int
    queued_lines: int
    overflow: bool
    trailing_partial: bool
    stdout_eof: bool
    stdin_closed: bool
    reaped: bool
    exit_code: int | None
    active_tasks: tuple[str, ...]
    ticket: BridgeQuiesced | None
    released: bool

@dataclass(frozen=True, slots=True)
class BridgeRunResult:
    done: Done
    status: BridgeStatus
```

**Regras de `DuplexBudget`:**
- Todos os cinco campos devem ser `int` ou `float` exatos (`type(v) in (int, float)`, `bool` e subclasses recusados), finitos (`math.isfinite` protegido contra `OverflowError` como em `_finite_or_none`) e dentro dos intervalos acima; violação no construtor de `DuplexBridge` levanta `BridgeRefusal(BridgeFault.BUDGET)` antes de criar instância.
- **Proibição de extensão oculta de prazo:** `DuplexBudget` governa apenas `spawn`, silêncio de `stdout` em `Wait`, dreno terminal (`drain_s`), teto global da rodada (`overall_s`) e `quiesce_s`. Todo `Send` usa exclusivamente `min(send.deadline, overall_deadline)` e todo `Act` usa exclusivamente `min(act.deadline, overall_deadline)`. A cerca `fence` de `Act(KILL_GATEWAY, 25)` **jamais** é estendida por `drain_s`, `silence_s` ou `quiesce_s`.

### 4.2 Portas confiáveis injetadas

A ponte não conhece `docker.exe`, SQL, DSN, `asyncio.create_subprocess_exec` nem `time.monotonic`. Recebe quatro portas explícitas verificadas por forma (`callable` dos métodos exigidos; falha levanta `BridgeRefusal(BridgeFault.PORT)` no construtor):

1. **`ClockPort`:**
   - `now() -> float`: devolve instante monotônico `int | float` exato, finito e `>= 0`. Se devolver tipo inválido, `NaN`/`inf` ou regredir em relação à última leitura do próprio owner, a ponte recusa com `BridgeRefusal(BridgeFault.PORT)` e marca `_retained = True`.
   - `await sleep_until(deadline: float, wake: WakeEvent) -> None`: suspende cooperativamente até `deadline` ou até que `wake` sinalize conclusão de task monitorada (leitor, escritor, ação ou saída do processo), sem loop ocupado infinito.
2. **`GatewayPort` e `GatewayProcess`:**
   - `spawn(deadline: float) -> TaskHandle[GatewayProcess]`: inicia a criação de **um único** processo gateway (`stdin=PIPE`, `stdout=PIPE`, `stderr=DEVNULL`).
   - `GatewayProcess` expõe:
     - `target_id: str` (identificador imutável do alvo associado ao processo);
     - `read_stdout(max_bytes: int) -> TaskHandle[bytes]`: lê até `max_bytes` (`1 <= max_bytes <= 4096`); `b""` significa `EOF` genuíno do pipe `stdout`;
     - `write_stdin(payload: bytes) -> TaskHandle[int]`: inicia escrita + `drain` local de `payload`; antes do primeiro byte, a ponte já marcou entrega em curso (`UNKNOWN`); se falhar provadamente antes de tocar o pipe (0 bytes), levanta ou retorna `0` como `NOT_SENT`;
     - `close_stdin() -> TaskHandle[bool]`: fecha `stdin` apenas em `quiesce()` após término do processo;
     - `wait_exit() -> TaskHandle[int]`: aguarda reap do processo e devolve `returncode` (`int` exato `0..255`);
     - `kill_process() -> None`: mata o processo local da CLI em `quiesce()` (o kill do container de `T6` pertence a `ActPort`);
     - `pipes_closed() -> bool`: prova positiva da porta de que os handles de `stdin` e `stdout` foram fechados após reap;
     - `issue_ticket(issued_at: float) -> BridgeQuiesced`: emite o ticket único após confirmação de quiescência.
3. **`ActPort`:**
   - `execute(act: Act) -> TaskHandle[ActResult]` onde `ActResult(status: ActStatus, facts: ActFacts | None)`.
   - Aceita **somente** os seis `ActKind` existentes (`TERMINATE_ONE_BACKEND`, `PAUSE_PG`, `RESTORE_PG`, `OBSERVE_HEAVY`, `ZERO_BACKENDS`, `KILL_GATEWAY`). Não possui parâmetro de comando nem de SQL.
   - Os `facts` só podem ser preenchidos (`ActStatus.OK`) após o efeito completo dentro do prazo.
4. **`TaskHandle[T]`:**
   - Representa uma operação assíncrona já agendada e retida fortemente: `done() -> bool`, `result() -> T`, `exception() -> BaseException | None`, `cancel() -> None`.

### 4.3 Classe `DuplexBridge` e reserva de slots antes de efeitos

```python
class DuplexBridge:
    def __init__(
        self,
        reactor: HostReactor,
        clock: ClockPort,
        gateway: GatewayPort,
        acts: ActPort,
        budget: DuplexBudget,
    ) -> None: ...

    def status(self) -> BridgeStatus: ...
    async def run(self) -> BridgeRunResult: ...
    async def quiesce(self) -> BridgeQuiesced | None: ...
    async def close(self, absent: BridgeAbsent | None = None) -> bool: ...
    def assert_released(self) -> None: ...
```

**Slots de ownership alocados no `__init__` (antes de qualquer efeito):**
- `_reactor`, `_clock`, `_gateway`, `_acts`, `_budget`;
- `_phase = BridgePhase.NEW`, `_fault: BridgeFault | None = None`, `_reactor_refusal: str | None = None`;
- `_attempt_consumed = False`, `_busy = False`, `_retained = False`, `_released = False`;
- `_process: GatewayProcess | None = None`, `_ticket: BridgeQuiesced | None = None`;
- `_tasks: dict[str, TaskHandle[object]] = {}` (chaves fixas: `"spawn"`, `"reader"`, `"writer"`, `"act"`, `"wait"`, `"stdin_close"` e tasks órfãs retidas `"writer_orphan_<token>"` / `"act_orphan_<token>"`);
- `_line_queue: collections.deque[bytes]` (capacidade lógica máxima `57` entradas, contendo **apenas** `raw: bytes`, sem timestamp);
- `_partial_buf: bytearray` (teto `513` bytes);
- `_total_stdout_bytes = 0`, `_overflow = False`, `_trailing_partial = False`;
- `_stdout_eof = False`, `_stdin_closed = False`, `_reaped = False`, `_exit_code: int | None = None`;
- `_last_clock: float | None = None`, `_overall_deadline: float = 0.0`, `_control_exc: BaseException | None = None`.

**Regras de reserva e tentativa única:**
1. Em `run()`, **antes** de chamar `gateway.spawn(...)`, a ponte verifica `_busy is False`, `_phase is BridgePhase.NEW` e `_attempt_consumed is False` (caso contrário levanta `BridgeRefusal(BridgeFault.REENTRY)` sem tocar nos slots existentes), lê `t0 = _now()`, fixa `_attempt_consumed = True`, `_overall_deadline = t0 + _budget.overall_s`, `_phase = BridgePhase.STARTING` e registra a task retornada em `self._tasks["spawn"]`.
2. Se qualquer falha ou `BaseException` ocorrer durante ou após `gateway.spawn(...)`, `_attempt_consumed` permanece `True`, `self._tasks["spawn"]` e `self._process` (se adotado) permanecem retidos, `_retained = True` e `_phase` vai para `HELD` (ou `REFUSED` com `_retained = True`).
3. Uma instância de `DuplexBridge` **nunca** executa segunda tentativa de `spawn` ou `run()`.

## 5. Escrita limitada (`Send`), leitura incremental (`stdout`) e política de overflow

### 5.1 Escritas de prazo absoluto (`Send`) e semântica de `Delivery`

Quando `HostReactor` devolve `Send(token, purpose, payload, issued_at, deadline)`:
1. A ponte verifica o domínio de `payload` antes de tocar na porta:
   - `Purpose.INIT`: `type(payload) is bytes` e `8 < len(payload) <= 65544`;
   - `Purpose.GO | STOP | NOSTOP | ACK`: `type(payload) is bytes` e `len(payload) == 16`, com total de frames de controle enviados `< 50`.
   - Violação levanta `BridgeRefusal(BridgeFault.WRITE)` com `_retained = True`.
2. **Captura de `pre` e classificação `NOT_SENT` vs. `UNKNOWN` vs. `SENT`:**
   - O owner lê `pre = _now()` (garantindo `pre >= issued_at` e `pre >= reactor.status().last_at`).
   - Se `_reaped` já é verdadeiro ou a porta informa indisponibilidade imediata antes de enfileirar qualquer byte (`0` bytes tocados), o owner lê `post = _now()` e alimenta `Delivered(token, Delivery.NOT_SENT, pre, post)`.
   - Caso contrário, o estado de entrega da operação passa imediatamente a `Delivery.UNKNOWN` **antes** do primeiro byte, a task `process.write_stdin(payload)` é registrada em `self._tasks["writer"]` e aguardada até `eff_deadline = min(send.deadline, _overall_deadline)` enquanto o leitor de `stdout` continua drenando.
   - Se a task concluir antes ou no prazo com todos os `len(payload)` bytes entregues ao pipe local da CLI e sem queda do pipe: o owner lê `post = _now()` e alimenta `Delivered(token, Delivery.SENT, pre, post)`. (Se `post >= send.deadline`, o próprio `HostReactor` classifica como entrega tardia e entra em `DRAINING`).
   - Se a task levantar exceção após início, escrever menos que `len(payload)` bytes, ou continuar viva em `eff_deadline`:
     - Se viva, a referência é preservada em `self._tasks[f"writer_orphan_{token}"]` (nunca descartada nem aguardada sem limite por cancelamento);
     - `_retained = True`;
     - O owner lê `post = _now()` e alimenta `Delivered(token, Delivery.UNKNOWN, pre, post)` — **sem retry e sem rebase de `seq` ou `deadline`**.

### 5.2 Leitura incremental de `stdout`, limites durante leitura e descarte limitado

Constantes fixas de leitura da ponte:
- `_READ_CHUNK: Final = 4096` bytes por chamada `read_stdout`;
- `_LINE_CAP: Final = 512` bytes incluindo `LF`; `_SLICE_CAP: Final = 513` bytes (`_LINE_CAP + 1`);
- `_QUEUE_LINE_CAP: Final = 57` entradas (`56` linhas válidas + `1` slot para a 57ª linha de recusa `LINE`);
- `_MAX_TOTAL_STDOUT: Final = 32768` bytes totais lidos do `stdout` na rodada (`<= 56 * 512 = 28672` B de protocolo + margem finita de diagnóstico).

**Regras do pump leitor (`_pump_stdout`):**
1. O leitor roda concorrentemente desde a adoção do processo em `STARTING` até `EOF` (`b""`), erro de leitura ou encerramento em `quiesce()`, impedindo bloqueio de pipe enquanto `writer`, `act` ou `wait_exit` aguardam.
2. A cada bloco `chunk` (`1..4096` bytes):
   - Atualiza `_total_stdout_bytes += len(chunk)`. Se `_total_stdout_bytes > _MAX_TOTAL_STDOUT`, marca `_overflow = True`, `_retained = True` e `_fault = BridgeFault.STDOUT_LIMIT` (se ainda `None`).
   - **Enquanto não está em modo de descarte (`not _overflow`):** percorre `chunk` procurando `b"\n"`:
     - Se encontrar `b"\n"`, extrai o segmento até `b"\n"` inclusive. Se `len(_partial_buf) + len(seg) <= _LINE_CAP`, completa a linha `raw = bytes(_partial_buf) + seg`, limpa `_partial_buf` e enfileira `raw` em `_line_queue`. Se `len(_partial_buf) + len(seg) > _LINE_CAP`, monta uma única amostra truncada de `513` bytes (`bytes((_partial_buf + seg)[:513])`), limpa `_partial_buf`, enfileira essa amostra (para que `HostReactor.feed` exerça a recusa exata `LINE` ou `ORDER`) e ativa `_overflow = True`, `_retained = True`.
     - Se não houver `b"\n"` no restante do `chunk`, acrescenta a `_partial_buf` apenas até atingir `_SLICE_CAP` (`513` bytes). Ao atingir `513` bytes sem `b"\n"`, enfileira imediatamente os `513` bytes em `_line_queue`, limpa `_partial_buf` e ativa `_overflow = True`, `_retained = True`.
     - Se `len(_line_queue)` atingir `_QUEUE_LINE_CAP` (`57` linhas), qualquer byte adicional após a 57ª linha ativa `_overflow = True`, `_retained = True`.
   - **Em modo de descarte (`_overflow is True`):** `_partial_buf` permanece vazio e os blocos lidos são descartados imediatamente sem alocação cumulativa, até `_total_stdout_bytes` atingir `_MAX_TOTAL_STDOUT` (ponto em que o leitor para e a ponte transita para falha fechada `STDOUT_LIMIT` com `_retained = True`) ou até `EOF`.
3. **Classificação de `EOF` e linha parcial final (`trailing_partial`):**
   - Quando `read_stdout` devolve `b""`, o leitor marca `_stdout_eof = True`.
   - Se `len(_partial_buf) > 0` no `EOF` (bytes finais sem `\n`), marca `_trailing_partial = True`, `_retained = True` e enfileira `bytes(_partial_buf)` (sem `\n`) em `_line_queue` antes de encerrar a task leitora. Assim, uma linha parcial final **jamais** é descartada como sucesso: ao ser entregue ao `HostReactor`, é recusada como `LINE` (ou `ORDER` se havia pendência).

## 6. Serialização crítica de timestamps do owner e ordenação de `T6`

### 6.1 Invariante de serialização sem modificar o `HostReactor`

O `HostReactor` exige tempos monotônicos não decrescentes (`moment >= last_at`) em todas as chamadas de `feed`, exige `Delivered.pre >= Send.issued_at` e `Delivered.post >= Delivered.pre`, e recusa qualquer `Line` não terminal enquanto `self._pending is not None` (`ORDER`).

Para cumprir esse contrato sem alterar uma única linha de `e86f8e32` e sem retrodatar recibos:

1. **A fila `_line_queue` armazena apenas `raw: bytes`:** o pump leitor **nunca** lê o relógio para carimbar linhas ao recebê-las do pipe.
2. **Recibo do efeito pendente SEMPRE precede linhas ou `Exited` enfileirados:**
   - Quando `reactor.feed(...)` devolve `Send` ou `Act`, a ponte executa esse único efeito até a conclusão ou até o seu `deadline`.
   - Enquanto `Send` ou `Act` está em execução na porta, o pump leitor drena o `stdout` para `_line_queue` e `wait_exit` observa o processo em background, mas o owner **não** desenfileira nenhuma `Line` nem alimenta `Exited` no `HostReactor`.
   - Assim que `Send` ou `Act` termina (ou atinge o `deadline` virando `UNKNOWN`), o owner alimenta **primeiro** `Delivered(token, delivery, pre, post)` ou `ActDone(token, kind, status, facts, at)` em `reactor.feed(...)`.
   - Como nenhuma `Line` ou `Exited` foi alimentada entre a emissão do `Send` (`issued_at`) e a entrega do `Delivered`, `Delivered.pre` (capturado imediatamente antes da escrita) satisfaz `issued_at <= pre <= post` sem jamais regredir em relação a observações intermediárias e sem jamais precisar de retrodatação.
3. **Timestamps pós-observação do owner ao desenfileirar `_line_queue`:**
   - Somente quando `reactor.status().pending is None` o owner retira o próximo `raw` da frente de `_line_queue`, lê `at = _now()` (que é garantidamente `>= reactor.status().last_at`, inclusive `>= Delivered.post` ou `>= ActDone.at` recém-entregues) e chama `reactor.feed(Line(raw=raw, at=at))`.
   - Se `reactor.feed(Line(...))` devolver novo `Send` ou `Act` (cujo `issued_at` será esse `at`), o owner passa imediatamente a executar esse `Send` ou `Act` e entrega seu recibo antes de desenfileirar a próxima linha de `_line_queue`.

### 6.2 Ordenação de `T6` (`KILL_GATEWAY` → `Exited` → `ZERO_BACKENDS`)

1. No caso `25`, o `Delivered.pre` real da escrita de `Send(GO, 25)` fica registrado no `HostReactor` como `t_go_pre`.
2. Ao alimentar `Line(ARMED{25})`, o `HostReactor` calcula `fence = t_go_pre + (live_window_ms / 1000) * (1 - t6_epsilon) - t6_margin_s`:
   - Se `fence - at < t6_kill_min_s`, o reator devolve imediatamente `Done(Outcome.T6_FAILED, ...)`. A ponte **não** emite `KILL_GATEWAY` substituto dentro do passo do protocolo; marca `_retained = True` e retorna o `BridgeRunResult` (restando `quiesce()`/limpeza externa).
   - Caso contrário, o reator devolve `Act(token, ActKind.KILL_GATEWAY, case=25, issued_at=at, deadline=fence)`.
3. A ponte executa `Act(KILL_GATEWAY, 25)` na `ActPort` com prazo estrito `min(fence, _overall_deadline)`.
4. **Regra de precedência do recibo de kill:** mesmo que o processo CLI encerre e `_reaped` / `_stdout_eof` ocorram enquanto `ActPort.execute(KILL_GATEWAY)` ainda está retornando, o owner alimenta **obrigatoriamente primeiro** `ActDone(token, ActKind.KILL_GATEWAY, status, facts, at)` no `HostReactor`.
5. Após `ActDone(KILL_GATEWAY)` (que devolve `Wait()`), o owner entra na coleta terminal limitada por `drain_deadline = min(_overall_deadline, _now() + _budget.drain_s)`:
   - Drena quaisquer linhas remanescentes em `_line_queue` com timestamps pós-observação (se o controlador emitiu `ABORT`/`TERMINAL` após `ARMED{25}`, o reator marca `T6` como `FAIL` e vai para `ENDING`).
   - Aguarda `_stdout_eof` e `wait_exit()` até `drain_deadline`.
   - Constrói e alimenta `Exited(at=_now(), status=..., code=..., eof=_stdout_eof, reaped=_reaped)`:
     - Somente se `ActDone(KILL_GATEWAY)` foi `OK` com `at < fence`, nenhuma linha veio após `ARMED{25}`, e `Exited` tem `status=ExitStatus.EXITED`, `code != 69`, `eof=True` e `reaped=True`, o `HostReactor` devolve `Act(token, ActKind.ZERO_BACKENDS, case=25, issued_at=exit_at, deadline=exit_at + policy.act_s)`.
     - A ponte executa `ZERO_BACKENDS` na `ActPort` até `min(act.deadline, _overall_deadline)` e alimenta `ActDone(ZERO_BACKENDS)`, recebendo `Done(Outcome.COMPLETE_CANDIDATE | Outcome.T6_FAILED, ...)`.

### 6.3 Limites de espera (`Wait`), dreno terminal, recusas e controles `BaseException`

Não existe laço `while Wait` ilimitado na ponte:
- **Espera em `AWAIT_GUARD`, `AWAIT_INIT_OK` ou `RUNNING` sem pendência (`Wait`):**
  - Se `_line_queue` não está vazia, o owner desenfileira a próxima linha imediatamente sem dormir.
  - Se `_line_queue` está vazia e não há `_stdout_eof` nem `_reaped`, o owner aguarda no máximo até `wait_deadline = min(_overall_deadline, _now() + _budget.silence_s)`.
  - Se `wait_deadline` vencer sem linha e sem saída do processo:
    - Se venceu `_overall_deadline` ou `_budget.silence_s` em fase ativa, a ponte interrompe a espera de linhas, marca `_retained = True`, alimenta `Exited(at=_now(), status=ExitStatus.NO_EXIT, code=None, eof=_stdout_eof, reaped=False)` no `HostReactor` — que devolve `Done(Outcome.RETAINED | Outcome.ENDED_UNKNOWN, controller_retained=True, ...)` — e coloca a ponte em `BridgePhase.HELD`.
- **Dreno em `HostPhase.DRAINING` ou `HostPhase.ENDING`:**
  - Quando uma entrega falha/atrasa ou uma ação falha/atrasa (`DRAINING`), ou quando chega `ABORT`/`TERMINAL` (`ENDING`), o owner aguarda linhas terminais e o término do processo limitados por `drain_deadline = min(_overall_deadline, _now() + _budget.drain_s)`.
  - Se o processo sair com `EOF` dentro de `drain_deadline`, o owner esvazia `_line_queue` (entregando eventuais linhas `ABORT`/`TERMINAL` com timestamps pós-observação) e entrega `Exited(at=_now(), status=ExitStatus.EXITED, code=_exit_code, eof=_stdout_eof, reaped=_reaped)`.
  - Se o processo permanecer vivo em `drain_deadline` (por exemplo, controlador em `HOLD` após `TERMINAL RETAINED` ou `ABORT` com `safe_exit=False`), marca `_retained = True` e entrega `Exited(at=_now(), status=ExitStatus.NO_EXIT, code=None, eof=_stdout_eof, reaped=False)`, produzindo `Done(Outcome.RETAINED | Outcome.ENDED_UNKNOWN, controller_retained=True, ...)`.
  - Se `wait_exit` falhar ou deixar estado incerto, marca `_retained = True` e entrega `Exited(..., status=ExitStatus.UNKNOWN, code=None, eof=_stdout_eof, reaped=False)`.
- **Recusas do `HostReactor` (`HostRefusal`):**
  - Qualquer `HostRefusal(cat)` levantada por `reactor.feed(...)` é capturada uma única vez na fronteira do passo, registra `_reactor_refusal = cat`, `_fault = BridgeFault.REACTOR_REFUSAL`, `_phase = BridgePhase.REFUSED` e `_retained = True` (preservando processo e tasks em `_tasks`), e levanta `BridgeRefusal(BridgeFault.REACTOR_REFUSAL, reactor_refusal=cat)` fora do handler (`from None`).
- **Preservação do primeiro `BaseException` de controle:**
  - Se `CancelledError`, `KeyboardInterrupt` ou `SystemExit` atingir a ponte durante qualquer `await` (spawn, leitura, escrita, ação, espera ou `quiesce`), o owner captura a exceção apenas para registrar `_control_exc = exc`, `_fault = BridgeFault.CONTROL`, `_retained = True` e `_phase = BridgePhase.HELD` (e se `writer` já havia iniciado, mantém entrega como `UNKNOWN`), **sem** limpar `_tasks`, **sem** descartar `_process` e **sem** iniciar novo I/O oculto no `finally`, relançando a mesma instância `exc` imediatamente.

## 7. Quiescência, ticket e liberação verificada (`quiesce` / `close` / `assert_released`)

Nenhum retorno de `run()` (nem `Done(COMPLETE_CANDIDATE)`) fecha a ponte. O ciclo de limpeza exige três passos explícitos:

1. **`await bridge.quiesce() -> BridgeQuiesced | None`:**
   - Se `_ticket` já existe, devolve `_ticket`.
   - Marca `_phase = BridgePhase.QUIESCING` e fixa `q_deadline = _now() + _budget.quiesce_s`.
   - Se `"spawn"` existe em `_tasks` e não concluiu, aguarda até `q_deadline`; se concluir, adota `_process`; se continuar viva em `q_deadline`, marca `_phase = BridgePhase.HELD`, `_retained = True` e devolve `None`.
   - Se `_process is not None`:
     - Enquanto `not _reaped` (em até 3 tentativas limitadas por `min(q_deadline, _now() + 0.25)` cada), chama `_process.kill_process()` e aguarda `wait_exit()`. Se continuar sem reap em `q_deadline`, marca `_phase = BridgePhase.HELD`, `_retained = True` e devolve `None`.
     - Só **depois** de `_reaped is True`, fecha `stdin` via `_process.close_stdin()` até `q_deadline`.
     - Cancela apenas tasks locais remanescentes cujo processo já morreu e aguarda que **todas** as entradas em `_tasks.values()` reportem `task.done() is True` até `q_deadline`.
     - Verifica `_process.pipes_closed() is True` e `(_stdout_eof or _process.pipes_closed())`.
   - Somente se `all(t.done() for t in _tasks.values())` e (nenhum processo foi alocado **ou** `(_reaped and _stdin_closed and _process.pipes_closed())`), emite `_ticket = _process.issue_ticket(_now())` (ou ticket de pré-spawn se `_process is None`), muda `_phase = BridgePhase.QUIESCED` e devolve `_ticket`. Caso contrário, permanece em `BridgePhase.HELD` e devolve `None`.
2. **`await bridge.close(absent: BridgeAbsent | None = None) -> bool`:**
   - Se `absent is None`, devolve `False`.
   - Exige `type(absent) is BridgeAbsent`, `_ticket is not None`, `absent.ticket is _ticket`, `absent.ticket.target_id == _ticket.target_id`, `absent.observed_at >= _ticket.issued_at` (finito) e `all(t.done() for t in _tasks.values())`; violação levanta `BridgeRefusal(BridgeFault.HELD)`.
   - Marca `_released = True`, `_phase = BridgePhase.CLOSED` e devolve `True`.
3. **`bridge.assert_released() -> None`:**
   - Exige `_phase is BridgePhase.CLOSED`, `_ticket is not None`, `_released is True`, `not _busy` e `all(t.done() for t in _tasks.values())`; caso contrário levanta `BridgeRefusal(BridgeFault.HELD)`.

## 8. Ligação futura ao Windows Proactor vs. portas falsas determinísticas

| Aspecto | Primeiro lote de testes (`tests/test_oracle9_w1_duplex_bridge.py`) | Ligação futura nativa Windows (`BLOCK_NATIVE`, fora deste lote) |
|---|---|---|
| Loop e relógio | `FakeClockPort` determinístico (floats diádicos exatos, avanço explícito em `sleep_until` sem esperar tempo real) | `asyncio.ProactorEventLoop` em CPython 3.11.3 Windows + camada de relógio pinada (`NOT_PREPARED`) |
| Processo e pipes | `FakeGatewayPort` / `FakeGatewayProcess` em memória (filas de chunks de `stdout`, simulação de escrita curta/bloqueada/EOF/exit, zero subprocesso real) | Único `docker.exe` pinado (`stdin=PIPE`, `stdout=PIPE`, `stderr=DEVNULL`, `creationflags=CREATE_NO_WINDOW`), `PipeHandle.handle is None` como prova de pipe fechado |
| Ações `ActKind` | `FakeActPort` determinístico por `(kind, case)` devolvendo `ActResult` ou retendo task viva até o prazo | Adaptador fechado que executa apenas as 6 ações por identidade/CID/SQL fixa do superuser, sem comando/SQL arbitrário (`NOT_PREPARED`) |
| Limpeza de container | `BridgeAbsent` sintético injetado pelo teste após `BridgeQuiesced` | Coordenador inspeciona CID próprio, mata se ativo, remove sem `--force` e confirma ausência por CID após `BridgeQuiesced.issued_at` |

Nenhum booleano devolvido por `FakeGatewayPort`, `FakeActPort` ou `BridgeAbsent` nos testes de unidade é apresentado como prova de kernel, de container Linux, de PostgreSQL 16 ou de limpeza física no host.

## 9. Oráculos dos primeiros testes (RED-first, somente portas falsas)

O próximo incremento após a revisão deste desenho pelo root será **exclusivamente** o arquivo de testes `tests/test_oracle9_w1_duplex_bridge.py` em estado RED (com `docs/poc/oracle9_w1_duplex_bridge.py` ainda ausente, carregado preguiçosamente dentro dos casos de teste para que a coleta passe as sanidades e falhe nos casos de feature). Zero socket, thread, processo, loop nativo, guard, sinal, Docker, PG ou SQL.

| Grupo | Oráculo obrigatório em `tests/test_oracle9_w1_duplex_bridge.py` |
|---|---|
| `D1` | **Transcript completo, fila FIFO e serialização de timestamps:** caminho feliz completo (`54` linhas, `50` frames de controle, `58` saídas `Send`/`Act`, `COMPLETE_CANDIDATE`) conduzindo o `HostReactor` real (`e86f8e32`); linhas de `stdout` que chegam enquanto `Send` ou `Act` está em voo ficam retidas em `_line_queue` como `bytes` brutos; o recibo (`Delivered`/`ActDone`) é entregue **primeiro** com `pre`/`post`/`at` reais sem retrodatação, e as linhas enfileiradas são entregues **depois** com timestamps pós-observação não decrescentes do owner |
| `D2` | **Escritas curtas, sem leitor, tardias e `NOT_SENT`:** falha antes do primeiro byte (`0` B) gera `Delivery.NOT_SENT` e `DRAINING`; escrita parcial, exceção após início ou task de escrita viva no `Send.deadline` gera `Delivery.UNKNOWN`, retém a task viva em `_tasks`, marca `retained=True` e entra em `DRAINING` sem retry nem rebase de `seq`/`deadline`; escrita completa com `post >= Send.deadline` entrega `Delivery.SENT` tardio e entra em `DRAINING` |
| `D3` | **Limites de flood no `stdout`, linha `> 512` B, 57ª linha e fronteiras de bloco:** linhas válidas fragmentadas em múltiplos chunks ou coladas no mesmo chunk `<= 4096` B; linha de `513` B sem `LF` truncada durante a leitura gera `HostRefusal("LINE")` (ou `ORDER` se pendente abaixo do teto) e ativa descarte limitado sem acumular memória; 57ª linha entregue ao reator dispara a exceção do teto (`LINE` antes de `ORDER`/parse); flood `> 32768` B continua drenando para não travar o pipe e fecha com `BridgeFault.STDOUT_LIMIT` e `retained=True` |
| `D4` | **`EOF` antecipado, `EOF` antes de escrita e linha parcial final (`trailing_partial`):** `EOF` sem nenhuma linha com códigos `64`/`65`/`66`/`67`/`70` produz o `Outcome` correspondente; código incoerente sem linha recusa `EXIT`; `EOF` com bytes finais sem `\n` marca `trailing_partial=True`, `retained=True` e entrega os bytes ao reator para recusa `LINE` (jamais descartado como sucesso); `EOF` antes/durante escrita de `Send` |
| `D5` | **Seis `ActKind` fechados, ações `UNKNOWN`/expiradas/falhas e facts incoerentes:** despacho exato dos 6 `ActKind` (`TERMINATE_ONE_BACKEND`, `PAUSE_PG`, `RESTORE_PG`, `OBSERVE_HEAVY`, `ZERO_BACKENDS`, `KILL_GATEWAY`); task de ação viva em `Act.deadline` vira `ActStatus.UNKNOWN` com task retida em `_tasks`, marca o caso `FAIL` (invalidando `RESULT PASS` anterior em `21`/`24`) e vai para `DRAINING` sem novo `Send`; facts incoerentes com `OK` geram `BridgeRefusal(REACTOR_REFUSAL)` com `"RECEIPT"` e `retained=True` |
| `D6` | **Fronteiras de partida, alocação e falha:** recusa de construtor (`BUDGET`, `PORT`) sem criar instância; falha/timeout em `spawn` antes e depois de alocar processo retém task `"spawn"` e `_process`, marca `attempt_consumed=True`, `retained=True` e `phase=HELD`; segunda chamada a `run()` na mesma instância recusa `BridgeFault.REENTRY` sem alterar slots ou pendências |
| `D7` | **Ordenação de `T6` e integridade da cerca `fence`:** `Delivered.pre` do `GO{25}` ancora `fence`; nenhum orçamento da ponte estende `Act(KILL_GATEWAY, 25).deadline`; `ActDone(KILL_GATEWAY)` é sempre entregue **antes** de coletar/entregar `Exited`, mesmo quando o processo termina durante o kill; orçamento `< t6_kill_min_s` devolve `Done(T6_FAILED)` sem chamar `KILL_GATEWAY`; somente `KILL_GATEWAY` `OK` tempestivo + zero linhas após `ARMED{25}` + `Exited(EXITED, code!=69, eof=True, reaped=True)` emite `Act(ZERO_BACKENDS, 25)` → `COMPLETE_CANDIDATE`; `eof=False` ou `reaped=False` resulta em `ENDED_UNKNOWN` com `controller_retained=True` e `retained=True` |
| `D8` | **Prazos de silêncio, dreno terminal e teto global (`silence_s`, `drain_s`, `overall_s`):** silêncio no `stdout` em `Wait` ou fim de `drain_s` com processo vivo em `HOLD` (`TERMINAL RETAINED` ou `ABORT` sem saída) alimenta `Exited(NO_EXIT)` e conclui com `Outcome.RETAINED` / `ENDED_UNKNOWN` e `retained=True`, sem laço infinito; expiração de `overall_s` encerra de forma conservadora e retida |
| `D9` | **Owner retido, preservação de `BaseException` de controle, limpeza verificada e estáticos AST:** primeiro `CancelledError`/`KeyboardInterrupt`/`SystemExit` durante `spawn`/leitura/escrita/ação/espera é relançado intacto após marcar `phase=HELD` e `retained=True`, mantendo todas as referências em `_tasks` e `_process`; `Done` nunca libera a ponte; `quiesce()` exige tasks concluídas + reap + `pipes_closed()` para emitir `BridgeQuiesced` (senão `HELD`/`None`); `close(absent)` e `assert_released()` exigem `BridgeAbsent` válido; inspeção AST de `docs/poc/oracle9_w1_duplex_bridge.py` proíbe imports de `os`, `subprocess`, `socket`, `threading`, `signal`, `select`, `ctypes`, `w1_bootstrap_channel`, chamadas a `communicate` ou `sleep` global, e confirma redigibilidade de `repr` sem segredos |

## 10. Próximo incremento mínimo e gates nativos/produto abertos

- **Único próximo incremento autorizado após revisão deste documento pelo root:** escrita de `tests/test_oracle9_w1_duplex_bridge.py` (somente testes com portas falsas determinísticas) e medição do RED congelado antes de criar `docs/poc/oracle9_w1_duplex_bridge.py`.
- **`NOT_PREPARED` (proibido gerar ou ler neste lote):** comando/argv de `docker.exe`, pins atuais de CLI/Desktop/stdlib/contexto, raiz da rodada, task, nonce, estado operacional, CIDs, rede `--internal`, IP e perfil de recursos do PG16, credenciais/canários de execução, e camada nativa do relógio do Windows.
- **Gates nativos e de produto permanecem abertos (`BLOCK_NATIVE` / produto):** sonda física de `T5`, `T2`/`T4`/`T6` nativos no Oracle Linux 9.8 (`621cc7f7`) contra PostgreSQL 16 isolado, `B-1`, `B-2`, `D-090` gate 2, `C1`/`D-119`, TLS upstream de produção, patches/minimalização e ingressos `PGWire`, `MCP`, `Admin` e `IDE`. O Gateway segue indisponível e SQL `PGWire` continua recusada.
