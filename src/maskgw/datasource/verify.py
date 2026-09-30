"""Verificacao de conexao/sessao/capabilities, em processo e em processo filho.

Fase 9, Etapa 7. O gate pos-conexao da D-090: as consultas de verificacao que
`PostgresAdapter.connect()` executa DEPOIS de autenticar (read-only,
`statement_timeout`, capability de proveniencia) so tem o `statement_timeout` do
proprio servidor como teto. Um upstream que completa a autenticacao e para de
responder deixaria o `recv` preso SEM TETO do lado do cliente.

Aqui a verificacao pos-conexao ganha um limite EFETIVO por processo filho
descartavel, imposto por supervisao com prazo que cobre envio, execucao e
recebimento, como a resolucao DNS da D-092. Estourado o prazo — ou excedido o
teto de stdout durante a leitura —, o filho recebe `kill()`, que rompe os pipes
e desbloqueia as threads de I/O, e o recolhimento roda antes de a funcao
retornar. A unica conexao upstream da verificacao vive dentro do filho e morre
com ele.

## Ownership supervisionado (revisao do `8261dc7`)

Cada filho e um registro (`_ChildRecord`) adotado pelo ledger do processo
(`_Ledger`) ANTES do `Popen`, junto com a vaga que consome. O registro guarda o
processo, as threads de I/O e os pipes ate que os tres estejam EFETIVAMENTE
recolhidos — `poll()` terminado, `is_alive()` falso em toda thread e `closed`
verdadeiro em todo pipe. So entao a vaga e liberada, exatamente uma vez, sob o
lock do ledger. Um erro de fechamento, de `kill()` ou de `poll()` nunca aprova
nem libera: o registro fica pendente, com dono, e o recolhimento e retentado
antes de toda nova admissao e no shutdown. Uma falha transitoria do SO devolve
a capacidade; uma persistente a retem, sem fingir recolhimento.

O prazo da verificacao e o orcamento de cleanup sao separados. O cleanup tem UM
prazo por passada, compartilhado entre tentativas, threads e registros, e nunca
espera sobre um filho vivo. Ele e best-effort: se uma chamada do SO bloquear,
nao ha teto absoluto. Retentar o recolhimento nao repete nada: o filho so
verifica, e nenhuma escrita e reexecutada.

`VerificationSupervisor` e o handle de lifecycle sobre o ledger: e o `Verifier`
injetado pelo composition root, recusa admissao desde `begin_shutdown()`/
`close()` e so se declara fechado quando nao resta registro seu.

O que este gate garante e so o teto de UMA verificacao: o prazo dela mais o
orcamento de cleanup, enquanto as chamadas do SO retornarem. Ele NAO da teto a
fila, ao DNS, ao filesystem nem ao shutdown inteiro. E, enquanto o handler v2
chamar o coordenador de forma sincrona no event loop (D-059; executor dedicado
ainda nao implementado), uma verificacao em voo continua bloqueando o event loop
administrativo por ate esse prazo — o gate limita a espera, nao a remove. Tornar
o event loop responsivo durante a verificacao exige o executor dedicado, fora
desta rodada.

Os dois caminhos — em processo (`verify_connection`) e em filho
(`verify_connection_in_child`) — chamam a MESMA primitiva de verificacao, sem
copia divergente das consultas de capability. O filho:

- roda `python -I` (isolado do ambiente e de `PYTHON*`), com `site` porque
  precisa importar `psycopg` e `maskgw` do site-packages da mesma venv (medido:
  `-I -S` nao importa `psycopg`);
- NAO recebe policy, chave HMAC nem `SecretProvider`, e NAO resolve DNS — o
  `conninfo` ja traz `hostaddr` com os enderecos fixados pelo pai (D-089);
- recebe o alvo — inclusive a senha upstream, dentro do `conninfo` — somente por
  `stdin`, nunca por `argv` (visivel na lista de processos) nem pelo ambiente; o
  resultado volta por `stdout` como categoria fechada; `stderr` e descartado.

O pai compila a politica, constroi o `PreparedRuntime` e publica exatamente o
alvo verificado. O filho so prova conectabilidade sobre o mesmo destino, nome
TLS, credencial e limites efetivos.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from typing import IO, Any, Final

from maskgw.config.gateway import DatabaseSettings
from maskgw.db.postgres import PostgresAdapter
from maskgw.masking.engine import MaskingEngine
from maskgw.masking.rules import MaskingPolicy
from maskgw.runtime.candidate import (
    CandidateFailure,
    PreparedRuntime,
    _raise_candidate,
    verify_adapter,
)

#: Prazo total, em segundos, de UMA verificacao pos-conexao de candidato. Fixo,
#: sem variavel de ambiente. Cobre `connect_timeout` (10 s de um endereco) mais
#: as consultas de sessao/capability, milissegundos num servidor sao. Limite
#: fail-closed: estourado, a verificacao falha como `CONNECTION`. NAO e teto de
#: fila, DNS, filesystem nem do shutdown inteiro (D-090).
VERIFY_TIMEOUT_SECONDS: Final = 12.0

#: Verificacoes simultaneas em processo filho. Semaforo proprio, distinto do da
#: resolucao DNS, para que os dois nao concorram pela mesma vaga.
MAX_CONCURRENT_VERIFICATIONS: Final = 4

#: Teto da resposta do filho.
MAX_OUTPUT_BYTES: Final = 4 * 1024

#: Teto da entrada lida pelo filho.
_MAX_INPUT_BYTES: Final = 64 * 1024

#: Engine so existe porque `PostgresAdapter` o exige no construtor; `connect()`
#: nunca o toca (so `execute`/masking o usam). A verificacao usa um placeholder.
_PLACEHOLDER_ENGINE: Final = MaskingEngine(MaskingPolicy())

#: Vagas do processo. Pertencem ao ledger (`_LEDGER`): adquiridas na admissao e
#: liberadas SOMENTE quando o registro que as consome e removido, recolhido.
_SLOTS: Final = threading.BoundedSemaphore(MAX_CONCURRENT_VERIFICATIONS)

#: Variaveis que o interpretador precisa para localizar a venv e conectar, mas
#: que nao carregam segredo. Diferente do filho DNS (que so precisa resolver),
#: este importa `psycopg`/`maskgw`, entao precisa de PATH e do contexto da venv.
#: `-I` ja ignora `PYTHON*`; aqui o ambiente e reconstruido do zero com uma
#: allowlist, para que nenhum segredo (`MASKGW_*`, DSN, chave, token) chegue ao
#: filho mesmo se estiver no ambiente do processo.
_ENV_ALLOWLIST: Final = (
    "PATH",
    "SYSTEMROOT",
    "SystemRoot",
    "WINDIR",
    "TEMP",
    "TMP",
    "LD_LIBRARY_PATH",
    "DYLD_LIBRARY_PATH",
    "VIRTUAL_ENV",
    "HOME",
    "USERPROFILE",
)


def _child_environment() -> dict[str, str]:
    """Ambiente do zero, so o que o interpretador precisa; nenhum segredo.

    Reconstruido por allowlist: nenhuma variavel de segredo (`MASKGW_*`, DSN,
    chave-mestra, token, HMAC) e nenhuma `PYTHON*` chega ao filho, mesmo que
    exista no processo. Segredo so por `stdin`.
    """
    env: dict[str, str] = {}
    for name in _ENV_ALLOWLIST:
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    return env


def verify_connection(conninfo: str, *, statement_timeout_ms: int) -> None:
    """Abre uma conexao de verificacao a partir do `conninfo` e a verifica.

    Usada pelo filho, que nao tem `PreparedRuntime`, policy nem factory: constroi
    um `PostgresAdapter` real (engine placeholder, que `connect()` nunca toca) e
    delega a `verify_adapter`. O mesmo destino, credencial e limite efetivo do
    pai chegam dentro do `conninfo`.
    """
    adapter = PostgresAdapter(
        conninfo,
        _PLACEHOLDER_ENGINE,
        settings=DatabaseSettings(statement_timeout_ms=statement_timeout_ms, max_rows=1),
        verify_capabilities=True,
    )
    verify_adapter(adapter)


#: Codigo fixo do filho. Nao e montado com dado algum: o alvo (com o segredo) e
#: o limite chegam por `stdin` como JSON. Importa a MESMA primitiva do pai, roda
#: a verificacao e escreve a categoria fechada. Qualquer falha inesperada sai
#: com codigo != 0 e sem saida.
_CHILD_CODE: Final = (
    "import json, sys\n"
    "from maskgw.datasource.verify import verify_connection\n"
    "from maskgw.runtime.candidate import DatasourceCandidateError\n"
    "try:\n"
    f"    payload = json.loads(sys.stdin.read({_MAX_INPUT_BYTES}))\n"
    "    conninfo = payload['conninfo']\n"
    "    timeout = payload['statement_timeout_ms']\n"
    "    if not isinstance(conninfo, str) or type(timeout) is not int:\n"
    "        raise ValueError\n"
    "except Exception:\n"
    "    sys.exit(3)\n"
    "try:\n"
    "    verify_connection(conninfo, statement_timeout_ms=timeout)\n"
    "except DatasourceCandidateError as exc:\n"
    "    sys.stdout.write(json.dumps({'failure': exc.category.value}))\n"
    "    sys.exit(0)\n"
    "except Exception:\n"
    "    sys.exit(4)\n"
    "sys.stdout.write(json.dumps({'ok': True}))\n"
)


#: Passo maximo de UMA espera do recolhimento (`wait`/`join`). O `kill()` rompe
#: os pipes e desbloqueia um writer preso num pipe cheio (medido: ~0 s), entao
#: este passo e folga, nao o teto.
_REAP_GRACE_SECONDS: Final = 2.0

#: Passos que compoem o orcamento de UMA passada de recolhimento:
#: `_REAP_ATTEMPTS x _REAP_GRACE_SECONDS` = 6 s. O orcamento e COMPARTILHADO por
#: todas as tentativas, threads e registros da passada, e nao se multiplica por
#: etapa (revisao do `8261dc7`: 3 x [wait 2 + join 2 + join 2] = 18,22 s
#: medidos). Falha transitoria e retentada dentro dele; esgotado, o registro
#: fica pendente com dono e e retentado depois. Best-effort: uma chamada do SO
#: que bloqueie nao tem teto absoluto.
_REAP_ATTEMPTS: Final = 3

#: Orcamento da passada de recolhimento que precede cada admissao. Curto: uma
#: falha persistente nao pode somar o cleanup inteiro a cada verificacao nova,
#: que ainda roda no event loop administrativo (sem executor dedicado).
_ADMISSION_COLLECT_SECONDS: Final = 1.0

#: Pausa entre tentativas dentro do orcamento, para nao girar em falso.
_REAP_PAUSE_SECONDS: Final = 0.05


def _cleanup_budget() -> float:
    return _REAP_ATTEMPTS * _REAP_GRACE_SECONDS


def _step(deadline: float) -> float:
    """Uma espera do recolhimento: no maximo um passo, nunca alem do prazo."""
    return max(0.0, min(_REAP_GRACE_SECONDS, deadline - time.monotonic()))


class VerificationResourceError(Exception):
    """O recolhimento do filho de verificacao NAO foi confirmado.

    O registro continua sob ownership do ledger, com a vaga retida, e o
    recolhimento e retentado depois — antes da proxima admissao e no shutdown.
    Um recurso vivo ou aberto nunca e apresentado como recolhido. O chamador
    converte em `CONNECTION` sanitizado, fora do `except`. Mensagem fixa.
    """

    def __init__(self) -> None:
        super().__init__("recolhimento do filho de verificacao nao concluido")


class VerificationUnavailableError(Exception):
    """Sem admissao: supervisor em shutdown ou sem vaga. Mensagem fixa."""

    def __init__(self) -> None:
        super().__init__("verificacao indisponivel")


class VerificationShutdownIncompleteError(Exception):
    """O shutdown do supervisor nao confirmou o recolhimento dos seus registros.

    Levantado por `VerificationSupervisor.close()` enquanto resta verificacao em
    voo ou registro pendente (processo, thread ou pipe vivo/aberto). O supervisor
    NAO se declara fechado nem libera vaga, e um `close()` posterior retenta.
    Nao reinicia nem finaliza o gateway. Mensagem fixa, sem dado.
    """

    def __init__(self) -> None:
        super().__init__("recolhimento de verificacoes pendente no shutdown")


def _pump_stdin(stream: IO[bytes], payload: bytes, sink: dict[str, bytes | bool]) -> None:
    """Escreve o payload e fecha o stdin; erro de envio e REGISTRADO, nao ignorado.

    Roda numa thread propria: um filho que NAO le o stdin encheria o buffer do
    pipe e bloquearia esta escrita, mas isso nunca prende o dono do registro, que
    tem prazo proprio e mata o filho — o que rompe o pipe e desbloqueia esta thread.
    Um erro de I/O marca `io_error` para que o chamador recuse o sucesso: um envio
    incompleto nao pode ser confundido com uma verificacao valida.
    """
    try:
        stream.write(payload)
        stream.flush()
    except OSError:
        sink["io_error"] = True
    finally:
        with contextlib.suppress(OSError):
            stream.close()


def _pump_stdout(stream: IO[bytes], sink: dict[str, bytes | bool]) -> None:
    """Le o stdout em blocos, cortando em `MAX_OUTPUT_BYTES` DURANTE a leitura.

    Nao acumula a saida inteira antes de conferir o teto: um filho que despeja
    sem parar e cortado assim que passa do limite. Um erro de I/O e REGISTRADO em
    `io_error` (nao ignorado): uma leitura que falhou depois de ja ter recebido
    `{"ok": true}` nao pode aprovar a verificacao — o chamador recusa.
    """
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_OUTPUT_BYTES:
                sink["too_big"] = True
                break
            chunks.append(chunk)
    except OSError:
        sink["io_error"] = True
    finally:
        with contextlib.suppress(OSError):
            stream.close()
    sink["data"] = b"".join(chunks)


def _is_closed(stream: IO[bytes]) -> bool:
    """`closed` EFETIVO; uma conferencia que falha nao conta como fechado."""
    try:
        return bool(stream.closed)
    except (OSError, ValueError, AttributeError):
        return False


#: Estados de ownership de um `_Pump` (ver a classe).
_PUMP_IDLE: Final = "idle"
_PUMP_STARTING: Final = "starting"
_PUMP_STARTED: Final = "started"


class _Pump:
    """Uma thread de I/O com dono, adotada pelo registro ANTES do `start()`.

    `start()` pode levantar depois de a thread ja estar rodando (inicio parcial)
    ou ser interrompido entre iniciar e retornar; e `is_alive()` falso de uma
    thread ainda em inicializacao NAO prova que ela nunca vai rodar. Por isso a
    thread executa `_guarded`, que so entra no alvo se, sob `lock`, o pump nao
    foi cancelado — e marca `ran`. O recolhimento, sob o MESMO lock, cancela um
    pump que nao entrou no alvo: dali em diante ele nunca toca pipe algum, nem
    se a thread vier a rodar. Cancelar o alvo, porem, NAO prova termino da
    thread nativa: so o estado de ownership decide (ver `settled`).

    Estados (sob `lock`): `_PUMP_IDLE` — `start()` nunca tentado, a thread
    nativa nunca foi pedida ao SO; `_PUMP_STARTING` — tentativa gravada ANTES de
    chamar `start()`, que nao retornou (em andamento, levantou ou foi
    interrompido: inicio INCERTO); `_PUMP_STARTED` — `start()` retornou. `join()`
    so ocorre com a thread comprovadamente iniciada (`_PUMP_STARTED` ou `done`).
    """

    __slots__ = ("cancelled", "done", "lock", "ran", "state", "thread")

    def __init__(self, target: Callable[..., None], args: tuple[object, ...], name: str) -> None:
        self.lock = threading.Lock()
        self.ran = False
        self.cancelled = False
        self.state = _PUMP_IDLE
        self.done = threading.Event()
        self.thread = threading.Thread(
            target=_guarded, args=(self, target, args), name=name, daemon=True
        )

    def joinable(self) -> bool:
        with self.lock:
            started = self.state == _PUMP_STARTED
        return started or self.done.is_set()

    def settled(self) -> bool:
        """Termino FISICO comprovado, ou `start()` nunca tentado.

        Cancela, sob o lock, o pump que ainda nao entrou no alvo. Fora de
        `_PUMP_IDLE`, so conta como encerrado com `done` (que `_guarded` marca ao
        sair, cancelada ou nao) E `is_alive()` falso. `ident is None` ou
        `is_alive()` falso durante o bootstrap NAO provam ausencia: uma tentativa
        de inicio incerta cuja thread nunca chega a rodar retem registro e vaga
        ate o reinicio (perda conservadora de capacidade, escolha do usuario).
        """
        with self.lock:
            if not self.ran:
                self.cancelled = True
            state = self.state
        if state == _PUMP_IDLE:
            return True
        return self.done.is_set() and not self.thread.is_alive()


def _guarded(pump: _Pump, target: Callable[..., None], args: tuple[object, ...]) -> None:
    """Corpo da thread: entra no alvo so se o recolhimento ainda nao cancelou."""
    try:
        with pump.lock:
            if pump.cancelled:
                return
            pump.ran = True
        target(*args)
    finally:
        pump.done.set()


def _ended(process: subprocess.Popen[bytes]) -> bool:
    """`poll()` EFETIVO; uma conferencia que falha nao conta como terminado.

    Inclui `AttributeError`: um objeto adotado com construcao incompleta nunca
    prova termino.
    """
    try:
        return process.poll() is not None
    except (OSError, AttributeError):
        return False


def _pipes(process: subprocess.Popen[bytes]) -> list[IO[bytes]] | None:
    """Os dois pipes pedidos, lidos do objeto; `None` se algum nao foi exposto."""
    stdin = getattr(process, "stdin", None)
    stdout = getattr(process, "stdout", None)
    if stdin is None or stdout is None:
        return None
    return [stdin, stdout]


def _known_pipes(process: subprocess.Popen[bytes]) -> list[IO[bytes]]:
    """Cada pipe pedido que o objeto expoe, mesmo que o outro nao tenha sido."""
    found = (getattr(process, "stdin", None), getattr(process, "stdout", None))
    return [stream for stream in found if stream is not None]


#: Estados de ownership da criacao do filho (ver `_ChildRecord`).
_SPAWN_IDLE: Final = "idle"
_SPAWN_ATTEMPTED: Final = "attempted"
_SPAWN_CREATED: Final = "created"


class _TrackedPopen(subprocess.Popen[bytes]):
    """`Popen` adotado pelo registro ANTES de o construtor criar o filho.

    Subclasse pela API publica: o registro recebe `self` como primeiro passo,
    entao um construtor que cria o filho e DEPOIS levanta (interrupcao, erro
    tardio) nao o tira de alcance. O que esta API NAO cobre: uma interrupcao
    entre a criacao nativa do processo e a exposicao do PID/handle dentro do
    proprio `Popen` — ai o filho existe, mas o objeto nao o alcanca; o registro
    o trata como incerto e retem a vaga ate o reinicio. Nao e garantia absoluta
    contra orfaos.
    """

    def __init__(self, record: _ChildRecord, args: list[str], **kwargs: Any) -> None:  # noqa: ANN401 - repasse integral ao Popen
        record.adopt(self)
        super().__init__(args, **kwargs)


def _spawn(record: _ChildRecord, args: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:  # noqa: ANN401 - repasse integral ao Popen
    """Cria o filho adotado por `record`. Ponto unico de criacao (seam de teste)."""
    return _TrackedPopen(record, args, **kwargs)


class _ChildRecord:
    """Um filho de verificacao e tudo que ele prende: processo, threads, pipes.

    Criado e adotado pelo ledger ANTES do `Popen`, com a vaga ja consumida, de
    modo que nenhum caminho — retorno, excecao, shutdown — fica sem dono. `owner`
    e o supervisor que o admitiu; `in_flight`, que a verificacao ainda corre sob
    o dono; `claimer`, o token de quem o esta recolhendo agora (`None`: livre).
    Os pumps de I/O entram em `pumps` antes de qualquer `start()`.

    `spawn` e o estado de ownership da CRIACAO do filho: `_SPAWN_IDLE` — o
    construtor do `Popen` nunca foi entrado, nada foi criado; `_SPAWN_ATTEMPTED`
    — o construtor adotou o objeto (`adopt`) e nao retornou normalmente:
    criacao incerta; `_SPAWN_CREATED` — o construtor retornou. Um objeto
    adotado sem PID ou pipes expostos NAO prova que nada foi criado: o registro
    e a vaga ficam retidos ate o reinicio (garantia estrita, escolha do
    usuario). Os pipes sao lidos do proprio objeto, nunca de copia anterior.
    """

    __slots__ = ("claimer", "in_flight", "owner", "process", "pumps", "sink", "spawn")

    def __init__(self, owner: VerificationSupervisor, claimer: object) -> None:
        self.owner = owner
        self.in_flight = True
        self.claimer: object | None = claimer
        self.process: subprocess.Popen[bytes] | None = None
        self.spawn = _SPAWN_IDLE
        self.sink: dict[str, bytes | bool] = {}
        self.pumps: list[_Pump] = []

    def adopt(self, process: subprocess.Popen[bytes]) -> None:
        """Primeiro passo do construtor: a tentativa vem ANTES da referencia.

        Uma interrupcao entre as duas atribuicoes deixa tentativa sem objeto —
        incerta, retida —, nunca objeto sem tentativa.
        """
        self.spawn = _SPAWN_ATTEMPTED
        self.process = process

    def run(self, payload: bytes, *, timeout: float) -> bool:
        """Executa o filho sob o prazo da verificacao; NAO recolhe.

        `True` se o filho terminou dentro do prazo; `False` se foi preciso mata-lo
        (prazo, saida grande), se o transporte falhou ou se nao houve filho. O
        prazo nao depende de uma thread bloqueada no envio: envio e recebimento
        rodam em threads proprias, e este laco espera o processo ate o deadline.
        O objeto `Popen` e adotado pelo registro como PRIMEIRO passo do
        construtor (`_TrackedPopen`), e os dois pumps entram em `pumps` ANTES de
        qualquer `start()`: nem um filho criado por um construtor que depois
        levantou, nem uma thread que o `start()` chegou a iniciar antes de
        levantar — `RuntimeError` ou `BaseException` —, ficam fora do alcance do
        recolhimento.
        """
        executable = sys.executable
        if not executable:
            return False
        try:
            # `-I` sem `-S`: isolado do ambiente e de `PYTHON*`, mas com `site`,
            # porque o filho importa `psycopg` e `maskgw` do site-packages da venv.
            process = _spawn(
                self,
                [executable, "-I", "-c", _CHILD_CODE],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=_child_environment(),
                close_fds=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, ValueError):
            # O estado do spawn decide: construtor nunca entrado libera; uma
            # tentativa sem filho exposto fica retida (ver `reap`).
            return False
        self.process = process
        self.spawn = _SPAWN_CREATED
        try:
            stdin = process.stdin
            stdout = process.stdout
            if stdin is None or stdout is None:  # pragma: no cover - PIPE sempre existe
                return False
            self.pumps.append(
                _Pump(_pump_stdin, (stdin, payload, self.sink), "maskgw-verify-stdin")
            )
            self.pumps.append(_Pump(_pump_stdout, (stdout, self.sink), "maskgw-verify-stdout"))
            # `start()` pode falhar antes OU depois de a thread rodar; o pump ja
            # tem dono. A tentativa e gravada ANTES da chamada; so o retorno
            # comprova o inicio. Qualquer coisa entre os dois e inicio incerto.
            for pump in self.pumps:
                with pump.lock:
                    pump.state = _PUMP_STARTING
                pump.thread.start()
                with pump.lock:
                    pump.state = _PUMP_STARTED

            deadline = time.monotonic() + timeout
            # Espera o fim do processo ate o deadline, sem depender das threads
            # de I/O. Se o reader ja sinalizou saida grande, desiste antes.
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or self.sink.get("too_big"):
                    return False
                try:
                    process.wait(timeout=min(remaining, 0.05))
                except subprocess.TimeoutExpired:
                    continue
                return True
        except (OSError, RuntimeError):
            # Falha de transporte ou de inicializacao de thread: o recolhimento
            # do dono cuida de tudo.
            return False

    def reap(self, deadline: float) -> bool:
        """Recolhe ate `deadline`; `True` SOMENTE com tudo efetivamente recolhido.

        A ordem importa: mata o filho PRIMEIRO, o que rompe os pipes e desbloqueia
        um writer preso num pipe cheio; so com o processo TERMINADO fecha os
        pipes e espera as threads. Fechar o stream do writer antes do `kill()`
        tentaria dar flush num pipe cheio e bloquearia o proprio recolhimento
        (medido: 15-24 s), e esperar threads sobre um filho vivo so queimaria o
        orcamento. Falha transitoria de `kill()`/`wait()`/`poll()`/`close()` e
        retentada dentro do MESMO prazo; registrar a falha nao e concluir.

        Criacao incerta sem processo exposto devolve `False` JA, sem queimar o
        orcamento. Processo exposto com pipe faltante e encerrado e tem os pipes
        conhecidos fechados; depois disso, nada observavel muda, e o registro
        fica retido sem gastar o resto do orcamento.
        """
        if self.spawn == _SPAWN_IDLE:
            return True  # o construtor nunca foi entrado: nada foi criado
        process = self._process()
        if process is None:
            return False
        while True:
            if self._reap_once(process, deadline):
                return True
            if self._only_unknown_pipe_left(process):
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(_REAP_PAUSE_SECONDS, remaining))

    def _reap_once(self, process: subprocess.Popen[bytes], deadline: float) -> bool:
        if not _ended(process):
            signalled = False
            with contextlib.suppress(OSError, AttributeError):
                process.kill()
                signalled = True
            # Esperar so faz sentido se o `kill()` foi entregue; senao, a
            # proxima volta o retenta apos a pausa, dentro do mesmo orcamento.
            step = _step(deadline)
            if signalled and step > 0:
                with contextlib.suppress(OSError, AttributeError, subprocess.TimeoutExpired):
                    process.wait(timeout=step)
            if not _ended(process):
                return False
        # Com o pipe rompido, o `close()` do writer nao bloqueia em flush. Cobre
        # tambem o stream de uma thread que nunca iniciou, e cada pipe exposto
        # mesmo que o outro nao tenha sido.
        for stream in _known_pipes(process):
            if not _is_closed(stream):
                with contextlib.suppress(OSError, ValueError):
                    stream.close()
        for pump in self.pumps:
            step = _step(deadline)
            if step <= 0:
                break
            # `join()` so sobre thread comprovadamente iniciada; uma que nunca
            # entrou no alvo e cancelada em `settled()`.
            if pump.joinable():
                pump.thread.join(step)
        return self.reaped()

    def _process(self) -> subprocess.Popen[bytes] | None:
        """O PROCESSO, se alcancavel pelos metodos publicos; `None` se incerto.

        Criado (`_SPAWN_CREATED`): o objeto devolvido pelo construtor. Tentativa
        incerta: o objeto adotado so conta se expoe PID inteiro. Alcancar o
        processo permite TENTAR `kill`/`poll`/`wait`, cujas falhas nunca contam
        como fim; a completude dos pipes e conferida a parte, so para liberar.
        """
        process = self.process
        if process is None:
            return None
        if self.spawn != _SPAWN_CREATED and not isinstance(getattr(process, "pid", None), int):
            return None
        return process

    def _only_unknown_pipe_left(self, process: subprocess.Popen[bytes]) -> bool:
        """Processo terminado e pipes conhecidos fechados, mas um pipe ausente."""
        return (
            _pipes(process) is None
            and _ended(process)
            and all(_is_closed(stream) for stream in _known_pipes(process))
        )

    def reaped(self) -> bool:
        """Conferencia EFETIVA, sem esperar: processo, TODOS os pumps e pipes.

        Um pipe pedido que nao foi exposto nao prova fechamento: o registro so
        e liberado com os dois pipes conhecidos e fechados.
        """
        if self.spawn == _SPAWN_IDLE:
            return True
        process = self._process()
        if process is None:
            return False
        # Laco explicito, sem curto-circuito: TODO pump e conferido (e todo
        # nao iniciado, cancelado), mesmo que o processo ainda viva.
        pumps_settled = True
        for pump in self.pumps:
            if not pump.settled():
                pumps_settled = False
        pipes = _pipes(process)
        if pipes is None or not (_ended(process) and pumps_settled):
            return False
        return all(_is_closed(stream) for stream in pipes)


class _Ledger:
    """Ownership dos filhos de verificacao do processo e das vagas que consomem.

    Um so por processo (`_LEDGER`): um registro deixado por um supervisor que
    falhou no startup ou teve shutdown incompleto continua alcancavel e e
    retentado por qualquer supervisor. Toda transicao de registro acontece sob
    `lock`; o recolhimento roda FORA do lock, por quem reivindicou o registro
    com o proprio token (`claimer`), entao dois coletores nunca recolhem o mesmo
    registro e a vaga sai exatamente uma vez — por quem remove o registro, e so
    recolhido. Um coletor reivindica UM registro por vez, dentro do `try` cujo
    `finally` o assenta, e so assenta o que carrega o SEU token: uma
    interrupcao nunca deixa reivindicacao sem coletor nem desfaz a de outro.
    """

    __slots__ = ("lock", "records", "slots")

    def __init__(self, slots: threading.BoundedSemaphore) -> None:
        self.lock = threading.Lock()
        self.slots = slots
        self.records: list[_ChildRecord] = []

    @property
    def pending(self) -> int:
        """Registros sem verificacao em curso que ainda prendem recurso."""
        with self.lock:
            return sum(1 for record in self.records if not record.in_flight)

    def finish(self, record: _ChildRecord, token: object, deadline: float) -> bool:
        """Recolhe um registro reivindicado por `token` e o assenta; nunca o abandona."""
        reaped = False
        try:
            reaped = record.reap(deadline)
        finally:
            self._settle(record, token, reaped=reaped)
        return reaped

    def _settle(self, record: _ChildRecord, token: object, *, reaped: bool) -> None:
        """Assenta SO o que carrega `token`; a reivindicacao de outro fica intacta."""
        with self.lock:
            if record.claimer is not token:
                return
            record.in_flight = False
            record.claimer = None
            if not reaped or record not in self.records:
                return
            self.records.remove(record)
            # A UNICA liberacao da vaga deste registro.
            self.slots.release()

    def collect(self, deadline: float) -> bool:
        """Uma passada sobre os pendentes livres, com UM prazo para todos.

        `True` quando, ao fim, nao resta pendente. Registros em voo pertencem ao
        dono; registros ja reivindicados por outra thread sao deixados a ela.
        Reivindica um por vez: uma interrupcao (`BaseException`) no recolhimento
        assenta o registro em curso e nao deixa nenhum outro reivindicado.
        """
        token = object()
        visited: set[int] = set()
        while True:
            record: _ChildRecord | None = None
            reaped = False
            try:
                with self.lock:
                    record = next(
                        (
                            r
                            for r in self.records
                            if not r.in_flight and r.claimer is None and id(r) not in visited
                        ),
                        None,
                    )
                    if record is None:
                        break
                    record.claimer = token
                visited.add(id(record))
                reaped = record.reap(deadline)
            finally:
                if record is not None:
                    self._settle(record, token, reaped=reaped)
        return self.pending == 0


class VerificationSupervisor:
    """Handle de lifecycle das verificacoes em filho; o `Verifier` de producao.

    Admite (vaga e registro adotados sob o lock do ledger), executa, recolhe e
    so devolve a vaga com tudo recolhido. Antes de admitir, retenta os
    pendentes. `begin_shutdown()` recusa admissao sem esperar nada; `close()`
    recusa, retenta os pendentes com o orcamento de cleanup e so se declara
    fechado quando nao resta registro seu — senao levanta
    `VerificationShutdownIncompleteError`, e um `close()` posterior retenta. Nao
    espera sem teto por uma verificacao em voo. Thread-safe: o estado e
    protegido pelo lock do ledger.
    """

    __slots__ = ("_closed", "_closing", "_ledger")

    def __init__(self, *, ledger: _Ledger | None = None) -> None:
        self._ledger = ledger if ledger is not None else _LEDGER
        self._closing = False
        self._closed = False

    def __call__(self, prepared: PreparedRuntime) -> None:
        """`Verifier`: o MESMO `conninfo` e `statement_timeout` da sessao real."""
        conninfo, statement_timeout_ms = prepared.verify_target()
        self.verify(conninfo, statement_timeout_ms=statement_timeout_ms)

    def verify(
        self,
        conninfo: str,
        *,
        statement_timeout_ms: int,
        timeout: float | None = None,
    ) -> None:
        """Verificacao pos-conexao com prazo efetivo, em processo filho.

        Falha fechada — `DatasourceCandidateError(CONNECTION)` — sem admissao
        (shutdown ou sem vaga), no prazo estourado, com saida invalida, com falha
        inesperada do filho ou com recolhimento nao confirmado; devolve a
        categoria exata (`CONNECTION`/`CAPABILITY`) quando o filho a reporta e
        tudo foi recolhido. Nunca levanta com host, destino, senha ou excecao
        original (D-017). O segredo (dentro do `conninfo`) viaja so por `stdin`.
        """
        deadline = VERIFY_TIMEOUT_SECONDS if timeout is None else timeout
        payload = json.dumps(
            {"conninfo": conninfo, "statement_timeout_ms": statement_timeout_ms}
        ).encode("utf-8")
        if len(payload) > _MAX_INPUT_BYTES:
            _raise_candidate(CandidateFailure.CONNECTION)
        refused = False
        output: bytes | None = None
        try:
            output = self._run(payload, timeout=deadline)
        except (VerificationResourceError, VerificationUnavailableError):
            refused = True
        if refused:
            # Fora do `except`: nem `__cause__` nem `__context__` (D-017).
            _raise_candidate(CandidateFailure.CONNECTION)
        result = None if output is None else _parse(output)
        if result is True:
            return
        if isinstance(result, CandidateFailure):
            _raise_candidate(result)
        _raise_candidate(CandidateFailure.CONNECTION)

    def collect(self) -> bool:
        """Retenta os pendentes do processo com o orcamento de cleanup."""
        return self._ledger.collect(time.monotonic() + _cleanup_budget())

    def begin_shutdown(self) -> None:
        """Recusa novas verificacoes. Permanente; nao espera nada."""
        with self._ledger.lock:
            self._closing = True

    def close(self) -> None:
        """Recusa admissao, retenta os pendentes e confere os registros proprios.

        Idempotente. So marca fechado sem registro seu no ledger — nem em voo,
        nem pendente. Caso contrario levanta `VerificationShutdownIncompleteError`
        sem liberar vaga; o proximo `close()` retenta.
        """
        with self._ledger.lock:
            if self._closed:
                return
            self._closing = True
        self._ledger.collect(time.monotonic() + _cleanup_budget())
        with self._ledger.lock:
            remaining = any(record.owner is self for record in self._ledger.records)
            self._closed = not remaining
        if remaining:
            raise VerificationShutdownIncompleteError

    @property
    def closing(self) -> bool:
        with self._ledger.lock:
            return self._closing

    @property
    def closed(self) -> bool:
        with self._ledger.lock:
            return self._closed

    @property
    def owned(self) -> int:
        """Registros deste supervisor ainda no ledger (em voo ou pendentes)."""
        with self._ledger.lock:
            return sum(1 for record in self._ledger.records if record.owner is self)

    def _admit(self, token: object) -> _ChildRecord:
        """Retenta os pendentes e adota vaga e registro na MESMA secao do lock.

        O registro nasce reivindicado pelo `token` do dono e em voo.
        """
        with self._ledger.lock:
            if self._closing:
                raise VerificationUnavailableError
        self._ledger.collect(time.monotonic() + _ADMISSION_COLLECT_SECONDS)
        with self._ledger.lock:
            if self._closing or not self._ledger.slots.acquire(blocking=False):
                raise VerificationUnavailableError
            record = _ChildRecord(self, token)
            self._ledger.records.append(record)
        return record

    def _run(self, payload: bytes, *, timeout: float) -> bytes | None:
        """Saida de um filho que terminou no prazo, com TUDO recolhido.

        `None` para prazo, saida grande, erro de I/O, codigo != 0 ou transporte.
        Levanta `VerificationResourceError` quando o recolhimento nao foi
        confirmado — o registro segue com dono e a vaga, retida.
        """
        token = object()
        record = self._admit(token)
        completed = False
        reaped = False
        try:
            completed = record.run(payload, timeout=timeout)
        finally:
            reaped = self._ledger.finish(record, token, time.monotonic() + _cleanup_budget())
        if not reaped:
            raise VerificationResourceError
        sink = record.sink
        if not completed or sink.get("too_big") or sink.get("io_error"):
            return None
        process = record.process
        if process is None or process.returncode != 0:
            return None
        output = sink.get("data")
        return output if isinstance(output, bytes) else None

    def __repr__(self) -> str:
        with self._ledger.lock:
            owned = sum(1 for record in self._ledger.records if record.owner is self)
            return (
                f"VerificationSupervisor(closing={self._closing}, closed={self._closed}, "
                f"owned={owned})"
            )


def _parse(output: bytes) -> CandidateFailure | bool | None:
    """Traduz a saida fechada do filho.

    Retorna `True` para sucesso, um `CandidateFailure` para recusa conhecida, ou
    `None` quando a saida e invalida (tratada como `CONNECTION` pelo chamador).
    """
    try:
        value = json.loads(output.decode("ascii"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(value, dict):
        return None
    if value.get("ok") is True and len(value) == 1:
        return True
    raw = value.get("failure")
    if isinstance(raw, str) and len(value) == 1:
        try:
            category = CandidateFailure(raw)
        except ValueError:
            return None
        if category in (CandidateFailure.CONNECTION, CandidateFailure.CAPABILITY):
            return category
    return None


#: Ownership do processo. Nao e `Final`: os testes isolam capacidade e ledger.
_LEDGER: _Ledger = _Ledger(_SLOTS)

#: Supervisor das funcoes de modulo abaixo. O composition root NAO o usa: compoe
#: o proprio supervisor, sobre o mesmo ledger, e o fecha no shutdown.
_DEFAULT_SUPERVISOR: VerificationSupervisor = VerificationSupervisor(ledger=_LEDGER)


def _run_child(payload: bytes, *, timeout: float) -> bytes | None:
    """Executa um filho pelo supervisor padrao; `None` sem admissao.

    Levanta `VerificationResourceError` quando o recolhimento nao foi
    confirmado; o registro continua com dono no ledger.
    """
    try:
        return _DEFAULT_SUPERVISOR._run(payload, timeout=timeout)
    except VerificationUnavailableError:
        return None


def verify_connection_in_child(
    conninfo: str,
    *,
    statement_timeout_ms: int,
    timeout: float | None = None,
) -> None:
    """Verificacao pos-conexao em filho, pelo supervisor padrao do modulo."""
    _DEFAULT_SUPERVISOR.verify(conninfo, statement_timeout_ms=statement_timeout_ms, timeout=timeout)


def child_verifier(prepared: PreparedRuntime) -> None:
    """`Verifier` em filho pelo supervisor padrao do modulo.

    O composition root injeta um `VerificationSupervisor` proprio, com lifecycle
    ligado ao catalogo; esta funcao segue para quem verifica fora dele.
    """
    _DEFAULT_SUPERVISOR(prepared)


__all__ = [
    "MAX_CONCURRENT_VERIFICATIONS",
    "VERIFY_TIMEOUT_SECONDS",
    "VerificationShutdownIncompleteError",
    "VerificationSupervisor",
    "child_verifier",
    "verify_adapter",
    "verify_connection",
    "verify_connection_in_child",
]
