"""Private owner with simulated OS. No subprocess, Linux guard or database."""

from __future__ import annotations

import ast
import hmac
import select
import socket
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from maskgw.pgwire.result_frame import ResultDeadline, ResultLimits
from maskgw.pgwire.transport import RawChannel, TransportLimits
from maskgw.runtime import worker_process as child
from maskgw.runtime import worker_protocol as wire
from maskgw.runtime import worker_session as owner
from maskgw.runtime.budget import (
    BudgetError,
    BudgetLedger,
    BudgetLimits,
    DatasourceCapacity,
    ReleaseOutcome,
    ReservationState,
    ReservationView,
)
from maskgw.runtime.linux_guard import GuardFacts, ProcessRole
from tests.test_result_frame import frame


def key() -> wire.SessionKey:
    return wire.SessionKey(b"S" * 16, b"D" * 16, 2, 3)


class Endpoint:
    def __init__(self, world: World, fd: int) -> None:
        self.world, self.fd = world, fd
        self.inbound = bytearray()
        self.outbound = bytearray()
        self.closed = False
        self.no_close = False
        self.reads: list[int] = []

    def set_inheritable(self, flag: bool) -> None:
        assert flag is False

    def settimeout(self, value: float) -> None:
        assert value > 0

    def fileno(self) -> int:
        return -1 if self.closed else self.fd

    def recv(self, size: int) -> bytes:
        self.reads.append(size)
        count = min(size, self.world.fragment, len(self.inbound))
        result = bytes(self.inbound[:count])
        del self.inbound[:count]
        return result

    def recv_into(self, view: memoryview, size: int) -> int:
        self.world.pins_during_frame.append(self.world.row.output_pinned)
        data = self.recv(size)
        view[: len(data)] = data
        return len(data)

    def send(self, view: memoryview) -> int:
        self.outbound.extend(view)
        if len(self.outbound) >= wire.HEADER_BYTES:
            kind, size = wire.parse_header(bytes(self.outbound[: wire.HEADER_BYTES]))
            if len(self.outbound) == wire.HEADER_BYTES + size:
                body = bytes(self.outbound[wire.HEADER_BYTES :])
                self.outbound.clear()
                if kind is wire.Kind.QUERY:
                    request = wire.decode_query(body)
                    self.world.queries.append(request.job_id)
                    self.inbound.extend(self.world.response(request))
                elif kind is wire.Kind.CLOSE:
                    self.world.process.returncode = 0
        return len(view)

    def close(self) -> None:
        if not self.no_close:
            self.closed = True


class Pipe:
    def __init__(self, world: World) -> None:
        self.world = world
        self.closed = False
        self.no_close = False
        self.data = bytearray()

    def fileno(self) -> int:
        return 6

    def close(self) -> None:
        if self.no_close:
            return
        if not self.closed and self.data:
            value = wire.decode_init(bytes(self.data[wire.HEADER_BYTES :]))
            tag = hmac.digest(value.nonce, value.snapshot, "sha256")
            if self.world.bad_tag:
                tag = b"x" * 32
            self.world.parent.inbound.extend(wire.encode_opened(tag))
        self.closed = True


class Process:
    pid = 77

    def __init__(self, world: World) -> None:
        self.world = world
        self.stdin = Pipe(world)
        self.returncode: int | None = None
        self.kills = 0
        self.kill_fail = 0
        self.poll_fail = 0
        self.wait_fail = 0

    def poll(self) -> int | None:
        if self.poll_fail:
            self.poll_fail -= 1
            raise OSError("PUBLIC_POLL_ERROR")
        return self.returncode

    def wait(self, timeout: float) -> int:
        assert timeout > 0
        if self.wait_fail:
            self.wait_fail -= 1
            raise OSError("PUBLIC_WAIT_ERROR")
        if self.returncode is None:
            raise subprocess.TimeoutExpired("PUBLIC", timeout)
        return self.returncode

    def kill(self) -> None:
        self.kills += 1
        if self.kill_fail:
            self.kill_fail -= 1
            raise OSError("PUBLIC_KILL_ERROR")
        self.returncode = -9


class World:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.fragment = 65536
        self.bad_tag = False
        self.spawn_late = False
        self.spawn_error = False
        self.clock_offset = 0.0
        self.queries: list[int] = []
        self.writes: list[int] = []
        self.pins_during_frame: list[bool] = []
        self.spawn_kwargs: dict[str, Any] = {}
        self.argv: list[str] = []
        self.parent, self.peer = Endpoint(self, 4), Endpoint(self, 5)
        self.process = Process(self)
        self.ledger = BudgetLedger(
            BudgetLimits(100000000, 10, 10, 8, 2, 2, 2, 2, 2), (DatasourceCapacity(2, 2),)
        )
        self.generation = self.ledger.reserve_candidate(0, shared_bytes=10)
        self.ledger.publish(self.generation)
        self.token = self.ledger.reserve_session(
            self.generation, worker_bytes=100, parent_bytes=16384
        )
        self.lock = threading.Lock()
        self.profile = owner.WorkerProfile(256 * 1024 * 1024, 10000, 1000, 512)
        self.guard = GuardFacts(ProcessRole.CONTROLLER, 1, 0, 384 * 1024 * 1024, 1, 0, 0, (0, 0))
        monkeypatch.setattr(
            owner, "sys", SimpleNamespace(platform="linux", executable="/private/python")
        )
        monkeypatch.setattr(
            owner,
            "os",
            SimpleNamespace(
                getpid=lambda: 1,
                urandom=lambda size: b"n" * size,
                set_blocking=lambda _fd, flag: flag is False,
                write=self.write,
            ),
        )
        monkeypatch.setattr(socket, "socketpair", lambda *_: (self.parent, self.peer))
        monkeypatch.setattr(subprocess, "Popen", self.spawn)
        monkeypatch.setattr(select, "select", lambda _r, w, _e, _t: ([], w, []))
        monkeypatch.setattr(
            owner,
            "_deadline",
            lambda seconds: ResultDeadline(
                expires_at=self.clock() + seconds,
                clock=self.clock,
            ),
        )
        monkeypatch.setattr(socket, "AF_UNIX", 1, raising=False)
        self.session = self.make_session()

    @property
    def row(self) -> ReservationView:
        row = self.ledger.status.entries[1]
        assert row is not None
        return row

    def clock(self) -> float:
        return time.monotonic() + self.clock_offset

    def make_session(self, token: Any = None) -> owner.WorkerSession:
        return owner.WorkerSession(
            self.ledger,
            self.token if token is None else token,
            lock=self.lock,
            key=key(),
            limits=ResultLimits(max_rows=10, max_frame_bytes=4096),
            profile=self.profile,
            guard=self.guard,
        )

    def spawn(self, argv: list[str], **kwargs: Any) -> Process:
        self.argv, self.spawn_kwargs = argv, kwargs
        assert self.row.state is ReservationState.LIVE
        if self.spawn_error:
            raise OSError("PUBLIC_SPAWN_ERROR")
        if self.spawn_late:
            self.clock_offset += 20
        self.parent.inbound.extend(wire.encode_guard(77, 1, self.profile.address_bytes))
        return self.process

    def write(self, fd: int, view: memoryview) -> int:
        assert fd == 6
        size = min(len(view), self.fragment)
        self.writes.append(size)
        self.process.stdin.data.extend(view[:size])
        return size

    def response(self, request: wire.Query) -> bytes:
        return (
            wire.encode_result_notice()
            + frame(
                rows=[[b"masked"]],
                fields={8: request.job_id},
            )
            + wire.encode_done(key(), request.job_id)
        )

    def open(self) -> None:
        self.session.open(b"SYNTHETIC_SNAPSHOT_NOT_LOGGED")
        assert self.session.state is owner.SessionState.READY


class Sink:
    def __init__(self, fail: bool = False) -> None:
        self.data = bytearray()
        self.fail = fail

    def settimeout(self, value: float) -> None:
        assert value > 0

    def send(self, value: memoryview) -> int:
        if self.fail:
            raise OSError("PUBLIC_OUTPUT_FAILURE")
        self.data.extend(value)
        return len(value)


def output(sink: Sink) -> RawChannel:
    return RawChannel(sink, stop=lambda: False, limits=TransportLimits())  # type: ignore[arg-type] # fake I/O only


def test_spawn_and_two_jobs_reuse_owner_with_pin_and_done(monkeypatch):
    world = World(monkeypatch)
    world.open()
    assert world.argv == [
        "/private/python",
        "-I",
        "-B",
        "-m",
        "maskgw.runtime.worker_process",
        "5",
        "1",
        str(world.profile.address_bytes),
        "10000",
    ]
    assert world.spawn_kwargs == {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "env": child.child_environment(),
        "close_fds": True,
        "pass_fds": (5,),
        "bufsize": 0,
    }
    assert world.peer.closed and world.process.stdin.closed
    for _ in range(2):
        assert world.session.query(b"SELECT 1") is None
        assert world.session.state is owner.SessionState.RESULT
        assert world.row.output_pinned
        with pytest.raises(owner.WorkerSessionError):
            world.session.query(b"SELECT 2")
        sink = Sink()
        summary = world.session.send_result_to(output(sink))
        assert summary.rows == 1 and b"masked" in sink.data
        assert not world.row.output_pinned
    assert world.queries == [1, 2] and all(world.pins_during_frame)
    assert world.session.close() is ReleaseOutcome.RELEASED
    assert world.session.close() is ReleaseOutcome.ALREADY_RELEASED
    assert world.ledger.status.sessions == 0 and world.parent.closed


@pytest.mark.parametrize("fragment", [1, 7, 16384])
def test_max_init_and_fragmented_or_coalesced_done(monkeypatch, fragment):
    world = World(monkeypatch)
    world.fragment = fragment
    world.session.open(b"x" * 65536)
    assert sum(world.writes) > 65536 and max(world.writes) <= 16384
    world.session.query(b"SELECT 1")
    assert not world.parent.inbound  # frame and DONE coalesced, exact reads lose no bytes
    assert world.session.close() is ReleaseOutcome.RELEASED  # unsent discard drains


@pytest.mark.parametrize("mode", ["late", "tag", "wrong_pid", "eof", "prestop", "spawn"])
def test_open_failure_no_secret_on_late_or_unverified_child(monkeypatch, mode):
    world = World(monkeypatch)
    if mode == "late":
        world.spawn_late = True
    elif mode == "tag":
        world.bad_tag = True
    elif mode == "spawn":
        world.spawn_error = True
    elif mode == "prestop":
        world.session.request_stop()
    else:
        original = world.spawn

        def changed(argv, **kwargs):
            process = original(argv, **kwargs)
            world.parent.inbound = bytearray(
                wire.encode_guard(99, 1, world.profile.address_bytes)
                if mode == "wrong_pid"
                else b""
            )
            return process

        monkeypatch.setattr(subprocess, "Popen", changed)
    with pytest.raises(owner.WorkerSessionError) as caught:
        world.session.open(b"SYNTHETIC_SNAPSHOT_NOT_LOGGED")
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    if mode != "tag":
        assert world.writes == []
    if mode == "spawn":
        assert world.session.state is owner.SessionState.HELD
        assert world.ledger.status.sessions == 1
    elif mode == "prestop":
        assert world.row.state is ReservationState.RESERVED
    else:
        assert world.process.returncode is not None and world.parent.closed
        assert world.ledger.status.sessions == 0


def test_duplicate_owner_and_wrong_token_never_release_foreign_reservation(monkeypatch):
    world = World(monkeypatch)
    world.open()
    second = world.make_session()
    with pytest.raises(owner.WorkerSessionError):
        second.open(b"SYNTHETIC")
    assert world.row.state is ReservationState.LIVE
    assert world.process.returncode is None
    foreign = world.ledger.reserve_auxiliary(shared_bytes=1)
    bad = world.make_session(foreign)
    with pytest.raises(owner.WorkerSessionError):
        bad.open(b"SYNTHETIC")
    assert world.ledger.status.auxiliaries == 1
    world.session.close()


@pytest.mark.parametrize("category", list(wire.WireFailure))
def test_error_continuation_closed_categories_and_no_output_pin(monkeypatch, category):
    world = World(monkeypatch)
    world.open()
    can_continue = category in {
        wire.WireFailure.QUERY,
        wire.WireFailure.TIMEOUT,
        wire.WireFailure.TYPE,
        wire.WireFailure.LIMIT,
    }
    monkeypatch.setattr(
        world,
        "response",
        lambda request: wire.encode_error(
            wire.ErrorReply(key(), request.job_id, category, can_continue)
        ),
    )
    reply = world.session.query(b"SELECT 1")
    assert reply is not None and reply.category is category
    assert world.pins_during_frame == []
    assert world.session.state is (
        owner.SessionState.READY if can_continue else owner.SessionState.CLOSED
    )
    if can_continue:
        monkeypatch.setattr(world, "response", lambda request: World.response(world, request))
        world.session.query(b"SELECT 2")
        assert world.queries == [1, 2]
    world.session.close()


@pytest.mark.parametrize(
    "mode", ["no_done", "extra", "wrong_done", "wrong_frame", "bad_kind", "wrong_error"]
)
def test_no_exposure_without_valid_frame_and_exact_done(monkeypatch, mode):
    world = World(monkeypatch)
    world.open()

    def response(request):
        prefix = wire.encode_result_notice() + frame(rows=[[b"masked"]], fields={8: request.job_id})
        if mode == "no_done":
            return prefix
        if mode == "extra":
            return prefix + b"x" + wire.encode_done(key(), request.job_id)
        if mode == "wrong_done":
            return prefix + wire.encode_done(key(), request.job_id + 1)
        if mode == "wrong_frame":
            return wire.encode_result_notice() + frame(rows=[[b"masked"]])
        if mode == "wrong_error":
            return wire.encode_error(wire.ErrorReply(key(), 42, wire.WireFailure.QUERY, True))
        return wire.encode_close()

    monkeypatch.setattr(world, "response", response)
    with pytest.raises(owner.WorkerSessionError):
        world.session.query(b"SELECT 1")
    with pytest.raises(owner.WorkerSessionError):
        world.session.send_result_to(output(Sink()))
    assert world.ledger.status.sessions == 0


def test_partial_client_send_closes_no_reuse_or_retry(monkeypatch):
    world = World(monkeypatch)
    world.open()
    world.session.query(b"SELECT 1")
    with pytest.raises(owner.WorkerSessionError) as caught:
        world.session.send_result_to(output(Sink(fail=True)))
    assert caught.value.__context__ is None
    assert world.session.state is owner.SessionState.CLOSED
    assert world.queries == [1]


def test_opaque_output_failure_retains_pin_and_capacity(monkeypatch):
    world = World(monkeypatch)
    world.open()
    world.session.query(b"SELECT 1")

    class OpaqueSink(Sink):
        def send(self, _value):
            raise ExceptionGroup("PUBLIC_OPAQUE", [RuntimeError("PUBLIC")])

    with pytest.raises(owner.WorkerSessionError):
        world.session.send_result_to(output(OpaqueSink()))
    assert world.session.state is owner.SessionState.HELD
    assert world.row.output_pinned and world.ledger.status.sessions == 1
    assert world.session.close() is ReleaseOutcome.HELD


@pytest.mark.parametrize("mode", ["idle", "invalid_utf8", "control_size"])
def test_job_refusals_never_read_oversized_control_or_reuse(monkeypatch, mode):
    world = World(monkeypatch)
    world.open()
    sql = b"SELECT 1"
    if mode == "idle":
        world.session._idle_end = time.monotonic() - 1
    elif mode == "invalid_utf8":
        sql = b"\xff"
    else:
        packet = wire.encode_query(wire.Query(key(), 1, time.monotonic() + 1, b"x" * 65536))
        monkeypatch.setattr(world, "response", lambda _: packet)
    world.parent.reads.clear()
    with pytest.raises(owner.WorkerSessionError):
        world.session.query(sql)
    if mode != "control_size":
        assert world.queries == []
    else:
        assert world.parent.reads == [wire.HEADER_BYTES]  # rejects kind/size before body allocation
    assert world.session.state is owner.SessionState.CLOSED


@pytest.mark.parametrize("boundary", ["kill", "poll", "wait"])
@pytest.mark.parametrize("persistent", [False, True])
def test_reap_failures_never_release_live_process(monkeypatch, boundary, persistent):
    world = World(monkeypatch)
    world.open()
    world.session.request_stop()
    setattr(world.process, boundary + "_fail", 100 if persistent else 1)
    result = world.session.close()
    if persistent and boundary != "wait":
        assert result is ReleaseOutcome.HELD
        assert world.ledger.status.sessions == 1
    else:
        assert result is ReleaseOutcome.RELEASED
        assert world.process.returncode is not None


def test_stop_during_pending_spawn_delivers_no_secret(monkeypatch):
    world = World(monkeypatch)
    original = world.spawn

    def stopped(argv, **kwargs):
        world.session.request_stop()
        return original(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", stopped)
    with pytest.raises(owner.WorkerSessionError):
        world.open()
    assert world.writes == [] and world.process.returncode is not None
    assert world.ledger.status.sessions == 0


def test_cross_thread_only_stop_and_busy_has_no_queue(monkeypatch):
    world = World(monkeypatch)
    world.open()
    original = world.session._thread
    world.session._thread = cast(
        threading.Thread, object()
    )  # simulate a different creator; no native thread
    with pytest.raises(owner.WorkerSessionError):
        world.session.close()
    world.session.request_stop()
    world.session._thread = original
    world.session._operation.acquire()
    try:
        with pytest.raises(owner.WorkerSessionError):
            world.session.close()
    finally:
        world.session._operation.release()
    world.session.close()


def test_shutdown_before_adoption_never_spawns(monkeypatch):
    world = World(monkeypatch)
    world.ledger.begin_shutdown()
    with pytest.raises(owner.WorkerSessionError):
        world.open()
    assert world.argv == [] and world.row.state is ReservationState.RESERVED


def test_adopt_session_rejects_other_kinds_and_is_exclusive(monkeypatch):
    world = World(monkeypatch)
    with pytest.raises(BudgetError):
        world.ledger.adopt_session(world.generation)
    world.ledger.adopt_session(world.token)
    with pytest.raises(BudgetError):
        world.ledger.adopt_session(world.token)
    assert world.row.state is ReservationState.LIVE


@pytest.mark.parametrize("boundary", ["socket", "pipe"])
def test_close_returning_without_closing_retains_capacity(monkeypatch, boundary):
    world = World(monkeypatch)
    if boundary == "socket":
        world.open()
        world.parent.no_close = True
        assert world.session.close() is ReleaseOutcome.HELD
    else:
        world.process.stdin.no_close = True
        with pytest.raises(owner.WorkerSessionError):
            world.open()
        assert world.session.state is owner.SessionState.HELD
    assert world.ledger.status.sessions == 1


@pytest.mark.parametrize("boundary", ["open", "close", "close_result"])
def test_common_lock_waits_within_deadline_instead_of_false_held(monkeypatch, boundary):
    world = World(monkeypatch)
    if boundary != "open":
        world.open()
    if boundary == "close_result":
        world.session.query(b"SELECT 1")
    held = threading.Event()

    def hold():
        with world.lock:
            held.set()
            time.sleep(0.5)

    thread = threading.Thread(target=hold, daemon=False)
    thread.start()
    try:
        assert held.wait(2)
        if boundary == "open":
            world.open()
        else:
            assert world.session.close() is ReleaseOutcome.RELEASED
    finally:
        thread.join(2)
        assert not thread.is_alive()
    if boundary == "open":
        world.session.close()


def test_owner_has_no_operational_importer_and_no_parent_sql():
    root = Path(__file__).resolve().parents[1] / "src/maskgw"
    source = root / "runtime/worker_session.py"
    tree = ast.parse(source.read_text("utf8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(
                (
                    "maskgw.db",
                    "maskgw.masking",
                    "maskgw.sql",
                    "maskgw.datasource",
                    "maskgw.runtime.snapshot",
                )
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "connect",
                "bind",
                "listen",
                "accept",
                "makefile",
                "communicate",
            }
    for path in root.rglob("*.py"):
        if path != source:
            for node in ast.walk(ast.parse(path.read_text("utf8"))):
                if isinstance(node, ast.ImportFrom):
                    assert not (node.module or "").endswith("worker_session")
                    assert all(n.name != "worker_session" for n in node.names)
                elif isinstance(node, ast.Import):
                    assert all(not n.name.endswith("worker_session") for n in node.names)
