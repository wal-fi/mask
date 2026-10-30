"""Private worker loop with fakes. No native guard, child, database or socket."""

from __future__ import annotations

import hmac
import select
import socket
import stat
import time
from types import SimpleNamespace
from typing import Any, cast

import pytest

from maskgw.config.gateway import DatabaseSettings
from maskgw.db.session_state import WorkerSessionState, WorkerSessionStateError
from maskgw.pgwire.result_frame import (
    RESULT_HEADER_BYTES,
    ResultDeadline,
    ResultFrameError,
    ResultLimits,
)
from maskgw.pgwire.transport import RawChannel, TransportError, TransportFailure
from maskgw.runtime import worker_process as worker
from maskgw.runtime import worker_protocol as wire
from maskgw.runtime.linux_guard import GuardFacts, GuardFailure, ProcessGuardError, ProcessRole
from maskgw.runtime.worker_job import JobFailure, JobOutcome


def key() -> wire.SessionKey:
    return wire.SessionKey(b"s" * 16, b"d" * 16, 1, 2)


def query(job: int = 1, **changes: Any) -> wire.Query:
    args: dict[str, Any] = {
        "key": key(),
        "job_id": job,
        "expires_at": time.monotonic() + 1.0,
        "sql": b"SELECT 1",
    }
    return wire.Query(**(args | changes))


class Channel:
    def __init__(self, *, fail_send: int | None = None) -> None:
        self.sent: list[bytes] = []
        self.fail_send = fail_send

    def send_all(self, data: bytes, deadline: ResultDeadline) -> None:
        if deadline.remaining() <= 0:
            raise TransportError(TransportFailure.TIMEOUT)
        self.sent.append(data)
        if len(self.sent) == self.fail_send:
            raise OSError("PUBLIC_PARTIAL_SEND_MARKER")


class Baseline:
    def __init__(self, fail_at: int | None = None) -> None:
        self.calls = 0
        self.fail_at = fail_at

    def require_same(self, _other: object) -> None:
        self.calls += 1
        if self.calls == self.fail_at:
            raise WorkerSessionStateError()


def adapter() -> Any:
    return SimpleNamespace(
        settings=DatabaseSettings(statement_timeout_ms=1000, max_rows=10),
        _worker_session_state=object,
    )


def one_job(channel: Channel, state: Baseline, request: wire.Query) -> bool:
    # Only fake I/O/metadata collaborators are cast, not production input types.
    return worker._one_job(
        cast(RawChannel, channel),
        adapter(),
        cast(WorkerSessionState, state),
        request,
        ResultLimits(max_rows=10),
    )


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["3", "1", "268435456"],
        ["3", "1", "268435456", "1000", "extra"],
        ["0", "1", "268435456", "1000"],
        ["3", "0", "268435456", "1000"],
        ["3", "1", "268435456", "0"],
        ["3", "1", "268435456", "-1"],
        ["3", "1", "268435456", "1.0"],
        ["3", "1", "268435456", "86400001"],
        ["3", "1", "0", "1000"],
        ["3", "1", "4294967297", "1000"],
        ["3", "1", "268435456", "\u0661\u0660\u0660\u0660"],
    ],
    ids=[
        "empty",
        "missing",
        "extra",
        "stdio-fd",
        "ppid0",
        "idle0",
        "negative",
        "float",
        "idle-over",
        "as0",
        "as-over",
        "unicode",
    ],
)
def test_entry_args_refuse_without_effect(args: list[str]) -> None:
    with pytest.raises(worker.WorkerInputError):
        worker.arguments(args)


def test_public_entry_limits_and_explicit_environment() -> None:
    assert worker.arguments(["3", "1", "67108864", "1000"]).idle_ms == 1000
    assert worker.arguments(["65535", "2147483647", "4294967296", "86400000"]).fd == 65535
    assert len(worker.child_environment()) == 6
    assert not any(k.startswith(("MASKGW", "PYTHON", "PG")) for k in worker.child_environment())


def test_guard_failure_never_touches_or_closes_host_descriptors(monkeypatch: Any) -> None:
    def refused(**_kwargs: Any) -> None:
        raise ProcessGuardError(GuardFailure.UNSUPPORTED)

    monkeypatch.setattr(worker, "protect_process", refused)
    monkeypatch.setattr(
        worker, "os", SimpleNamespace(close=lambda _fd: pytest.fail("closed unadopted fd"))
    )
    assert worker.main(["3", "1", "268435456", "1000"]) == 1


def test_main_guard_before_environment_fd_and_serve(monkeypatch: Any) -> None:
    events: list[str] = []

    def protect(**_kwargs: Any) -> Any:
        events.append("guard")
        return SimpleNamespace(pid=33, parent_pid=1, address_limit_bytes=268435456)

    class OS:
        @property
        def environ(self) -> dict[str, str]:
            assert events == ["guard"]
            events.append("environment")
            return worker.child_environment()

        def fstat(self, fd: int) -> Any:
            events.append("fstat")
            return SimpleNamespace(st_mode=stat.S_IFIFO if fd == 0 else stat.S_IFSOCK)

    sock = SimpleNamespace(
        family=1,
        getsockopt=lambda *_a: 1,
        getpeername=lambda: "",
        set_inheritable=lambda value: (
            events.append("non-inheritable") if value is False else pytest.fail("inheritable")
        ),
        close=lambda: events.append("close"),
    )
    monkeypatch.setattr(worker, "os", OS())
    monkeypatch.setattr(
        worker,
        "socket",
        SimpleNamespace(
            socket=lambda **_kw: sock, AF_UNIX=1, SOL_SOCKET=1, SOCK_STREAM=1, SO_TYPE=3
        ),
    )
    monkeypatch.setattr(worker, "protect_process", protect)
    monkeypatch.setattr(
        worker,
        "sys",
        SimpleNamespace(flags=SimpleNamespace(isolated=1, dont_write_bytecode=1, optimize=0)),
    )

    def serve(*_args: Any) -> int:
        events.append("serve")
        return 0

    monkeypatch.setattr(worker, "_serve", serve)
    assert worker.main(["3", "1", "268435456", "1000"]) == 0
    assert events[0:2] == ["guard", "environment"]
    assert events[-3:] == ["non-inheritable", "serve", "close"]


def test_pipe_read_is_bounded_fragmented_and_exact(monkeypatch: Any) -> None:
    raw = bytearray(b"x" * 65644)  # maximum INIT metadata + 64KiB snapshot, over pipe capacity
    pieces: list[int] = []

    def readv(_fd: int, buffers: list[memoryview]) -> int:
        piece = buffers[0]
        pieces.append(len(piece))
        size = min(len(piece), len(raw), 3000)
        piece[:size] = raw[:size]
        del raw[:size]
        return size

    monkeypatch.setattr(worker, "os", SimpleNamespace(readv=readv))
    monkeypatch.setattr(select, "select", lambda *_a: ([0], [], []))
    deadline = ResultDeadline(expires_at=time.monotonic() + 1.0)
    assert worker._read_pipe(0, 65644, deadline) == b"x" * 65644
    assert raw == b"" and max(pieces) <= 16384
    with pytest.raises(worker.WorkerInputError):
        worker._read_pipe(0, 66001, deadline)


def test_pipe_io_failure_is_closed_and_chainless(monkeypatch: Any) -> None:
    def broken(_fd: int, _buffers: list[memoryview]) -> int:
        raise OSError("PRIVATE_OS_MARKER")

    monkeypatch.setattr(worker, "os", SimpleNamespace(readv=broken))
    monkeypatch.setattr(select, "select", lambda *_a: ([0], [], []))
    with pytest.raises(worker.WorkerInputError) as exc:
        worker._read_pipe(0, 1, ResultDeadline(expires_at=time.monotonic() + 1.0))
    assert exc.value.__context__ is None and "PRIVATE" not in str(exc.value)


@pytest.mark.parametrize("extra", [b"", b"x"])
def test_init_requires_pipe_eof_after_one_bounded_packet(monkeypatch: Any, extra: bytes) -> None:
    value = wire.SecretInit(
        key(), ResultLimits(max_rows=10), time.monotonic() + 1.0, b"n" * 32, b"PUBLIC_FIXTURE"
    )
    packet = wire.encode_init(value)
    chunks = [packet[: wire.HEADER_BYTES], packet[wire.HEADER_BYTES :]]
    monkeypatch.setattr(worker, "_read_pipe", lambda *_a: chunks.pop(0))
    monkeypatch.setattr(
        worker, "os", SimpleNamespace(set_blocking=lambda *_a: None, read=lambda *_a: extra)
    )
    monkeypatch.setattr(select, "select", lambda *_a: ([0], [], []))
    deadline = ResultDeadline(expires_at=time.monotonic() + 2.0)
    if extra:
        with pytest.raises(worker.WorkerInputError):
            worker._read_init(deadline)
    else:
        received = worker._read_init(deadline)
        assert wire.encode_init(received) == packet


def test_success_is_state_checked_before_and_after_then_result_frame_done(monkeypatch: Any) -> None:
    channel, state = Channel(), Baseline()
    frame = b"f" * RESULT_HEADER_BYTES
    monkeypatch.setattr(
        worker,
        "run_job",
        lambda *_a, **_k: JobOutcome(frame=frame, failure=None, can_continue=True),
    )
    request = query()
    assert one_job(channel, state, request) is True
    assert state.calls == 2 and len(channel.sent) == 3
    assert wire.parse_header(channel.sent[0]) == (wire.Kind.RESULT, 0)
    assert channel.sent[1] == frame
    assert wire.decode_done(channel.sent[2][wire.HEADER_BYTES :]) == (key(), 1)


@pytest.mark.parametrize("failure", list(JobFailure))
def test_recovery_needs_body_intent_and_state_probe(monkeypatch: Any, failure: JobFailure) -> None:
    channel, state = Channel(), Baseline()
    continuing = failure.name in {"QUERY", "TIMEOUT", "TYPE", "LIMIT"}
    monkeypatch.setattr(
        worker,
        "run_job",
        lambda *_a, **_k: JobOutcome(frame=None, failure=failure, can_continue=continuing),
    )
    assert one_job(channel, state, query()) is continuing
    assert state.calls == (2 if continuing else 1) and len(channel.sent) == 1
    reply = wire.decode_error(channel.sent[0][wire.HEADER_BYTES :])
    assert reply.category.name == failure.name and reply.can_continue is continuing


@pytest.mark.parametrize("fail_at", [1, 2])
def test_state_mismatch_discards_success_and_never_sends_result(
    monkeypatch: Any, fail_at: int
) -> None:
    channel, state = Channel(), Baseline(fail_at)
    called = []

    def run(*_a: Any, **_kw: Any) -> JobOutcome:
        called.append(True)
        return JobOutcome(frame=b"f" * RESULT_HEADER_BYTES, failure=None, can_continue=True)

    monkeypatch.setattr(worker, "run_job", run)
    assert one_job(channel, state, query()) is False
    assert len(called) == (0 if fail_at == 1 else 1) and len(channel.sent) == 1
    reply = wire.decode_error(channel.sent[0][wire.HEADER_BYTES :])
    assert reply.category is wire.WireFailure.CONNECTION and not reply.can_continue


@pytest.mark.parametrize("fail_send", [1, 2, 3])
def test_partial_response_never_gets_a_second_error(monkeypatch: Any, fail_send: int) -> None:
    channel = Channel(fail_send=fail_send)
    monkeypatch.setattr(
        worker,
        "run_job",
        lambda *_a, **_kw: JobOutcome(
            frame=b"f" * RESULT_HEADER_BYTES, failure=None, can_continue=True
        ),
    )
    with pytest.raises(OSError):
        one_job(channel, Baseline(), query())
    assert len(channel.sent) == fail_send
    assert wire.parse_header(channel.sent[0]) == (wire.Kind.RESULT, 0)


def test_expired_request_runs_nothing_and_emits_no_late_error(monkeypatch: Any) -> None:
    channel, state = Channel(), Baseline()
    monkeypatch.setattr(worker, "run_job", lambda *_a, **_kw: pytest.fail("late work"))
    with pytest.raises(TransportError) as exc:
        one_job(channel, state, query(expires_at=time.monotonic() - 0.1))
    assert exc.value.kind is TransportFailure.TIMEOUT and state.calls == 0 and not channel.sent


@pytest.mark.parametrize("first", [1, 2])
def test_job_sequence_is_strict_and_connection_is_persistent(monkeypatch: Any, first: int) -> None:
    messages = [
        (wire.Kind.QUERY, wire.encode_query(query(first))[wire.HEADER_BYTES :]),
        (wire.Kind.QUERY, wire.encode_query(query(first + 1))[wire.HEADER_BYTES :]),
        (wire.Kind.CLOSE, b""),
    ]
    monkeypatch.setattr(worker, "_next", lambda *_a: messages.pop(0))
    calls: list[tuple[Any, int]] = []
    same_adapter = adapter()

    def keep(_c: Any, a: Any, _s: Any, q: wire.Query, _l: ResultLimits) -> bool:
        calls.append((a, q.job_id))
        return True

    monkeypatch.setattr(worker, "_one_job", keep)
    if first == 2:
        with pytest.raises(worker.WorkerInputError):
            worker._loop(
                cast(RawChannel, Channel()),
                same_adapter,
                cast(WorkerSessionState, Baseline()),
                key=key(),
                limits=ResultLimits(max_rows=10),
                idle_ms=1000,
            )
        assert calls == []
    else:
        assert (
            worker._loop(
                cast(RawChannel, Channel()),
                same_adapter,
                cast(WorkerSessionState, Baseline()),
                key=key(),
                limits=ResultLimits(max_rows=10),
                idle_ms=1000,
            )
            == 0
        )
        assert calls == [(same_adapter, 1), (same_adapter, 2)]


@pytest.mark.parametrize("fail_opened", [False, True])
def test_opened_after_connect_state_and_no_double_error_after_partial_ack(
    monkeypatch: Any, fail_opened: bool
) -> None:
    channel = Channel(fail_send=2 if fail_opened else None)
    events = []
    value = wire.SecretInit(
        key(), ResultLimits(max_rows=10), time.monotonic() + 2.0, b"n" * 32, b"PUBLIC_FIXTURE"
    )
    expected_tag = hmac.digest(value.nonce, value.snapshot, "sha256")
    compiled = SimpleNamespace(
        config=SimpleNamespace(
            database=DatabaseSettings(statement_timeout_ms=1000, max_rows=10), sql=object()
        ),
        engine=object(),
        connection_target=lambda: "PRIVATE_TARGET",
    )
    baseline = object()

    def state() -> object:
        events.append("state")
        return baseline

    def loop(*_args: Any, **_kwargs: Any) -> int:
        events.append("loop")
        return 0

    instance = SimpleNamespace(
        connect=lambda: events.append("connect"),
        close=lambda: events.append("close"),
        _worker_session_state=state,
    )
    monkeypatch.setattr(worker, "RawChannel", lambda *_a, **_kw: channel)
    monkeypatch.setattr(worker, "_read_init", lambda *_a: value)
    monkeypatch.setattr(worker, "recompile_snapshot", lambda *_a, **_kw: compiled)
    monkeypatch.setattr(worker, "PostgresAdapter", lambda *_a, **_kw: instance)
    monkeypatch.setattr(worker, "_loop", loop)
    guard = GuardFacts(ProcessRole.WORKER, 33, 1, 268435456, 25 * 1024 * 1024, 0, 9, (0, 0))
    args = worker.EntryArguments(3, 1, 268435456, 1000)
    code = worker._serve(cast(socket.socket, object()), args, guard, time.monotonic() + 3.0)
    assert code == (1 if fail_opened else 0)
    assert events == (
        ["connect", "state", "close"] if fail_opened else ["connect", "state", "loop", "close"]
    )
    assert len(channel.sent) == 2  # GUARD then (possibly partial) OPENED; never another ERROR
    actual_tag = wire.decode_opened(channel.sent[1][wire.HEADER_BYTES :])
    matched = hmac.compare_digest(actual_tag, expected_tag)
    assert matched  # no nonce/tag in diagnostics/evidence


@pytest.mark.parametrize("isolated,bytecode,optimize", [(0, 1, 0), (1, 0, 0), (0, 0, 0), (1, 1, 1)])
def test_bad_interpreter_flags_refuse_before_environment_or_ready(
    monkeypatch: Any, isolated: int, bytecode: int, optimize: int
) -> None:
    events = []

    class OS:
        @property
        def environ(self) -> dict[str, str]:
            events.append("environment")
            return worker.child_environment()

        def close(self, _fd: int) -> None:
            events.append("close")

    monkeypatch.setattr(worker, "os", OS())
    monkeypatch.setattr(
        worker,
        "sys",
        SimpleNamespace(
            flags=SimpleNamespace(
                isolated=isolated, dont_write_bytecode=bytecode, optimize=optimize
            )
        ),
    )
    monkeypatch.setattr(worker, "protect_process", lambda **_kw: object())
    assert worker.main(["3", "1", "268435456", "1000"]) == 1
    assert events == ["close"]


def test_pipe_deadline_expiring_mid_read_never_returns_partial_data(monkeypatch: Any) -> None:
    clock = [0.0]
    reads = []

    def readv(_fd: int, buffers: list[memoryview]) -> int:
        buffers[0][0] = 120
        reads.append(True)
        clock[0] += 0.2
        return 1

    monkeypatch.setattr(worker, "os", SimpleNamespace(readv=readv))
    monkeypatch.setattr(select, "select", lambda *_a: ([0], [], []))
    with pytest.raises(ResultFrameError):
        worker._read_pipe(0, 4, ResultDeadline(expires_at=0.25, clock=lambda: clock[0]))
    assert len(reads) == 2


@pytest.mark.parametrize("bad", ["repeated", "skipped", "wrong-key"])
def test_later_job_identity_or_sequence_fault_is_fatal(monkeypatch: Any, bad: str) -> None:
    second = query(1 if bad == "repeated" else 3 if bad == "skipped" else 2)
    if bad == "wrong-key":
        second = query(2, key=wire.SessionKey(b"x" * 16, b"d" * 16, 1, 2))
    messages = [
        (wire.Kind.QUERY, wire.encode_query(q)[wire.HEADER_BYTES :]) for q in (query(), second)
    ]
    monkeypatch.setattr(worker, "_next", lambda *_a: messages.pop(0))
    calls = []

    def keep(*_args: Any) -> bool:
        calls.append(True)
        return True

    monkeypatch.setattr(worker, "_one_job", keep)
    with pytest.raises(worker.WorkerInputError):
        worker._loop(
            cast(RawChannel, Channel()),
            adapter(),
            cast(WorkerSessionState, Baseline()),
            key=key(),
            limits=ResultLimits(max_rows=10),
            idle_ms=1000,
        )
    assert calls == [True]


def test_recoverable_error_becomes_fatal_when_state_changed(monkeypatch: Any) -> None:
    channel, baseline = Channel(), Baseline(fail_at=2)
    monkeypatch.setattr(
        worker,
        "run_job",
        lambda *_a, **_k: JobOutcome(frame=None, failure=JobFailure.QUERY, can_continue=True),
    )
    assert one_job(channel, baseline, query()) is False
    reply = wire.decode_error(channel.sent[0][wire.HEADER_BYTES :])
    assert reply.category is wire.WireFailure.CONNECTION and not reply.can_continue


@pytest.mark.parametrize("end", [TransportFailure.EOF, TransportFailure.TIMEOUT])
def test_eof_or_timeout_at_idle_is_graceful(end: TransportFailure) -> None:
    def stopped(*_args: Any) -> bytes:
        raise TransportError(end)

    assert worker._next(cast(RawChannel, SimpleNamespace(recv_exact=stopped)), 1000) is None


def test_eof_inside_header_is_fatal_not_idle_success() -> None:
    calls = []

    def partial(*_args: Any) -> bytes:
        calls.append(True)
        if len(calls) == 1:
            return b"M"
        raise TransportError(TransportFailure.EOF)

    with pytest.raises(TransportError):
        worker._next(cast(RawChannel, SimpleNamespace(recv_exact=partial)), 1000)


@pytest.mark.parametrize(
    "kind", [wire.Kind.INIT, wire.Kind.OPENED, wire.Kind.RESULT, wire.Kind.ERROR]
)
def test_wrong_control_kind_after_open_refuses_before_body(kind: wire.Kind) -> None:
    if kind is wire.Kind.INIT:
        packet = wire.encode_init(
            wire.SecretInit(
                key(), ResultLimits(max_rows=10), time.monotonic() + 1.0, b"n" * 32, b"fixture"
            )
        )
    elif kind is wire.Kind.OPENED:
        packet = wire.encode_opened(b"t" * 32)
    elif kind is wire.Kind.RESULT:
        packet = wire.encode_result_notice()
    else:
        packet = wire.encode_error(wire.ErrorReply(key(), 1, wire.WireFailure.QUERY, False))
    pending = bytearray(packet)

    def read(size: int, _deadline: ResultDeadline) -> bytes:
        part = bytes(pending[:size])
        del pending[:size]
        return part

    with pytest.raises(worker.WorkerInputError):
        worker._next(cast(RawChannel, SimpleNamespace(recv_exact=read)), 1000)
    assert len(pending) == len(packet) - wire.HEADER_BYTES


def test_environment_mismatch_closes_adopted_fd_without_ready(monkeypatch: Any) -> None:
    closed: list[int] = []
    monkeypatch.setattr(worker, "protect_process", lambda **_kw: object())
    monkeypatch.setattr(
        worker,
        "sys",
        SimpleNamespace(flags=SimpleNamespace(isolated=1, dont_write_bytecode=1, optimize=0)),
    )
    monkeypatch.setattr(
        worker,
        "os",
        SimpleNamespace(
            environ=worker.child_environment() | {"MASKGW_NOT_ALLOWED": "PUBLIC_MARKER"},
            close=closed.append,
        ),
    )
    assert worker.main(["3", "1", "268435456", "1000"]) == 1
    assert closed == [3]
