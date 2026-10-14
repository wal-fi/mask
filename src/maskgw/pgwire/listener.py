"""Listener PGWire: admissao, ownership e encerramento (Fase 9, Etapa 7, D-110).

Lote 3. Recebe settings, principal, TLS e o callback de alias JA preparados.
Nao le ambiente, nao resolve DNS, nao abre registry, sessao de datasource nem
upstream, nao executa SQL. Nao e ligado pelo composition root neste lote.

**Threads.** Um acceptor e um worker por conexao, todos nao daemon, criados
por uma fabrica injetavel. Teto: `1 + P + S` (P = vagas pre-auth, S =
`max_sessions`). Nenhum backend e criado nesta etapa.

**Ownership (D-107/D-108).** Cada thread vive num `_Owned`, adotado ANTES do
`start()`, com estados `idle -> starting -> started`, mais `ran`, `cancelled`
e `done`. O wrapper confere `cancelled` sob o lock antes de marcar `ran`, e
marca `done` no `finally`. `settled()` so e verdade com `idle` (nunca
tentado), ou com `done` MAIS a thread fisicamente morta. `ident`/`is_alive`
sozinhos nunca provam ausencia de um inicio tentado. Se o `start()` falha e o
alvo ainda nao entrou, o owner marca `cancelled`: o alvo, se um dia rodar,
sai sem tocar nada. Sem prova de termino, registro e vaga ficam retidos e o
listener passa a `broken` (nenhuma admissao nova).

**Recolhimento so pelo owner.** O worker nunca remove o proprio registro nem
libera vaga, e nunca fecha o socket. O reaper (acceptor, a cada volta, e
`stop()`) fecha o socket da conexao so quando o worker esta `settled` ou com
cancelamento provado antes de entrar, e remove o registro e libera o contador
so com o worker `settled` E o socket com `close()` concluido sem erro. Se o
`close()` levanta `OSError`, o registro fica retido para sempre e o listener
vai a `broken`: depois de um `close()` falho o SO nao oferece como reprovar a
liberacao do handle (limite documentado).

**Barreira.** Um unico lock governa estado, admissao, criacao/adocao de
registros, contadores e a transicao pre-auth -> auth. Ele nunca envolve
handshake, `join`, `close` nem espera longa.

**Admissao.** Por conexao aceita, sob o lock: estado `RUNNING`, um token do
bucket GLOBAL (reservado por tentativa: EOF, framing invalido e falha TLS
consomem o token) e uma vaga pre-auth. Sem isso: `53300` em melhor esforco,
sem bloquear, e o socket e fechado na hora, sem criar thread. O `Deadline` da
conexao e criado imediatamente apos o `accept`, registrado antes do `start`
e passado ao driver, que nunca o renova. A reserva de sessao (callback do
driver, depois da prova) move a conexao de pre-auth para auth, ate S.

**Parada.** `stop()` e permanente e idempotente: fecha a admissao, sinaliza
acceptor e workers (o driver confere a cada fatia; o socket raw nunca muda de
dono), espera sem prazo os iniciados (o limite e o trabalho em fatias, nao a
espera, como na D-108), recolhe e fecha o socket do listener. Com qualquer
thread de inicio/termino incerto ou `close()` falho, termina `incomplete` e
levanta erro fixo; repetir `stop()` refaz o recolhimento. Chamado de uma
thread do proprio listener, recusa ANTES de qualquer efeito.

**Hostname.** Sem DNS aqui: bind por hostname exige um colaborador interno
explicito com exatamente um IP literal ja resolvido; sem ele, falha fechada
antes do bind. A resolucao limitada no composition root e pendente.
"""

from __future__ import annotations

import contextlib
import ipaddress
import os
import socket
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from maskgw.errors import ConfigError
from maskgw.pgwire.credential import PrincipalCredential
from maskgw.pgwire.driver import DriverLimits, SessionOutcome, run_startup_session
from maskgw.pgwire.errors import PgwireErrorCategory, error_response
from maskgw.pgwire.settings import PgwireSettings, validate
from maskgw.pgwire.tls import ServerTls
from maskgw.pgwire.transport import Deadline, TransportLimits

_IDLE: Final = "idle"
_STARTING: Final = "starting"
_STARTED: Final = "started"
_REFUSAL: Final = error_response(PgwireErrorCategory.TOO_MANY_CONNECTIONS)

ThreadFactory = Callable[..., threading.Thread]


class ListenerState(StrEnum):
    NEW = "new"
    STARTING = "starting"
    RUNNING = "running"
    BROKEN = "broken"
    STOPPING = "stopping"
    STOPPED = "stopped"
    INCOMPLETE = "incomplete"


class PgwireListenerError(Exception):
    """Falha fixa do listener: so o texto, sem causa."""


class PgwireListenerIncompleteError(PgwireListenerError):
    """Encerramento sem prova fisica de todo recurso; `stop()` pode repetir."""

    def __init__(self) -> None:
        super().__init__("pgwire: encerramento do listener incompleto")


@dataclass(frozen=True, slots=True)
class ListenerStatus:
    state: ListenerState
    pre_auth: int
    authenticated: int
    connections: int
    retained_sockets: int


class _AdmissionBucket:
    """Token bucket GLOBAL (sem chave por IP). Usado so sob o lock do listener."""

    __slots__ = ("_burst", "_clock", "_last", "_rate", "_tokens")

    def __init__(self, burst: int, rate: int, clock: Callable[[], float]) -> None:
        self._burst = float(burst)
        self._rate = float(rate)
        self._clock = clock
        self._tokens = float(burst)
        self._last = clock()

    def take(self) -> bool:
        now = self._clock()
        elapsed = max(0.0, now - self._last)
        self._last = now
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        if self._tokens >= 1:
            self._tokens -= 1
            return True
        return False


class _Owned:
    """Uma thread com dono, adotada antes do `start()` (D-107/D-108)."""

    __slots__ = ("_body", "cancelled", "done", "lock", "ran", "state", "thread")

    def __init__(self, factory: ThreadFactory, body: Callable[[], None], name: str) -> None:
        self.lock = threading.Lock()
        self.state = _IDLE
        self.ran = False
        self.cancelled = False
        self.done = threading.Event()
        self._body = body
        self.thread = factory(target=self._wrapper, name=name, daemon=False)
        if self.thread.daemon:
            msg = "thread daemon recusada"
            raise ValueError(msg)

    def _wrapper(self) -> None:
        try:
            with self.lock:
                if self.cancelled:
                    return
                self.ran = True
            self._body()
        except BaseException:  # noqa: S110 - so audit/ loga; a causa e descartada (D-017)
            pass
        finally:
            self.done.set()

    def start(self) -> bool:
        """`True` se o `start()` retornou. Falha: cancela se ainda nao entrou."""
        with self.lock:
            self.state = _STARTING
        failed = False
        try:
            self.thread.start()
        except BaseException:  # inicio incerto; a causa e descartada
            failed = True
        if failed:
            with self.lock:
                if not self.ran:
                    self.cancelled = True
            return False
        with self.lock:
            self.state = _STARTED
        return True

    def joinable(self) -> bool:
        with self.lock:
            started = self.state == _STARTED or self.ran
        return started or self.done.is_set()

    def cancelled_before_entering(self) -> bool:
        """Prova de que o alvo nunca toca recurso algum (cancelado sem entrar)."""
        with self.lock:
            return self.cancelled and not self.ran

    def settled(self) -> bool:
        """Termino FISICO comprovado, ou `start()` nunca tentado."""
        with self.lock:
            if not self.ran and self.state != _STARTED:
                self.cancelled = True
            state = self.state
        if state == _IDLE:
            return True
        return self.done.is_set() and not self.thread.is_alive()


class _Connection:
    __slots__ = ("authenticated", "close_failed", "closed", "deadline", "outcome", "owned", "sock")

    def __init__(self, sock: socket.socket, deadline: Deadline) -> None:
        self.sock = sock
        self.deadline = deadline
        self.owned: _Owned | None = None
        self.authenticated = False
        self.closed = False
        self.close_failed = False
        self.outcome: SessionOutcome | None = None


def _close_socket(sock: socket.socket) -> bool:
    """`True` so se `close()` concluiu sem erro. Nao e repetido depois de falhar."""
    try:
        sock.close()
    except OSError:
        return False
    return sock.fileno() == -1


def _bind_address(settings: PgwireSettings, resolved: Sequence[str] | None) -> str:
    if settings.bind_is_hostname:
        if resolved is None or isinstance(resolved, str) or len(resolved) != 1:
            raise ConfigError("pgwire: bind por hostname exige um endereco literal resolvido")
        candidate = resolved[0]
    else:
        if resolved is not None:
            raise ConfigError("pgwire: endereco resolvido so vale para bind por hostname")
        candidate = settings.bind
    try:
        ipaddress.ip_address(candidate)
    except (ValueError, TypeError):
        candidate = ""
    if not candidate:
        raise ConfigError("pgwire: endereco de bind invalido")
    return candidate


class PgwireListener:
    """Listener de uma porta; dono do socket, do acceptor e das conexoes."""

    def __init__(  # noqa: PLR0913 - colaboradores ja preparados, keyword-only
        self,
        settings: PgwireSettings,
        *,
        principal: PrincipalCredential,
        tls: ServerTls | None,
        alias_accepted: Callable[[str], bool],
        resolved_addresses: Sequence[str] | None = None,
        test_port: int | None = None,
        transport: TransportLimits | None = None,
        clock: Callable[[], float] = time.monotonic,
        thread_factory: ThreadFactory = threading.Thread,
    ) -> None:
        # Settings injetados sao revalidados AQUI, antes de qualquer efeito.
        validate(settings)
        if settings.tls_configured != (tls is not None):
            raise ConfigError("pgwire: contexto TLS incoerente com as settings")
        if settings.tls_required and tls is None:
            raise ConfigError("pgwire: bind fora de loopback exige TLS")
        if test_port is not None and test_port != 0:
            raise ConfigError("pgwire: porta de teste so pode ser efemera")
        if not isinstance(principal, PrincipalCredential) or not callable(alias_accepted):
            raise ConfigError("pgwire: colaboradores do listener invalidos")
        self._address = _bind_address(settings, resolved_addresses)
        self._port = settings.port if test_port is None else 0
        self._settings = settings
        self._principal = principal
        self._tls = tls
        self._alias_accepted = alias_accepted
        limits = settings.limits
        self._driver_limits = DriverLimits(
            limits.startup_deadline_ms,
            settings.idle_timeout_ms,
            transport if transport is not None else TransportLimits(poll_ms=limits.poll_ms),
        )
        self._poll = limits.poll_ms / 1000
        self._pre_auth_slots = limits.pre_auth_slots
        self._session_slots = settings.max_sessions
        self._thread_factory = thread_factory
        self._lock = threading.Lock()
        self._reap_lock = threading.Lock()
        self._stop = threading.Event()
        self._state = ListenerState.NEW
        self._bucket = _AdmissionBucket(
            limits.admission_burst, limits.admission_refill_per_s, clock
        )
        self._pre_auth = 0
        self._auth = 0
        self._connections: list[_Connection] = []
        self._retained: list[socket.socket] = []
        self._socket: socket.socket | None = None
        self._socket_closed = False
        self._socket_close_failed = False
        self._start_in_flight = False
        # Adotado ANTES do start (D-107): o acceptor existe como registro.
        self._acceptor = _Owned(thread_factory, self._accept_loop, "maskgw-pgwire-acceptor")

    # -- leitura -------------------------------------------------------------

    @property
    def port(self) -> int:
        sock = self._socket
        if sock is None or self._socket_closed:
            msg = "listener sem socket aberto"
            raise RuntimeError(msg)
        return int(sock.getsockname()[1])

    def status(self) -> ListenerStatus:
        with self._lock:
            return ListenerStatus(
                self._state,
                self._pre_auth,
                self._auth,
                len(self._connections),
                len(self._retained),
            )

    def owns_current_thread(self) -> bool:
        current = threading.current_thread()
        if self._acceptor.thread is current:
            return True
        with self._lock:
            records = list(self._connections)
        return any(rec.owned is not None and rec.owned.thread is current for rec in records)

    def __repr__(self) -> str:
        return f"PgwireListener(state={self.status().state.value})"

    # -- start -----------------------------------------------------------------

    def start(self) -> None:
        """Bind sincrono e acceptor. Falha parcial conserva o ownership."""
        if self.owns_current_thread():
            msg = "start recusado a partir de uma thread do listener"
            raise RuntimeError(msg)
        with self._lock:
            if self._state is not ListenerState.NEW:
                raise PgwireListenerError("pgwire: listener ja iniciado ou encerrado")
            self._state = ListenerState.STARTING
            # Enquanto o start estiver em voo, `stop()` nao pode concluir: o
            # bind ainda pode criar recursos.
            self._start_in_flight = True
        try:
            self._start_body()
        finally:
            with self._lock:
                self._start_in_flight = False

    def _start_body(self) -> None:
        if not self._bind():
            raise PgwireListenerError("pgwire: bind do listener falhou")
        with self._lock:
            proceed = self._state is ListenerState.STARTING and not self._stop.is_set()
            if proceed:
                self._state = ListenerState.RUNNING
        if not proceed:
            # Parada pedida durante o bind: desfaz o que este start criou e
            # NAO inicia o acceptor. O `stop()` seguinte recolhe e conclui.
            self._close_listener_socket()
            raise PgwireListenerError("pgwire: listener parado durante o inicio")
        if not self._acceptor.start():
            # Inicio incerto: nenhuma admissao; o dono retem e `stop()` recolhe.
            self._mark_broken()
            self._stop.set()
            raise PgwireListenerError("pgwire: inicio do listener falhou")

    def _bind(self) -> bool:
        """Cria, adota e liga o socket. `False` com o socket ja tratado."""
        failed = False
        sock: socket.socket | None = None
        try:
            # Endereco numerico ja validado: AI_NUMERICHOST nunca consulta DNS.
            family, kind, proto, _, address = socket.getaddrinfo(
                self._address,
                self._port,
                type=socket.SOCK_STREAM,
                flags=socket.AI_NUMERICHOST | socket.AI_PASSIVE,
            )[0]
            sock = socket.socket(family, kind, proto)
            self._socket = sock  # adotado antes de qualquer outro efeito
            if os.name == "nt":
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(address)
            sock.listen(self._pre_auth_slots)
            sock.settimeout(self._poll)
        except (OSError, IndexError, ValueError):
            failed = True
        if not failed:
            return True
        with self._lock:
            if self._state is ListenerState.STARTING:
                self._state = ListenerState.INCOMPLETE
        self._stop.set()
        if sock is not None:
            self._close_listener_socket()
        return False

    # -- admissao ------------------------------------------------------------

    def _mark_broken(self) -> None:
        with self._lock:
            if self._state in (ListenerState.RUNNING, ListenerState.STARTING):
                self._state = ListenerState.BROKEN

    def _accept_loop(self) -> None:
        """Corpo do acceptor. Qualquer excecao inesperada vira `broken`.

        Conter a excecao nao basta: o estado precisa deixar de ser `running`,
        honestamente. A causa e descartada; o recolhimento fica com `stop()`.
        """
        broken = False
        try:
            self._accept_body()
        except BaseException:
            broken = True
        if broken:
            self._mark_broken()

    def _accept_body(self) -> None:
        sock = self._socket
        if sock is None:
            return
        while not self._stop.is_set():
            self._reap()
            with self._lock:
                admitting = self._state is ListenerState.RUNNING
            if not admitting:
                # `broken`: nada e aceito (o backlog do SO e o teto); so recolhe.
                self._stop.wait(self._poll)
                continue
            conn: socket.socket | None = None
            fatal = False
            try:
                conn, _ = sock.accept()
            except TimeoutError:
                continue
            except (ConnectionResetError, ConnectionAbortedError):
                continue
            except Exception:  # OSError ou qualquer falha inesperada do accept
                fatal = True
            if fatal or conn is None:
                self._mark_broken()
                continue
            # Prazo absoluto da conexao: criado AGORA, nunca renovado.
            deadline = Deadline(self._driver_limits.startup_deadline_ms / 1000)
            admitted = False
            try:
                self._admit(conn, deadline)
                admitted = True
            except BaseException:
                admitted = False
            if not admitted:
                # Falha inesperada na admissao: o socket, se nao foi adotado por
                # um registro, e fechado pelo dono (ou retido se o close falhar).
                self._mark_broken()
                self._release_unregistered(conn)
        self._reap()

    def _release_unregistered(self, conn: socket.socket) -> None:
        with self._lock:
            registered = any(record.sock is conn for record in self._connections)
            retained = any(sock is conn for sock in self._retained)
        if registered or retained:
            return
        if not _close_socket(conn):
            with self._lock:
                self._retained.append(conn)

    def _admit(self, conn: socket.socket, deadline: Deadline) -> None:
        record: _Connection | None = None
        with self._lock:
            admitted = (
                self._state is ListenerState.RUNNING
                and self._bucket.take()  # um token por tentativa aceita
                and self._pre_auth < self._pre_auth_slots
            )
            if admitted:
                candidate = _Connection(conn, deadline)
                created = True
                try:
                    candidate.owned = _Owned(
                        self._thread_factory,
                        lambda: self._serve(candidate),
                        "maskgw-pgwire-connection",
                    )
                except Exception:
                    created = False
                if created:
                    self._connections.append(candidate)  # adotado ANTES do start
                    self._pre_auth += 1
                    record = candidate
        if record is None or record.owned is None:
            self._refuse(conn)
            return
        if not record.owned.start():
            # Inicio incerto: retem registro e vaga; nenhuma admissao nova.
            self._mark_broken()

    def _refuse(self, conn: socket.socket) -> None:
        """`53300` em melhor esforco, sem bloquear, e fecha. Sem thread."""
        with contextlib.suppress(OSError):
            conn.setblocking(False)
            conn.send(_REFUSAL)
        with contextlib.suppress(OSError):
            conn.shutdown(socket.SHUT_WR)
        if not _close_socket(conn):
            with self._lock:
                self._retained.append(conn)
            self._mark_broken()

    def _promote(self, record: _Connection) -> bool:
        """Reserva de sessao (callback do driver): pre-auth -> auth, ate S."""
        with self._lock:
            if self._state is not ListenerState.RUNNING or self._stop.is_set():
                return False
            if record.authenticated or self._auth >= self._session_slots:
                return False
            self._auth += 1
            self._pre_auth -= 1
            record.authenticated = True
            return True

    def _serve(self, record: _Connection) -> None:
        outcome: SessionOutcome | None = None
        try:
            result = run_startup_session(
                record.sock,
                principal=self._principal,
                tls=self._tls,
                tls_required=self._settings.tls_required,
                alias_accepted=self._alias_accepted,
                reserve_session=lambda: self._promote(record),
                limits=self._driver_limits,
                stop=self._stop.is_set,
                deadline=record.deadline,
            )
            outcome = result.outcome
        except BaseException:  # defeito: categoria fixa, nada guardado
            outcome = SessionOutcome.INTERNAL_ERROR
        record.outcome = outcome

    # -- recolhimento ----------------------------------------------------------

    def _reap(self) -> None:
        """Fecha e remove so o que tem prova fisica. Nunca chamado com o lock."""
        with self._reap_lock:
            with self._lock:
                records = list(self._connections)
            for record in records:
                owned = record.owned
                if owned is None:
                    continue
                settled = owned.settled()
                closable = settled or owned.cancelled_before_entering()
                if closable and not record.closed and not record.close_failed:
                    if _close_socket(record.sock):
                        record.closed = True
                    else:
                        record.close_failed = True
                        self._mark_broken()
                if settled and record.closed:
                    with self._lock:
                        self._connections.remove(record)
                        if record.authenticated:
                            self._auth -= 1
                        else:
                            self._pre_auth -= 1

    def _close_listener_socket(self) -> None:
        if self._socket is None or self._socket_closed or self._socket_close_failed:
            return
        if _close_socket(self._socket):
            self._socket_closed = True
        else:
            self._socket_close_failed = True

    # -- stop --------------------------------------------------------------------

    def request_stop(self) -> None:
        """Fecha a admissao e sinaliza, SEM esperar nada. Curto e idempotente.

        Usado pelo composition root para fechar TODAS as admissoes antes de
        drenar o trabalho v2 aceito. Nao faz `join`, `close` nem I/O; nao e
        prova de nada: o recolhimento com prova continua sendo `stop()`.
        """
        with self._lock:
            if self._state is ListenerState.NEW:
                self._state = ListenerState.STOPPED
            elif self._state in (
                ListenerState.STARTING,
                ListenerState.RUNNING,
                ListenerState.BROKEN,
            ):
                self._state = ListenerState.STOPPING
            self._stop.set()

    def stop(self) -> None:
        """Permanente e idempotente. `incomplete` sem prova fisica de tudo."""
        if self.owns_current_thread():
            msg = "parada recusada a partir de uma thread do listener"
            raise RuntimeError(msg)
        with self._lock:
            if self._state is ListenerState.NEW:
                self._state = ListenerState.STOPPED
                self._stop.set()
                return
            if self._state is not ListenerState.STOPPED:
                self._state = ListenerState.STOPPING
            self._stop.set()
        acceptor = self._acceptor
        acceptor.settled()  # cancela um acceptor que nunca entrou
        if acceptor.joinable():
            acceptor.thread.join()
        with self._lock:
            records = list(self._connections)
        for record in records:
            if record.owned is None:
                continue
            record.owned.settled()
            if record.owned.joinable():
                record.owned.thread.join()
        self._reap()
        if acceptor.settled() or acceptor.cancelled_before_entering():
            self._close_listener_socket()
        with self._lock:
            retained = list(self._retained)
        complete = (
            acceptor.settled() and (self._socket is None or self._socket_closed) and not retained
        )
        with self._lock:
            # Um start em voo ainda pode criar socket/acceptor: sem prova.
            complete = complete and not self._connections and not self._start_in_flight
            self._state = ListenerState.STOPPED if complete else ListenerState.INCOMPLETE
        if not complete:
            raise PgwireListenerIncompleteError

    def __enter__(self) -> PgwireListener:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()


__all__ = [
    "ListenerState",
    "ListenerStatus",
    "PgwireListener",
    "PgwireListenerError",
    "PgwireListenerIncompleteError",
]
