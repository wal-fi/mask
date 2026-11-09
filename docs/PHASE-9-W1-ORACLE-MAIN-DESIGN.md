# W1 Oracle — main físico D2 e bindings das portas (desenho, v2)

2026-11-09. Somente desenho, escrito pelo Claude2 (sessão
51ea0d85-05bb-4d24-ba9a-c9627c3f832f, claude-opus-5-5, esforço medium), sob a
delegação vigente. Nenhuma aprovação individual do usuário é inventada ou
pedida. Nada executado para escrevê-lo: nenhum teste, Docker, PostgreSQL,
SQL, socket, thread, processo, guard, sinal ou chamada nativa real. Nenhuma
contagem medida é alegada aqui.

A v1 (8d5bc0dd, 29127 bytes) foi arquivada pelo root como dado e não foi
aceita. Esta v2 corrige seis lacunas de contrato apontadas na revisão: posse
antecipada e contenção externa, vida do link, hold e sinais, posse do frame
inteiro pelo leitor, wire inalterado e fatos do SDK/sinais.

Fixos e inalterados: driver `deploy/oracle9_w1_driver.py` SHA-256
`39a6890457c3bc9331fc371948fce896cbbc37e2d49f1584a5629490f43d2794`
(36956 bytes), núcleo puro `deploy/oracle9_w1_controller.py`
`4c155d76208f113852f95fec4c57253eef480c610aa390423fa6f82baf1f7bc7`
(22453 bytes), os 114 testes D1, os 35 testes de sessão `585540af`, o SDK
(`worker_session`, `result_receiver`, `transport`, `budget`, `linux_guard`),
source23, app124, estado16 e a tentativa consumida.

## 1. Fontes e referências

Lidas: driver vigente (`Ports`, `Owner`, `_claim`, `run`, `_Driver`);
`runtime/linux_guard.py` completo; `runtime/worker_session.py`
(`_exclusive`, `open`, `query`, `send_result_to`, `_cleanup`, `close`);
`pgwire/transport.py`; `pgwire/result_receiver.py`; `runtime/budget.py`;
NATIVE-PLAN v4; DRIVER-DESIGN v3 e sua revisão; DRIVER-SESSION-DESIGN. O
documento DRIVER-SESSION-VALIDATION não foi relido; uso o registro do root
(35 próprios, 1109 relacionados).

Referências normativas (documentação primária, **não** evidência medida no
Oracle Linux):

- Python 3.11 `signal`: handlers Python rodam sempre na thread principal;
  só a thread principal pode instalar handler; o interpretador instala por
  padrão SIGINT → `KeyboardInterrupt` e ignora SIGPIPE.
  https://docs.python.org/3.11/library/signal.html
- Python 3.11 `threading`: `Thread.join` devolve `None`; o término deve ser
  conferido com `is_alive()`; `threading.excepthook` padrão escreve em
  stderr. https://docs.python.org/3.11/library/threading.html
- PEP 475: chamadas interrompidas por sinal são retomadas depois do handler,
  salvo se ele levantar exceção. https://peps.python.org/pep-0475/
- Linux `pid_namespaces(7)`: o init do namespace só recebe sinais de dentro
  dele para os quais instalou handler; SIGKILL/SIGSTOP vindos do namespace
  ancestral são sempre entregues.
  https://man7.org/linux/man-pages/man7/pid_namespaces.7.html

## 2. Reconciliação dos binds: emenda prospectiva para três RO

Histórico, preservado como estava: NATIVE-PLAN §4 com um único bind RO;
DRIVER-DESIGN §2 com dois binds RO e o driver como entry point.

Emenda prospectiva sob delegação (não é aprovação do usuário nem mount
realizado): **três binds RO de arquivo único** mais os tmpfs do perfil:

| destino | fonte | pin |
|---|---|---|
| `/opt/maskgw/lab/oracle9_w1_main.py` | `deploy/oracle9_w1_main.py` | NOT_PREPARED (ainda não existe) |
| `/opt/maskgw/lab/oracle9_w1_driver.py` | `deploy/oracle9_w1_driver.py` | `39a68904…2794`, 36956 |
| `/opt/maskgw/lab/oracle9_w1_controller.py` | `deploy/oracle9_w1_controller.py` | `4c155d76…7bc7`, 22453 |

Comando: `python -I -B /opt/maskgw/lab/oracle9_w1_main.py`. O driver deixa de
ser entry point e continua só definições. Sem rebuild de imagem ou pacote,
sem `sys.path`, `PYTHONPATH`, `.pth` ou import de vizinho; segundo a
documentação, `-I` no 3.11 implica `-E -s -P` (a conferir no runtime, §12).

## 3. Módulo `deploy/oracle9_w1_main.py`: fronteira e API mínima

Import do módulo é **só definições**. Única execução de topo:
`if __name__ == "__main__": raise SystemExit(entry(real_system()))`. Imports
de topo: stdlib (`errno`, `hashlib`, `os`, `select`, `signal`, `socket`,
`stat`, `sys`, `threading`, `time`, `types`) e o `maskgw` instalado
(`RawChannel`, `TransportLimits`, `WorkerSession`, `protect_process`,
`SessionState`, `ReservationKind`). Nenhum segredo, leitura de stdin ou
thread antes do guard.

Constantes:

```text
MAIN_PATH     = "/opt/maskgw/lab/oracle9_w1_main.py"
DRIVER_PATH   = "/opt/maskgw/lab/oracle9_w1_driver.py"
DRIVER_SHA    = "39a6890457c3bc9331fc371948fce896cbbc37e2d49f1584a5629490f43d2794"
DRIVER_BYTES  = 36956
DRIVER_MODULE = "_maskgw_w1_lab_driver"
PURE_SHA      = "4c155d76208f113852f95fec4c57253eef480c610aa390423fa6f82baf1f7bc7"
PURE_BYTES    = 22453
INIT_HEADER   = 8       # >4sI, magic MGI1
INIT_BODY_MAX = 65536
CONTROL_BYTES = 16      # >4sBBHII, magic MGL1
LINE_MAX      = 512     # INCLUINDO o LF final: payload 1..511
LINES_MAX     = 56      # cap original do driver
WRITE_CAP_S   = 2.0
SLICE_S       = 0.25
HOLD_BACKOFF_S = 1.0
SLOTS         = ("pair_writer", "pair_reader", "sink_thread", "watcher_thread", "link")
TICKET        = "source_fd"
```

`WRITE_CAP_S`, `SLICE_S` e `HOLD_BACKOFF_S` são escolhas sob delegação, não
medições.

API estável (testável com fakes, sem efeito no import):

| nome | papel |
|---|---|
| `System` | dataclass congelada de callables do SO (§10) |
| `real_system()` | só chamado no bloco `__main__` |
| `MainRoot`, `Phase`, `Slot`, `SlotState` (EMPTY/UNKNOWN/OWNED), `SlotRefusal` | §5 |
| `read_pinned(root, path, size, limit) -> bytes` | leitura pelo ticket (§5.3) |
| `load_driver(root) -> types.ModuleType` | loader pinado (§4) |
| `PinnedReader`, `ControllerGuard`, `MonotonicClock`, `SessionIds`, `SessionFactory`, `HostLink`, `SocketPairs`/`PairWriter`/`PairReader`, `ThreadPorts`/`ThreadHandle` | bindings (§6) |
| `build_ports(root) -> Ports` | monta o `Ports` do namespace vinculado |
| `safe_exit(root) -> bool` | predicado (§7) |
| `_run_once(root) -> MainDecision` | tentativa contida B1..B7 e decisão finita sobre a raiz já criada (§7) |
| `MainDecision` | `EXIT(code)` ou `HOLD`, valor fechado, sem posse própria |
| `hold_step(root) -> HoldStep` | **um** passo finito do hold, com `root.system.pause`/`sleep` (§8) |
| `hold(root) -> NoReturn` | laço sem retorno sobre `hold_step` (§8) |
| `entry(system) -> int` | cria a raiz, chama `_run_once`, sai ou retém (§7) |
| `MainOutcome` + `EXIT_CODES` | §7 |

Exceções próprias: `MainRefusal(Exception)` com categoria fechada (recusas de
binding que o driver trata como falha comum) e `MainSignal(BaseException)`
sem texto, levantada só nos pontos cooperativos do §8. Nenhuma carrega
entrada, caminho, errno ou exceção original; são levantadas fora de `except`
ou com `__context__`/`__cause__` zerados como no `_claim` do driver.

## 4. Bootstrap confiável antes do guard

Tudo depois do import ocorre dentro de `entry(system)`, sob contenção (§7).
Ordem exata:

| fase | ação | aquisição explícita |
|---|---|---|
| B0 | `root = MainRoot(system)`; `phase = BOOT`; namespace e owner `None` | nenhuma (objeto Python) |
| B1 | handler permanente e **não levantador** para SIGTERM, SIGINT, SIGHUP (§8) | nenhuma de recurso |
| B2 | silêncio: `sys.stdout = None`, `sys.stderr = None`, `sys.excepthook`, `threading.excepthook` e `sys.unraisablehook` viram funções fechadas no-op | nenhuma |
| B3 | `load_driver(root)` pelo ticket `source_fd` (§5.3) | fd do arquivo do driver |
| B4 | `root.bind(module, module.Owner())`: uma única vez | nenhuma |
| B5 | link: `HostLink` reserva e ocupa o slot `link` (§6.6) | nenhuma; fd0/fd1 são emprestados |
| B6 | `ports = build_ports(root)`; `run(ports, owner=root.owner)` | via portas (§6) |
| B7 | aposentadoria lógica do link (§6.6) | — |
| B8 | decisão: `safe_exit` → código, senão hold | — |

Silêncio sem descritor novo: fd2 é **emprestado e nunca tocado** (sem
`open("/dev/null")`, `dup2` ou `close`). Fechar fd2 liberaria o número para
um fd próprio posterior, onde uma escrita de erro fatal em C cairia. Código
Python do main e do driver não escreve em stderr; o que o interpretador
escrever em fd2 por erro fatal em C não é controlado aqui e o host deve
descartar stderr (contrato da ponte D4, a conferir).

`load_driver`: `read_pinned(root, DRIVER_PATH, DRIVER_BYTES, DRIVER_BYTES+1)`
devolve os bytes só com o ticket já EMPTY por fechamento verificado (§5.3,
inclusive o caminho de erro); confere tamanho exato e SHA-256 **antes** de
executar; `types.ModuleType(DRIVER_MODULE)`,
`__file__ = DRIVER_PATH`, registro em `sys.modules` e `exec` dos mesmos bytes;
confere no namespace `PURE_SHA`, `PURE_BYTES`, `PURE_PATH`, `Owner`, `Ports` e
`run`. Falha comum depois de o ticket voltar a EMPTY: remove o nome de
`sys.modules` e marca `LOAD_FAILED`. Se o ticket estiver UNKNOWN ou OWNED
(open/close falho ou interrompido), **não** existe `LOAD_FAILED` limpo: o
resultado é hold.

`root.bind(module, owner)`: exige `phase` BOOT, namespace e owner `None`,
`type(owner) is module.Owner`; grava os dois e passa a `BOUND`. Segunda
chamada é `SlotRefusal`. O owner nunca é trocado depois.

Limite honesto: executar o driver importa transitivamente `maskgw` e a stdlib
(`socket`, `subprocess`, `select`, …). Não se alega ausência de efeito
físico implícito desses imports, nem que a admissão Linux (VmSize antes do
guard, `Threads: 1`) foi medida para este conjunto. Antes de B1 o SIGINT tem o
handler padrão do Python e pode levantar `KeyboardInterrupt` durante os
imports de topo; nessa janela o main ainda não fez aquisição explícita, mas
os imports podem ter efeitos implícitos não atestados.

Guard antes de segredo: a primeira porta usada em `run` é `guard.protect`.
LAB_INIT e a carga/captura do núcleo puro continuam depois do guard
aprovado, dentro do driver. O main não cria nenhuma thread de aplicação
adicional antes do guard; a thread principal existe, e o estado de threads
de imports transitivos ou bibliotecas nativas não foi medido (o próprio
guard confere `Threads: 1` no instante em que roda).

## 5. MainRoot, slots e ticket

```text
MainRoot
  system    : System
  phase     : Phase   BOOT → BOUND → LINKED → RUNNING → DECIDING → EXITING | HOLDING
  namespace : types.ModuleType | None     # vinculado uma vez em B4, depois retido
  owner     : namespace.Owner | None      # idem; passado a run e nunca trocado
  slots     : dict[str, Slot]             # exatamente as 5 chaves de SLOTS
  ticket    : Slot                        # único ticket fixo "source_fd"
  ledger    : BudgetLedger | None         # único ledger visto pela factory
  sessions  : list[WorkerSession]         # toda sessão criada
  result    : DriverResult | None
  control   : str | None                  # classe fechada do BaseException contido
  failure   : MainOutcome | None          # SETUP/LOAD/LINK quando aplicável
  signal_seen : bool                      # pegajoso, nunca volta a False
  hold_faults : int                       # falhas de primitiva do hold, saturado

Slot: state ∈ {EMPTY, UNKNOWN, OWNED}; value: objeto/fd exato ou None
```

### 5.1 Operações de slot

- `reserve(*names)`: todos EMPTY, senão `SlotRefusal` **antes** de qualquer
  efeito; todos viram UNKNOWN. OWNED/UNKNOWN nunca é sobrescrito.
- `own(name, value)`: exige UNKNOWN; grava o valor exato; vira OWNED, **antes**
  de devolver o objeto a quem pediu.
- `clear(name, value)`: exige OWNED e `value is slot.value` (fd: igualdade
  de int); vira EMPTY. Só depois de fechamento físico verificado (fds
  próprios) ou aposentadoria lógica verificada (link, §6.6).
- Exceção ou interrupção entre `reserve` e `own`, ou durante o fechamento,
  deixa UNKNOWN/OWNED: incerteza retida, nunca limpa por exceção.

Um par reserva **os dois** slots antes do `socketpair`. O registro no `Owner`
do driver vem depois do `own` (endpoints antes do uso, handle antes do
`start`).

### 5.2 Intervalo não atômico

Em CPython o intervalo entre o retorno da chamada ao SO e a gravação no slot
não é atômico. Com handler não levantador (§8) um sinal não injeta exceção
nesse intervalo, mas uma exceção de outra origem (falha comum como
`MemoryError` ou um `BaseException` não originado em sinal) pode ocorrer. O slot
fica UNKNOWN e a raiz não prova a ausência do recurso: o resultado é hold.
Máscara de sinais não é usada nem apresentada como prova de atomicidade.

### 5.3 Ticket `source_fd` (fixo, sob delegação)

Um único ticket explícito, não registro genérico, para os dois arquivos de
fonte lidos em sequência: o driver (B3) e o núcleo puro (porta reader, logo
após o guard). `read_pinned(root, path, size, limit)`:

1. `root.reserve_ticket()` (exige EMPTY);
2. `fd = os.open(path, O_RDONLY|O_NOFOLLOW|O_CLOEXEC)`; `own_ticket(fd)`.
   Se o `open` levantar (inclusive recusa por `O_NOFOLLOW`) ou for
   interrompido depois da reserva, não há fd exato conhecido para fechar: o
   ticket fica UNKNOWN e a decisão é HOLD;
3. com o fd conhecido e OWNED: `fstat(fd)` exige arquivo regular com
   `st_size == size`; leitura até `limit` bytes num buffer local;
4. **uma** tentativa de fechamento do fd exato original, tanto no sucesso
   quanto depois de falha comum em `fstat`, leitura ou validação (a falha é
   preservada como categoria fechada, sem texto): `os.close(fd)` sem
   exceção, **e** em seguida `fstat(fd)` falha com `EBADF`, **e**
   `threading.active_count() == 1` no instante da conferência; só então
   `clear_ticket(fd)`. Close com exceção, interrupção ou verificação
   incerta mantém OWNED, sem segunda tentativa, e a decisão é HOLD;
5. nenhum byte lido sai de `read_pinned` antes de o ticket estar EMPTY. Com
   ticket EMPTY: falha preservada → exceção comum fechada (LOAD); sucesso →
   os bytes.

Assim, tamanho, SHA ou tipo de arquivo inválidos podem terminar em
`LOAD_FAILED` (65) depois do fechamento verificado; falha do próprio `open`
nunca é saída limpa.

O fechamento do ticket é a única verificação de fd que o main faz fora da
prova nativa. `active_count() == 1` conta só threads gerenciadas pelo
Python; não prova que nenhuma thread nativa de biblioteca reutilizou o
número. A checagem é conservadora (mais retenção, nunca menos), e a prova
física continua separada (§12). As duas leituras ocorrem antes de qualquer
thread criada pelo driver.

## 6. Bindings das portas (assinaturas exatas, SDK inalterado)

### 6.1 reader — `read(path: str, limit: int) -> bytes`

Aceita só `path == namespace.PURE_PATH` e `limit == PURE_BYTES + 1`; ponto
de observação cooperativo (§8); `read_pinned(root, path, PURE_BYTES, limit)`
pelo mesmo ticket. Erros comuns sobem; o driver converte em `LOAD`.

### 6.2 guard — `protect(*, role, address_limit_bytes) -> GuardFacts`

`protect_process(role=role, address_limit_bytes=address_limit_bytes)`.
Fato do SDK: `protect_process` captura `BaseException` e devolve
`ProcessGuardError(SYSTEM)`. Com handler não levantador, um sinal durante o
guard só marca `signal_seen` e é observado no próximo ponto cooperativo.

### 6.3 clock — `monotonic() -> float`, `sleep_until(when: float) -> None`

`time.monotonic`, absoluto. `sleep_until` dorme em fatias de no máximo
`SLICE_S` até `monotonic() >= when`; nunca volta antes; é ponto de
observação entre fatias (§8). Sem busy loop.

### 6.4 ids — `session_id() -> bytes`

`os.urandom(16)`; unicidade conferida pelo driver.

### 6.5 factory — `create(ledger, token, *, lock, key, limits, profile, guard)`

Ponto de observação; exige exatamente esses argumentos; grava o ledger na
raiz (um ledger diferente depois é `MainRefusal`); constrói
`WorkerSession(ledger, token, lock=lock, key=key, limits=limits,
profile=profile, guard=guard)`, a classe pública exata; acrescenta a
`root.sessions` antes de devolver. O construtor não cria fd, thread ou
processo de aplicação (cria `threading.Lock`/`Event` do Python); não se
alega ausência de qualquer recurso de SO subjacente.

### 6.6 link — fd0/fd1 emprestados, `HostLink` com vida lógica

**Separação.** fd0 e fd1 são herdados e **emprestados**: o main nunca os
abre, fecha, duplica ou devolve a bloqueante. O que o main possui é o objeto
`HostLink` no slot `link`. Fechamento físico verificado vale só para fds
próprios (ticket, socketpair); para o link existe apenas aposentadoria
lógica.

Configuração (B5): `reserve("link")`; `fstat` de fd0 e fd1 exige FIFO ou
socket; `isatty` falso nos dois; `set_blocking(0, False)` e
`set_blocking(1, False)`; `own("link", HostLink)`; `phase = LINKED`. Falha:
o slot fica UNKNOWN ou OWNED conforme o ponto (estado O_NONBLOCK pode ter
mudado) e não há saída limpa: hold.

Estado do `HostLink`: `ACTIVE | POISONED | RETIRED`, contador de linhas,
`threading.Lock` de leitor, status fechado do último evento
`OK | EOF | EXPIRED | IO | POISONED | CONCURRENT | RETIRED`.

**Leitura com posse do frame inteiro.** `read_init(*, deadline)` e
`read_control(*, deadline)` adquirem o lock de leitor **uma vez** com
`acquire(blocking=False)` e o seguram até o fim do frame (em `read_init`,
cabeçalho **e** corpo, sem intervalo). Ocupado → `CONCURRENT`, `POISONED`,
`None`. Dentro dessa posse, a função privada sem lock `_read_exact(n,
deadline)`:

- `select([0], [], [], min(restante, SLICE_S))`; pronto → `os.read(0,
  faltam)`; **nunca** pede mais que o restante do frame (sem read-ahead);
- `b""` → EOF; `EAGAIN`/`EINTR` → continua; outro `OSError` → IO;
  restante ≤ 0 → EXPIRED;
- **depois** de cada retorno de `select` e de `read`, reconfere o prazo
  antes de prosseguir; frame completo com `monotonic() >= deadline` é
  EXPIRED e não é entregue.

`read_init`: lê 8 bytes; magic ≠ `MGI1` ou comprimento > `INIT_BODY_MAX` →
devolve **só** os 8 bytes (o decoder puro recusa → `ABORT{INIT}`), sem ler
corpo; senão lê exatamente o corpo e devolve cabeçalho+corpo.
`read_control`: exatamente 16 bytes. Qualquer saída não-OK com bytes já
consumidos, ou EXPIRED depois de consumir, deixa `POISONED`; depois disso
toda leitura devolve `None` sem tocar fd0. O lock é liberado em `finally`;
`BaseException` dentro da posse também envenena. EOF/EXPIRED/IO chegam ao
driver como `None`; o driver separa prazo pelo relógio e relata IO como EOF
(limitação do enum atual do driver, sem mudá-lo).

**Veneno pegajoso durante a operação.** Outro leitor que tente entrar
enquanto um frame tem o lock marca `POISONED` sem esperar. Por isso toda
operação em andamento (leitura dentro da posse, escrita) reconfere o
estado `ACTIVE` depois de cada retorno de `select`, `read` ou `write` e
imediatamente antes de devolver bytes ou `True`. Visto qualquer veneno, a
operação para sem nova chamada de IO e devolve `None`/`False`; nunca entrega
OK depois de observar veneno. `POISONED` e `RETIRED` nunca voltam a
`ACTIVE`, e um link aposentado não faz mais nenhum IO.

**Escrita.** `write(line: bytes) -> bool`: exige link ACTIVE, `bytes`,
payload 1..511 ASCII sem `\n`/`\r` (512 com o LF), e linhas já escritas <
`LINES_MAX` (56). Escreve `line + b"\n"` com `select` em fd1 e `os.write`
até completar, prazo absoluto `agora + WRITE_CAP_S`, reconferido depois de
cada retorno. Completa → `True`. Parcial, `EPIPE` ou prazo → `POISONED`,
`False`; nunca levanta para conteúdo. Escritor único: a thread principal (só
o driver escreve). O main **não escreve nenhuma linha própria**: o wire é o
do driver, inalterado; resultados do main são só decisão de saída ou hold.

**Leitor único e handoff T4.** A principal lê GO{23}; só então o driver cria
e inicia o watcher; o watcher lê exatamente um frame; a principal só volta a
ler depois de join verificado. Com join negativo o driver aborta sem ler; o
watcher pode continuar com o lock de leitor; o slot `watcher_thread` segue
OWNED.

**Aposentadoria lógica (B7).** `HostLink.retire()` só é aceito quando: o
slot `link` está OWNED por este objeto exato; `run` já voltou ou o controle
já foi contido (nenhuma saída posterior é permitida); o lock de leitor está
livre (`acquire(blocking=False)` bem-sucedido e mantido até o fim da
aposentadoria); não há escrita em andamento (só a principal escreve e é ela
que aposenta). Então o estado vira `RETIRED` (toda leitura devolve `None` e
toda escrita `False`, sem tocar fds) e `root.clear("link", self)`. Lock de
leitor ocupado (watcher ainda lendo), slot UNKNOWN ou objeto diferente →
recusa: o slot permanece como está e a decisão é hold. Aposentar não fecha
nem altera fd0/fd1.

### 6.7 pair — `create() -> (writer, reader)`

Ponto de observação; `reserve("pair_writer", "pair_reader")` (ocupado →
`MainRefusal` antes do SO); `a, b = socket.socketpair(AF_UNIX,
SOCK_STREAM)`; `own` dos dois objetos exatos; devolve.

`PairWriter.channel(*, stop) -> RawChannel(a, stop=stop,
limits=TransportLimits())`, a classe pública exata. `shutdown_write()` →
`a.shutdown(SHUT_WR)`. `PairReader.read(limit, *, deadline)`: fatias de
`settimeout(min(restante, SLICE_S))`; `recv(limit)` nunca devolve mais que
`limit`; `b""` → `None`; prazo sem dado → `TimeoutError`; outro erro sobe.
`close()`: `sock.close()` sem exceção e `fileno() == -1` → `clear`. Senão o
slot fica OWNED e a exceção sobe ao driver, que retém. Isso é fato de objeto
mais ausência de erro do close; prova de fechamento no kernel é obrigação
nativa (§12).

### 6.8 threads — `create(target, *, name)`; `start() -> bool`; `join(*, deadline) -> bool`

- `name` só `"sink"` → `sink_thread`, `"watcher"` → `watcher_thread`; outro →
  `MainRefusal` antes de efeito. `create` é ponto de observação.
- `create`: `reserve(slot)`; `threading.Thread(target=wrapper, name=name,
  daemon=False)`; `own(slot, handle)`; devolve sem iniciar.
- `wrapper`: `try: target()` / `except BaseException:` registra categoria
  fechada (`RETURNED`/`RAISED`), sem guardar a exceção / `finally:` marca
  `exited` (Event). Assim nem o `threading.excepthook` padrão (que escreve em
  stderr) nem o fechado de B2 é acionado por exceção do alvo.
- `start()`: `True` só se `thread.start()` voltou normalmente; exceção sobe
  (comum ao driver, `BaseException` à contenção); slot continua OWNED.
- `join(*, deadline)`: em fatias, `thread.join(timeout=min(restante,
  SLICE_S))`, que devolve `None`. **Só depois de um join sem exceção** confere
  `exited.is_set() and not thread.is_alive()`; verdadeiro → `clear(slot,
  self)` e `True`. Prazo sem isso → `False`, slot OWNED. Exceção dentro de
  `thread.join` → slot OWNED; comum sobe ao driver (que retém), interrupção
  sobe à contenção. Término antes de `start` voltar: `exited` marcado e
  thread morta → `True`. Thread que nunca entrou no wrapper → `False`.
- Threads nunca chamam métodos exclusivos da `WorkerSession`; só o watcher
  recebe `request_stop`, o sink só lê o `PairReader`. Thread viva nunca é
  abandonada: mantém o slot OWNED e leva ao hold.

## 7. Contenção, resultado e predicado de saída segura

A raiz é criada pelo chamador e entregue já pronta; ninguém recebe uma raiz
nova criada em outro lugar. Seam finito, testável, sem laço infinito:

```text
def _run_once(root) -> MainDecision:       # root já criada, antes de qualquer efeito
    try:
        B1..B7 em ordem, parando na primeira falha fechada (failure)
    except BaseException as control:       # inclusive antes de run
        root.control = classe fechada      # KeyboardInterrupt|SystemExit|MainSignal|OTHER
        del control                        # sem traceback, texto ou reraise
    try:
        root.phase = DECIDING
        if safe_exit(root):
            root.phase = EXITING
            return EXIT(EXIT_CODES[outcome])
    except BaseException:
        pass
    root.phase = HOLDING
    return HOLD
```

Entrada real:

```text
def entry(system) -> int:
    root = MainRoot(system)                # B0, sem aquisição
    decision = HOLD
    try:
        decision = _run_once(root)
    except BaseException:
        decision = HOLD
    if decision is EXIT: return decision.code
    hold(root)                             # mesma raiz; nunca volta
```

`hold` usa diretamente `root.system.pause` e `root.system.sleep`, sem fábrica
de primitivas nova depois da contenção. Os testes de caminhos retidos ou de
controle chamam `_run_once` com uma raiz fake e conferem a decisão HOLD e a
raiz retida; o caminho infinito é coberto só por testes estruturais e,
depois, pela prova física. Não há knob de retorno finito, exceção especial
de teste nem substituto de `hold` na produção.

B7 (aposentadoria do link) é tentada também depois de controle contido,
quando o slot está OWNED e as condições do §6.6 valem. Nada é reexecutado:
sem segundo `run`, retry de recurso, reset de owner ou limpeza legada. O
retorno de `entry` só acontece com `EXIT`, isto é, depois de `safe_exit`
verdadeiro; o bloco `__main__` faz `raise SystemExit(código)`, sem aquisição
entre a decisão e a saída e sem nenhuma escrita depois do predicado.

Resultado e códigos (nenhum é 0; não existe verde global no main):

```text
SETUP_FAILED  → 64   (B1/B2 falhou; nada adquirido)
LOAD_FAILED   → 65   (B3/B4 falhou com ticket EMPTY verificado)
LINK_FAILED   → 66   (B5 recusou ANTES de alterar fd0/fd1, slot EMPTY)
GUARD_FAILED  → 67
ABORTED       → 68
T6_UNKILLED   → 69
CONTROL       → 70   (root.control definido; prioridade sobre o outcome)
HOLDING       → sem saída (§8)
```

`RETAINED` vai sempre para hold; com resultado RETAINED exige-se ainda
`result.owner is root.owner`.

`safe_exit(root)` é `True` somente se **todos** valem, sobre objetos reais
(exceção na avaliação → `False`):

1. Há decisão fechada: `root.failure` ∈ {SETUP_FAILED, LOAD_FAILED,
   LINK_FAILED}, ou `root.result` é um `DriverResult` do namespace com outcome
   GUARD_FAILED/ABORTED/T6_UNKILLED, ou `root.control` definido. RETAINED ou
   nenhum desses → `False`.
2. Ticket `source_fd` EMPTY.
3. Se há owner: `session is None`, `session_token is None`, `endpoints`,
   `handles` e `unknown` vazios. Referências lógicas em `_retained` (ledger,
   lock, tokens de geração) **não** tornam a saída insegura.
4. Toda sessão em `root.sessions` tem `state is SessionState.CLOSED`.
5. Se houve ledger: `status.failed` falso; nenhuma entrada, nem quarentenada,
   do tipo SESSION; nenhuma com `output_pinned`. GENERATION LIVE/DRAINING é
   permitida (lógica, não recurso nativo).
6. Os cinco slots EMPTY, inclusive `link` (aposentado logicamente ou nunca
   ocupado). Nunca se aposenta UNKNOWN nem se esconde posse para passar aqui.
7. `threading.active_count() == 1`.

Labels não substituem fatos: ABORTED com sessão HELD, linha SESSION, ticket
ou slot ocupado é inseguro. CLOSED/RELEASED vem do estado da sessão e do
ledger, nunca do outcome. Os critérios 4–7 são fatos de objetos e do
runtime Python; o fechamento no kernel e o reap físico além do que o SDK
confirma são provas nativas (§12).

Fatos do SDK relevantes (lidos no código, sem mudança):

- `open`, `query` e `send_result_to` entram em `_exclusive`; o corpo
  interno captura `BaseException`, faz `_cleanup` e levanta
  `WorkerSessionError` fechado.
- `close()` entra em `_exclusive` e chama `_cleanup`. Uma recusa de estado ou
  um controle durante `_exclusive` pode subir a quem chamou. Dentro de
  `_cleanup` os passos físicos e o release capturam `BaseException`
  internamente: o resultado é `RELEASED` quando os fatos confirmam a limpeza
  (estado CLOSED) ou `HELD` quando há incerteza (estado HELD). Falhas de
  limpeza tratadas ali não levantam necessariamente `WorkerSessionError`.
  O driver trata HELD como não liquidado e retém.

## 8. Sinais, observação cooperativa e hold

**Handler único e permanente (B1).** Instalado pela thread principal (só ela
pode) para SIGTERM, SIGINT e SIGHUP, antes de qualquer aquisição explícita,
e **nunca trocado** depois, nem na entrada do hold. Ele só faz
`root.signal_seen = True` e retorna: nunca levanta, nunca escreve, nunca
toca fd ou slot. A marca é pegajosa; não se alega contagem exata nem ordem
de entrega. SIGPIPE e SIGCHLD não são alterados. Falha ao instalar →
`SETUP_FAILED` (nada adquirido ainda).

**Observação cooperativa.** `MainSignal` só é levantado pelos bindings, na
thread principal, em pontos seguros onde nada foi reservado nem adquirido
ainda naquela chamada:

- entrada de `reader.read`, `factory.create`, `pair.create`,
  `threads.create`;
- entrada de `read_init`/`read_control` **antes** de tomar o lock de leitor,
  e entre fatias de `select` enquanto nenhum byte do frame foi consumido;
- entre fatias de `clock.sleep_until`.

Nunca em `write`, `close`, `join`, `start`, `retire`, nem em leituras feitas
pelo watcher (thread não principal): limpeza e escrita de ABORT seguem. O
`MainSignal` não é `Exception`, atravessa o driver e é contido em `entry`
como CONTROL, com owner e slots como estavam.

Latência honesta: o sinal só é observado na próxima chamada a um desses
pontos. Operações sem ponto de observação (guard, `WorkerSession.open`/
`query`/`send_result_to`/`close`, joins, escritas) seguem até seus próprios
prazos: até `statement_timeout + 10 s` numa query, 30 s num envio, mais
joins. Não há cancelamento imediato nem atomicidade. Como o handler não
levanta, nenhum sinal entra no SDK como exceção.

`BaseException` de outra origem durante chamadas ao SO continua coberta
pelos slots (§5) e pela contenção (§7).

**Hold.** Entradas: RETAINED, `safe_exit` falso, exceção na decisão, ou
qualquer falha posterior da contenção. `root.phase = HOLDING`; os handlers
já são não levantadores, então não há troca nem janela nova.

```text
def hold(root) -> NoReturn:
    while True:
        hold_step(root)

def hold_step(root) -> HoldStep:                   # finito, testável
    try:
        root.system.pause()                        # real: signal.pause()
        return WOKE
    except BaseException:
        root.hold_faults = min(root.hold_faults + 1, LIMITE)
    try:
        root.system.sleep(HOLD_BACKOFF_S)          # real: time.sleep
        return BACKOFF
    except BaseException:
        return FAULT
```

- Sem retorno, sem timeout que abandone posse, sem reavaliar o predicado,
  sem fechar, ler fd0, limpar slot ou chamar o driver. Retido até o kill
  duro do host (SIGKILL vindo do namespace ancestral), externo ao processo.
- Falha de `pause` não vira laço apertado: o passo cai no backoff
  bloqueante. Limite honesto: se `pause` **e** `sleep` falharem de imediato
  e de forma persistente, o laço pode girar consumindo CPU; isso é risco
  registrado, nunca motivo para soltar recurso, sair ou marcar PASS nativo.
- Testes exercitam só `hold_step` e `_run_once` com um `System` fake e
  verificam estruturalmente que `hold` é `while True` sem
  `break`/`return`/`except` externo e que `entry` chama `hold` com a mesma
  raiz criada em B0. Nenhum teste executa `hold` nem `entry` no caminho
  retido; o caminho principal nunca volta por fim de seam.

Isto é política de **uma tentativa de laboratório**, não a política de
shutdown do Gateway de produção.

Premissas que exigem conferência autoritativa e prova física antes de rodar
(§12): semântica de sinais do init no namespace (pid_namespaces(7)) com
Python como PID1 sem `--init`; entrega do kill do host; retomada de chamadas
bloqueantes (PEP 475) com handler não levantador; SIGINT padrão antes de B1;
`signal.pause` sem consumo de CPU.

## 9. Fluxo de T4 e T6 com os bindings

T4: a principal lê GO{23} (posse do frame inteiro), o driver cria o watcher
(`watcher_thread` OWNED), inicia, emite ARMED e consulta; o watcher lê um
frame com a própria posse do lock; join verificado limpa o slot e a
principal volta a ler. Join negativo: watcher pode manter o lock; o link não
pode ser aposentado; hold.

T6: a principal lê dentro da janela até o kill do host; sem kill, o driver
fecha a sessão e devolve T6_UNKILLED; B7 aposenta o link; `safe_exit` decide.

## 10. Seam de SO para testes

`System`, dataclass congelada construída só por `real_system()`: `open`,
`read`, `close`, `fstat`, `isatty`, `set_blocking`, `os_read`, `os_write`,
`select`, `socketpair`, `thread_class`, `active_count`, `signal`,
`monotonic`, `sleep`, `pause`, `urandom`, `protect`. O hold usa
diretamente `pause` e `sleep` do mesmo `System` guardado na raiz. Bindings usam só o seam; os
testes não fazem monkeypatch global da stdlib. Lista fechada das chamadas
deste main, não framework.

## 11. Matriz D2 de testes (fake OS, antes da implementação)

Arquivo futuro `tests/test_oracle9_w1_main.py`; main carregado por
`runpy.run_path(..., run_name="_lab_test")`. Driver, núcleo, SDK e testes
existentes não mudam. Contagem prevista não é medição.

| # | caso |
|---|---|
| M-1 | import só definições: nenhum callable do seam chamado; AST com único bloco `__main__` que chama `entry(real_system())`; imports na lista do §3 |
| M-2 | raiz antes de qualquer aquisição: B0 sem chamada ao seam; handler instalado antes do primeiro `open` |
| M-3 | ticket do driver: UNKNOWN antes do `open`, fd exato OWNED, close verificado (sem exceção, EBADF, uma thread) limpa; `open` com exceção (inclusive `O_NOFOLLOW`) ou interrompido → UNKNOWN e `_run_once` devolve HOLD; close falho, interrompido ou com verificação incerta → OWNED, uma única tentativa, HOLD; nenhum byte devolvido antes do ticket EMPTY |
| M-4 | loader: não regular, tamanho ±1 ou SHA errado → uma tentativa de close do fd exato; verificado → LOAD_FAILED/65 com ticket EMPTY; close incerto → HOLD; sem guard, link ou escrita; nome removido de `sys.modules` |
| M-5 | `bind` uma vez: owner exato do namespace; segunda chamada recusada; pins `PURE_*` cruzados |
| M-6 | ordem B0..B8; guard é a primeira porta; o main não cria thread de aplicação antes do guard (construtor de thread do `System` fake não chamado); reader do núcleo puro pelo mesmo ticket, com o mesmo caminho de erro de M-3/M-4 (open falho do puro → ticket UNKNOWN → HOLD) |
| M-7 | guard: argumentos exatos; `ProcessGuardError` → GUARD_FAILED/67; sinal durante guard só marca e é observado depois |
| M-8 | `read_init`: lock único sobre cabeçalho e corpo; cabeçalho inválido devolve só 8 bytes; EOF/IO/prazo/parcial → `None`; prazo reconferido após `select`/`read`; parcial ou expirado após consumir envenena; sem read-ahead |
| M-9 | `read_control`: 16 exatos, mesmas regras |
| M-10 | `write`: payload 1..511 com LF, 56 linhas, ASCII sem CR/LF; parcial/EPIPE/prazo → `False` e envenenado; nenhuma linha do main |
| M-11 | leitor único: leitura concorrente → `None`/CONCURRENT; sobreposição adversarial: um segundo leitor envenena durante o frame em posse e o primeiro, ao reconferir após `select`/`read`, devolve `None` sem entregar bytes; escrita em andamento após veneno devolve `False`; veneno pegajoso; handoff T4; join negativo mantém lock e slot, principal nunca lê (fake de fd pelo `System`, sem patch global) |
| M-12 | aposentadoria do link: só com lock livre e slot OWNED pelo objeto; limpa o slot; leituras/escritas posteriores recusadas; com watcher lendo, recusa e hold; fd0/fd1 nunca fechados |
| M-13 | pair: dois slots UNKNOWN antes do `socketpair`; falha mantém UNKNOWN; ocupado recusa antes do SO; `RawChannel` exato; `read` bytes/None/TimeoutError; close verificado limpa, falho mantém OWNED |
| M-14 | threads: não daemon e nomeadas; UNKNOWN antes do construtor, OWNED antes do retorno; wrapper captura e marca `exited`; `start` True só após retorno; `join` devolve só após join sem exceção com `exited` e não vivo; término antes do `start` voltar; nunca iniciada → False; exceção no join mantém OWNED |
| M-15 | factory: `WorkerSession` real exata (SO simulado do teste de sessão) com os valores do driver; ledger diferente recusado |
| M-16 | clock absoluto, `sleep_until` sem retorno antecipado; ids de 16 bytes |
| M-17 | `safe_exit`: run limpo com gerações retidas e link aposentado → True; sessão não CLOSED, linha SESSION, pin, ticket ou slot ocupado, link não aposentado, thread extra ou RETAINED → False; outcome ABORTED com fatos ruins → False |
| M-18 | contenção em todas as fases via `_run_once`: controle em B1..B7 retém a mesma raiz, namespace/owner (se já vinculados), ticket e slots, e a decisão segue os fatos (HOLD com recurso; CONTROL/70 só se seguro); sem segundo `run`, retry ou reset; em fases tardias o prefixo já emitido de metadados válidos do driver é preservado, sem nenhuma saída nova, bruta ou com segredo do main e nada em fd2 |
| M-19 | sinais: handler único não levantador e pegajoso, instalado só pela principal e nunca trocado; `MainSignal` só nos pontos do §8 e só na principal; watcher nunca recebe `MainSignal` |
| M-20 | `hold_step` com `System` fake: pause ok → WOKE; pause falha → `sleep` de backoff; ambos falham → FAULT com contador saturado; nenhum passo solta slot, lê fd0 ou escreve; AST confere `hold` sem retorno, `entry` criando a raiz antes de `_run_once` e passando a mesma raiz a `hold`, sem fábrica de primitivas |
| M-21 | integração fake: main + driver pinado + WorkerSession real em SO simulado, EOF no GO 3 → ABORTED/68 com `safe_exit` |
| M-22 | RETAINED (ex.: start do sink falho) → `_run_once` devolve HOLD com a mesma raiz, owner e slots retidos |

Distinções preservadas: import só definições (M-1); bootstrap confiável e
posse antecipada (M-2..M-5); guard antes de segredo (M-6, M-7); bindings
(M-8..M-16); posse de slots e ticket (M-3, M-13, M-14); leitor único e
aposentadoria do link (M-11, M-12); saída segura (M-17); contenção de
controle (M-18, M-19); passos finitos do hold (M-20). Nada substitui a prova
nativa do §12 nem o worker real.

## 12. Prova ainda necessária no Oracle Linux 9.8 (BLOCK_NATIVE)

- três binds RO legíveis pelo UID10001; `-I` sem o diretório do script no
  path;
- VmSize e `Threads: 1` no guard depois da carga do driver (AS384MiB com
  margem 8MiB);
- fd0/fd1 como pipe ou socket sem TTY sob `docker run -i`; `O_NONBLOCK`
  efetivo; escrita limitada; stderr descartado pelo host;
- semântica de sinais no PID1 próprio, entrega do kill do host, retomada de
  chamadas com handler não levantador, comportamento de SIGINT antes de B1;
- `signal.pause` sem CPU; prova de vida do processo retido até o kill, com
  recursos ainda presentes;
- fechamento real no kernel dos fds de ticket e socketpair e término real das
  threads, além dos fatos de objeto do §7.

Nada disso está medido. Gate não medido ou reprovado não vira PASS.

## 13. Fora deste desenho e ainda abertos

Implementação do main e testes RED-first do §11 (depois de revisão
documental deste desenho); T5; gerador de expectativas; ponte duplex do
host; fixture/perfil PG; frescor; prova de vida de T6; readmissão da
candidata 621cc7f7; B1, B2, D-090 gate 2, C1, TLS de upstream, ingressos e
produção. SQL PGWire continua recusada; Gateway indisponível.

## 14. Não resolvido

- Intervalo não atômico entre retorno do SO e gravação de slot/ticket:
  tratado só por retenção. Falha do `open` do ticket nunca é saída limpa.
- `active_count() == 1` não exclui threads nativas de bibliotecas; o estado
  de threads dos imports transitivos não foi medido.
- Falha persistente e imediata de `pause` e `sleep` no hold pode girar CPU.
- Latência de observação de sinal limitada só pelos prazos das operações sem
  ponto cooperativo.
- IO no link chega ao driver como EOF (enum atual).
- Erros fatais em C do interpretador ainda podem escrever no fd2 emprestado;
  depende do descarte pelo host.
- `WRITE_CAP_S`, `SLICE_S` e `HOLD_BACKOFF_S` são escolhas, não medidas.
- O pin do próprio main só existe depois da implementação e revisão.
