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

## Job fixo de DNS do bind PGWire (D-110, opcao B)

`resolve_bind_host_in_child` reutiliza a MESMA supervisao (`_spawn`/
`_TrackedPopen`, `_Pump`/`_guarded`, `_pump_stdin`, `reap`, `_Ledger`) para um
segundo job, fixo e interno: resolver o hostname do bind PGWire. Nao e
framework nem API generica: o codigo do filho, o interpretador (`-I -S -B`), o
ambiente (so `SYSTEMROOT` no Windows, vazio no POSIX) e os tetos sao
constantes deste modulo, e o host so viaja por `stdin`. O caminho da
verificacao (`_ChildRecord.run`) nao muda: continua lendo `_CHILD_CODE`,
`_child_environment` e `MAX_OUTPUT_BYTES` no momento da execucao.

- Capacidade propria: `_BIND_LEDGER`, com 4 vagas, separado das vagas da
  verificacao e do semaforo do `resolver.py`; sem vaga, recusa sem esperar. E
  um limite interno de concorrencia do DNS, nao de sessoes.
- Prazo ABSOLUTO de trabalho (5 s), criado ANTES da admissao, do spawn e dos
  pumps, nunca renovado: a coleta de pendentes na admissao respeita o mesmo
  prazo, e o retorno tardio do spawn ou de `start()` e conferido logo em
  seguida. O cleanup e UMA passada separada, com o orcamento da verificacao
  (6 s). Chamadas bloqueantes do SO nao tem teto absoluto.
- O filho devolve a resposta BRUTA do `getaddrinfo` como triplas JSON ASCII
  `[family, ip, scope_id]`, sem escolher, deduplicar nem filtrar; a politica
  de enderecos e de quem chama.
- Recolhimento nao confirmado: o registro fica no `_BIND_LEDGER`, com dono
  forte do modulo, e retem a vaga (incompleto, nao "sem recurso vivo"); a
  proxima admissao retenta, dentro do proprio prazo.
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
from enum import Enum
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

    def __init__(self, owner: VerificationSupervisor | _BindDnsOwner, claimer: object) -> None:
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

    def run_bind_dns(self, payload: bytes, *, deadline: float) -> bool:
        """Job FIXO de DNS do bind PGWire, sob um prazo ABSOLUTO; NAO recolhe.

        O mesmo ownership de `run` (objeto adotado pelo construtor rastreado,
        pumps adotados antes de qualquer `start()`), com tres diferencas fixas:
        o interpretador `-I -S -B` com `_BIND_DNS_CHILD_CODE` e o ambiente de
        `_bind_dns_environment`; o leitor com o teto do DNS; e o prazo, que vem
        pronto do chamador (criado antes da admissao) e e conferido de novo
        logo depois de cada operacao que pode retornar tarde — o spawn e cada
        `start()` —, sem nunca ser renovado. `True` so com o filho terminado
        dentro do prazo.
        """
        # Prazo ja vencido: nenhum filho e criado.
        process = None if time.monotonic() >= deadline else self._spawn_bind_dns()
        if process is None:
            return False
        try:
            stdin = process.stdin
            stdout = process.stdout
            if stdin is None or stdout is None:  # pragma: no cover - PIPE sempre existe
                return False
            self.pumps.append(
                _Pump(_pump_stdin, (stdin, payload, self.sink), "maskgw-bind-dns-stdin")
            )
            self.pumps.append(
                _Pump(_pump_bind_dns_stdout, (stdout, self.sink), "maskgw-bind-dns-stdout")
            )
            for pump in self.pumps:
                # Spawn ou `start()` anterior que voltou tarde: o prazo NAO
                # recomeca; vencido, nenhum outro pump e iniciado.
                if time.monotonic() >= deadline:
                    return False
                with pump.lock:
                    pump.state = _PUMP_STARTING
                pump.thread.start()
                with pump.lock:
                    pump.state = _PUMP_STARTED
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or self.sink.get("too_big"):
                    return False
                try:
                    process.wait(timeout=min(remaining, 0.05))
                except subprocess.TimeoutExpired:
                    continue
                # `wait()` que voltou DEPOIS do prazo nao aprova; e a resposta
                # tambem precisa ter sido LIDA ate o fim dentro dele: bytes que
                # so chegam no cleanup nao concluem nada.
                return self._bind_dns_read_in_time(self.pumps[1], deadline)
        except (OSError, RuntimeError):
            return False

    @staticmethod
    def _bind_dns_read_in_time(reader: _Pump, deadline: float) -> bool:
        """`True` so se o leitor chegou ao fim ANTES do prazo absoluto.

        Espera em fatias curtas, reconferindo o prazo a cada uma; nunca o
        renova. O recolhimento do leitor continua com o dono (`reap`).
        """
        while not reader.done.wait(max(0.0, min(deadline - time.monotonic(), 0.05))):
            if time.monotonic() >= deadline:
                return False
        return time.monotonic() < deadline

    def _spawn_bind_dns(self) -> subprocess.Popen[bytes] | None:
        """Cria o filho DNS adotado por este registro; `None` se nao criou.

        O estado do spawn decide o recolhimento: construtor nunca entrado
        libera; tentativa sem filho exposto fica retida (ver `reap`).
        """
        executable = sys.executable
        if not executable:
            return None
        try:
            process = _spawn(
                self,
                [executable, "-I", "-S", "-B", "-c", _BIND_DNS_CHILD_CODE],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=_bind_dns_environment(),
                close_fds=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, ValueError):
            return None
        self.process = process
        self.spawn = _SPAWN_CREATED
        return process

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

    def collect_until(self, deadline: float) -> bool:
        """Como `collect`, mas sem passar do prazo: a coleta da admissao do DNS.

        Dois limites que `collect` (o da verificacao, inalterado) nao tem: so
        visita os registros presentes no INICIO da passada — os que chegam
        durante a coleta ficam para a proxima admissao, entao ela nao vira uma
        fila sem prazo — e confere o prazo antes de reivindicar cada um. Mesma
        reivindicacao por token e o mesmo `_settle`.
        """
        token = object()
        with self.lock:
            # Referencias fortes: nenhum `id` da passada e reaproveitado.
            initial = list(self.records)
        initial_ids = {id(record) for record in initial}
        visited: set[int] = set()
        while time.monotonic() < deadline:
            record: _ChildRecord | None = None
            reaped = False
            try:
                with self.lock:
                    record = next(
                        (
                            r
                            for r in self.records
                            if id(r) in initial_ids
                            and id(r) not in visited
                            and not r.in_flight
                            and r.claimer is None
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
        del initial
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


# ---- Job fixo de DNS do bind PGWire (D-110, opcao B) -------------------------
#
# Constantes privadas e internas. NAO sao settings nem limites de sessao, e
# nao tem variavel de ambiente.

#: Prazo de trabalho de UMA resolucao (mesmo valor da D-092), absoluto,
#: criado antes da admissao. O cleanup e separado (`_cleanup_budget`).
_BIND_DNS_TIMEOUT_SECONDS: Final = 5.0

#: Resolucoes simultaneas no processo. Vagas PROPRIAS: nao concorrem com as da
#: verificacao (`_SLOTS`) nem com as do `resolver.py`.
_BIND_DNS_MAX_CONCURRENT: Final = 4

#: Teto do `stdin` do filho (o host em JSON), conferido ANTES do spawn.
_BIND_DNS_MAX_INPUT_BYTES: Final = 1024

#: Teto do `stdout`, cortado DURANTE a leitura e tambem imposto pelo filho.
_BIND_DNS_MAX_OUTPUT_BYTES: Final = 16 * 1024

#: Entradas brutas do `getaddrinfo` aceitas pelo filho, antes de qualquer
#: deduplicacao (que e da politica, no pai).
_BIND_DNS_MAX_ENTRIES: Final = 64

#: Codigo fixo do filho DNS, so stdlib. O host chega por `stdin` como JSON; a
#: saida e a lista BRUTA de `[family, ip, scope_id]` na ordem do
#: `getaddrinfo`, sem escolher, deduplicar nem filtrar: um item que nao se
#: deixa descrever vira `ip` nulo, e a politica do pai recusa a resposta
#: inteira. `scope_id` do IPv6 e preservado para a recusa. Qualquer falha sai
#: com codigo != 0 e sem saida.
_BIND_DNS_CHILD_CODE: Final = (
    "import json, socket, sys\n"
    "try:\n"
    f"    raw = sys.stdin.buffer.read({_BIND_DNS_MAX_INPUT_BYTES + 1})\n"
    f"    if len(raw) > {_BIND_DNS_MAX_INPUT_BYTES}:\n"
    "        raise ValueError\n"
    "    host = json.loads(raw.decode('ascii'))\n"
    "    if type(host) is not str or not host:\n"
    "        raise ValueError\n"
    "    found = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)\n"
    f"    if not found or len(found) > {_BIND_DNS_MAX_ENTRIES}:\n"
    "        raise ValueError\n"
    "    answers = []\n"
    "    for item in found:\n"
    "        address = item[4]\n"
    "        shaped = isinstance(address, tuple) and len(address) in (2, 4)\n"
    "        text = address[0] if shaped and type(address[0]) is str else None\n"
    "        scope = address[3] if shaped and len(address) == 4 else 0\n"
    "        answers.append([int(item[0]), text, scope])\n"
    "    body = json.dumps(answers, ensure_ascii=True, separators=(',', ':'))\n"
    f"    if len(body) > {_BIND_DNS_MAX_OUTPUT_BYTES}:\n"
    "        raise ValueError\n"
    "except Exception:\n"
    "    sys.exit(3)\n"
    "sys.stdout.write(body)\n"
)


def _bind_dns_environment() -> dict[str, str]:
    """Somente o que o resolver do sistema precisa (D-092); nenhum segredo."""
    if sys.platform != "win32":
        return {}
    root = os.environ.get("SYSTEMROOT")
    return {} if root is None else {"SYSTEMROOT": root}


def _pump_bind_dns_stdout(stream: IO[bytes], sink: dict[str, bytes | bool]) -> None:
    """Leitor do DNS: corta em `_BIND_DNS_MAX_OUTPUT_BYTES` DURANTE a leitura.

    Mesma forma de `_pump_stdout`, com o teto proprio do DNS; o leitor da
    verificacao e o teto dele ficam intactos.
    """
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            total += len(chunk)
            if total > _BIND_DNS_MAX_OUTPUT_BYTES:
                sink["too_big"] = True
                break
            chunks.append(chunk)
    except OSError:
        sink["io_error"] = True
    finally:
        with contextlib.suppress(OSError):
            stream.close()
    sink["data"] = b"".join(chunks)


class _BindDnsOwner:
    """Dono forte, de modulo, dos registros DNS do bind (sem `Application`)."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "BindDnsOwner()"


_BIND_OWNER: Final = _BindDnsOwner()

#: Vagas e ledger do DNS do bind. Nao sao `Final`: os testes os isolam. Um
#: registro nao recolhido fica aqui, com a vaga retida, ate uma admissao
#: futura confirmar o recolhimento.
_BIND_SLOTS: threading.BoundedSemaphore = threading.BoundedSemaphore(_BIND_DNS_MAX_CONCURRENT)
_BIND_LEDGER: _Ledger = _Ledger(_BIND_SLOTS)


class BindDnsFailure(Enum):
    """Categoria FECHADA de falha da resolucao do bind."""

    #: Nada foi criado: entrada invalida, prazo ja vencido ou sem vaga.
    REFUSED = "refused"
    #: Sem resposta valida (prazo, saida grande, erro de I/O, codigo != 0 ou
    #: falha do spawn), com tudo recolhido e a vaga devolvida.
    FAILED = "failed"
    #: Recolhimento NAO confirmado: registro e vaga retidos no `_BIND_LEDGER`.
    INCOMPLETE = "incomplete"


class BindDnsError(Exception):
    """Falha da resolucao do bind. Mensagem fixa: sem host, endereco ou causa."""

    def __init__(self, failure: BindDnsFailure) -> None:
        super().__init__("resolucao do bind nao concluida")
        self.failure = failure


def _bind_dns_payload(host: object) -> bytes | None:
    """O host como JSON ASCII para o `stdin`; `None` se invalido ou acima do teto."""
    if not isinstance(host, str) or not host:
        return None
    payload = json.dumps(host).encode("ascii")
    return payload if len(payload) <= _BIND_DNS_MAX_INPUT_BYTES else None


def _bind_dns_admit(ledger: _Ledger, token: object, deadline: float) -> _ChildRecord | None:
    """Coleta os pendentes DENTRO do mesmo prazo e adota vaga e registro.

    A coleta so visita os pendentes ja existentes e para no prazo
    (`collect_until`). Sem vaga, `None` imediato: nao ha fila nem espera.
    """
    ledger.collect_until(min(deadline, time.monotonic() + _ADMISSION_COLLECT_SECONDS))
    with ledger.lock:
        if not ledger.slots.acquire(blocking=False):
            return None
        record = _ChildRecord(_BIND_OWNER, token)
        ledger.records.append(record)
    return record


def _bind_dns_output(record: _ChildRecord, *, completed: bool) -> bytes | BindDnsFailure:
    """Saida de um filho recolhido que terminou no prazo com codigo 0."""
    sink = record.sink
    process = record.process
    ok = completed and not sink.get("too_big") and not sink.get("io_error")
    output = sink.get("data")
    if not ok or process is None or process.returncode != 0 or not isinstance(output, bytes):
        return BindDnsFailure.FAILED
    return output


def _bind_dns_run(host: object, deadline: float) -> bytes | BindDnsFailure:
    """Admite, executa e recolhe UMA resolucao; nunca levanta por falha propria.

    Uma `BaseException` durante a execucao ainda recolhe (best-effort) e
    propaga a original.
    """
    payload = _bind_dns_payload(host)
    if payload is None or time.monotonic() >= deadline:
        return BindDnsFailure.REFUSED
    ledger = _BIND_LEDGER
    token = object()
    record = _bind_dns_admit(ledger, token, deadline)
    if record is None:
        return BindDnsFailure.REFUSED
    completed = False
    reaped = False
    try:
        completed = record.run_bind_dns(payload, deadline=deadline)
    finally:
        reaped = ledger.finish(record, token, time.monotonic() + _cleanup_budget())
    if not reaped:
        return BindDnsFailure.INCOMPLETE
    if record.spawn == _SPAWN_IDLE:
        # O prazo venceu antes do spawn (por exemplo, na coleta): nada criado.
        return BindDnsFailure.REFUSED
    return _bind_dns_output(record, completed=completed)


def resolve_bind_host_in_child(host: str, *, deadline: float | None = None) -> bytes:
    """Resposta BRUTA do `getaddrinfo` do bind PGWire, por filho supervisionado.

    Interno (D-110): o unico consumidor previsto e a politica do bind PGWire,
    que valida e decide. `deadline` e um instante ABSOLUTO de
    `time.monotonic()`; sem ele, o prazo de 5 s comeca AQUI, antes da
    admissao. Levanta somente `BindDnsError`, fora de `except`, sem cadeia e
    sem citar o host.
    """
    limit = time.monotonic() + _BIND_DNS_TIMEOUT_SECONDS if deadline is None else deadline
    result = _bind_dns_run(host, limit)
    if isinstance(result, BindDnsFailure):
        raise BindDnsError(result)
    return result


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
