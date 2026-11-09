"""W1 driver over the REAL public WorkerSession with an entirely simulated OS (D2 tests).

DRIVER-SESSION-DESIGN (92191298) sections 2-4 plus DRIVER-SESSION-PENDING-REVIEW.
No real socket, thread, subprocess, Linux guard, DLL, Docker, PostgreSQL, SQL or
network. Nothing here is native evidence: process, sockets and worker are fakes.

Harness contract:

- Only attributes of ``maskgw.runtime.worker_session`` are monkeypatched: ``time``,
  ``ResultDeadline``, ``sys``, ``os``, ``socket``, ``subprocess`` and ``select``.
  No global stdlib attribute is mutated and no SDK algorithm is replaced. One fake
  clock covers the driver port, ``_set_idle`` and EVERY ``ResultDeadline`` the SDK
  builds (``_deadline`` and the direct one in ``_query``).
- The old ``World`` of ``tests/test_worker_session.py`` is never instantiated and
  that file is unchanged. Its ``Endpoint``/``Process``/``Pipe`` are typed against
  that ``World``, so a minimal local copy keeps the same attribute names
  (``fragment``, ``queries``, ``pins_during_frame``, ``writes``, ``row``...) plus
  the read marks and the in-SDK interrupt these cases need.
- ``RecordingFactory`` retains the ledger, token, key, limits, profile and guard it
  receives and returns the exact real ``WorkerSession`` built from them.
- ``SessionContext.row`` is the unique SESSION reservation in ``ledger.status``,
  never a fixed slot. Result frames and DONE carry the recorded key and job.
- Output goes through an exact public ``RawChannel`` over a fake socket held in a
  local ``Any`` variable: no cast and no ignore.
- The D1 port host (``tests.test_oracle9_w1_driver.World``: reader, guard, link,
  ids, threads, FakeSession) is reused for the deterministic driver ports only.

Owner contract for the FUTURE minimal driver API ``run(ports, *, owner=None)``
(not implemented in driver e9d8de9b; the S-2..S-7 cases are the expected RED):

- Without ``owner`` the current behavior is unchanged (S-1, I1-6, I1-7).
- Accepted only when ``type(owner) is Owner`` of the SAME loaded driver namespace,
  with the explicit private latch ``_entered`` being exactly ``False`` (bool) and
  every existing field empty: ``_session_token`` and ``_session`` None,
  ``_endpoints``, ``_handles``, ``_unknown`` and ``_retained`` empty lists.
  ``Owner()`` therefore has exactly those seven fields.
- ``run`` sets ``_entered = True`` BEFORE ``guard.protect``; one use only.
- Anything else raises ``DriverRefusal("OWNER")``, ``args == ("OWNER",)``, no cause
  or context, before ANY port call, leaving the owner untouched.
- RETAINED with a supplied owner returns that exact object.
- ``KeyboardInterrupt``/``SystemExit`` (BaseException outside Exception) raised by
  a port escape ``run``; the caller still holds its owner and acquired resources.
  Inside the SDK a control becomes a closed ``WorkerSessionError`` after the
  SDK's own cleanup; no survival of the original control is claimed (I1-7).

Cleanup coherence: a failed session is accepted only as CLOSED with no SESSION
row (then ``close`` is ALREADY_RELEASED) or HELD with the SAME reservation (slot,
epoch, view) in ReservationState.HELD before and after another HELD ``close``.

Owner refusals run over ``PortTrap`` collaborators that record every attribute
read, call or write, including clock and link reads; the record must stay empty.
"""

from __future__ import annotations

import functools
import hashlib
import hmac
import json
import os
import runpy
import select
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from types import SimpleNamespace
from typing import Any, NoReturn

import pytest

from maskgw.pgwire.result_frame import RESULT_HEADER_BYTES, ResultDeadline, ResultLimits
from maskgw.pgwire.result_receiver import ResultSummary
from maskgw.pgwire.transport import RawChannel, TransportLimits
from maskgw.runtime import worker_process as child
from maskgw.runtime import worker_protocol as wire
from maskgw.runtime import worker_session as session_module
from maskgw.runtime.budget import (
    BudgetLedger,
    BudgetLimits,
    DatasourceCapacity,
    ReleaseOutcome,
    ReservationKind,
    ReservationState,
    ReservationView,
)
from maskgw.runtime.linux_guard import GuardFacts
from maskgw.runtime.worker_protocol import SessionKey
from maskgw.runtime.worker_session import (
    SessionFailure,
    SessionState,
    WorkerProfile,
    WorkerSessionError,
)
from tests import test_oracle9_w1_driver as d1
from tests.test_result_frame import HEADER as RESULT_HEADER
from tests.test_result_frame import frame as result_frame

MIB = d1.MIB
PARENT_BYTES = 2 * d1.FRAME_LIMIT + MIB
EXECUTABLE = "/opt/maskgw/venv/bin/python"
AF_UNIX = 1
STDIN_FD = 6
NONCE = bytes(range(100, 132))
OTHER_SESSION = bytes([0xEE]) * 16
SDK_JOBS = (1, 2)
CONTROL_EXIT = 3
LATCH = "_entered"
FRESH_OWNER: dict[str, object] = {
    "_session_token": None,
    "_session": None,
    "_endpoints": [],
    "_handles": [],
    "_unknown": [],
    "_retained": [],
    LATCH: False,
}

LAB_BUDGET = BudgetLimits(512 * MIB, 128 * MIB, 64 * MIB, 4, 1, 1, 1, 2, 1)
LAB_KEY = SessionKey(bytes(range(1, 17)), d1.DATASOURCE_BYTES, 1, 1)
LAB_RESULT_LIMITS = ResultLimits(max_rows=1000, max_frame_bytes=d1.FRAME_LIMIT)
LAB_PROFILE = WorkerProfile(256 * MIB, 30000, 1000, MIB)
LAB_SNAPSHOT: bytes = d1.PURE["capture"](d1.PURE["decode_init"](d1.PACKET), 1)


def rows_of(job: int) -> list[list[bytes | None]]:
    return [[f"masked-{job:02d}".encode("ascii")]]


def body_of(job: int) -> bytes:
    """Body-only D-113 bytes (header 76 excluded); identity fields do not change it."""
    return result_frame(rows=rows_of(job))[RESULT_HEADER_BYTES:]


def lab_packet() -> bytes:
    """D1 LAB_INIT with jobs 1 and 2 expecting the real SDK body-only output."""
    records = d1.expected_records()
    for job in SDK_JOBS:
        body = body_of(job)
        records[job - 1] = {
            "bytes": len(body),
            "job": job,
            "kind": "RESULT",
            "reason": None,
            "rows": 1,
            "sha256": hashlib.sha256(body).hexdigest(),
        }
    init = json.loads(d1.INIT_BODY)
    init["expected"] = records
    body = d1.canonical(init)
    return d1.INIT_HEADER.pack(b"MGI1", len(body)) + body


def session_rows(ledger: BudgetLedger) -> list[ReservationView]:
    return [
        row
        for row in ledger.status.entries
        if row is not None and row.kind is ReservationKind.SESSION
    ]


def frame_identity(raw: bytes) -> tuple[Any, ...]:
    return tuple(RESULT_HEADER.unpack(raw[:RESULT_HEADER_BYTES])[4:9])


def state_of(session: session_module.WorkerSession) -> SessionState:
    """Fresh read: no property narrowing is carried across an SDK call."""
    return session.state


def pinned_of(context: SessionContext) -> bool:
    """Fresh pin read: no attribute narrowing is carried across an SDK call."""
    return context.row.output_pinned


def session_slots(ledger: BudgetLedger) -> list[tuple[int, int, ReservationView]]:
    """SESSION reservations with slot index and epoch, so identity is comparable."""
    status = ledger.status
    return [
        (index, status.epochs[index], row)
        for index, row in enumerate(status.entries)
        if row is not None and row.kind is ReservationKind.SESSION
    ]


def assert_held_retained(session: session_module.WorkerSession, ledger: BudgetLedger) -> None:
    """HELD session keeps the SAME HELD reservation before and after another close."""
    before = session_slots(ledger)
    assert len(before) == 1
    assert before[0][2].state is ReservationState.HELD
    assert state_of(session) is SessionState.HELD
    assert session.close() is ReleaseOutcome.HELD
    assert state_of(session) is SessionState.HELD
    after = session_slots(ledger)
    assert after == before
    assert after[0][2].state is ReservationState.HELD


# ---------------------------------------------------------------- simulated OS


class Endpoint:
    def __init__(self, context: SessionContext, fd: int) -> None:
        self.context, self.fd = context, fd
        self.inbound = bytearray()
        self.outbound = bytearray()
        self.closed = False
        self.reads: list[int] = []

    def set_inheritable(self, flag: bool) -> None:
        assert flag is False

    def settimeout(self, value: float) -> None:
        assert value > 0

    def fileno(self) -> int:
        return -1 if self.closed else self.fd

    def recv(self, size: int) -> bytes:
        self.reads.append(size)
        if self.context.raise_next:
            self.context.raise_next = False
            self.context.interrupts += 1
            raise KeyboardInterrupt
        count = min(size, self.context.fragment, len(self.inbound))
        result = bytes(self.inbound[:count])
        del self.inbound[:count]
        return result

    def recv_into(self, view: memoryview, size: int) -> int:
        self.context.pins_during_frame.append(self.context.row.output_pinned)
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
                self.context.deliver(kind, body)
        return len(view)

    def close(self) -> None:
        self.closed = True


class StdinPipe:
    def __init__(self, context: SessionContext) -> None:
        self.context = context
        self.closed = False
        self.data = bytearray()

    def fileno(self) -> int:
        return STDIN_FD

    def close(self) -> None:
        if not self.closed and self.data:
            value = wire.decode_init(bytes(self.data[wire.HEADER_BYTES :]))
            tag = hmac.digest(value.nonce, value.snapshot, "sha256")
            self.context.opened_tag = tag
            self.context.parent.inbound.extend(wire.encode_opened(tag))
        self.closed = True


class Process:
    pid = 77

    def __init__(self, context: SessionContext) -> None:
        self.stdin = StdinPipe(context)
        self.returncode: int | None = None
        self.kills = 0

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float) -> int:
        assert timeout > 0
        if self.returncode is None:
            raise subprocess.TimeoutExpired("PUBLIC", timeout)
        return self.returncode

    def kill(self) -> None:
        self.kills += 1
        self.returncode = -9


class SessionContext:
    """Per-session simulated OS state for one real WorkerSession."""

    def __init__(
        self, ledger: BudgetLedger, key: SessionKey, profile: WorkerProfile, mode: str
    ) -> None:
        self.ledger, self.key, self.profile, self.mode = ledger, key, profile, mode
        self.fragment = 65536
        self.raise_next = False
        self.interrupts = 0
        self.queries: list[int] = []
        self.query_marks: list[int] = []
        self.query_expiries: list[float] = []
        self.statements: list[bytes] = []
        self.writes: list[int] = []
        self.pins_during_frame: list[bool] = []
        self.frames: list[bytes] = []
        self.responses: list[bytes] = []
        self.argv: list[str] = []
        self.spawn_kwargs: dict[str, Any] = {}
        self.opened_tag = b""
        self.parent, self.peer = Endpoint(self, 4), Endpoint(self, 5)
        self.process = Process(self)

    @property
    def row(self) -> ReservationView:
        rows = session_rows(self.ledger)
        assert len(rows) == 1
        return rows[0]

    def spawn(self, argv: list[str], **kwargs: Any) -> Process:
        self.argv, self.spawn_kwargs = list(argv), kwargs
        assert self.row.state is ReservationState.LIVE
        self.parent.inbound.extend(wire.encode_guard(Process.pid, 1, self.profile.address_bytes))
        return self.process

    def write(self, view: memoryview) -> int:
        size = min(len(view), self.fragment)
        self.writes.append(size)
        self.process.stdin.data.extend(view[:size])
        return size

    def deliver(self, kind: wire.Kind, body: bytes) -> None:
        if kind is wire.Kind.CLOSE:
            self.process.returncode = 0
            return
        assert kind is wire.Kind.QUERY
        request = wire.decode_query(body)
        self.query_marks.append(len(self.parent.reads))
        self.queries.append(request.job_id)
        self.query_expiries.append(request.expires_at)
        self.statements.append(request.sql)
        if self.mode == "interrupt":
            self.raise_next = True
            return
        self.parent.inbound.extend(self.response(request))

    def response(self, request: wire.Query) -> bytes:
        assert request.key == self.key
        key, job = self.key, request.job_id
        fields: dict[int, Any] = {
            4: key.session_id,
            5: key.datasource_id,
            6: key.generation,
            7: key.record_revision,
            8: job,
        }
        rows: Sequence[Sequence[bytes | None]] = rows_of(job)
        done_key, done_job = key, job
        if self.mode == "truncated":
            fields[2] = 1
            rows = [[b"m"] for _ in range(LAB_RESULT_LIMITS.max_rows)]
        elif self.mode == "wrong_job":
            fields[8] = job + 1
        elif self.mode == "done_job":
            done_job = job + 1
        elif self.mode == "done_session":
            done_key = SessionKey(
                OTHER_SESSION, key.datasource_id, key.generation, key.record_revision
            )
        raw = result_frame(rows=rows, fields=fields)
        packet = wire.encode_result_notice() + raw + wire.encode_done(done_key, done_job)
        self.frames.append(raw)
        self.responses.append(packet)
        return packet


def select_ready(
    _read: list[int], write: list[int], _error: list[int], _timeout: float
) -> tuple[list[int], list[int], list[int]]:
    return [], write, []


class Hub:
    """Routes the SDK module namespaces to the current session context."""

    def __init__(self, clock: d1.Clock, modes: tuple[str, ...]) -> None:
        self.clock, self.modes = clock, modes
        self.contexts: list[SessionContext] = []
        self.blocking: list[int] = []

    @property
    def current(self) -> SessionContext:
        assert self.contexts
        return self.contexts[-1]

    def attach(self, ledger: BudgetLedger, key: SessionKey, profile: WorkerProfile) -> None:
        index = len(self.contexts)
        mode = self.modes[index] if index < len(self.modes) else "ok"
        self.contexts.append(SessionContext(ledger, key, profile, mode))

    def deadline(self, *, expires_at: float) -> ResultDeadline:
        return ResultDeadline(expires_at=expires_at, clock=self.clock.monotonic)

    def socketpair(self, family: int, kind: int) -> tuple[Endpoint, Endpoint]:
        assert family == AF_UNIX
        assert kind == socket.SOCK_STREAM
        return self.current.parent, self.current.peer

    def spawn(self, argv: list[str], **kwargs: Any) -> Process:
        return self.current.spawn(argv, **kwargs)

    def urandom(self, size: int) -> bytes:
        assert size == len(NONCE)
        return NONCE

    def set_blocking(self, fd: int, flag: bool) -> None:
        assert fd == STDIN_FD
        assert flag is False
        self.blocking.append(fd)

    def write(self, fd: int, view: memoryview) -> int:
        assert fd == STDIN_FD
        return self.current.write(view)


def install(monkeypatch: pytest.MonkeyPatch, clock: d1.Clock, modes: tuple[str, ...]) -> Hub:
    """Patch ONLY names inside the SDK module; stdlib modules stay untouched."""
    hub = Hub(clock, modes)
    monkeypatch.setattr(session_module, "time", SimpleNamespace(monotonic=clock.monotonic))
    monkeypatch.setattr(session_module, "ResultDeadline", hub.deadline)
    monkeypatch.setattr(
        session_module, "sys", SimpleNamespace(platform="linux", executable=EXECUTABLE)
    )
    monkeypatch.setattr(
        session_module,
        "os",
        SimpleNamespace(
            getpid=lambda: 1,
            urandom=hub.urandom,
            set_blocking=hub.set_blocking,
            write=hub.write,
        ),
    )
    monkeypatch.setattr(
        session_module,
        "socket",
        SimpleNamespace(
            socketpair=hub.socketpair,
            AF_UNIX=AF_UNIX,
            SOCK_STREAM=socket.SOCK_STREAM,
        ),
    )
    monkeypatch.setattr(
        session_module,
        "subprocess",
        SimpleNamespace(
            Popen=hub.spawn,
            PIPE=subprocess.PIPE,
            DEVNULL=subprocess.DEVNULL,
            TimeoutExpired=subprocess.TimeoutExpired,
        ),
    )
    monkeypatch.setattr(session_module, "select", SimpleNamespace(select=select_ready))
    return hub


class RecordingFactory:
    """Retains what the caller supplies and returns the exact real WorkerSession."""

    def __init__(self, hub: Hub) -> None:
        self.hub = hub
        self.calls: list[dict[str, Any]] = []
        self.sessions: list[session_module.WorkerSession] = []

    def create(self, *args: Any, **kwargs: Any) -> session_module.WorkerSession:
        assert len(args) == 2
        assert set(kwargs) == {"lock", "key", "limits", "profile", "guard"}
        ledger, token = args
        self.calls.append({"ledger": ledger, "token": token, **kwargs})
        self.hub.attach(ledger, kwargs["key"], kwargs["profile"])
        session = session_module.WorkerSession(
            ledger,
            token,
            lock=kwargs["lock"],
            key=kwargs["key"],
            limits=kwargs["limits"],
            profile=kwargs["profile"],
            guard=kwargs["guard"],
        )
        self.sessions.append(session)
        return session


# ---------------------------------------------------------------- typed output


class PipeSocket:
    """Fake output socket; ``probe`` samples the SESSION output pin on each send."""

    def __init__(self, pipe: d1.Pipe, probe: Callable[[], bool] | None = None) -> None:
        self.pipe, self.probe = pipe, probe
        self.pins: list[bool] = []

    def settimeout(self, value: float) -> None:
        assert value > 0

    def send(self, view: memoryview) -> int:
        if self.probe is not None:
            self.pins.append(self.probe())
        self.pipe.data.extend(view)
        return len(view)


def raw_output(target: PipeSocket, stop: Callable[[], bool]) -> RawChannel:
    sock: Any = target  # exact public RawChannel over a fake socket, no cast/ignore
    return RawChannel(sock, stop=stop, limits=TransportLimits())


class RawWriter:
    def __init__(self, pipe: d1.Pipe) -> None:
        self.pipe = pipe
        self.closed = False
        self.channels: list[RawChannel] = []

    def channel(self, *, stop: Callable[[], bool]) -> RawChannel:
        made = raw_output(PipeSocket(self.pipe), stop)
        self.channels.append(made)
        return made

    def shutdown_write(self) -> None:
        self.pipe.shut = True

    def close(self) -> None:
        self.closed = True


class RawPair:
    """Driver pair port whose writer yields an exact RawChannel over the sink pipe."""

    def __init__(self, world: d1.World) -> None:
        self.world = world
        self.pipes: list[d1.Pipe] = []
        self.writers: list[RawWriter] = []
        self.readers: list[d1.ReaderEnd] = []

    def create(self) -> tuple[RawWriter, d1.ReaderEnd]:
        pipe = d1.Pipe()
        writer, reader = RawWriter(pipe), d1.ReaderEnd(self.world, pipe)
        self.pipes.append(pipe)
        self.writers.append(writer)
        self.readers.append(reader)
        return writer, reader


# ---------------------------------------------------------------- LAB session


class Lab:
    """LAB values built independently of the driver; one real session over fakes."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        parent_bytes: int = PARENT_BYTES,
        mode: str = "ok",
    ) -> None:
        self.hub = install(monkeypatch, d1.Clock(), (mode,))
        self.ledger = BudgetLedger(LAB_BUDGET, (DatasourceCapacity(1, 1),))
        generation = self.ledger.reserve_candidate(0, shared_bytes=MIB)
        self.ledger.publish(generation)
        token = self.ledger.reserve_session(
            generation, worker_bytes=256 * MIB, parent_bytes=parent_bytes
        )
        self.factory = RecordingFactory(self.hub)
        self.session = self.factory.create(
            self.ledger,
            token,
            lock=threading.Lock(),
            key=LAB_KEY,
            limits=LAB_RESULT_LIMITS,
            profile=LAB_PROFILE,
            guard=d1.GUARD_FACTS,
        )
        self.sink = d1.Pipe()

    @property
    def context(self) -> SessionContext:
        return self.hub.contexts[0]

    def open(self) -> None:
        self.session.open(LAB_SNAPSHOT)
        assert self.session.state is SessionState.READY

    def failed_query(self) -> None:
        with pytest.raises(WorkerSessionError) as caught:
            self.session.query(b"SELECT 1")
        assert caught.value.category is SessionFailure.JOB
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None

    def refused_send(self) -> None:
        with pytest.raises(WorkerSessionError) as caught:
            self.session.send_result_to(raw_output(PipeSocket(self.sink), stop=lambda: False))
        assert caught.value.category is SessionFailure.STATE
        assert bytes(self.sink.data) == b""


def secret_init(context: SessionContext) -> wire.SecretInit:
    packet = bytes(context.process.stdin.data)
    header = wire.parse_header(packet[: wire.HEADER_BYTES])
    assert header == (wire.Kind.INIT, len(packet) - wire.HEADER_BYTES)
    return wire.decode_init(packet[wire.HEADER_BYTES :])


def assert_cleanup_coherent(session: session_module.WorkerSession, ledger: BudgetLedger) -> None:
    """No enum accepted on its own: session state, ledger row and close must agree."""
    rows = session_rows(ledger)
    if state_of(session) is SessionState.CLOSED:
        assert rows == []
        assert session.close() is ReleaseOutcome.ALREADY_RELEASED
        return
    assert_held_retained(session, ledger)


# ---------------------------------------------------------------- driver ports


def ports_for(world: d1.World, **overrides: Any) -> Any:
    ports: dict[str, Any] = {
        "reader": d1.PureReader(world),
        "guard": d1.Guard(world),
        "clock": world.clock,
        "link": world.link,
        "ids": d1.Ids(world),
        "factory": d1.Factory(world),
        "pair": d1.Pair(world),
        "threads": d1.Threads(world),
    }
    assert set(overrides) <= set(ports)
    ports.update(overrides)
    return d1.driver()["Ports"](**ports)


@functools.cache
def other_namespace() -> dict[str, Any]:
    """A second, separately loaded copy of the same driver source."""
    return runpy.run_path(str(d1.SOURCE))


def owner_state(owner: object) -> list[tuple[str, int, object]]:
    fields: dict[str, object] = getattr(owner, "__dict__", {})
    return [
        (name, id(value), list(value) if type(value) is list else value)
        for name, value in sorted(fields.items())
    ]


PORT_NAMES = ("reader", "guard", "clock", "link", "ids", "factory", "pair", "threads")


class PortTrap:
    """Records EVERY attribute read/write on a port and never delegates.

    The record is kept outside the trap, so an operation the driver catches and
    hides internally is still visible to the test.
    """

    _trap: tuple[str, list[tuple[str, str]]]

    def __init__(self, name: str, operations: list[tuple[str, str]]) -> None:
        object.__setattr__(self, "_trap", (name, operations))

    def __getattr__(self, attribute: str) -> Callable[..., NoReturn]:
        name, operations = self._trap
        operations.append((name, attribute))

        def blocked(*_args: object, **_kwargs: object) -> NoReturn:
            operations.append((name, attribute + "()"))
            raise AssertionError(name)

        return blocked

    def __setattr__(self, attribute: str, _value: object) -> None:
        name, operations = self._trap
        operations.append((name, attribute + "="))
        raise AssertionError(name)


def trap_ports(operations: list[tuple[str, str]]) -> Any:
    return d1.driver()["Ports"](**{name: PortTrap(name, operations) for name in PORT_NAMES})


def assert_owner_refused(world: d1.World, owner: object) -> None:
    module = d1.driver()
    operations: list[tuple[str, str]] = []
    ports = trap_ports(operations)
    before = owner_state(owner)
    with pytest.raises(module["DriverRefusal"]) as caught:
        module["run"](ports, owner=owner)
    d1.assert_closed(caught.value, "OWNER")
    assert operations == []  # no port operation at all, not even a caught/hidden one
    assert world.log == []
    assert world.link.lines == []
    assert world.sessions == []
    assert owner_state(owner) == before


class LatchGuard(d1.Guard):
    def __init__(self, world: d1.World, owner: Any) -> None:
        super().__init__(world)
        self.owner = owner
        self.seen: list[object] = []

    def protect(self, *, role: object, address_limit_bytes: int) -> GuardFacts:
        self.seen.append(self.owner._entered)
        return super().protect(role=role, address_limit_bytes=address_limit_bytes)


class ControlLink(d1.Link):
    """Raises a control at the GO 1 read; records the log length at that point."""

    def __init__(self, world: d1.World, control: BaseException) -> None:
        super().__init__(world)
        self.control = control
        self.raised = 0
        self.mark = -1

    def read_control(self, *, deadline: float) -> bytes | None:
        if self.last == ("READY", 1):
            self.raised += 1
            self.mark = len(self.world.log)
            raise self.control
        return super().read_control(deadline=deadline)


class ControlHandle(d1.Handle):
    def __init__(
        self, world: d1.World, target: Callable[[], object], name: str, control: BaseException
    ) -> None:
        super().__init__(world, target, name)
        self.control = control
        self.mark = -1

    def start(self) -> bool:
        self.world.log.append(("start", self.name))
        self.started = True
        self.mark = len(self.world.log)
        raise self.control


class ControlThreads(d1.Threads):
    def __init__(self, world: d1.World, control: BaseException) -> None:
        super().__init__(world)
        self.control = control

    def create(self, target: Callable[[], object], *, name: str) -> d1.Handle:
        self.world.log.append(("create_thread", name))
        handle = d1.Handle(self.world, target, name)
        if name == "sink":
            handle = ControlHandle(self.world, target, name, self.control)
        self.world.handles.append(handle)
        return handle


# ---------------------------------------------------------------- sanities


def test_sanity_harness_patches_only_sdk_module_names(monkeypatch):
    before = (
        socket.socketpair,
        subprocess.Popen,
        select.select,
        time.monotonic,
        os.urandom,
        sys.platform,
    )
    clock = d1.Clock()
    hub = install(monkeypatch, clock, ())
    after = (
        socket.socketpair,
        subprocess.Popen,
        select.select,
        time.monotonic,
        os.urandom,
        sys.platform,
    )
    assert after == before
    made = hub.deadline(expires_at=d1.START + 5.0)
    assert type(made) is ResultDeadline
    assert made.remaining() == 5.0
    clock.now += 2.0
    namespace: dict[str, Any] = vars(session_module)
    patched_time: Any = namespace["time"]
    assert patched_time.monotonic() == d1.START + 2.0
    assert made.remaining() == 3.0


def test_sanity_port_trap_records_clock_and_link_reads_without_driver():
    operations: list[tuple[str, str]] = []
    ports = trap_ports(operations)
    assert operations == []  # building Ports touches no collaborator
    with pytest.raises(AssertionError):
        ports.clock.monotonic()
    with pytest.raises(AssertionError):
        ports.link.read_control(deadline=d1.START)
    attribute = ports.link.lines  # a plain read is recorded even without a call
    assert callable(attribute)
    with pytest.raises(AssertionError):
        ports.guard.marker = 1
    assert operations == [
        ("clock", "monotonic"),
        ("clock", "monotonic()"),
        ("link", "read_control"),
        ("link", "read_control()"),
        ("link", "lines"),
        ("guard", "marker="),
    ]


def test_sanity_lab_packet_expects_sdk_bodies():
    init = d1.PURE["decode_init"](lab_packet())
    assert body_of(1) != body_of(2)
    for job in SDK_JOBS:
        record = init.expected[job - 1]
        body = body_of(job)
        assert (record.kind, record.rows) == ("RESULT", 1)
        assert (record.bytes, record.sha256) == (len(body), hashlib.sha256(body).hexdigest())


# ---------------------------------------------------------------- I1: real SDK, LAB identity


def test_i1_1_open_result_send_close_with_lab_identity(monkeypatch):
    lab = Lab(monkeypatch)
    context = lab.context
    lab.open()
    assert context.argv == [
        EXECUTABLE,
        "-I",
        "-B",
        "-m",
        "maskgw.runtime.worker_process",
        "5",
        "1",
        str(256 * MIB),
        "30000",
    ]
    assert context.spawn_kwargs == {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "env": child.child_environment(),
        "close_fds": True,
        "pass_fds": (5,),
        "bufsize": 0,
    }
    assert context.peer.closed
    assert context.process.stdin.closed
    init = secret_init(context)
    assert init.key == LAB_KEY
    assert init.limits == LAB_RESULT_LIMITS
    assert init.snapshot == LAB_SNAPSHOT
    assert init.nonce == NONCE
    assert init.expires_at == d1.START + 12.0  # SDK open deadline on the shared clock
    assert context.opened_tag == hmac.digest(NONCE, LAB_SNAPSHOT, "sha256")

    assert lab.session.query(b"SELECT 1") is None
    assert state_of(lab.session) is SessionState.RESULT
    assert context.queries == [1]
    assert context.query_expiries == [d1.START + 11.0]
    assert context.pins_during_frame
    assert all(context.pins_during_frame)
    assert pinned_of(context) is True

    target = PipeSocket(lab.sink, probe=lambda: context.row.output_pinned)
    summary = lab.session.send_result_to(raw_output(target, stop=lambda: False))
    assert bytes(lab.sink.data) == context.frames[0][RESULT_HEADER_BYTES:] == body_of(1)
    assert target.pins
    assert all(target.pins)
    assert summary == ResultSummary(1, 1, False)
    assert type(summary.truncated) is bool
    assert pinned_of(context) is False
    assert state_of(lab.session) is SessionState.READY

    assert lab.session.close() is ReleaseOutcome.RELEASED
    assert state_of(lab.session) is SessionState.CLOSED
    assert session_rows(lab.ledger) == []
    assert context.process.returncode == 0
    assert context.parent.closed


def test_i1_2_truncated_result_reports_exact_flag(monkeypatch):
    lab = Lab(monkeypatch, mode="truncated")
    lab.open()
    assert lab.session.query(b"SELECT 1") is None
    summary = lab.session.send_result_to(raw_output(PipeSocket(lab.sink), stop=lambda: False))
    assert summary == ResultSummary(1, 1000, True)
    assert summary.truncated is True
    assert bytes(lab.sink.data) == lab.context.frames[0][RESULT_HEADER_BYTES:]
    assert lab.session.close() is ReleaseOutcome.RELEASED
    assert session_rows(lab.ledger) == []


def test_i1_3_parent_one_byte_short_refuses_after_control_header_only(monkeypatch):
    lab = Lab(monkeypatch, parent_bytes=PARENT_BYTES - 1)
    context = lab.context
    lab.open()  # open never takes the output pin
    lab.failed_query()
    mark = context.query_marks[0]
    assert context.parent.reads[mark:] == [wire.HEADER_BYTES]  # RESULT control header only
    assert context.pins_during_frame == []  # no D-113 header/body read, no pin
    assert bytes(context.parent.inbound) == context.responses[0][wire.HEADER_BYTES :]
    assert all(row.output_pinned is False for row in session_rows(lab.ledger))
    lab.refused_send()
    assert_cleanup_coherent(lab.session, lab.ledger)


def test_i1_4_wrong_result_identity_is_never_exposed(monkeypatch):
    lab = Lab(monkeypatch, mode="wrong_job")
    context = lab.context
    lab.open()
    lab.failed_query()
    assert frame_identity(context.frames[0])[4] == context.queries[0] + 1
    assert context.pins_during_frame
    assert all(context.pins_during_frame)
    lab.refused_send()
    assert_cleanup_coherent(lab.session, lab.ledger)


@pytest.mark.parametrize("mode", ["done_job", "done_session"], ids=["done-job", "done-session"])
def test_i1_5_wrong_done_after_valid_frame_is_never_exposed(monkeypatch, mode):
    lab = Lab(monkeypatch, mode=mode)
    context = lab.context
    lab.open()
    lab.failed_query()
    assert context.pins_during_frame
    assert all(context.pins_during_frame)  # the whole frame was read under the pin
    assert bytes(context.parent.inbound) == b""  # DONE consumed, then refused
    lab.refused_send()
    assert_cleanup_coherent(lab.session, lab.ledger)


# ---------------------------------------------------------------- I1: driver over the real SDK


def test_i1_6_driver_runs_two_real_sdk_results_then_eof_on_go3(monkeypatch):
    packet = lab_packet()
    world = d1.World(eof={(d1.GO, 3)}, init=packet)
    hub = install(monkeypatch, world.clock, ("ok",))
    factory, pair = RecordingFactory(hub), RawPair(world)
    result = d1.driver()["run"](ports_for(world, factory=factory, pair=pair))

    assert result.outcome == "ABORTED"
    assert result.owner is None
    assert result.verdicts == ("PASS", "PASS", "FAIL", *("NOT_RUN",) * 22)
    events = world.events()
    assert [(event["e"], event.get("case")) for event in events] == [
        ("GUARD", None),
        ("INIT_OK", None),
        ("READY", 1),
        ("RESULT", 1),
        ("READY", 2),
        ("RESULT", 2),
        ("READY", 3),
        ("ABORT", 3),
        ("TERMINAL", None),
    ]
    for job in SDK_JOBS:
        event = {k: v for k, v in events[2 * job + 1].items() if k != "next_seq"}
        assert event == {
            "bytes": len(body_of(job)),
            "case": job,
            "e": "RESULT",
            "kind": "RESULT",
            "reason": None,
            "release": None,
            "rows": 1,
            "sink": "OK",
            "stop_applied": None,
            "truncated": False,
            "verdict": "PASS",
        }
    assert events[-2] == {
        "case": 3,
        "e": "ABORT",
        "phase": "CASE",
        "reason": "EOF",
        "retained": False,
    }
    assert events[-1] == {"e": "TERMINAL", "outcome": "ABORTED"}

    assert len(factory.calls) == len(hub.contexts) == 1
    call, context, session = factory.calls[0], hub.contexts[0], factory.sessions[0]
    expected_key = SessionKey(bytes([1]) * 16, d1.DATASOURCE_BYTES, 1, d1.PURE["RECORD_REVISION"])
    assert type(session) is session_module.WorkerSession
    assert call["key"] == expected_key
    assert call["limits"] == LAB_RESULT_LIMITS
    assert call["profile"] == LAB_PROFILE
    assert call["guard"] is d1.GUARD_FACTS
    snapshot = d1.PURE["capture"](d1.PURE["decode_init"](packet), 1)
    init = secret_init(context)
    assert init.key == expected_key
    assert init.limits == LAB_RESULT_LIMITS
    assert init.snapshot == snapshot
    assert init.nonce == NONCE
    assert context.opened_tag == hmac.digest(NONCE, snapshot, "sha256")

    assert context.queries == list(SDK_JOBS)
    assert context.statements == [d1.SQL[job].encode("ascii") for job in SDK_JOBS]
    assert context.query_expiries == [d1.START + 11.0] * 2
    identity = (expected_key.session_id, expected_key.datasource_id, 1, d1.PURE["RECORD_REVISION"])
    assert [frame_identity(raw) for raw in context.frames] == [(*identity, job) for job in SDK_JOBS]
    assert [bytes(pipe.data) for pipe in pair.pipes] == [body_of(job) for job in SDK_JOBS]
    assert all(type(writer.channels[0]) is RawChannel for writer in pair.writers)
    assert all(writer.closed for writer in pair.writers)
    assert all(reader.closed for reader in pair.readers)

    assert session.state is SessionState.CLOSED
    assert session_rows(call["ledger"]) == []
    assert context.process.returncode == 0
    assert context.process.kills == 0
    assert world.violations == []


def test_i1_7_control_inside_sdk_becomes_a_closed_session_failure(monkeypatch):
    world = d1.World(init=lab_packet())
    hub = install(monkeypatch, world.clock, ("interrupt",))
    factory, pair = RecordingFactory(hub), RawPair(world)
    escaped: list[BaseException] = []
    result: Any = None
    try:
        result = d1.driver()["run"](ports_for(world, factory=factory, pair=pair))
    except KeyboardInterrupt as control:  # converted to a failure, never a pytest abort
        escaped.append(control)
    assert escaped == []
    context, session = hub.contexts[0], factory.sessions[0]
    assert context.interrupts == 1
    assert context.queries == [1]
    assert pair.pipes == []
    assert result.outcome in ("ABORTED", "RETAINED")
    retained = result.outcome == "RETAINED"
    events = world.events()
    assert events[-2] == {
        "case": 1,
        "e": "ABORT",
        "phase": "CASE",
        "reason": "SESSION",
        "retained": retained,
    }
    ledger = factory.calls[0]["ledger"]
    rows = session_rows(ledger)
    if retained:
        assert result.owner is not None
        assert result.owner.session is session
        assert_held_retained(session, ledger)
    else:
        assert result.owner is None
        assert session.state is SessionState.CLOSED
        assert rows == []


# ---------------------------------------------------------------- S: caller owner


def test_s1_default_path_without_owner_is_unchanged():
    world = d1.World(eof={(d1.GO, 1)})
    result = d1.driver()["run"](ports_for(world))
    assert result.outcome == "ABORTED"
    assert result.owner is None
    assert result.verdicts == ("FAIL", *("NOT_RUN",) * 24)
    assert world.sessions[0].state is SessionState.CLOSED
    assert world.events()[-2] == {
        "case": 1,
        "e": "ABORT",
        "phase": "CASE",
        "reason": "EOF",
        "retained": False,
    }
    assert world.violations == []


def test_s7_fresh_owner_constructs_exact_false_latch_and_empty_fields():
    owner = d1.driver()["Owner"]()
    assert vars(owner) == FRESH_OWNER
    assert type(vars(owner)[LATCH]) is bool


def test_s2_supplied_owner_is_the_exact_retained_owner():
    module = d1.driver()
    owner = module["Owner"]()
    world = d1.World(start_fail="sink")
    guard = LatchGuard(world, owner)
    result = module["run"](ports_for(world, guard=guard), owner=owner)
    assert result.outcome == "RETAINED"
    assert result.owner is owner
    assert guard.seen == [True]  # latch set BEFORE the guard
    assert vars(owner)[LATCH] is True
    assert owner.session is world.sessions[0]
    assert owner.session_token is world.tokens[0]
    assert owner.handles == tuple(world.handles)
    assert owner.endpoints == tuple(world.endpoints)


def test_s3_reused_owner_is_refused_before_any_port():
    module = d1.driver()
    owner = module["Owner"]()
    first = d1.World(eof={(d1.GO, 1)})
    result = module["run"](ports_for(first), owner=owner)
    assert result.outcome == "ABORTED"
    assert result.owner is None
    assert first.sessions[0].state is SessionState.CLOSED
    assert vars(owner)[LATCH] is True
    assert_owner_refused(d1.World(), owner)


def foreign_owner(kind: str) -> object:
    owner_class = d1.driver()["Owner"]
    if kind == "object":
        return object()
    if kind == "subclass":
        return type("ForeignOwner", (owner_class,), {})()
    other = other_namespace()["Owner"]
    assert other is not owner_class
    return other()


@pytest.mark.parametrize("kind", ["object", "subclass", "namespace"])
def test_s4_foreign_owner_is_refused_before_guard(kind):
    assert_owner_refused(d1.World(), foreign_owner(kind))


def test_s5_keyboard_interrupt_at_go1_escapes_with_owner_intact():
    module = d1.driver()
    owner = module["Owner"]()
    world = d1.World()
    control = KeyboardInterrupt()
    link = ControlLink(world, control)
    with pytest.raises(KeyboardInterrupt) as caught:
        module["run"](ports_for(world, link=link), owner=owner)
    assert caught.value is control
    assert link.raised == 1
    assert len(world.log) == link.mark  # no port call after the control
    assert json.loads(link.lines[-1])["e"] == "READY"
    session = world.sessions[0]
    assert owner.session is session
    assert owner.session_token is world.tokens[0]
    assert session.state is SessionState.READY
    assert (owner.handles, owner.endpoints, owner.unknown) == ((), (), ())
    assert [row.state for row in session_rows(world.ledger)] == [ReservationState.LIVE]
    assert vars(owner)[LATCH] is True


def test_s6_system_exit_at_sink_start_escapes_with_handle_registered():
    module = d1.driver()
    owner = module["Owner"]()
    world = d1.World()
    control = SystemExit(CONTROL_EXIT)
    threads = ControlThreads(world, control)
    with pytest.raises(SystemExit) as caught:
        module["run"](ports_for(world, threads=threads), owner=owner)
    assert caught.value is control
    handle = world.handles[0]
    assert type(handle) is ControlHandle
    assert handle.started is True
    assert len(world.log) == handle.mark  # no port call after the control
    assert owner.handles == (handle,)  # registered BEFORE start
    assert len(world.endpoints) == 2
    assert owner.endpoints == tuple(world.endpoints)
    assert owner.session is world.sessions[0]
    assert owner.session_token is world.tokens[0]
    assert world.sessions[0].state is SessionState.RESULT
    assert world.sends == []
    assert vars(owner)[LATCH] is True


def latch_true(owner: Any) -> None:
    owner._entered = True


def latch_zero(owner: Any) -> None:
    owner._entered = 0


def latch_none(owner: Any) -> None:
    owner._entered = None


def with_token(owner: Any) -> None:
    owner._session_token = object()


def with_session(owner: Any) -> None:
    owner._session = object()


def with_endpoint(owner: Any) -> None:
    owner._endpoints.append(object())


def with_handle(owner: Any) -> None:
    owner._handles.append(object())


def with_unknown(owner: Any) -> None:
    owner._unknown.append("pair")


def with_retained(owner: Any) -> None:
    owner._retained.append(object())


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(latch_true, id="latch-true"),
        pytest.param(latch_zero, id="latch-zero"),
        pytest.param(latch_none, id="latch-none"),
        pytest.param(with_token, id="token"),
        pytest.param(with_session, id="session"),
        pytest.param(with_endpoint, id="endpoint"),
        pytest.param(with_handle, id="handle"),
        pytest.param(with_unknown, id="unknown"),
        pytest.param(with_retained, id="retained"),
    ],
)
def test_s7_invalid_latch_or_prefilled_owner_is_refused_unchanged(mutate):
    owner = d1.driver()["Owner"]()
    mutate(owner)
    assert_owner_refused(d1.World(), owner)


CALLER_CANARY = "SYNTHETIC-CALLER-CANARY-0001"  # closed synthetic text, no private data


def prepared_owner(path: str) -> object:
    """Refusal input built BEFORE the caller handler; reuse comes from a real D1 run."""
    if path == "foreign":
        return foreign_owner("namespace")
    module = d1.driver()
    owner = module["Owner"]()
    if path == "latch":
        latch_true(owner)
        return owner
    result = module["run"](ports_for(d1.World(eof={(d1.GO, 1)})), owner=owner)
    assert result.outcome == "ABORTED"
    assert vars(owner)[LATCH] is True
    return owner


@pytest.mark.parametrize("path", ["foreign", "latch", "reused"])
@pytest.mark.parametrize("caller", [RuntimeError, KeyError], ids=["runtime-error", "key-error"])
def test_s8_refusal_inside_active_caller_handler_has_no_context(caller, path):
    owner = prepared_owner(path)
    handled: list[BaseException] = []
    try:
        raise caller(CALLER_CANARY)
    except (RuntimeError, KeyError) as active:
        handled.append(active)
        assert sys.exc_info()[1] is active  # the caller exception IS active here
        # Exact __context__ is None, not merely suppressed: checked by assert_closed.
        assert_owner_refused(d1.World(), owner)
    assert len(handled) == 1
    assert type(handled[0]) is caller
