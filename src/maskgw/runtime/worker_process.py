"""Private Linux worker entry, not a gateway ingress or an operational caller.

Imports are pure. The final process guards itself BEFORE any secret read/READY.
Only a trusted owner may supply its empty stdin pipe and private socket FD.
No stdout/stderr diagnostics, reconnect, retry, state repair or child spawn.
"""

from __future__ import annotations

import contextlib
import hmac
import os
import select
import socket
import stat
import sys
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, cast

from maskgw.db.postgres import PostgresAdapter
from maskgw.db.session_state import WorkerSessionState, WorkerSessionStateError
from maskgw.errors import CapabilityError, DatabaseError
from maskgw.pgwire.result_frame import (
    ResultDeadline,
    ResultErrorCategory,
    ResultFrameError,
    ResultLimits,
)
from maskgw.pgwire.transport import RawChannel, TransportError, TransportFailure, TransportLimits
from maskgw.runtime import worker_protocol as wire
from maskgw.runtime.linux_guard import GuardFacts, ProcessRole, protect_process
from maskgw.runtime.snapshot import (
    RecompiledSnapshot,
    SnapshotError,
    SnapshotFailure,
    SnapshotIdentity,
    recompile_snapshot,
)
from maskgw.runtime.worker_job import JobOutcome, run_job

_OPEN_SECONDS: Final = 12.0
_HEADER_SECONDS: Final = 10.0
_BODY_SECONDS: Final = 30.0
_MAX_PIPE_BYTES: Final = 66000
_IO_BLOCK: Final = 16384
_MIN_IDLE_MS: Final = 1000
_MAX_IDLE_MS: Final = 86400000
_ARGUMENTS: Final = 4
_MAX_DECIMAL_DIGITS: Final = 10
_MIN_PRIVATE_FD: Final = 3
_MAX_PRIVATE_FD: Final = 65535


class WorkerInputError(Exception):
    def __init__(self) -> None:
        super().__init__("entrada privada do worker recusada")


def _need(value: bool) -> None:
    if not value:
        raise WorkerInputError()


@dataclass(frozen=True, slots=True, repr=False)
class EntryArguments:
    fd: int
    parent_pid: int
    address_bytes: int
    idle_ms: int


def arguments(values: list[str]) -> EntryArguments:
    _need(type(values) is list and len(values) == _ARGUMENTS)
    _need(
        all(
            type(v) is str and 0 < len(v) <= _MAX_DECIMAL_DIGITS and v.isascii() and v.isdecimal()
            for v in values
        )
    )
    fd, parent, address, idle = (int(v) for v in values)
    _need(_MIN_PRIVATE_FD <= fd <= _MAX_PRIVATE_FD and 1 <= parent < (1 << 31))
    _need(64 * 1024 * 1024 <= address <= 4096 * 1024 * 1024)
    _need(_MIN_IDLE_MS <= idle <= _MAX_IDLE_MS)
    return EntryArguments(fd, parent, address, idle)


def child_environment() -> dict[str, str]:
    return {
        "PATH": "/opt/maskgw/venv/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "HOME": "/var/empty",
        "TMPDIR": "/tmp",  # noqa: S108 - dedicated, bounded private tmpfs in the qualified profile
        "MALLOC_ARENA_MAX": "1",
    }


def _read_pipe(fd: int, size: int, deadline: ResultDeadline) -> bytes:
    _need(type(size) is int and 0 <= size <= _MAX_PIPE_BYTES)
    deadline.check()
    buffer = bytearray(size)
    readv = cast(Callable[[int, list[memoryview]], int], getattr(os, "readv"))  # noqa: B009 - Linux binding after the platform guard
    offset = 0
    with memoryview(buffer) as view:
        while offset < size:
            deadline.check()
            ready, _, _ = select.select([fd], [], [], min(0.25, deadline.remaining()))
            if not ready:
                continue
            count = -1
            failed = False
            try:
                with view[offset : min(size, offset + _IO_BLOCK)] as piece:
                    count = readv(fd, [piece])
            except BlockingIOError:
                continue
            except OSError:
                failed = True
            _need(not failed and type(count) is int and 0 < count <= min(size - offset, _IO_BLOCK))
            offset += count
    deadline.check()
    return bytes(buffer)


def _read_init(deadline: ResultDeadline) -> wire.SecretInit:
    set_blocking = cast(Callable[[int, bool], None], getattr(os, "set_blocking"))  # noqa: B009 - Linux pipe support, guarded at entry
    set_blocking(0, False)
    header = _read_pipe(0, wire.HEADER_BYTES, deadline)
    kind, size = wire.parse_header(header)
    _need(kind is wire.Kind.INIT)
    data = _read_pipe(0, size, deadline)
    value = wire.decode_init(data)
    del data  # decoded snapshot has its own bounded copy; no original body retained
    while True:
        deadline.check()
        ready, _, _ = select.select([0], [], [], min(0.25, deadline.remaining()))
        if not ready:
            continue
        try:
            extra = os.read(0, 1)
        except BlockingIOError:
            continue
        _need(extra == b"")
        break
    wire.check_deadline(value.expires_at, now=time.monotonic(), maximum_seconds=_OPEN_SECONDS)
    return value


def _next(channel: RawChannel, idle_ms: int) -> tuple[wire.Kind, bytes] | None:
    idle = ResultDeadline(expires_at=time.monotonic() + idle_ms / 1000)
    first: bytes | None = None
    idle_end = False
    try:
        first = channel.recv_exact(1, idle)
    except TransportError as error:
        if error.kind in (TransportFailure.EOF, TransportFailure.TIMEOUT):
            idle_end = True
        else:
            raise
    if idle_end:
        return None
    _need(first is not None)
    header_deadline = ResultDeadline(expires_at=time.monotonic() + _HEADER_SECONDS)
    header = cast(bytes, first) + channel.recv_exact(wire.HEADER_BYTES - 1, header_deadline)
    kind, size = wire.parse_header(header)
    _need(kind in (wire.Kind.QUERY, wire.Kind.CLOSE))
    body_deadline = ResultDeadline(expires_at=time.monotonic() + _BODY_SECONDS)
    return kind, channel.recv_exact(size, body_deadline)


def _failure(error: BaseException) -> wire.WireFailure:  # noqa: PLR0911 - closed exact-type dispatch
    kind = type(error)
    if kind is MemoryError:
        return wire.WireFailure.MEMORY
    if kind in (WorkerInputError, wire.WorkerProtocolError):
        return wire.WireFailure.PROTOCOL
    if kind in (WorkerSessionStateError, CapabilityError, DatabaseError):
        return wire.WireFailure.CONNECTION
    if kind is SnapshotError:
        return (
            wire.WireFailure.RESOURCE
            if cast(SnapshotError, error).category is SnapshotFailure.UNAVAILABLE
            else wire.WireFailure.PROTOCOL
        )
    if kind is ResultFrameError:
        if cast(ResultFrameError, error).memory_exhausted:
            return wire.WireFailure.MEMORY
        if cast(ResultFrameError, error).category is ResultErrorCategory.DEADLINE:
            return wire.WireFailure.DEADLINE
        return wire.WireFailure.PROTOCOL
    if kind is TransportError:
        return (
            wire.WireFailure.DEADLINE
            if cast(TransportError, error).kind is TransportFailure.TIMEOUT
            else wire.WireFailure.CONNECTION
        )
    return wire.WireFailure.INTERNAL


def _one_job(
    channel: RawChannel,
    adapter: PostgresAdapter,
    baseline: WorkerSessionState,
    request: wire.Query,
    limits: ResultLimits,
) -> bool:
    deadline = ResultDeadline(expires_at=request.expires_at)
    outcome: JobOutcome | None = None
    failure: wire.WireFailure | None = None
    try:
        wire.check_deadline(
            request.expires_at,
            now=time.monotonic(),
            maximum_seconds=adapter.settings.statement_timeout_ms / 1000 + 10.0,
        )
        baseline.require_same(adapter._worker_session_state())
        deadline.check()
        outcome = run_job(
            adapter,
            request.sql.decode("utf-8"),
            identity=request.key.result_identity(request.job_id),
            limits=limits,
            deadline=deadline,
        )
        if outcome.failure is None or outcome.can_continue:
            baseline.require_same(adapter._worker_session_state())
            deadline.check()
    except BaseException as error:
        outcome = None
        failure = _failure(error)
        with contextlib.suppress(BaseException):
            traceback.clear_frames(error.__traceback__)
    # Network emission is OUTSIDE computation handling: a partial response can
    # never be followed by a second ERROR for the same job.
    if failure is not None:
        channel.send_all(
            wire.encode_error(wire.ErrorReply(request.key, request.job_id, failure, False)),
            deadline,
        )
        return False
    _need(outcome is not None)
    result = cast(JobOutcome, outcome)
    if result.failure is not None:
        channel.send_all(
            wire.encode_error(
                wire.ErrorReply(
                    request.key,
                    request.job_id,
                    wire.WireFailure[result.failure.name],
                    result.can_continue,
                )
            ),
            deadline,
        )
        deadline.check()
        return result.can_continue
    _need(type(result.frame) is bytes)
    channel.send_all(wire.encode_result_notice(), deadline)
    channel.send_all(cast(bytes, result.frame), deadline)
    channel.send_all(wire.encode_done(request.key, request.job_id), deadline)
    deadline.check()
    return True


def _loop(  # noqa: PLR0913 - explicit private collaborators, no hidden global session
    channel: RawChannel,
    adapter: PostgresAdapter,
    baseline: WorkerSessionState,
    *,
    key: wire.SessionKey,
    limits: ResultLimits,
    idle_ms: int,
) -> int:
    previous = 0
    while True:
        message = _next(channel, idle_ms)
        if message is None or message[0] is wire.Kind.CLOSE:
            return 0
        request = wire.decode_query(message[1])
        _need(request.key == key and request.job_id == previous + 1)
        previous = request.job_id
        if not _one_job(channel, adapter, baseline, request, limits):
            return 1


def _serve(sock: socket.socket, args: EntryArguments, guard: GuardFacts, opening_end: float) -> int:
    channel = RawChannel(sock, stop=lambda: False, limits=TransportLimits())
    local = ResultDeadline(expires_at=opening_end)
    channel.send_all(
        wire.encode_guard(guard.pid, guard.parent_pid, guard.address_limit_bytes), local
    )
    value: wire.SecretInit | None = None
    value = _read_init(local)
    opening = ResultDeadline(expires_at=value.expires_at)
    key, limits = value.key, value.limits
    adapter: PostgresAdapter | None = None
    opened = False
    failure: wire.WireFailure | None = None
    compiled: RecompiledSnapshot | None = None
    try:
        compiled = recompile_snapshot(
            value.snapshot,
            expected=SnapshotIdentity(
                datasource_id=key.datasource_text(),
                generation=key.generation,
                record_revision=key.record_revision,
            ),
        )
        _need(limits.max_rows == compiled.config.database.max_rows)
        tag = hmac.digest(value.nonce, value.snapshot, "sha256")
        value = None
        opening.check()
        adapter = PostgresAdapter(
            compiled.connection_target(),
            compiled.engine,
            settings=compiled.config.database,
            sql_policy=compiled.config.sql,
            verify_capabilities=True,
        )
        compiled = None
        adapter.connect()
        baseline = adapter._worker_session_state()
        opening.check()
        opened = True
        # Mark emission before sending: partial OPENED cannot be followed by ERROR.
        channel.send_all(wire.encode_opened(tag), opening)
        del tag
        return _loop(channel, adapter, baseline, key=key, limits=limits, idle_ms=args.idle_ms)
    except BaseException as error:
        if not opened:
            failure = _failure(error)
        with contextlib.suppress(BaseException):
            traceback.clear_frames(error.__traceback__)
    finally:
        value = None
        if adapter is not None:
            adapter.close()  # once; the parent kills/reaps if this blocks
    if failure is not None:
        channel.send_all(wire.encode_error(wire.ErrorReply(key, 0, failure, False)), opening)
    return 1


def main(argv: list[str] | None = None) -> int:
    opening_end = time.monotonic() + _OPEN_SECONDS
    sock: socket.socket | None = None
    args: EntryArguments | None = None
    fd_owned = False
    try:
        args = arguments(sys.argv[1:] if argv is None else argv)
        guard = protect_process(
            role=ProcessRole.WORKER,
            address_limit_bytes=args.address_bytes,
            expected_parent_pid=args.parent_pid,
        )
        fd_owned = True  # never touch any descriptor when platform/guard admission failed
        _need(
            sys.flags.isolated == 1
            and sys.flags.dont_write_bytecode == 1
            and sys.flags.optimize == 0
        )
        _need(dict(os.environ) == child_environment())
        _need(stat.S_ISSOCK(os.fstat(args.fd).st_mode) and stat.S_ISFIFO(os.fstat(0).st_mode))
        sock = socket.socket(fileno=args.fd)
        _need(
            sock.family == getattr(socket, "AF_UNIX")  # noqa: B009 - Linux-only qualified entry
            and sock.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) == socket.SOCK_STREAM
        )
        sock.getpeername()  # must be connected, no claim of peer PID authentication
        sock.set_inheritable(False)
        return _serve(sock, args, guard, opening_end)
    except BaseException:
        return 1  # no traceback, argv, secret, nonce or native diagnostic to stdout/stderr
    finally:
        if sock is not None:
            with contextlib.suppress(OSError):
                sock.close()
        elif args is not None and fd_owned:
            with contextlib.suppress(OSError):
                os.close(args.fd)


if __name__ == "__main__":
    raise SystemExit(main())
