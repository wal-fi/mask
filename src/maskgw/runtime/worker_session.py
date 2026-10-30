"""Private Linux worker owner. No operational caller, ingress or parent SQL.

Trusted caller applies the controller guard BEFORE secrets, reserves a session
of the SAME captured generation, registers this handle, then calls open on the
main or a dedicated non-daemon thread living until reap. Never a thread pool.
Logical credits are not an OS quota; native/installed/C1 gates remain separate.
"""

from __future__ import annotations

import contextlib
import hmac
import os
import select
import socket
import subprocess
import sys
import threading
import time
from _thread import LockType
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import BinaryIO, Final, NoReturn, cast

from maskgw.pgwire.result_frame import ResultDeadline, ResultFrameError, ResultLimits
from maskgw.pgwire.result_receiver import (
    ReceiverError,
    ReceiverFailure,
    ResultReceiver,
    ResultSummary,
    _clear_error,
)
from maskgw.pgwire.transport import RawChannel, TlsChannel, TransportError, TransportLimits
from maskgw.runtime import worker_protocol as wire
from maskgw.runtime.budget import (
    BudgetLedger,
    BudgetToken,
    CleanupConfirmation,
    OutputReleaseOutcome,
    ReleaseOutcome,
)
from maskgw.runtime.linux_guard import GuardFacts, ProcessRole

_OPEN_SECONDS: Final = 12.0
_SEND_SECONDS: Final = 30.0
_CLEAN_SECONDS: Final = 3.0
_REAP_ATTEMPTS: Final = 3
_REAP_SECONDS: Final = 0.25
_MAX_SQL: Final = 65536
_BLOCK: Final = 16384
_MAX_JOB: Final = (1 << 63) - 1
_MIN_IDLE_MS: Final = 1000
_MAX_IDLE_MS: Final = 86400000
_MAX_STATEMENT_MS: Final = 600000
_CONTROL_BYTES: Final = 256


class SessionFailure(StrEnum):
    STATE = "WORKER_SESSION_STATE"
    OPEN = "WORKER_SESSION_OPEN"
    JOB = "WORKER_SESSION_JOB"
    OUTPUT = "WORKER_SESSION_OUTPUT"
    CLEANUP = "WORKER_SESSION_CLEANUP"


class WorkerSessionError(Exception):
    def __init__(self, category: SessionFailure) -> None:
        self.category = category
        super().__init__(category.value)


def _fail(category: SessionFailure) -> NoReturn:
    raise WorkerSessionError(category) from None


def _need(condition: bool) -> None:
    if not condition:
        _fail(SessionFailure.STATE)


class SessionState(StrEnum):
    NEW = "NEW"
    OPENING = "OPENING"
    READY = "READY"
    RESULT = "RESULT"
    CLOSING = "CLOSING"
    HELD = "HELD"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class WorkerProfile:
    """Internal public limits, not a containment qualification/config surface."""

    address_bytes: int
    idle_ms: int
    statement_timeout_ms: int
    output_overhead_bytes: int

    def __post_init__(self) -> None:
        _need(
            all(
                type(v) is int
                for v in (
                    self.address_bytes,
                    self.idle_ms,
                    self.statement_timeout_ms,
                    self.output_overhead_bytes,
                )
            )
            and 64 * 1024 * 1024 <= self.address_bytes <= 4096 * 1024 * 1024
            and _MIN_IDLE_MS <= self.idle_ms <= _MAX_IDLE_MS
            and 1 <= self.statement_timeout_ms <= _MAX_STATEMENT_MS
            and 1 <= self.output_overhead_bytes <= (1 << 63) - 1
        )


def _environment() -> dict[str, str]:
    # Fixed public spawn profile, tested equal to the child allowlist. No inherited env.
    return {
        "PATH": "/opt/maskgw/venv/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "HOME": "/var/empty",
        "TMPDIR": "/tmp",  # noqa: S108 - bounded private profile tmpfs
        "MALLOC_ARENA_MAX": "1",
    }


def _deadline(seconds: float) -> ResultDeadline:
    return ResultDeadline(expires_at=time.monotonic() + seconds)


def _send_pipe(
    stream: BinaryIO, packet: bytes, deadline: ResultDeadline, stop: Callable[[], bool]
) -> None:
    fd = stream.fileno()
    blocking = cast(Callable[[int, bool], None], getattr(os, "set_blocking"))  # noqa: B009 - Linux-only entry
    blocking(fd, False)
    offset = 0
    with memoryview(packet) as view:
        while offset < len(view):
            deadline.check()
            _need(not stop())
            _, ready, _ = select.select([], [fd], [], min(0.25, deadline.remaining()))
            if not ready:
                continue
            try:
                with view[offset : min(len(view), offset + _BLOCK)] as piece:
                    sent = os.write(fd, piece)
            except BlockingIOError:
                continue
            _need(type(sent) is int and 0 < sent <= min(len(view) - offset, _BLOCK))
            offset += sent
    deadline.check()
    _need(not stop())
    stream.close()  # unbuffered PIPE: no flush of queued secret bytes
    _need(stream.closed)


def _control(
    channel: RawChannel, allowed: tuple[wire.Kind, ...], deadline: ResultDeadline
) -> tuple[wire.Kind, bytes]:
    kind, size = wire.parse_header(channel.recv_exact(wire.HEADER_BYTES, deadline))
    _need(kind in allowed and size <= _CONTROL_BYTES)  # BEFORE any body read/allocation
    return kind, channel.recv_exact(size, deadline)


def _exchange_init(  # noqa: PLR0913, PLR0917 - bounded handshake with explicit trusted collaborators
    channel: RawChannel,
    stream: BinaryIO,
    snapshot: bytes,
    key: wire.SessionKey,
    limits: ResultLimits,
    deadline: ResultDeadline,
    stop: Callable[[], bool],
) -> None:
    # Locals live only during the handshake, no secret retained on the handle.
    nonce = os.urandom(32)
    expected = hmac.digest(nonce, snapshot, "sha256")
    packet = wire.encode_init(
        wire.SecretInit(key, limits, float(deadline.expires_at), nonce, snapshot)
    )
    _send_pipe(stream, packet, deadline, stop)
    del packet, snapshot, nonce
    kind, body = _control(channel, (wire.Kind.OPENED, wire.Kind.ERROR), deadline)
    _need(kind is wire.Kind.OPENED and hmac.compare_digest(wire.decode_opened(body), expected))
    deadline.check()


class WorkerSession:
    """Exclusive owner, sequential jobs, no raw/frame-returning API or finalizer.

    Only request_stop is cross-thread. Closing HELD retries physical cleanup but
    never overrides uncertainty already recorded about handles/output/spawn.
    """

    def __init__(  # noqa: PLR0913 - explicit trusted generation/ownership dependencies
        self,
        ledger: BudgetLedger,
        token: BudgetToken,
        *,
        lock: LockType,
        key: wire.SessionKey,
        limits: ResultLimits,
        profile: WorkerProfile,
        guard: GuardFacts,
    ) -> None:
        _need(
            type(ledger) is BudgetLedger and type(token) is BudgetToken and type(lock) is LockType
        )
        _need(
            type(key) is wire.SessionKey
            and type(limits) is ResultLimits
            and type(profile) is WorkerProfile
        )
        wire.SessionKey.__post_init__(key)
        ResultLimits.__post_init__(limits)
        WorkerProfile.__post_init__(profile)
        _need(
            sys.platform == "linux"
            and type(guard) is GuardFacts
            and guard.role is ProcessRole.CONTROLLER
            and guard.pid == os.getpid() == 1
            and guard.dumpable == 0
            and guard.core == (0, 0)
            and guard.parent_death_signal == 0
        )
        self._ledger, self._token, self._lock = ledger, token, lock
        self._key, self._limits, self._profile = key, limits, profile
        self._state = SessionState.NEW
        self._operation = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._ident: int | None = None
        self._adopted = False
        self._spawn_unknown = False
        self._uncertain = False
        self._process: subprocess.Popen[bytes] | None = None
        self._sock: socket.socket | None = None
        self._child_sock: socket.socket | None = None
        self._channel: RawChannel | None = None
        self._receiver: ResultReceiver | None = None
        self._job = 0
        self._idle_end = 0.0

    def __repr__(self) -> str:
        return "WorkerSession(<private>)"

    @property
    def state(self) -> SessionState:
        return self._state  # metadata only; never a synchronization claim

    def request_stop(self) -> None:
        self._stop.set()

    @contextlib.contextmanager
    def _exclusive(self) -> Iterator[None]:
        current = threading.current_thread()
        _need(
            self._thread is None
            or (self._thread is current and self._ident == threading.get_ident())
        )
        _need(self._operation.acquire(blocking=False))
        try:
            yield
        finally:
            self._operation.release()

    @contextlib.contextmanager
    def _coordinated(self, deadline: ResultDeadline) -> Iterator[None]:
        while True:
            deadline.check()
            if self._lock.acquire(timeout=min(0.25, deadline.remaining())):
                break
        try:
            yield
        finally:
            self._lock.release()

    def open(self, snapshot: bytes) -> None:
        with self._exclusive():
            _need(self._state is SessionState.NEW and not self._stop.is_set())
            _need(type(snapshot) is bytes and 1 <= len(snapshot) <= wire.MAX_SNAPSHOT_BYTES)
            _need(not threading.current_thread().daemon)
            self._thread, self._ident = threading.current_thread(), threading.get_ident()
            failed = False
            try:
                self._open(snapshot)
            except BaseException as error:
                self._uncertain |= not _clear_error(error)
                failed = True
            snapshot = b""
            if failed:
                self._cleanup(graceful=False)
                _fail(SessionFailure.OPEN)

    def _open(self, snapshot: bytes) -> None:
        deadline = _deadline(_OPEN_SECONDS)  # includes socketpair and Popen time
        with self._coordinated(deadline):
            self._ledger.adopt_session(self._token)
            self._adopted = True  # second owner never acquires/relinquishes this token
        self._state = SessionState.OPENING
        _need(not self._stop.is_set())
        family = getattr(socket, "AF_UNIX")  # noqa: B009 - Linux guarded
        self._sock, self._child_sock = socket.socketpair(family, socket.SOCK_STREAM)
        self._sock.set_inheritable(False)
        self._child_sock.set_inheritable(False)
        child_fd = self._child_sock.fileno()
        self._spawn_unknown = True  # if spawn raises, do not pretend no child existed
        self._process = subprocess.Popen(  # noqa: S603 - exact installed interpreter/module, no shell or secret argv
            [
                sys.executable,
                "-I",
                "-B",
                "-m",
                "maskgw.runtime.worker_process",
                str(child_fd),
                str(os.getpid()),
                str(self._profile.address_bytes),
                str(self._profile.idle_ms),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=_environment(),
            close_fds=True,
            pass_fds=(child_fd,),
            bufsize=0,
        )
        self._spawn_unknown = False
        deadline.check()  # late spawn gets NO INIT byte
        _need(not self._stop.is_set())
        self._child_sock.close()
        _need(self._child_sock.fileno() == -1)
        self._child_sock = None
        self._channel = RawChannel(self._sock, stop=self._stop.is_set, limits=TransportLimits())
        _, body = _control(self._channel, (wire.Kind.GUARD_READY,), deadline)
        _need(
            wire.decode_guard(body) == (self._process.pid, os.getpid(), self._profile.address_bytes)
        )
        _need(self._process.stdin is not None)
        _exchange_init(
            self._channel,
            cast(BinaryIO, self._process.stdin),
            snapshot,
            self._key,
            self._limits,
            deadline,
            self._stop.is_set,
        )
        _need(not self._stop.is_set())
        self._state = SessionState.READY
        self._set_idle()

    def _set_idle(self) -> None:
        # Finish parent send strictly before the child idle boundary. Scheduling is
        # not a promise of acceptance: any idle race remains a fatal EOF.
        self._idle_end = time.monotonic() + self._profile.idle_ms / 1000 - 0.25

    def query(self, sql: bytes) -> wire.ErrorReply | None:
        with self._exclusive():
            _need(self._state is SessionState.READY and self._job < _MAX_JOB)
            _need(type(sql) is bytes and 1 <= len(sql) <= _MAX_SQL)
            failure = False
            result: wire.ErrorReply | None = None
            try:
                result = self._query(sql)
            except BaseException as error:
                self._uncertain |= not _clear_error(error)
                failure = True
            sql = b""
            if failure:
                self._cleanup(graceful=False)
                _fail(SessionFailure.JOB)
            if result is not None and not result.can_continue:
                self._cleanup(graceful=False)
            return result

    def _query(self, sql: bytes) -> wire.ErrorReply | None:
        _need(self._channel is not None and not self._stop.is_set())
        channel = cast(RawChannel, self._channel)
        deadline = _deadline(self._profile.statement_timeout_ms / 1000 + 10.0)
        self._job += 1
        packet = wire.encode_query(
            wire.Query(self._key, self._job, float(deadline.expires_at), sql)
        )
        del sql
        send_deadline = ResultDeadline(expires_at=min(deadline.expires_at, self._idle_end))
        channel.send_all(packet, send_deadline)
        del packet
        kind, body = _control(channel, (wire.Kind.ERROR, wire.Kind.RESULT), deadline)
        if kind is wire.Kind.ERROR:
            reply = wire.decode_error(body)
            _need(reply.key == self._key and reply.job_id == self._job)
            deadline.check()
            if reply.can_continue:
                self._set_idle()
            return reply
        receiver = ResultReceiver(
            self._ledger,
            self._token,
            lock=self._lock,
            expected=self._key.result_identity(self._job),
            limits=self._limits,
            overhead_bytes=self._profile.output_overhead_bytes,
            deadline=deadline,
        )  # maximum output pin acquired BEFORE any D-113 header/body read
        self._receiver = receiver
        receiver.receive(channel)
        _, body = _control(channel, (wire.Kind.DONE,), deadline)
        _need(wire.decode_done(body) == (self._key, self._job))
        deadline.check()
        self._set_idle()
        self._state = SessionState.RESULT  # the ONLY point where send_to becomes available
        return None

    def send_result_to(self, channel: RawChannel | TlsChannel) -> ResultSummary:
        with self._exclusive():
            _need(self._state is SessionState.RESULT and self._receiver is not None)
            failed = False
            summary: ResultSummary | None = None
            try:
                _need(not self._stop.is_set())
                summary = cast(ResultReceiver, self._receiver).send_to(
                    channel, deadline=_deadline(_SEND_SECONDS)
                )
                outcome = self._close_output()
                _need(outcome is not OutputReleaseOutcome.HELD)
                self._receiver = None
                self._state = SessionState.READY
            except BaseException as error:
                self._uncertain |= not _clear_error(error)
                failed = True
            if failed:
                self._cleanup(graceful=False)
                _fail(SessionFailure.OUTPUT)
            _need(summary is not None)
            return cast(ResultSummary, summary)

    def _reap(self, *, graceful: bool) -> bool:
        process = self._process
        if process is None:
            return not self._spawn_unknown
        if graceful:
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                process.wait(timeout=1.0)
        for _ in range(_REAP_ATTEMPTS):
            try:
                if process.poll() is not None:
                    return True  # Popen.poll performs waitpid/reaps on POSIX
            except OSError:
                pass
            with contextlib.suppress(OSError):
                process.kill()  # always BEFORE closing stdin, no flush deadlock
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                process.wait(timeout=_REAP_SECONDS)
        try:
            return process.poll() is not None
        except OSError:
            return False

    def _close_output(self) -> OutputReleaseOutcome:
        _need(self._receiver is not None)
        deadline = _deadline(_CLEAN_SECONDS)
        while True:
            deadline.check()
            try:
                return cast(ResultReceiver, self._receiver).close(deadline=deadline)
            except ReceiverError as error:
                if error.category is not ReceiverFailure.BUSY:
                    raise
                # Only a lock-acquisition refusal is retried. No receive/send or
                # ledger mutation/uncertainty is repeated as though it succeeded.

    def _cleanup(self, *, graceful: bool) -> ReleaseOutcome:
        if not self._adopted:
            return ReleaseOutcome.HELD  # no ownership acquired, never claim caller token released
        self._state = SessionState.CLOSING
        if graceful and self._channel is not None and not self._stop.is_set():
            with contextlib.suppress(TransportError, ResultFrameError, OSError):
                self._channel.send_all(wire.encode_close(), _deadline(1.0))
        self._stop.set()
        terminated = False
        try:
            terminated = self._reap(graceful=graceful)
        except BaseException:
            self._uncertain = True
        # No buffered writer. Still do not touch stdin while a child is alive.
        if terminated and self._process is not None and self._process.stdin is not None:
            try:
                self._process.stdin.close()
                _need(self._process.stdin.closed)
            except BaseException:
                self._uncertain = True
        for sock in (self._child_sock, self._sock):
            if sock is not None:
                try:
                    sock.close()
                    _need(sock.fileno() == -1)
                except BaseException:
                    self._uncertain = True
        output_clean = self._receiver is None
        if self._receiver is not None:
            try:
                output_outcome = self._close_output()
                output_clean = output_outcome is not OutputReleaseOutcome.HELD
            except BaseException:
                output_clean = False
            if output_clean:
                self._receiver = None
        outcome = ReleaseOutcome.HELD
        try:
            with self._coordinated(_deadline(_CLEAN_SECONDS)):
                self._ledger.begin_drain(self._token)
                outcome = self._ledger.release(
                    self._token,
                    CleanupConfirmation(
                        processes=terminated and not self._spawn_unknown,
                        threads=True,
                        pipes=terminated and not self._uncertain,
                        handles=not self._uncertain,
                        output=output_clean and not self._uncertain,
                    ),
                )
        except BaseException:
            outcome = ReleaseOutcome.HELD
        self._state = SessionState.HELD if outcome is ReleaseOutcome.HELD else SessionState.CLOSED
        return outcome

    def close(self) -> ReleaseOutcome:
        with self._exclusive():
            if self._state is SessionState.CLOSED:
                return ReleaseOutcome.ALREADY_RELEASED
            _need(self._adopted)
            return self._cleanup(graceful=self._state in (SessionState.READY, SessionState.RESULT))
