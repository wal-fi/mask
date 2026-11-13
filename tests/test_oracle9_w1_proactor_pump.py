"""W1 Proactor pump oracles (PROACTOR-DESIGN P3 + PROACTOR-REVIEW R8); RED-first.

Contract for the FUTURE ``docs/poc/oracle9_w1_proactor_pump.py``. The module stays
absent until the root reviews these oracles and freezes RED; it is loaded lazily as the
FIRST statement of each feature case (``pump_module()``), never inside ``pytest.raises``,
so its absence fails per case with ``FileNotFoundError`` and never breaks collection or
lets a negative oracle pass. The ``test_sanity_*`` cases never load the absent module:
they validate only this file's fake SDK.

The fake SDK is a deterministic, single-threaded model of the PUBLIC CPython 3.11.3
surfaces named by the design seam (``LoopSeam``/``TimerSeam``/``TaskSeam``/
``TransportSeam``/``PipeSeam``), following the read-only copies in
``docs/poc/evidence/oracle9-w1-proactor-design-review-20261112/public-sdk-context/``:
default NON-eager ``create_task``, ready callbacks run in per-iteration FIFO batches,
``stop()`` honored at the end of the batch, timers on a dyadic clock, ``Handle._run``
and ``call_exception_handler`` precedence including the default-handler fallback,
``_connect_pipes`` ordering (``connection_made`` and ``_pending_calls`` before the
waiter), read pausing that retains a completed read/EOF, and ``call_at``/``create_task``
failures before or after insertion. It is not asyncio and never creates a loop, thread,
process, socket, signal, guard, DLL, Docker, PostgreSQL or SQL effect.

The owner (a5d233ae), DuplexBridge (5a09be1c) and HostReactor (e86f8e32) are the real
published engines loaded through the frozen owner test module; owner ProtocolState,
``_facts_ok``, bridge outcomes and native cleanup are never faked. Nothing here is a
native proof: N1..N16 of the design remain OPEN.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium, from P3 and normative R8.
V2 applies PROACTOR-TEST-REVIEW T1-T4 only: waiter control precedence of the fake SDK
(windows_events.py:403-410) with its sanity regression, constructor identity semantics,
the initial-drain deferred snapshot of R8.4, and style.
Senff policy: AI-generated tests require human and security review before merge.
"""

from __future__ import annotations

import ast
import functools
import inspect
import math
import runpy
import warnings
import weakref
from collections import deque
from collections.abc import Callable, Coroutine, Generator
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn

import pytest

from tests import test_oracle9_w1_driver as d1
from tests import test_oracle9_w1_duplex_bridge as bt
from tests import test_oracle9_w1_host_reactor as ht
from tests import test_oracle9_w1_port_ownership as base

core = base.core  # published load_pure fixture over the pinned trusted core

REPO = Path(__file__).resolve().parents[1]
PUMP_FILE = REPO / "docs/poc/oracle9_w1_proactor_pump.py"

T0 = base.T0
DT = base.DT
FAKE_PIPE = -1
FAKE_DEVNULL = -3
OWNER_THREAD = 7001
OTHER_THREAD = 7002
GATEWAY_KEY = "gateway-cli"
IDLE_SEGMENTS_MAX = 64
SDK_DEFAULT_LIMITS = (16384, 65536)  # (low, high) as returned by get_write_buffer_limits()
FAILED_LIMITS = (-1, -1)
CANARY = "SYNTHETIC-PROACTOR-CANARY-DO-NOT-RETAIN"
SECRET_TEXTS = (*base.SECRET_TEXTS, CANARY)


# ---------------------------------------------------------------- lazy loading of the absent module


@functools.cache
def _pump_namespace() -> dict[str, Any]:
    return runpy.run_path(str(PUMP_FILE), run_name="_proactor_pump_test")


def pump_module() -> Any:
    """FIRST statement of every feature case; never called inside pytest.raises."""
    return SimpleNamespace(**_pump_namespace())


def make_pump(pm: Any, loop: FakeLoop, *, max_starts: int | None = None) -> Any:
    if max_starts is None:
        return pm.ProactorPump(loop=loop, pipe=FAKE_PIPE, devnull=FAKE_DEVNULL, ident=loop.ident)
    return pm.ProactorPump(
        loop=loop, pipe=FAKE_PIPE, devnull=FAKE_DEVNULL, ident=loop.ident, max_starts=max_starts
    )


def assert_pump_fault(pm: Any, error: BaseException) -> None:
    assert type(error) is pm.PumpFault
    assert error.args == ()
    assert error.__cause__ is None and error.__context__ is None
    text = str(error) + repr(error)
    assert all(secret not in text for secret in SECRET_TEXTS)


def fault_of(pm: Any, call: Callable[[], object]) -> bool:
    """Runs ``call`` expecting PumpFault; drops the exception (and its frames) on return."""
    try:
        call()
    except pm.PumpFault as error:
        assert_pump_fault(pm, error)
        return True
    return False


def control_of(call: Callable[[], object]) -> BaseException | None:
    """Runs ``call`` expecting a non-Exception control; returns it by identity."""
    try:
        call()
    except Exception:
        return None
    except BaseException as control:
        return control
    return None


# ---------------------------------------------------------------- controls (identity, not bool)


class FalseCtl(BaseException):
    """Control whose truthiness is False; any bool() probe is recorded."""

    def __init__(self, probes: list[str]) -> None:
        super().__init__()
        self.probes = probes

    def __bool__(self) -> bool:
        self.probes.append("bool")
        return False


class BoomCtl(BaseException):
    """Control whose truthiness explodes; any bool() probe is recorded first."""

    def __init__(self, probes: list[str]) -> None:
        super().__init__()
        self.probes = probes

    def __bool__(self) -> bool:
        self.probes.append("bool")
        raise AssertionError("control truthiness inspected")


class FalseInterrupt(KeyboardInterrupt):
    """Raw KeyboardInterrupt (propagates through Handle._run) with a False truthiness."""

    def __init__(self, probes: list[str]) -> None:
        super().__init__()
        self.probes = probes

    def __bool__(self) -> bool:
        self.probes.append("bool")
        return False


# ---------------------------------------------------------------- fake futures, tasks and timers


class FakeFuture:
    """Minimal future: done callbacks are always deferred through call_soon (SDK rule)."""

    def __init__(self, loop: FakeLoop) -> None:
        self._loop = loop
        self._done = False
        self._result: object = None
        self._exc: BaseException | None = None
        self._callbacks: list[Callable[[FakeFuture], None]] = []

    def done(self) -> bool:
        return self._done

    def add_done_callback(self, callback: Callable[[FakeFuture], None]) -> None:
        if self._done:
            self._loop.call_soon(callback, self)
        else:
            self._callbacks.append(callback)

    def _finish(self) -> None:
        self._done = True
        callbacks, self._callbacks = self._callbacks, []
        for callback in callbacks:
            self._loop.call_soon(callback, self)

    def set_result(self, value: object) -> None:
        assert not self._done
        self._result = value
        self._finish()

    def set_exception(self, exc: BaseException) -> None:
        assert not self._done
        self._exc = exc
        self._finish()

    def __await__(self) -> Generator[FakeFuture, None, Any]:
        if not self._done:
            yield self
        assert self._done, "fake task resumed before its future completed"
        if self._exc is not None:
            raise self._exc
        return self._result


class FakeTask:
    """Default NON-eager Task: create_task only queues the first step (SDK 3.11.3)."""

    def __init__(self, loop: FakeLoop, coro: Coroutine[Any, Any, Any]) -> None:
        self._loop = loop
        self._coro = coro
        self._done = False
        self.steps = 0

    def done(self) -> bool:
        return self._done

    def step(self, _fut: FakeFuture | None = None) -> None:
        self.steps += 1
        loop = self._loop
        loop.trace.append(("task.step", loop.callback_seq))
        try:
            yielded = self._coro.send(None)
        except StopIteration:
            self._done = True
            return
        except (KeyboardInterrupt, SystemExit) as exc:
            self._done = True
            loop.task_exceptions.append(exc)
            raise
        except BaseException as exc:  # Task.__step: stored on the task, never raised
            self._done = True
            loop.task_exceptions.append(exc)
            return
        assert isinstance(yielded, FakeFuture), "coroutine yielded a foreign awaitable"
        yielded.add_done_callback(self.step)


@dataclass
class FakeHandle:
    label: str
    callback: Callable[..., object]
    args: tuple[object, ...]
    cancelled: bool = False


@dataclass
class FakeTimer:
    loop: FakeLoop
    when: float
    seq: int
    handle: FakeHandle
    internal: bool
    cancelled: bool = False

    def cancel(self) -> None:
        self.loop.timer_cancel(self)


def label_of(callback: Callable[..., object]) -> str:
    name = getattr(callback, "__name__", None)
    return name if isinstance(name, str) else type(callback).__name__


# ---------------------------------------------------------------- fake loop (public LoopSeam only)


class FakeLoop:
    """Deterministic model of the public BaseEventLoop/ProactorEventLoop surface."""

    def __init__(self, start: float = T0) -> None:
        self.t = start
        self.trace: list[tuple[Any, ...]] = []
        self.ready: deque[FakeHandle] = deque()
        self.scheduled: list[FakeTimer] = []
        self._seq = 0
        self.callback_seq = 0
        self.iterations = 0
        self.running = False
        self.closed = False
        self.stopping = False
        self.debug = True  # coroutines._is_debug_mode() may enable it; the pump must disable it
        self.task_factory: object = None
        self.handler: Callable[..., object] | None = None
        self.fallback_calls: list[str] = []
        self.task_exceptions: list[BaseException] = []
        self.task_coros: list[Coroutine[Any, Any, Any]] = []
        self.time_script: Callable[[FakeLoop], object] | None = None
        self.ident_script: Callable[[], object] | None = None
        self.call_at_fault: tuple[str, BaseException] | None = None
        self.create_task_fault: tuple[str, BaseException] | None = None
        self.duplicate_next_call_at = False
        self.cancel_fault: BaseException | None = None
        self.stop_fault: BaseException | None = None
        self.close_fault: BaseException | None = None
        self.raw_after: tuple[str, BaseException] | None = None
        self.error_after: tuple[str, BaseException] | None = None
        self.early_fire = 0.0
        self.early_fire_budget = 0
        self.scripts: dict[str, deque[ProcScript]] = {}
        self.transports: list[FakeTransport] = []
        self.next_pid = 4000
        self.gateway_emit_guard = True
        self.gateway_auto_respond = True
        self.live_ms = ht.LIVE_MS
        self.default_observe_true_at = 2
        self.on_direct_write: Callable[[FakeLoop, bytes], None] | None = None

    # -- counters over the effect trace
    def count(self, kind: str, *, since: int = 0) -> int:
        return sum(1 for entry in self.trace[since:] if entry[0] == kind)

    def entries(self, kind: str) -> list[tuple[Any, ...]]:
        return [entry for entry in self.trace if entry[0] == kind]

    def mark(self) -> int:
        return len(self.trace)

    # -- seam: identity and clock
    def ident(self) -> object:
        self.trace.append(("ident",))
        if self.ident_script is not None:
            return self.ident_script()
        return OWNER_THREAD

    def time(self) -> object:
        if self.time_script is not None:
            return self.time_script(self)
        return self.t

    # -- SDK-internal scheduling (never part of the pump's seam)
    def call_soon(self, callback: Callable[..., object], *args: object) -> FakeHandle:
        if self.closed:
            raise RuntimeError("Event loop is closed")
        handle = FakeHandle(label_of(callback), callback, args)
        self.ready.append(handle)
        return handle

    def _push_timer(
        self, when: float, callback: Callable[..., object], args: tuple[object, ...]
    ) -> FakeTimer:
        self._seq += 1
        handle = FakeHandle(label_of(callback), callback, args)
        timer = FakeTimer(self, when, self._seq, handle, False)
        self.scheduled.append(timer)
        return timer

    def sdk_at(self, when: float, callback: Callable[..., object], *args: object) -> None:
        """I/O completion or wait-handle callback of the SDK (not a pump call_at)."""
        timer = self._push_timer(when, callback, args)
        timer.internal = True

    # -- seam: timers and tasks (failures before or after insertion)
    def call_at(self, when: float, callback: Callable[..., object], *args: object) -> FakeTimer:
        self.trace.append(("call_at", when))
        if self.closed:
            raise RuntimeError("Event loop is closed")
        fault, self.call_at_fault = self.call_at_fault, None
        if fault is not None and fault[0] == "before":
            raise fault[1]
        timer = self._push_timer(when, callback, args)
        if self.duplicate_next_call_at:
            self.duplicate_next_call_at = False
            self._push_timer(when, callback, args)
        if fault is not None:
            raise fault[1]
        return timer

    def timer_cancel(self, timer: FakeTimer) -> None:
        self.trace.append(("timer.cancel", timer.when))
        fault, self.cancel_fault = self.cancel_fault, None
        if fault is not None:
            raise fault
        timer.cancelled = True
        timer.handle.cancelled = True

    def create_task(self, coro: Coroutine[Any, Any, Any]) -> FakeTask:
        self.trace.append(("create_task", self.callback_seq))
        if self.closed:
            raise RuntimeError("Event loop is closed")
        self.task_coros.append(coro)
        fault, self.create_task_fault = self.create_task_fault, None
        if fault is not None and fault[0] == "before":
            raise fault[1]
        task = FakeTask(self, coro)
        self.call_soon(task.step)
        if fault is not None:
            raise fault[1]
        return task

    # -- seam: driving
    def run_forever(self) -> None:
        self.trace.append(("run_forever", self.t))
        if self.closed:
            raise RuntimeError("Event loop is closed")
        if self.running:
            raise RuntimeError("This event loop is already running")
        self.running = True
        try:
            while True:
                self._run_once()
                if self.stopping:
                    break
        finally:
            self.stopping = False
            self.running = False

    def _advance_clock(self) -> None:
        if self.ready or self.stopping:
            return
        live = [timer for timer in self.scheduled if not timer.cancelled]
        assert live, "fake loop would block forever (no ready callback and no timer)"
        early = self.early_fire if self.early_fire_budget > 0 else 0.0
        self.t = max(self.t, min(timer.when for timer in live) - early)

    def _collect_due(self) -> None:
        early = self.early_fire if self.early_fire_budget > 0 else 0.0
        due = sorted(
            (timer for timer in self.scheduled if timer.when <= self.t + early),
            key=lambda timer: (timer.when, timer.seq),
        )
        if any(timer.when > self.t for timer in due):
            self.early_fire_budget -= 1
        for timer in due:
            self.scheduled.remove(timer)
            if not timer.cancelled:
                self.ready.append(timer.handle)

    def _run_once(self) -> None:
        self.iterations += 1
        assert self.iterations < 200_000, "fake loop iteration bound exceeded"
        self.scheduled = [timer for timer in self.scheduled if not timer.cancelled]
        self._advance_clock()
        self._collect_due()
        for _ in range(len(self.ready)):  # snapshot: callbacks queued now run next iteration
            handle = self.ready.popleft()
            if not handle.cancelled:
                self._run_handle(handle)

    def _run_handle(self, handle: FakeHandle) -> None:
        self.callback_seq += 1
        try:
            handle.callback(*handle.args)
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException as exc:  # Handle._run: custom controls also reach the handler
            self.call_exception_handler({"message": "Exception in callback", "exception": exc})
        self._after_handle(handle.label)

    def _after_handle(self, label: str) -> None:
        raw = self.raw_after
        if raw is not None and raw[0] == label:
            self.raw_after = None
            raise raw[1]  # signal-like raw control propagating out of run_forever
        err = self.error_after
        if err is not None and err[0] == label:
            self.error_after = None
            self.call_exception_handler({"message": "Exception in callback", "exception": err[1]})

    def stop(self) -> None:
        self.trace.append(("stop",))
        fault, self.stop_fault = self.stop_fault, None
        if fault is not None:
            raise fault
        self.stopping = True

    def is_running(self) -> bool:
        return self.running

    def is_closed(self) -> bool:
        return self.closed

    def close(self) -> None:
        self.trace.append(("loop.close",))
        if self.running:
            raise RuntimeError("Cannot close a running event loop")
        fault, self.close_fault = self.close_fault, None
        if fault is not None:
            raise fault
        self.closed = True
        self.ready.clear()
        self.scheduled.clear()

    def get_debug(self) -> bool:
        return self.debug

    def set_debug(self, enabled: bool) -> None:
        self.trace.append(("set_debug", enabled))
        self.debug = enabled

    def get_task_factory(self) -> object:
        return self.task_factory

    def set_exception_handler(self, handler: Callable[..., object] | None) -> None:
        self.trace.append(("set_exception_handler",))
        self.handler = handler

    def get_exception_handler(self) -> object:
        return self.handler

    def call_exception_handler(self, context: dict[str, object]) -> None:
        """BaseEventLoop.call_exception_handler precedence, recording any fallback use."""
        self.trace.append(("exception_handler",))
        if self.handler is None:
            self.fallback_calls.append("default_exception_handler")
            return
        try:
            self.handler(self, context)
        except (SystemExit, KeyboardInterrupt):
            raise
        except BaseException:
            self.fallback_calls.append("unhandled_error_in_exception_handler")

    # -- seam: subprocess_exec (windows_events/_make_subprocess_transport ordering)
    def push_script(self, key: str, *scripts: ProcScript) -> None:
        self.scripts.setdefault(key, deque()).extend(scripts)

    def script_for(self, key: str) -> ProcScript:
        queue = self.scripts.get(key)
        if queue:
            return queue.popleft()
        if key == GATEWAY_KEY:
            return ProcScript(never_exit=True)
        if key.startswith("act-observe-"):
            active = int(key.rsplit("-", 1)[1]) == self.default_observe_true_at
            return ProcScript(stdout=[base.observe_line(active=active)])
        return ProcScript(stdout=list(base.default_child_outputs().get(key, [])))

    async def subprocess_exec(
        self, protocol_factory: Callable[[], object], *argv: str, **stdio: int
    ) -> tuple[Any, Any]:
        assert set(stdio) == {"stdin", "stdout", "stderr"}, "stdio must be passed by keyword"
        stdin, stdout, stderr = stdio["stdin"], stdio["stdout"], stdio["stderr"]
        key = argv[1] if len(argv) > 1 and argv[0] == "helper" else argv[0]
        self.trace.append(("exec", key, self.callback_seq, stdin, stdout, stderr))
        protocol = protocol_factory()
        script = self.script_for(key)
        if script.exec_mode == "raise_before":
            raise_scripted(script)
        transport = FakeTransport(self, key, script, (stdin, stdout, stderr))
        transport.protocol = protocol
        if script.prestart:
            transport.prestart_io()
        if script.exec_mode == "raise_after_popen":
            transport.sdk_auto_close()
            raise_scripted(script)
        waiter = FakeFuture(self)
        self.call_soon(transport.connect_pipes, waiter)
        if script.exec_mode == "raise_with_live_connect":
            raise_scripted(script)
        try:
            await waiter
        except (SystemExit, KeyboardInterrupt):
            raise  # windows_events.py:405-406: re-raised BEFORE any automatic close/kill
        except BaseException:
            transport.sdk_auto_close()  # windows_events.py:407-410: close() + _wait()
            await FakeFuture(self)  # transp._wait(): its waiter stays in _pending_calls
            raise
        if script.exec_mode == "raise_after_connected":
            raise_scripted(script)
        if script.exec_mode == "foreign_transport":
            foreign = FakeTransport(self, key + "-foreign", script, (stdin, stdout, stderr))
            foreign.protocol = protocol
            return foreign, protocol
        return transport, protocol

    def gateway_transport(self) -> FakeTransport:
        found = [t for t in self.transports if t.key == GATEWAY_KEY]
        assert found, "no gateway transport"
        return found[-1]

    def kill_gateway(self) -> None:
        found = [t for t in self.transports if t.key == GATEWAY_KEY]
        if found and found[-1].returncode is None:
            found[-1].die(137)


@dataclass
class ProcScript:
    """Deterministic behavior of one spawned process in the fake SDK."""

    stdout: list[bytes] = field(default_factory=list)
    stderr: list[bytes] = field(default_factory=list)
    exit_code: object = 0
    # ok | raise_before | raise_after_popen | connect_fail | raise_with_live_connect |
    # raise_after_connected | foreign_transport
    exec_mode: str = "ok"
    exec_exc: BaseException | None = None
    prestart: bool = False  # every fact happens before connect: all in _pending_calls
    never_exit: bool = False
    exit_first: bool = False
    limits_mode: str = "ok"  # ok | raise_after_set | raise_before_set | missing_stdin
    limits_exc: BaseException | None = None
    write_mode: str = "sync"  # sync | pending | force_close
    write_delay: float | None = 2 * DT


def raise_scripted(script: ProcScript) -> NoReturn:
    exc = script.exec_exc
    assert exc is not None, "scripted failure without an exception object"
    raise exc


class FakeTransport:
    """Public SubprocessTransport surface plus the SDK-internal base_subprocess ordering."""

    def __init__(
        self, loop: FakeLoop, key: str, script: ProcScript, stdio: tuple[int, int, int]
    ) -> None:
        stdin, stdout, stderr = stdio
        self.loop = loop
        self.key = key
        self.script = script
        self.protocol: Any = None
        loop.next_pid += 4
        self.pid = loop.next_pid
        self.returncode: object = None
        self.closed = False
        self.proc_alive = True
        self.finished = False
        self.dying = False
        self.pending: list[tuple[Callable[..., object], tuple[object, ...]]] | None = []
        self.pipes: dict[int, Any] = {}
        if stdin == FAKE_PIPE and script.limits_mode != "missing_stdin":
            self.pipes[0] = FakeWritePipe(self)
        if stdout == FAKE_PIPE:
            self.pipes[1] = FakeReadPipe(self, 1)
        if stderr == FAKE_PIPE:
            self.pipes[2] = FakeReadPipe(self, 2)
        loop.transports.append(self)

    def __repr__(self) -> str:
        return "FakeTransport(<redacted>)"

    # -- public surface used by the pump's handle
    def get_pid(self) -> int:
        self.loop.trace.append(("get_pid", self.key))
        return self.pid

    def get_returncode(self) -> object:
        self.loop.trace.append(("get_returncode", self.key))
        return self.returncode

    def get_pipe_transport(self, fd: int) -> Any:
        self.loop.trace.append(("get_pipe_transport", self.key, fd))
        return self.pipes.get(fd)

    def is_closing(self) -> bool:
        return self.closed

    def close(self) -> None:
        self.loop.trace.append(("transport.close", self.key))
        if not self.closed:
            self._close_effects()

    def kill(self) -> None:
        self.loop.trace.append(("transport.kill", self.key))
        if not self.proc_alive:
            raise ProcessLookupError
        self.die(1)  # Popen.kill == terminate == TerminateProcess(handle, 1)

    # -- SDK-internal behavior (K4: automatic close/kill is NOT a DISPOSE)
    def _close_effects(self) -> None:
        self.closed = True
        for pipe in self.pipes.values():
            pipe.close()
        if self.proc_alive and self.returncode is None:
            self.loop.trace.append(("sdk.kill", self.key))
            self.die(1)

    def sdk_auto_close(self) -> None:
        self.loop.trace.append(("sdk.close", self.key))
        if not self.closed:
            self._close_effects()

    def die(self, code: int) -> None:
        if self.dying:
            return
        self.dying = True
        self.loop.sdk_at(self.loop.t + DT, self.process_exited, code)
        for fd in (1, 2):
            pipe = self.pipes.get(fd)
            if pipe is not None and not pipe.disconnected:
                pipe.feed(None)
        if 0 in self.pipes:
            self.loop.sdk_at(self.loop.t + DT, self.pipes[0].peer_closed)

    def call(self, callback: Callable[..., object], *args: object) -> None:
        if self.pending is not None:
            self.pending.append((callback, args))
        else:
            self.loop.call_soon(callback, *args)

    def pipe_data(self, fd: int, data: bytes) -> None:
        self.call(self.protocol.pipe_data_received, fd, bytearray(data))  # SDK: bytearray slice

    def pipe_lost(self, fd: int, exc: BaseException | None) -> None:
        self.call(self.protocol.pipe_connection_lost, fd, exc)
        self.try_finish()

    def process_exited(self, code: object) -> None:
        if self.returncode is not None:
            return
        self.returncode = code
        self.loop.trace.append(("exited", self.key, code))
        self.call(self.protocol.process_exited)
        self.try_finish()
        if self.key == "act-kill-1":
            self.loop.kill_gateway()

    def try_finish(self) -> None:
        if self.returncode is None or self.finished:
            return
        if all(pipe.disconnected for pipe in self.pipes.values()):
            self.finished = True
            self.call(self.call_connection_lost, None)

    def call_connection_lost(self, exc: BaseException | None) -> None:
        self.loop.trace.append(("connection_lost", self.key))
        try:
            self.protocol.connection_lost(exc)
        finally:
            self.proc_alive = False

    def connect_pipes(self, waiter: FakeFuture) -> None:
        self.loop.trace.append(("connect_pipes", self.key))
        if self.script.exec_mode == "connect_fail":
            waiter.set_exception(OSError(CANARY))
            return
        for pipe in self.pipes.values():
            pipe.connect()
        self.loop.call_soon(self.protocol.connection_made, self)
        pending, self.pending = self.pending, None
        for callback, args in pending or ():
            self.loop.call_soon(callback, *args)
        waiter.set_result(None)
        if not self.script.prestart:
            self.start_io()

    def prestart_io(self) -> None:
        """Every fact happens before connect, so all of them sit in _pending_calls."""
        for chunk in self.script.stdout:
            self.pipe_data(1, chunk)
        for fd in (1, 2):
            pipe = self.pipes.get(fd)
            if pipe is not None:
                pipe.disconnected = True
                self.pipe_lost(fd, None)
        self.process_exited(self.script.exit_code)

    def start_io(self) -> None:
        script = self.script
        if self.key == GATEWAY_KEY:
            if self.loop.gateway_emit_guard:
                self.pipes[1].feed(ht.line_bytes(ht.GUARD))
            return
        if script.never_exit:
            return
        for chunk in script.stdout:
            self.pipes[1].feed(chunk)
        self.pipes[1].feed(None)
        if 2 in self.pipes:
            for chunk in script.stderr:
                self.pipes[2].feed(chunk)
            self.pipes[2].feed(None)
        exit_at = self.loop.t + (DT / 2 if script.exit_first else 3 * DT)
        self.loop.sdk_at(exit_at, self.process_exited, script.exit_code)

    def respond(self, payload: bytes) -> None:
        if self.key != GATEWAY_KEY or not self.loop.gateway_auto_respond:
            return
        lines = bt.respond(payload, self.loop.live_ms)
        raw = b"".join(ht.line_bytes(event) for event in lines)
        if raw:
            self.pipes[1].feed(raw)


class FakeReadPipe:
    """ReadTransport: one read in flight; a read completed while paused is RETAINED."""

    def __init__(self, transport: FakeTransport, fd: int) -> None:
        self.transport = transport
        self.loop = transport.loop
        self.fd = fd
        self.queue: deque[bytes | BaseException | None] = deque()  # None == EOF
        self.paused = False
        self.closing = False
        self.disconnected = False
        self.connected = False
        self.outstanding = False  # one recv_into in flight, issued BEFORE delivering data
        self.reading = False
        self.held: list[bytes | BaseException | None] = []

    def connect(self) -> None:
        self.connected = True
        self.outstanding = not self.disconnected
        self.kick()

    def feed(self, item: bytes | BaseException | None) -> None:
        self.queue.append(item)
        self.kick()

    def kick(self) -> None:
        if self.reading or not self.outstanding or self.closing or self.disconnected:
            return
        if not self.queue:
            return
        self.reading = True
        self.loop.sdk_at(self.loop.t + DT, self.read_complete)

    def read_complete(self) -> None:
        self.reading = False
        if self.closing or not self.queue:
            return
        item = self.queue.popleft()
        self.outstanding = False
        if self.paused:  # completed while paused: kept in _pending_data_length (bpo-33694)
            self.held.append(item)
            self.loop.trace.append(("read.held", self.transport.key, self.fd, item is None))
            return
        self.deliver(item)
        if not self.disconnected:  # not paused: the next read is issued immediately
            self.outstanding = True
            self.kick()

    def deliver(self, item: bytes | BaseException | None) -> None:
        if item is None:
            self.disconnected = True
            self.transport.pipe_lost(self.fd, None)
        elif isinstance(item, BaseException):
            self.disconnected = True
            self.transport.pipe_lost(self.fd, item)
        else:
            self.transport.pipe_data(self.fd, item)

    def pause_reading(self) -> None:
        self.loop.trace.append(("pause_reading", self.transport.key, self.fd))
        if not (self.closing or self.paused):
            self.paused = True

    def resume_reading(self) -> None:
        self.loop.trace.append(("resume_reading", self.transport.key, self.fd))
        if self.closing or not self.paused:
            return
        self.paused = False
        held, self.held = self.held, []
        for item in held:
            self.loop.call_soon(self.deliver, item)
        if not self.outstanding and not self.disconnected and not held:
            self.outstanding = True
        self.kick()

    def is_closing(self) -> bool:
        return self.closing

    def close(self) -> None:
        if self.closing:
            return
        self.closing = True
        if not self.disconnected:
            self.disconnected = True
            self.loop.call_soon(self.transport.pipe_lost, self.fd, None)


class FakeWritePipe:
    """WriteTransport with _FlowControlMixin pause/resume on the protocol."""

    def __init__(self, transport: FakeTransport) -> None:
        self.transport = transport
        self.loop = transport.loop
        self.low, self.high = SDK_DEFAULT_LIMITS
        self.buffer = 0
        self.closing = False
        self.disconnected = False
        self.connected = False
        self.protocol_paused = False
        self.writes: list[bytes] = []

    def connect(self) -> None:
        self.connected = True

    def set_write_buffer_limits(self, high: int | None = None, low: int | None = None) -> None:
        key, script = self.transport.key, self.transport.script
        self.loop.trace.append(("set_write_buffer_limits", key, high, low))
        if script.limits_mode == "raise_before_set":
            assert script.limits_exc is not None
            raise script.limits_exc
        self.high = 65536 if high is None else high
        self.low = self.high // 4 if low is None else low
        if script.limits_mode == "raise_after_set":  # values ALREADY changed to (0, 0)
            assert script.limits_exc is not None
            raise script.limits_exc

    def get_write_buffer_limits(self) -> tuple[int, int]:
        self.loop.trace.append(("get_write_buffer_limits", self.transport.key))
        return (self.low, self.high)

    def get_write_buffer_size(self) -> int:
        self.loop.trace.append(("get_write_buffer_size", self.transport.key))
        return self.buffer

    def is_closing(self) -> bool:
        return self.closing

    def write(self, data: bytes) -> None:
        loop, transport = self.loop, self.transport
        loop.trace.append(("write", transport.key, len(data)))
        if loop.on_direct_write is not None:
            loop.on_direct_write(loop, data)
        if self.closing:
            loop.trace.append(("write.dropped", transport.key))
            return
        mode = transport.script.write_mode
        if mode == "force_close":  # _fatal_error/_force_close: buffer reset, closing
            self.closing = True
            self.buffer = 0
            loop.call_soon(self.force_lost)
            return
        self.writes.append(bytes(data))
        if mode == "pending":
            self.buffer += len(data)
            if self.buffer > self.high and not self.protocol_paused:
                self.protocol_paused = True
                transport.protocol.pause_writing()  # synchronous, inside write()
            if transport.script.write_delay is not None:
                loop.sdk_at(loop.t + transport.script.write_delay, self.write_complete, bytes(data))
            return
        transport.respond(bytes(data))

    def write_complete(self, data: bytes) -> None:
        self.buffer = 0
        if self.protocol_paused and self.buffer <= self.low:
            self.protocol_paused = False
            self.transport.protocol.resume_writing()  # direct call from _loop_writing
        self.transport.respond(data)

    def force_lost(self) -> None:
        self.disconnected = True
        self.transport.pipe_lost(0, BrokenPipeError(CANARY))

    def peer_closed(self) -> None:
        if self.closing or self.disconnected:
            return
        self.closing = True
        self.disconnected = True
        self.transport.pipe_lost(0, None)

    def close(self) -> None:
        if self.closing:
            return
        self.closing = True
        if not self.disconnected:
            self.disconnected = True
            self.loop.call_soon(self.transport.pipe_lost, 0, None)


# ---------------------------------------------------------------- unit-level request/events doubles


class FakeAuthorize:
    """authorize() double: records the fake callback sequence of each call."""

    def __init__(self, loop: FakeLoop, rid: int, result: object = True) -> None:
        self.loop = loop
        self.rid = rid
        self.result = result
        self.exc: BaseException | None = None
        self.calls = 0

    def __call__(self) -> object:
        self.calls += 1
        self.loop.trace.append(("authorize", self.rid, self.loop.callback_seq))
        if self.exc is not None:
            raise self.exc
        return self.result


class FakeEvents:
    """ProcessEvents double: records facts on the shared trace; one-shot hooks/raises."""

    def __init__(self, loop: FakeLoop, rid: int) -> None:
        self.loop = loop
        self.rid = rid
        self.seen: list[tuple[Any, ...]] = []
        self.raise_on: dict[str, BaseException] = {}
        self.hooks: dict[str, Callable[[], None]] = {}
        self.handle: Any = None

    def _record(self, name: str, *args: object) -> None:
        self.seen.append((name, *args))
        self.loop.trace.append(("event", self.rid, name, *args))
        hook = self.hooks.pop(name, None)
        if hook is not None:
            hook()
        exc = self.raise_on.pop(name, None)
        if exc is not None:
            raise exc

    def names(self) -> list[str]:
        return [entry[0] for entry in self.seen]

    def started(self, handle: Any) -> None:
        self.handle = handle
        self._record("started")

    def start_failed(self) -> None:
        self._record("start_failed")

    def not_started(self) -> None:
        self._record("not_started")

    def data(self, fd: int, chunk: bytes) -> None:
        self._record("data", fd, type(chunk).__name__, bytes(chunk))

    def pipe_lost(self, fd: int, failed: bool) -> None:
        self._record("pipe_lost", fd, failed)

    def exited(self, code: object) -> None:
        self._record("exited", code)

    def write_resumed(self) -> None:
        self._record("write_resumed")

    def closed(self) -> None:
        self._record("closed")


@dataclass(eq=False)
class FakeRequest:
    """StartRequest-shaped request (weak-referenceable) for pump unit cases."""

    record_id: object
    argv: object
    stdin_pipe: object
    not_before: object
    authorize: object
    events: object


def request_for(
    loop: FakeLoop, rid: int, tag: str = "act-term-0", *, stdin: bool = False
) -> tuple[FakeRequest, FakeEvents, FakeAuthorize]:
    events = FakeEvents(loop, rid)
    auth = FakeAuthorize(loop, rid)
    if stdin:
        argv: tuple[str, ...] = (GATEWAY_KEY, f"--scope={base.SCOPE_ID}", base.ARGV_CANARY)
    else:
        argv = ("helper", tag, f"--scope={base.SCOPE_ID}", base.ARGV_CANARY)
    return FakeRequest(rid, argv, stdin, loop.t, auth, events), events, auth


def schedule(
    pump: Any, loop: FakeLoop, rid: int, tag: str = "act-term-0"
) -> tuple[FakeEvents, FakeAuthorize, weakref.ref[FakeRequest]]:
    """Schedules a fresh helper request keeping only a weak reference to it."""
    req, events, auth = request_for(loop, rid, tag)
    ref = weakref.ref(req)
    pump.schedule_start(req)
    del req
    return events, auth, ref


def schedule_failing(
    pm: Any, pump: Any, loop: FakeLoop, rid: int
) -> tuple[FakeEvents, FakeAuthorize, weakref.ref[FakeRequest], BaseException | None]:
    """schedule_start under an armed call_at fault; returns a control by identity, if any."""
    req, events, auth = request_for(loop, rid)
    ref = weakref.ref(req)
    control = None
    try:
        pump.schedule_start(req)
    except pm.PumpFault as error:
        assert_pump_fault(pm, error)
    except Exception:
        pytest.fail("schedule_start leaked a non-PumpFault exception")
    except BaseException as caught:
        control = caught
    else:
        pytest.fail("schedule_start accepted a request whose call_at failed")
    del req
    return events, auth, ref, control


def never() -> bool:
    return False


# ---------------------------------------------------------------- owner/bridge/host over the pump


class ProHarness:
    """Real owner + DuplexBridge + HostReactor over ProactorPump(FakeLoop)."""

    def __init__(
        self,
        core_mod: Any,
        *,
        loop: FakeLoop | None = None,
        limits_changes: dict[str, int] | None = None,
    ) -> None:
        self.pm = pump_module()  # the absent module fails here, per case
        self.m = base.ownership_module()
        self.b_ns = base.bridge_mod()
        self.r_ns = base.reactor_mod()
        self.loop = FakeLoop() if loop is None else loop
        self.pump = make_pump(self.pm, self.loop)
        changes = limits_changes or {}
        self.limits = self.m.OwnerLimits(**{**base.DEFAULT_LIMITS, **changes})
        self.plan = base.make_plan(self.m, self.r_ns, observe_children=20)
        self.owner = self.m.PortOwnership(
            self.pump, self.plan, self.limits, bridge_ns=self.b_ns, reactor_ns=self.r_ns
        )
        self.host = self.r_ns.HostReactor(core_mod, base.PACKET, ht.policy_for(self.r_ns))
        self.budget = self.b_ns.DuplexBudget(
            spawn_s=base.SPAWN_S,
            silence_s=base.SILENCE_S,
            drain_s=base.DRAIN_S,
            overall_s=base.OVERALL_S,
        )
        self.bridge = self.b_ns.DuplexBridge(
            self.r_ns,
            self.host,
            self.owner.clock(),
            self.owner.gateway(),
            self.owner.acts(),
            self.budget,
        )

    def records_of(self, kind_name: str) -> list[Any]:
        kind = getattr(self.m.InvocationKind, kind_name)
        return [record for record in self.owner.records() if record.kind is kind]

    def first_of(self, kind_name: str) -> Any:
        return self.records_of(kind_name)[0]

    def spawn_slot(self) -> Any:
        slot = self.b_ns.OperationSlot("spawn")
        self.owner.gateway().begin_spawn_into(slot, self.loop.t + 5.0)
        self.owner.clock().poll((slot,), self.loop.t + 5.0)
        return slot

    def spawn_gateway(self) -> Any:
        slot = self.spawn_slot()
        outcome = slot.op.outcome()
        assert outcome.ok is True
        return outcome.process

    def make_act(self, kind_name: str, case: int, *, window: float = 2.0) -> Any:
        return self.r_ns.Act(
            token=1,
            kind=getattr(self.r_ns.ActKind, kind_name),
            case=case,
            issued_at=self.loop.t,
            deadline=self.loop.t + window,
        )

    def run_act(self, act: Any) -> Any:
        slot = self.b_ns.OperationSlot("act")
        self.owner.acts().begin_act_into(slot, act, act.deadline)
        self.owner.clock().poll((slot,), act.deadline)
        return slot

    def close_all_settled(self) -> int:
        m = self.m
        settled = [
            r
            for r in self.owner.records()
            if r.kind in (m.InvocationKind.SPAWN, m.InvocationKind.CHILD)
            and r.physical is m.PhysicalState.SETTLED_RETAINED
        ]
        for record in settled:
            deadline = self.loop.t + 5.0
            self.owner.begin_dispose(m.DisposeKind.CLOSE_HANDLE, record.record_id, deadline)
            self.owner.settle(deadline)
        return len(settled)


# ---------------------------------------------------------------- sanity cases (no pump module)


class DummyProtocol:
    """SubprocessProtocol double used ONLY by the fake-SDK sanity cases."""

    def __init__(self, order: list[str], *, pause_on_data: bool = False) -> None:
        self.order = order
        self.pause_on_data = pause_on_data
        self.transport: Any = None

    def connection_made(self, transport: Any) -> None:
        self.transport = transport
        self.order.append("connection_made")

    def pipe_data_received(self, fd: int, data: bytes) -> None:
        self.order.append(f"data:{fd}:{type(data).__name__}")
        if self.pause_on_data and fd == 1:
            self.transport.get_pipe_transport(1).pause_reading()

    def pipe_connection_lost(self, fd: int, exc: BaseException | None) -> None:
        self.order.append(f"pipe_connection_lost:{fd}:{exc is not None}")

    def process_exited(self) -> None:
        self.order.append("process_exited")

    def connection_lost(self, exc: BaseException | None) -> None:
        self.order.append(f"connection_lost:{exc is not None}")

    def pause_writing(self) -> None:
        self.order.append("pause_writing")

    def resume_writing(self) -> None:
        self.order.append("resume_writing")


def test_sanity_fake_loop_non_eager_tasks_fifo_batches_and_stop() -> None:
    loop = FakeLoop()
    order: list[str] = []

    async def body() -> None:
        order.append("step1")
        fut = FakeFuture(loop)
        loop.call_soon(fut.set_result, 5)
        value = await fut
        order.append(f"step2:{value}")

    def queue_more() -> None:
        order.append("b")
        loop.call_soon(order.append, "next-iteration")

    task = loop.create_task(body())
    assert order == [] and task.done() is False  # default factory is NOT eager
    loop.call_soon(order.append, "a")
    loop.call_soon(queue_more)
    loop.call_soon(loop.stop)
    loop.call_soon(order.append, "after-stop-same-batch")
    loop.run_forever()
    assert order == ["step1", "a", "b", "after-stop-same-batch"]
    loop.call_soon(loop.stop)
    loop.run_forever()
    assert order[-1] == "next-iteration" and task.done() is False
    loop.call_soon(loop.stop)
    loop.run_forever()
    assert order[-1] == "step2:5" and task.done() is True
    assert loop.task_exceptions == [] and loop.running is False


def test_sanity_fake_timers_clock_and_exception_handler_precedence() -> None:
    loop = FakeLoop()
    seen: list[object] = []
    loop.call_at(T0 + 2 * DT, seen.append, "late")
    loop.call_at(T0 + DT, seen.append, "early")
    loop.call_at(T0 + DT, seen.append, "cancelled").cancel()
    loop.call_at(T0 + 3 * DT, loop.stop)
    loop.run_forever()
    assert seen == ["early", "late"] and loop.t == T0 + 3 * DT

    def boom() -> None:
        raise ValueError(CANARY)

    loop.call_soon(boom)
    loop.call_soon(loop.stop)
    loop.run_forever()
    assert loop.fallback_calls == ["default_exception_handler"]

    def broken_handler(_loop: object, _context: object) -> None:
        raise RuntimeError(CANARY)

    loop.set_exception_handler(broken_handler)
    loop.call_soon(boom)
    loop.call_soon(loop.stop)
    loop.run_forever()
    assert loop.fallback_calls[-1] == "unhandled_error_in_exception_handler"

    probes: list[str] = []
    custom = FalseCtl(probes)

    def collecting_handler(_loop: object, context: dict[str, object]) -> None:
        seen.append(context["exception"])

    def raise_custom() -> None:
        raise custom

    loop.set_exception_handler(collecting_handler)
    loop.call_soon(raise_custom)
    loop.call_soon(loop.stop)
    loop.run_forever()
    assert seen[-1] is custom and probes == []  # Handle._run routes custom controls

    interrupt = KeyboardInterrupt()

    def raise_interrupt() -> None:
        raise interrupt

    loop.call_soon(raise_interrupt)
    assert control_of(loop.run_forever) is interrupt
    assert loop.running is False and loop.stopping is False


def run_dummy_exec(loop: FakeLoop, protocol: DummyProtocol, order: list[str]) -> None:
    async def start() -> None:
        await loop.subprocess_exec(
            lambda: protocol,
            "helper",
            "act-term-0",
            stdin=FAKE_DEVNULL,
            stdout=FAKE_PIPE,
            stderr=FAKE_PIPE,
        )
        order.append("exec-returned")

    loop.create_task(start())
    loop.call_at(loop.t + 0.5, loop.stop)
    loop.run_forever()


def test_sanity_fake_pending_calls_precede_waiter_and_pause_retains_eof() -> None:
    loop = FakeLoop()
    loop.push_script("act-term-0", ProcScript(stdout=[b"x" * 10], prestart=True))
    order: list[str] = []
    run_dummy_exec(loop, DummyProtocol(order), order)
    assert order == [
        "connection_made",
        "data:1:bytearray",
        "pipe_connection_lost:1:False",
        "pipe_connection_lost:2:False",
        "process_exited",
        "connection_lost:False",
        "exec-returned",
    ]

    loop = FakeLoop()
    loop.push_script("act-term-0", ProcScript(stdout=[b"x" * 10]))
    order = []
    run_dummy_exec(loop, DummyProtocol(order, pause_on_data=True), order)
    assert order[:2] == ["connection_made", "exec-returned"]
    assert "data:1:bytearray" in order and "process_exited" in order
    assert "pipe_connection_lost:2:False" in order
    assert "pipe_connection_lost:1:False" not in order  # EOF retained while paused
    assert "connection_lost:False" not in order
    assert ("read.held", "act-term-0", 1, True) in loop.trace


@pytest.mark.parametrize("phase", ["before", "after"])
def test_sanity_fake_call_at_and_create_task_fail_before_or_after_insertion(phase: str) -> None:
    loop = FakeLoop()
    fired: list[str] = []
    loop.call_at_fault = (phase, OSError(CANARY))
    with pytest.raises(OSError, match=CANARY):
        loop.call_at(T0, fired.append, "timer")
    ran: list[str] = []

    async def body() -> None:
        ran.append("step")

    coro = body()
    loop.create_task_fault = (phase, OSError(CANARY))
    with pytest.raises(OSError, match=CANARY):
        loop.create_task(coro)
    loop.call_at(T0 + DT, loop.stop)
    loop.run_forever()
    inserted = phase == "after"
    assert fired == (["timer"] if inserted else [])
    assert ran == (["step"] if inserted else [])
    if not inserted:
        coro.close()
    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED


WAITER_FAILURES = ("keyboard-interrupt", "system-exit", "exception", "custom-control")


@pytest.mark.parametrize("case", WAITER_FAILURES)
def test_sanity_fake_waiter_failure_follows_pinned_sdk_precedence(
    case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """windows_events.py:403-410 (v3.11.3): SystemExit/KeyboardInterrupt from the waiter are
    re-raised with no automatic close/kill; any other BaseException closes and awaits _wait().
    Only this fake is exercised; no SDK import and no native injection is claimed."""
    probes: list[str] = []
    failures: dict[str, BaseException] = {
        "keyboard-interrupt": KeyboardInterrupt(),
        "system-exit": SystemExit(0),
        "exception": OSError(CANARY),
        "custom-control": FalseCtl(probes),
    }
    failure = failures[case]

    def resolve_with_failure(_transport: FakeTransport, waiter: FakeFuture) -> None:
        waiter.set_exception(failure)

    monkeypatch.setattr(FakeTransport, "connect_pipes", resolve_with_failure)
    loop = FakeLoop()
    order: list[str] = []
    protocol = DummyProtocol(order)

    async def body() -> None:
        await loop.subprocess_exec(
            lambda: protocol,
            "helper",
            "act-term-0",
            stdin=FAKE_DEVNULL,
            stdout=FAKE_PIPE,
            stderr=FAKE_PIPE,
        )
        order.append("exec-returned")

    task = loop.create_task(body())
    loop.call_at(loop.t + 1.0, loop.stop)
    observed = control_of(loop.run_forever)
    propagates = case in ("keyboard-interrupt", "system-exit")
    if propagates:
        assert observed is failure and task.done() is True
        assert (loop.count("sdk.close"), loop.count("sdk.kill")) == (0, 0)
    else:  # common Exception and custom controls: automatic close/kill, then _wait() hangs
        assert observed is None and task.done() is False
        assert (loop.count("sdk.close"), loop.count("sdk.kill")) == (1, 1)
    assert order == [] and probes == [] and loop.fallback_calls == []
    for coro in loop.task_coros:
        coro.close()


# ---------------------------------------------------------------- construction and identity (R7-a)


def raiser(exc: BaseException) -> Callable[..., NoReturn]:
    def go(*_args: object) -> NoReturn:
        raise exc

    return go


def test_construct_disables_debug_installs_closed_handler_and_never_drives() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    assert loop.debug is False and loop.entries("set_debug") == [("set_debug", False)]
    assert loop.count("set_exception_handler") == 1
    assert getattr(loop.handler, "__self__", None) is pump  # bound method of this pump
    first_ident = loop.trace.index(("ident",))
    assert first_ident < loop.trace.index(("set_debug", False))
    for kind in ("call_at", "create_task", "run_forever", "exec", "stop", "loop.close"):
        assert loop.count(kind) == 0
    assert repr(pump) == "ProactorPump(<redacted>)"


BAD_CTOR = (
    "max_starts-0",
    "max_starts-513",
    "max_starts-bool",
    "max_starts-float",
    "pipe-equals-devnull",
    "pipe-bool",
    "ident-not-callable",
    "loop-running",
    "loop-closed",
    "task-factory-set",
)


def bad_ctor_kwargs(case: str, loop: FakeLoop) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "loop": loop,
        "pipe": FAKE_PIPE,
        "devnull": FAKE_DEVNULL,
        "ident": loop.ident,
        "max_starts": 512,
    }
    overrides: dict[str, tuple[str, object]] = {
        "max_starts-0": ("max_starts", 0),
        "max_starts-513": ("max_starts", 513),
        "max_starts-bool": ("max_starts", True),
        "max_starts-float": ("max_starts", 512.0),
        "pipe-equals-devnull": ("pipe", FAKE_DEVNULL),
        "pipe-bool": ("pipe", True),
        "ident-not-callable": ("ident", OWNER_THREAD),
    }
    if case in overrides:
        key, value = overrides[case]
        kwargs[key] = value
    loop.running = case == "loop-running"
    loop.closed = case == "loop-closed"
    if case == "task-factory-set":
        loop.task_factory = object()
    return kwargs


@pytest.mark.parametrize("case", BAD_CTOR)
def test_construct_refuses_bad_arguments_and_loop_state_before_configuring(case: str) -> None:
    pm = pump_module()
    loop = FakeLoop()
    kwargs = bad_ctor_kwargs(case, loop)
    with pytest.raises(pm.PumpFault) as caught:
        pm.ProactorPump(**kwargs)
    assert_pump_fault(pm, caught.value)
    assert loop.count("set_debug") == 0 and loop.count("set_exception_handler") == 0
    assert loop.handler is None


class StickyDebugLoop(FakeLoop):
    def set_debug(self, enabled: bool) -> None:
        self.trace.append(("set_debug", enabled))  # never takes effect


class DeafHandlerLoop(FakeLoop):
    def set_exception_handler(self, handler: Callable[..., object] | None) -> None:
        self.trace.append(("set_exception_handler", handler is None))  # never installed


@pytest.mark.parametrize("loop_cls", [StickyDebugLoop, DeafHandlerLoop])
def test_construct_rereads_debug_and_handler(loop_cls: type[FakeLoop]) -> None:
    pm = pump_module()
    loop = loop_cls()
    with pytest.raises(pm.PumpFault) as caught:
        make_pump(pm, loop)
    assert_pump_fault(pm, caught.value)
    assert loop.count("call_at") == 0 and loop.count("run_forever") == 0


# The constructor records the FIRST valid ident() as the owner (P3 section 2): a different but
# valid initial identity is not a failure, so only invalid types, Exception and controls refuse.
IDENT_FAILURES = ("exception", "bool", "str", "control")


def ident_script_for(case: str, ctl: BaseException) -> Callable[[], object]:
    values: dict[str, object] = {"bool": True, "str": str(OWNER_THREAD)}
    if case == "exception":
        return raiser(OSError(CANARY))
    if case == "control":
        return raiser(ctl)
    value = values[case]
    return lambda: value


@pytest.mark.parametrize("case", IDENT_FAILURES)
def test_r7a_constructor_ident_failure_is_closed_before_loop_configuration(case: str) -> None:
    pm = pump_module()
    loop = FakeLoop()
    probes: list[str] = []
    ctl = FalseCtl(probes)
    loop.ident_script = ident_script_for(case, ctl)
    if case == "control":
        assert control_of(lambda: make_pump(pm, loop)) is ctl
    else:
        assert fault_of(pm, lambda: make_pump(pm, loop))
    assert loop.count("set_debug") == 0 and loop.count("set_exception_handler") == 0
    assert probes == []


def test_r7a_any_valid_initial_identity_owns_the_pump_until_it_changes() -> None:
    pm = pump_module()
    loop = FakeLoop()
    initial = OTHER_THREAD + 1000  # valid, and different from every constant of this file
    loop.ident_script = lambda: initial
    pump = make_pump(pm, loop)
    assert loop.debug is False and loop.count("set_exception_handler") == 1
    assert pump.now() == T0
    events, auth, _ref = schedule(pump, loop, 1)
    pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())
    assert auth.calls == 1 and events.names()[-1] == "closed"
    req2, ev2, auth2 = request_for(loop, 2)
    mark = loop.mark()
    loop.ident_script = lambda: OWNER_THREAD  # another valid int, but not the recorded owner
    assert fault_of(pm, pump.now)
    assert fault_of(pm, lambda: pump.schedule_start(req2))
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))
    assert fault_of(pm, pump.close)
    for kind in ("call_at", "run_forever", "create_task", "loop.close", "stop", "authorize"):
        assert loop.count(kind, since=mark) == 0
    assert ev2.seen == [] and auth2.calls == 0
    loop.ident_script = lambda: initial
    pump.schedule_start(req2)  # the refused call registered nothing
    pump.run_until(loop.t + 1.0, lambda: "closed" in ev2.names())
    assert auth2.calls == 1 and ev2.names()[-1] == "closed"


def test_r7a_public_methods_close_ident_failures_without_latch_or_state_change() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events, auth, _ref = schedule(pump, loop, 1)
    req2, ev2, _auth2 = request_for(loop, 2)
    mark = loop.mark()
    loop.ident_script = raiser(OSError(CANARY))
    assert fault_of(pm, pump.now)
    assert fault_of(pm, lambda: pump.schedule_start(req2))
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))
    assert fault_of(pm, pump.close)
    probes: list[str] = []
    ctl = BoomCtl(probes)
    loop.ident_script = raiser(ctl)
    assert control_of(pump.now) is ctl
    loop.ident_script = lambda: OTHER_THREAD
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))
    for kind in ("call_at", "run_forever", "create_task", "loop.close", "stop"):
        assert loop.count(kind, since=mark) == 0
    loop.ident_script = None
    pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())  # no latch was left
    assert auth.calls == 1 and events.names()[-1] == "closed" and ev2.seen == []
    pump.schedule_start(req2)  # rid 2 was never registered by the refused call
    assert probes == []


# ---------------------------------------------------------------- clock (R8.1, R1-e)


def test_r8_first_valid_clock_reading_initializes_then_monotonic_finite_time() -> None:
    pm = pump_module()
    loop = FakeLoop(start=0.0)
    pump = make_pump(pm, loop)
    values: deque[object] = deque([math.nan, 0.0, 0.0, 5.0, 4.0, True, -1.0, math.inf, 5.0])
    loop.time_script = lambda _loop: values.popleft()
    assert fault_of(pm, pump.now)  # NaN as the very first reading: never compared with None
    assert pump.now() == 0.0  # first VALID reading initializes the baseline
    assert pump.now() == 0.0  # equal readings are monotonic
    assert pump.now() == 5.0
    assert fault_of(pm, pump.now)  # 4.0 regresses
    assert fault_of(pm, pump.now)  # bool is not a time
    assert fault_of(pm, pump.now)  # negative
    assert fault_of(pm, pump.now)  # infinite
    assert pump.now() == 5.0
    assert values == deque()


@pytest.mark.parametrize("mode", ["nan", "regress", "bool", "negative", "raises"])
def test_r1e_bad_time_inside_run_is_pump_fault_after_own_timer_cancel(mode: str) -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    bad: dict[str, object] = {"nan": math.nan, "regress": T0 - 1.0, "bool": True, "negative": -1.0}

    def script(lp: FakeLoop) -> object:
        if lp.count("run_forever") == 0 or lp.running:
            return lp.t
        if mode == "raises":
            raise OSError(CANARY)
        return bad[mode]

    loop.time_script = script
    target = loop.t + 1.0
    assert fault_of(pm, lambda: pump.run_until(target, never))
    assert loop.count("run_forever") == 1
    assert len([e for e in loop.entries("call_at") if e[1] == target]) == 1
    assert loop.count("timer.cancel") == 1


# ---------------------------------------------------------------- Q2 / R8.3 / R7-b / R7-c (unit)


def test_q2_authorize_and_exec_share_one_step_and_spent_gate_still_delivers_facts() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events, auth, ref = schedule(pump, loop, 1)
    assert loop.entries("call_at") == [("call_at", T0)]
    assert events.seen == [] and auth.calls == 0 and loop.count("create_task") == 0  # inert
    end = pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())
    (authorized,) = loop.entries("authorize")
    (executed,) = loop.entries("exec")
    assert authorized[2] == executed[2]  # same task step: no loop iteration in between
    assert executed == ("exec", "act-term-0", executed[2], FAKE_DEVNULL, FAKE_PIPE, FAKE_PIPE)
    assert loop.entries("create_task")[0][1] < authorized[2]  # non-eager: step runs later
    assert events.seen == [
        ("started",),
        ("data", 1, "bytes", base.terminate_line()),
        ("pipe_lost", 2, False),
        ("pipe_lost", 1, False),
        ("exited", 0),
        ("closed",),
    ]
    assert end == T0 + 3 * DT
    assert loop.count("get_pipe_transport") == 0 and loop.count("set_write_buffer_limits") == 0
    assert ref() is None  # request released at the terminal phase of S4
    assert loop.task_exceptions == [] and loop.fallback_calls == []


def test_q2_stdin_limits_precede_started_and_handle_works_inside_owner_callbacks() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    req, events, _auth = request_for(loop, 1, stdin=True)
    pump.schedule_start(req)
    seen_inside: list[object] = []

    def inside_started() -> None:
        handle = events.handle
        seen_inside.append((handle.pid(), handle.write_limits(), handle.is_closing()))
        seen_inside.append(handle.buffer_size())
        handle.pause_reading(1)

    events.hooks["started"] = inside_started
    pump.run_until(loop.t + 1.0, lambda: "started" in events.names())
    gateway = loop.gateway_transport()
    assert seen_inside == [(gateway.pid, (0, 0), False), 0]
    limits_at = loop.trace.index(("set_write_buffer_limits", GATEWAY_KEY, 0, 0))
    assert limits_at < loop.trace.index(("event", 1, "started"))
    (executed,) = loop.entries("exec")
    assert executed[3:] == (FAKE_PIPE, FAKE_PIPE, FAKE_DEVNULL)
    assert ("pause_reading", GATEWAY_KEY, 1) in loop.trace


# ---------------------------------------------------------------- Q1 complete positive path


def test_q1_full_complete_candidate_then_quiescent_idempotent_close(core: Any) -> None:
    pm = pump_module()
    h = ProHarness(core)
    m, owner, loop, pump = h.m, h.owner, h.loop, h.pump
    result = h.bridge.run()
    assert result.done.outcome.name == "COMPLETE_CANDIDATE"
    assert ht.names(result.done.verdicts) == ["PASS"] * 25
    assert owner.first_control() is None
    assert len(h.records_of("WRITE")) == 51 and len(h.records_of("ACT")) == 7
    assert all(r.protocol is m.ProtocolState.SUCCEEDED for r in h.records_of("ACT"))
    fence = owner.seal()
    assert fence.open_ids == () and fence.unknown_ids == ()
    before = loop.t
    assert owner.settle(before + 10.0) == before
    loop.t += DT
    owner.begin_audit(m.AuditKind.GATEWAY_ABSENT, loop.t + 5.0)
    owner.settle(loop.t + 5.0)
    owner.begin_audit(m.AuditKind.BACKENDS_ZERO, loop.t + 5.0)
    owner.settle(loop.t + 5.0)
    assert owner.audit().quiet_scoped is True and owner.audit().control_history is False
    assert pump.close() is False and loop.count("loop.close") == 0  # handles still retained
    assert h.close_all_settled() >= 15
    assert owner.audit().quiet_scoped is True and owner.custody().entries == ()
    assert loop.count("sdk.kill") == 0 and loop.count("transport.kill") == 0
    assert loop.task_exceptions == [] and loop.fallback_calls == []
    assert pump.close() is True and loop.count("loop.close") == 1
    assert pump.close() is True and loop.count("loop.close") == 1  # idempotent (R4-c)
    stray, _events, _auth = request_for(loop, 999)
    assert fault_of(pm, pump.now)
    assert fault_of(pm, lambda: pump.schedule_start(stray))
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))


# ---------------------------------------------------------------- Q3 / Q4 / X5 (owner integration)


def test_q3_write_sent_synchronously_and_via_resume_writing(core: Any) -> None:
    pm = pump_module()
    h = ProHarness(core)
    loop, b_ns, r_ns = h.loop, h.b_ns, h.r_ns
    assert pm.ProactorPump is not None
    loop.gateway_auto_respond = False
    proc = h.spawn_gateway()
    frame1 = d1.frame(base.GO, 1, 1)
    slot1 = b_ns.OperationSlot("write")
    proc.begin_write_into(slot1, frame1, loop.t + 5.0)
    assert slot1.op.outcome() == b_ns.WriteOutcome(delivery=r_ns.Delivery.SENT, bytes_written=16)
    loop.gateway_transport().script.write_mode = "pending"
    slot2 = b_ns.OperationSlot("write")
    proc.begin_write_into(slot2, d1.frame(base.ACK, 1, 2), loop.t + 5.0)
    assert slot2.op.done() is False  # buffered: pause_writing is no owner event
    h.owner.clock().poll((slot2,), loop.t + 5.0)
    assert slot2.op.outcome() == b_ns.WriteOutcome(delivery=r_ns.Delivery.SENT, bytes_written=16)
    writes = h.records_of("WRITE")
    assert [w.protocol for w in writes] == [h.m.ProtocolState.SUCCEEDED] * 2
    assert all(w.handoff_zero is True and w.uncertain is False for w in writes)
    assert loop.count("write") == 2


def test_x5_forced_close_with_zero_buffer_is_never_sent(core: Any) -> None:
    pm = pump_module()
    h = ProHarness(core)
    loop, b_ns, r_ns, m = h.loop, h.b_ns, h.r_ns, h.m
    assert pm.ProactorPump is not None
    loop.gateway_auto_respond = False
    proc = h.spawn_gateway()
    loop.gateway_transport().script.write_mode = "force_close"
    slot = b_ns.OperationSlot("write")
    proc.begin_write_into(slot, d1.frame(base.GO, 1, 1), loop.t + 5.0)
    assert slot.op.outcome() == b_ns.WriteOutcome(delivery=r_ns.Delivery.UNKNOWN, bytes_written=0)
    h.owner.seal()
    h.owner.settle(loop.t + 4 * DT)
    assert h.first_of("SPAWN").pipes_lost[0] is True
    write = h.first_of("WRITE")
    assert write.protocol is m.ProtocolState.UNKNOWN and m.FaultKind.WRITE in write.faults


@pytest.mark.parametrize("variant", ["all-in-pending-calls", "exit-before-eof"])
def test_q4_fact_orders_settle_child_and_decode_act(core: Any, variant: str) -> None:
    pm = pump_module()
    loop = FakeLoop()
    prestart = variant == "all-in-pending-calls"
    script = ProcScript(stdout=[base.terminate_line()], prestart=prestart, exit_first=not prestart)
    loop.push_script("act-term-0", script)
    h = ProHarness(core, loop=loop)
    assert pm.ProactorPump is not None
    slot = h.run_act(h.make_act("TERMINATE_ONE_BACKEND", 20))
    outcome = slot.op.outcome()
    assert outcome.status is h.r_ns.ActStatus.OK
    assert outcome.facts == h.r_ns.TerminateFacts(found=1, terminated=True)
    child = h.first_of("CHILD")
    assert child.physical is h.m.PhysicalState.SETTLED_RETAINED
    assert (child.pipes_lost, child.returncode, child.exited) == ((None, False, False), 0, True)


# ---------------------------------------------------------------- Q5 four late-deadline cases


def late_write_handoff(h: ProHarness, proc: Any) -> Any:
    script = h.loop.gateway_transport().script
    script.write_mode, script.write_delay = "pending", 1.0 + DT
    slot = h.b_ns.OperationSlot("write")
    deadline = h.loop.t + 1.0
    proc.begin_write_into(slot, base.PACKET, deadline)
    h.owner.clock().poll((slot,), deadline + 2 * DT)
    return slot.op.outcome()


def sync_write_crossing(h: ProHarness, proc: Any) -> Any:
    slot = h.b_ns.OperationSlot("write")
    deadline = h.loop.t + 1.0

    def cross(lp: FakeLoop, _data: bytes) -> None:
        lp.t = deadline + DT

    h.loop.on_direct_write = cross
    proc.begin_write_into(slot, base.PACKET, deadline)
    return slot.op.outcome()


@pytest.mark.parametrize("case", ["late-write-handoff", "sync-write-crosses-deadline"])
def test_q5_late_write_cases_stay_unknown(core: Any, case: str) -> None:
    pm = pump_module()
    h = ProHarness(core)
    assert pm.ProactorPump is not None
    h.loop.gateway_emit_guard = False
    h.loop.gateway_auto_respond = False
    proc = h.spawn_gateway()
    run = late_write_handoff if case == "late-write-handoff" else sync_write_crossing
    outcome = run(h, proc)
    assert outcome == h.b_ns.WriteOutcome(delivery=h.r_ns.Delivery.UNKNOWN, bytes_written=0)
    assert h.first_of("WRITE").protocol is h.m.ProtocolState.UNKNOWN


@pytest.mark.parametrize("case", ["late-data", "late-eof"])
def test_q5_late_read_cases_fail_and_keep_late_bytes(core: Any, case: str) -> None:
    pm = pump_module()
    h = ProHarness(core)
    assert pm.ProactorPump is not None
    loop = h.loop
    loop.gateway_emit_guard = False
    proc = h.spawn_gateway()
    pipe = loop.gateway_transport().pipes[1]
    slot = h.b_ns.OperationSlot("read")
    deadline = loop.t + 1.0
    proc.begin_read_into(slot, 64, deadline)
    loop.sdk_at(deadline, pipe.feed, b"late" if case == "late-data" else None)  # completes +DT
    h.owner.clock().poll((slot,), deadline + 2 * DT)
    outcome = slot.op.outcome()
    assert outcome.ok is False and outcome.data == b""
    if case == "late-data":
        second = h.b_ns.OperationSlot("read")
        proc.begin_read_into(second, 64, loop.t + 1.0)
        assert second.op.outcome() == h.b_ns.ReadOutcome(ok=True, data=b"late")
    assert slot.op.outcome() is outcome


# ---------------------------------------------------------------- R1 run_until precedence


def test_r1a_raw_interrupt_reraised_by_identity_after_single_own_timer_cancel() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events, _auth, _ref = schedule(pump, loop, 1)
    probes: list[str] = []
    raw = FalseInterrupt(probes)
    loop.raw_after = ("connection_made", raw)
    target = loop.t + 1.0
    assert control_of(lambda: pump.run_until(target, never)) is raw
    assert len([e for e in loop.entries("call_at") if e[1] == target]) == 1
    assert loop.count("timer.cancel") == 1 and loop.running is False
    assert events.names() == ["started"]
    pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())
    assert events.names()[-1] == "closed" and probes == []


def test_r1b_first_event_control_wins_over_later_raw_interrupt() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events, _auth, _ref = schedule(pump, loop, 1)
    probes: list[str] = []
    first = FalseCtl(probes)
    events.raise_on["data"] = first
    loop.raw_after = ("pipe_data_received", KeyboardInterrupt())
    assert control_of(lambda: pump.run_until(loop.t + 1.0, never)) is first
    assert first.__context__ is None and first.__cause__ is None and probes == []
    pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())
    assert events.names()[-1] == "closed"


def test_r1c_cancel_exception_never_replaces_raw_and_is_reported_once() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events, _auth, _ref = schedule(pump, loop, 1)
    raw = KeyboardInterrupt()
    loop.raw_after = ("connection_made", raw)
    loop.cancel_fault = OSError(CANARY)
    assert control_of(lambda: pump.run_until(loop.t + 1.0, never)) is raw
    mark = loop.mark()
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))
    assert loop.count("call_at", since=mark) == 0 and loop.count("run_forever", since=mark) == 0
    pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())
    assert events.names()[-1] == "closed"


def test_r1d_cancel_control_is_reported_by_identity() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events, _auth, _ref = schedule(pump, loop, 1)
    probes: list[str] = []
    ctl = BoomCtl(probes)
    loop.cancel_fault = ctl
    got = control_of(lambda: pump.run_until(loop.t + 1.0, lambda: "closed" in events.names()))
    assert got is ctl and probes == []
    assert events.names()[-1] == "closed"


@pytest.mark.parametrize("phase", ["before", "after"])
def test_r1f_wait_timer_registration_failure_never_drives(phase: str) -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    loop.call_at_fault = (phase, OSError(CANARY))
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))
    assert loop.count("run_forever") == 0
    assert pump.run_until(loop.t + DT, never) == T0 + DT  # stale timer is harmless


def failing_stop(mode: str, pump: Any, events: FakeEvents, ctl: BaseException) -> Callable[[], Any]:
    def stop() -> object:
        if "started" not in events.names():
            return False
        if mode == "exception":
            raise ValueError(CANARY)
        if mode == "control":
            raise ctl
        if mode == "non-bool":
            return 1
        pump.run_until(pump.now() + 1.0, never)  # reentry from inside stop()
        return False

    return stop


@pytest.mark.parametrize("mode", ["exception", "control", "non-bool", "reentry"])
def test_r1g_stop_predicate_failures_are_closed(mode: str) -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events, _auth, _ref = schedule(pump, loop, 1)
    probes: list[str] = []
    ctl = FalseCtl(probes)
    stop = failing_stop(mode, pump, events, ctl)
    if mode == "control":
        assert control_of(lambda: pump.run_until(loop.t + 1.0, stop)) is ctl
    else:
        assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, stop))
    assert loop.count("run_forever") == 1 and probes == []  # the reentry never drove


def test_r1g_stop_is_evaluated_non_recursively_and_may_read_now() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events, _auth, _ref = schedule(pump, loop, 1)
    depth = [0, 0, 0]  # current, maximum, calls

    def stop() -> bool:
        depth[0] += 1
        depth[1] = max(depth[1], depth[0])
        depth[2] += 1
        try:
            pump.now()
            return "closed" in events.names()
        finally:
            depth[0] -= 1

    pump.run_until(loop.t + 1.0, stop)
    assert depth[1] == 1 and depth[2] >= len(events.seen) + 1


def test_r1h_expired_target_returns_now_without_driving_starts_or_deferred() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events, auth, _ref = schedule(pump, loop, 1)
    loop.call_at_fault = ("before", OSError(CANARY))
    deferred, _auth2, _ref2, _ctl = schedule_failing(pm, pump, loop, 2)
    mark = loop.mark()
    assert pump.run_until(loop.t, never) == T0
    assert pump.run_until(loop.t - DT, never) == T0
    for kind in ("call_at", "run_forever", "create_task", "authorize", "event", "stop"):
        assert loop.count(kind, since=mark) == 0
    pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())
    assert deferred.names() == ["not_started"] and auth.calls == 1
    first_auth = next(i for i, e in enumerate(loop.trace) if e[0] == "authorize")
    assert loop.trace.index(("event", 2, "not_started")) < first_auth  # deferred first


def test_r1i_idle_segments_fault_on_the_64th() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    frozen = loop.t
    loop.time_script = lambda _loop: frozen
    target = frozen + 1.0
    assert fault_of(pm, lambda: pump.run_until(target, never))
    assert loop.count("run_forever") == IDLE_SEGMENTS_MAX
    assert len([e for e in loop.entries("call_at") if e[1] == target]) == IDLE_SEGMENTS_MAX
    assert loop.count("timer.cancel") == IDLE_SEGMENTS_MAX
    loop.time_script = None
    assert pump.run_until(loop.t + DT, never) == loop.t  # no stale latch after the report


def test_r1j_early_timer_fire_within_resolution_takes_another_segment() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    loop.early_fire = DT / 2
    loop.early_fire_budget = 1
    target = loop.t + 4 * DT
    assert pump.run_until(target, never) == target
    assert loop.count("run_forever") == 2 and loop.count("timer.cancel") == 2


def test_r1k_boundary_refusals_never_consume_a_pending_latch() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    loop.call_exception_handler({"message": CANARY, "exception": ValueError(CANARY)})
    loop.ident_script = raiser(OSError(CANARY))
    mark = loop.mark()
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))  # identity boundary
    loop.ident_script = None
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))  # the latch, not driving
    assert loop.count("call_at", since=mark) == 0 and loop.count("run_forever", since=mark) == 0
    assert pump.run_until(loop.t + DT, never) == T0 + DT
    assert loop.count("run_forever", since=mark) == 1


# ---------------------------------------------------------------- R5 identity, handler, deferred


def stop_raising_at(site: str, events: FakeEvents, ctl: BaseException) -> Callable[[], bool]:
    def stop() -> bool:
        if site == "stop" and "started" in events.names():
            raise ctl
        return "closed" in events.names()

    return stop


@pytest.mark.parametrize("site", ["event", "stop", "cancel", "handler"])
@pytest.mark.parametrize("ctl_kind", ["falsey", "explosive"])
def test_r5ab_controls_are_kept_by_identity_without_truthiness(site: str, ctl_kind: str) -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events, _auth, _ref = schedule(pump, loop, 1)
    probes: list[str] = []
    ctl: BaseException = FalseCtl(probes) if ctl_kind == "falsey" else BoomCtl(probes)
    if site == "event":
        events.raise_on["started"] = ctl
    elif site == "cancel":
        loop.cancel_fault = ctl
    elif site == "handler":
        loop.error_after = ("connection_made", ctl)  # Handle._run routes it to the handler
    stop = stop_raising_at(site, events, ctl)
    assert control_of(lambda: pump.run_until(loop.t + 1.0, stop)) is ctl
    assert probes == [] and loop.fallback_calls == []


def test_r5c_second_control_is_dropped_and_report_clears_the_latch() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    loop.push_script("act-term-0", ProcScript(stdout=[base.terminate_line()], prestart=True))
    events, _auth, _ref = schedule(pump, loop, 1)
    probes: list[str] = []
    first = FalseCtl(probes)
    events.raise_on["started"] = first
    events.raise_on["data"] = FalseCtl(probes)  # same batch, after the first
    assert control_of(lambda: pump.run_until(loop.t + 1.0, never)) is first
    assert events.names() == ["started", "data", "pipe_lost", "pipe_lost", "exited", "closed"]
    assert pump.run_until(loop.t + DT, never) == loop.t  # next conduction is normal
    assert probes == []


MALFORMED_CONTEXTS: dict[str, dict[str, object]] = {
    "int": {"exception": 7},
    "object": {"exception": object()},
    "exception": {"exception": ValueError(CANARY)},
    "empty": {},
    "none": {"exception": None},
}


@pytest.mark.parametrize("case", sorted(MALFORMED_CONTEXTS))
def test_r5d_handler_without_real_control_records_only_a_fault(case: str) -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    loop.call_exception_handler(dict(MALFORMED_CONTEXTS[case]))
    assert loop.fallback_calls == []
    mark = loop.mark()
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))  # never TypeError/control
    assert loop.count("run_forever", since=mark) == 0
    assert pump.run_until(loop.t + DT, never) == T0 + DT


def test_r5e_exact_dict_control_is_raised_at_the_next_boundary() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    probes: list[str] = []
    ctl = BoomCtl(probes)
    loop.call_exception_handler({"message": CANARY, "exception": ctl})
    mark = loop.mark()
    assert control_of(lambda: pump.run_until(loop.t + 1.0, never)) is ctl
    assert loop.count("call_at", since=mark) == 0 and probes == []
    assert loop.fallback_calls == []


class HostileContext(dict[Any, Any]):
    """dict subclass: the closed handler must never call any of its methods."""

    def __init__(self, touched: list[str], exc: BaseException) -> None:
        super().__init__(exception=exc)
        self.touched = touched

    def get(self, key: Any, default: Any = None) -> Any:
        self.touched.append(f"get:{key}:{default is None}")
        raise AssertionError("context.get called")

    def __getitem__(self, key: Any) -> Any:
        self.touched.append(f"getitem:{key}")
        raise AssertionError("context[...] called")

    def __contains__(self, key: object) -> bool:
        self.touched.append(f"contains:{key}")
        raise AssertionError("key in context called")


def test_r5f_non_exact_dict_context_is_never_inspected() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    touched: list[str] = []
    probes: list[str] = []
    loop.call_exception_handler(HostileContext(touched, FalseCtl(probes)))
    assert touched == [] and loop.fallback_calls == []
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))  # only a fault
    assert probes == []


@pytest.mark.parametrize("prior_control", [False, True])
def test_r5g_handler_stop_failure_never_reaches_the_fallback(prior_control: bool) -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events, _auth, _ref = schedule(pump, loop, 1)
    probes: list[str] = []
    prior = FalseCtl(probes)
    interrupt = KeyboardInterrupt()
    if prior_control:
        events.raise_on["started"] = prior
    loop.error_after = ("connection_made", ValueError(CANARY))
    loop.stop_fault = interrupt  # the first loop.stop() requested by a latch fails
    expected = prior if prior_control else interrupt
    assert control_of(lambda: pump.run_until(loop.t + 1.0, never)) is expected
    assert loop.fallback_calls == [] and probes == []


class TrapValue:
    def __init__(self, touched: list[str]) -> None:
        self.touched = touched

    def __repr__(self) -> str:
        self.touched.append("repr")
        return "TrapValue"

    def __str__(self) -> str:
        self.touched.append("str")
        return "TrapValue"


def test_r5h_handler_never_formats_or_retains_context_values() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    touched: list[str] = []
    value = TrapValue(touched)
    ref = weakref.ref(value)
    context: dict[str, object] = {"message": CANARY, "exception": ValueError(CANARY)}
    context["transport"] = value
    loop.call_exception_handler(context)
    del context, value
    assert ref() is None and touched == []
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))


@pytest.mark.parametrize("failure", ["exception", "control"])
def test_r5i_deferred_failure_blocks_every_segment_and_start_until_reported(failure: str) -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    loop.call_at_fault = ("before", OSError(CANARY))
    ev_a, auth_a, ref_a, ctl_a = schedule_failing(pm, pump, loop, 1)
    assert ctl_a is None
    ev_b, auth_b, _ref_b = schedule(pump, loop, 2)
    probes: list[str] = []
    ctl = FalseCtl(probes)
    ev_a.raise_on["not_started"] = ValueError(CANARY) if failure == "exception" else ctl
    mark = loop.mark()
    if failure == "exception":
        assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))
    else:
        assert control_of(lambda: pump.run_until(loop.t + 1.0, never)) is ctl
    assert ev_a.names() == ["not_started"] and auth_b.calls == 0
    for kind in ("call_at", "run_forever", "create_task"):
        assert loop.count(kind, since=mark) == 0
    pump.run_until(loop.t + 1.0, lambda: "closed" in ev_b.names())  # real admission now
    assert auth_b.calls == 1 and auth_a.calls == 0 and ev_a.names() == ["not_started"]
    assert ref_a() is None and probes == []


def test_r5j_deferred_drain_stops_when_stop_becomes_true() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    loop.call_at_fault = ("before", OSError(CANARY))
    ev1, _a1, _r1, _c1 = schedule_failing(pm, pump, loop, 1)
    loop.call_at_fault = ("before", OSError(CANARY))
    ev2, _a2, _r2, _c2 = schedule_failing(pm, pump, loop, 2)
    pump.run_until(loop.t + 1.0, lambda: "not_started" in ev1.names())
    assert ev1.names() == ["not_started"] and ev2.seen == []
    pump.run_until(loop.t + 1.0, lambda: "not_started" in ev2.names())
    assert ev2.names() == ["not_started"] and loop.count("run_forever") == 0


def test_r2d_handler_faults_outside_run_are_reported_once_without_driving() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    loop.call_exception_handler({"exception": ValueError(CANARY)})
    loop.call_exception_handler({"exception": RuntimeError(CANARY)})
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))
    assert loop.count("run_forever") == 0 and loop.fallback_calls == []
    assert pump.run_until(loop.t + DT, never) == T0 + DT


# ---------------------------------------------------------------- R8.2 / R8.4 normative


def test_r8_2_fresh_time_after_deferred_reaching_target_opens_no_segment() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    loop.call_at_fault = ("before", OSError(CANARY))
    ev_a, _auth_a, _ref_a, _ctl_a = schedule_failing(pm, pump, loop, 1)
    _ev_b, auth_b, _ref_b = schedule(pump, loop, 2)
    target = loop.t + 1.0

    def jump() -> None:
        loop.t = target + DT

    ev_a.hooks["not_started"] = jump
    mark = loop.mark()
    assert pump.run_until(target, never) == target + DT
    assert ev_a.names() == ["not_started"] and auth_b.calls == 0
    for kind in ("call_at", "run_forever", "create_task"):
        assert loop.count(kind, since=mark) == 0


def test_r8_4_deferred_created_during_a_callback_waits_for_the_next_conduction() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events_a, _auth_a, _ref_a = schedule(pump, loop, 1)
    child: dict[str, Any] = {}

    def schedule_child_with_failure() -> None:
        loop.call_at_fault = ("after", OSError(CANARY))  # inserted, then failed
        req, ev_c, auth_c = request_for(loop, 2)
        child["events"], child["auth"] = ev_c, auth_c
        child["refused"] = fault_of(pm, lambda: pump.schedule_start(req))

    events_a.hooks["started"] = schedule_child_with_failure
    pump.run_until(loop.t + 1.0, lambda: "closed" in events_a.names())
    ev_c = child["events"]
    assert child["refused"] is True and ev_c.seen == []  # never in the creating conduction
    pump.run_until(loop.t + 1.0, lambda: "not_started" in ev_c.names())
    pump.run_until(loop.t + 2 * DT, never)  # the inserted stale _due fires harmlessly
    assert ev_c.names() == ["not_started"] and child["auth"].calls == 0
    assert loop.count("create_task") == 1 and loop.count("exec") == 1


def test_r8_4_initial_drain_delivers_only_the_snapshot_present_at_entry() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop, max_starts=2)
    loop.call_at_fault = ("before", OSError(CANARY))
    ev_a, auth_a, _ref_a, _ctl_a = schedule_failing(pm, pump, loop, 1)
    created: dict[str, Any] = {}

    def defer_another_during_drain() -> None:
        loop.call_at_fault = ("after", OSError(CANARY))  # inserted, then failed
        req, ev_b, auth_b = request_for(loop, 2)
        created["events"], created["auth"] = ev_b, auth_b
        created["refused"] = fault_of(pm, lambda: pump.schedule_start(req))

    ev_a.hooks["not_started"] = defer_another_during_drain
    target = loop.t + 4 * DT
    assert pump.run_until(target, never) == target  # stop() stays False for the whole run
    ev_b = created["events"]
    assert created["refused"] is True
    assert ev_a.names() == ["not_started"]
    assert ev_b.seen == []  # appended during the drain: NOT part of the entry snapshot
    pump.run_until(loop.t + 4 * DT, never)
    assert ev_b.names() == ["not_started"] and ev_a.names() == ["not_started"]
    assert auth_a.calls == 0 and created["auth"].calls == 0
    assert loop.count("create_task") == 0 and loop.count("exec") == 0
    extra = request_for(loop, 3)[0]
    assert fault_of(pm, lambda: pump.schedule_start(extra))  # bounds: max_starts == 2
    assert pump.close() is True


# ---------------------------------------------------------------- R6 gate, record ids and bounds


def failure_object(kind: str, probes: list[str]) -> BaseException:
    return OSError(CANARY) if kind == "exception" else FalseCtl(probes)


@pytest.mark.parametrize("kind", ["exception", "control"])
@pytest.mark.parametrize("phase", ["before", "after"])
def test_r6abcd_registration_failure_closes_gate_and_defers_true_not_started(
    phase: str, kind: str
) -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    probes: list[str] = []
    failure = failure_object(kind, probes)
    loop.call_at_fault = (phase, failure)
    events, auth, ref, got = schedule_failing(pm, pump, loop, 1)
    assert got is (failure if kind == "control" else None)
    assert ref() is None  # request released when the gate closed
    pump.run_until(loop.t + 1.0, lambda: "not_started" in events.names())
    pump.run_until(loop.t + 2 * DT, never)  # an inserted stale _due fires here, harmlessly
    assert events.names() == ["not_started"]
    assert auth.calls == 0  # it would have returned True: no reliance on owner state
    assert loop.count("create_task") == 0 and loop.count("exec") == 0
    assert probes == []
    assert pump.close() is True


@pytest.mark.parametrize("kind", ["exception", "control"])
@pytest.mark.parametrize("phase", ["before", "after"])
def test_r6e_task_creation_failure_defers_not_started_and_closes_own_coroutine(
    phase: str, kind: str
) -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events, auth, _ref = schedule(pump, loop, 1)
    probes: list[str] = []
    failure = failure_object(kind, probes)
    loop.create_task_fault = (phase, failure)
    if kind == "exception":
        assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))
    else:
        assert control_of(lambda: pump.run_until(loop.t + 1.0, never)) is failure
    assert events.seen == []
    pump.run_until(loop.t + 1.0, lambda: "not_started" in events.names())
    pump.run_until(loop.t + 2 * DT, never)  # a step queued despite the failure must not authorize
    assert events.names() == ["not_started"] and auth.calls == 0 and loop.count("exec") == 0
    (coro,) = loop.task_coros
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert pump.close() is True
    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED
    assert not any("never awaited" in str(item.message) for item in caught)
    assert loop.count("loop.close") == 1 and probes == []


def test_r6f_record_ids_are_never_reused_and_max_starts_bounds_entries() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop, max_starts=4)
    ev1, auth1, _r1 = schedule(pump, loop, 1)

    def dup(rid: int) -> Callable[[], None]:
        req = request_for(loop, rid)[0]
        return lambda: pump.schedule_start(req)

    assert fault_of(pm, dup(1))  # QUEUED
    loop.call_at_fault = ("before", OSError(CANARY))
    ev2, _a2, _r2, _c2 = schedule_failing(pm, pump, loop, 2)
    assert fault_of(pm, dup(2))  # gate CLOSED
    req3, ev3, auth3 = request_for(loop, 3)
    auth3.result = False
    pump.schedule_start(req3)
    pump.run_until(
        loop.t + 1.0,
        lambda: "closed" in ev1.names() and "not_started" in ev3.names(),
    )
    assert ev2.names() == ["not_started"]
    for rid in (1, 2, 3):  # STARTED/closed, NOT_STARTED (gate), NOT_STARTED (authorize)
        assert fault_of(pm, dup(rid))
    schedule(pump, loop, 4)
    assert fault_of(pm, dup(5))  # max_starts reached
    assert ev1.names() == ["started", "data", "pipe_lost", "pipe_lost", "exited", "closed"]
    assert auth1.calls == 1 and auth3.calls == 1


class PartialEvents:
    def started(self, handle: Any) -> None:
        raise AssertionError(handle)


MALFORMED_REQUESTS = (
    "rid-zero",
    "rid-bool",
    "rid-huge",
    "argv-empty",
    "argv-list",
    "argv-65",
    "argv-non-str",
    "stdin-int",
    "not-before-nan",
    "authorize-none",
    "events-missing-methods",
)


def malformed_request(case: str, loop: FakeLoop) -> FakeRequest:
    req, _events, _auth = request_for(loop, 1)
    changes: dict[str, tuple[str, object]] = {
        "rid-zero": ("record_id", 0),
        "rid-bool": ("record_id", True),
        "rid-huge": ("record_id", 2**31),
        "argv-empty": ("argv", ()),
        "argv-list": ("argv", ["helper", "act-term-0", base.SCOPE_ID]),  # a list, not a tuple
        "argv-65": ("argv", ("x",) * 65),
        "argv-non-str": ("argv", ("helper", 7)),
        "stdin-int": ("stdin_pipe", 0),
        "not-before-nan": ("not_before", math.nan),
        "authorize-none": ("authorize", None),
        "events-missing-methods": ("events", PartialEvents()),
    }
    name, value = changes[case]
    setattr(req, name, value)
    return req


@pytest.mark.parametrize("case", MALFORMED_REQUESTS)
def test_x9_malformed_request_is_refused_without_any_registration(case: str) -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    bad = malformed_request(case, loop)
    assert fault_of(pm, lambda: pump.schedule_start(bad))
    assert loop.count("call_at") == 0
    events, _auth, _ref = schedule(pump, loop, 1)  # rid 1 is still free
    pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())
    assert events.names()[-1] == "closed"


def test_r6g_duplicated_due_callback_authorizes_exactly_once() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    loop.duplicate_next_call_at = True
    events, auth, _ref = schedule(pump, loop, 1)
    pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())
    pump.run_until(loop.t + 2 * DT, never)
    assert auth.calls == 1 and loop.count("exec") == 1
    assert events.names() == ["started", "data", "pipe_lost", "pipe_lost", "exited", "closed"]


# ---------------------------------------------------------------- R7 stdin limits, handle


def test_r7c_helper_without_stdin_never_touches_fd0_and_settles(core: Any) -> None:
    pm = pump_module()
    h = ProHarness(core)
    assert pm.ProactorPump is not None
    slot = h.run_act(h.make_act("TERMINATE_ONE_BACKEND", 20))
    assert slot.op.outcome().status is h.r_ns.ActStatus.OK
    child = h.first_of("CHILD")
    assert child.physical is h.m.PhysicalState.SETTLED_RETAINED
    assert ("get_pipe_transport", "act-term-0", 0) not in h.loop.trace
    assert not [e for e in h.loop.entries("set_write_buffer_limits") if e[1] == "act-term-0"]


LIMIT_FAILURES = (
    "raise_after_set-exception",
    "raise_after_set-control",
    "raise_before_set-exception",
    "missing_stdin",
)


def poll_spawn_with_limit_failure(h: ProHarness, mode: str, ctl: BaseException) -> Any:
    slot = h.b_ns.OperationSlot("spawn")
    h.owner.gateway().begin_spawn_into(slot, h.loop.t + 5.0)

    def poll() -> object:
        return h.owner.clock().poll((slot,), h.loop.t + 5.0)

    if mode.endswith("-control"):
        assert control_of(poll) is ctl and h.owner.first_control() is ctl
    elif mode.endswith("-exception"):
        with pytest.raises(h.m.OwnershipRefusal) as caught:
            poll()
        base.assert_refusal(h.m, caught.value, "PUMP")  # the pump latched a closed fault
    else:
        poll()
    return slot.op.outcome()


@pytest.mark.parametrize("mode", LIMIT_FAILURES)
def test_r7de_failed_stdin_limits_stay_a_failure_even_if_values_became_zero(
    core: Any, mode: str
) -> None:
    pm = pump_module()
    loop = FakeLoop()
    probes: list[str] = []
    ctl = FalseCtl(probes)
    limits_mode = mode.split("-", maxsplit=1)[0]
    exc: BaseException = ctl if mode.endswith("-control") else OSError(CANARY)
    script = ProcScript(never_exit=True, limits_mode=limits_mode, limits_exc=exc)
    loop.push_script(GATEWAY_KEY, script)
    h = ProHarness(core, loop=loop)
    assert pm.ProactorPump is not None
    outcome = poll_spawn_with_limit_failure(h, mode, ctl)
    assert outcome.ok is False and outcome.process is None
    spawn = h.first_of("SPAWN")
    m = h.m
    assert spawn.protocol is m.ProtocolState.UNKNOWN and m.FaultKind.WRITE_LIMITS in spawn.faults
    assert spawn.physical is m.PhysicalState.OPEN and m.Retained.TRANSPORT in spawn.retained
    assert loop.count("get_write_buffer_limits") == 0  # (-1, -1) is constant, never re-read
    assert loop.count("write") == 0 and probes == []
    if limits_mode == "raise_after_set":
        assert loop.gateway_transport().pipes[0].get_write_buffer_limits() == (0, 0)


def pump_tree() -> ast.Module:
    return ast.parse(PUMP_FILE.read_text(encoding="utf-8"))


def find_def(tree: ast.AST, name: str) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name:
            return node
    pytest.fail(f"design-named definition {name} not found")


def called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            if isinstance(func, ast.Attribute):
                names.add(func.attr)
            elif isinstance(func, ast.Name):
                names.add(func.id)
    return names


def test_r7f_gate_consults_ident_and_handle_bypasses_gate() -> None:
    pm = pump_module()
    assert pm.ProactorPump is not None
    tree = pump_tree()
    gate_calls = called_names(find_def(tree, "_gate"))
    reaches_ident = any("ident" in name for name in gate_calls)
    if not reaches_ident and "_ident_ok" in gate_calls:
        reaches_ident = any("ident" in n for n in called_names(find_def(tree, "_ident_ok")))
    assert reaches_ident
    handle = find_def(tree, "_Handle")
    assert "_gate" not in {n.attr for n in ast.walk(handle) if isinstance(n, ast.Attribute)}


# ---------------------------------------------------------------- R3 startup phases and custody


AUTHORIZE_REFUSALS = ("one", "none", "exception", "control")


@pytest.mark.parametrize("case", AUTHORIZE_REFUSALS)
def test_r3d_authorize_refusal_is_not_started_without_exec(case: str) -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    events, auth, ref = schedule(pump, loop, 1)
    probes: list[str] = []
    ctl = FalseCtl(probes)
    auth.result = 1 if case == "one" else None
    if case in ("exception", "control"):
        auth.exc = OSError(CANARY) if case == "exception" else ctl

    def run() -> object:
        return pump.run_until(loop.t + 1.0, lambda: "not_started" in events.names())

    if case == "exception":
        assert fault_of(pm, run)
    elif case == "control":
        assert control_of(run) is ctl
    else:
        run()
    assert events.names() == ["not_started"] and auth.calls == 1
    assert loop.count("exec") == 0 and ref() is None and probes == []
    assert pump.close() is True


@pytest.mark.parametrize("kind", ["exception", "control"])
@pytest.mark.parametrize("mode", ["raise_before", "raise_after_popen"])
def test_r3eg_exec_failure_before_started_is_start_failed_never_not_started(
    mode: str, kind: str
) -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    probes: list[str] = []
    failure = failure_object(kind, probes)
    loop.push_script("act-term-0", ProcScript(exec_mode=mode, exec_exc=failure))
    events, _auth, ref = schedule(pump, loop, 1)

    def run() -> object:
        return pump.run_until(loop.t + 1.0, lambda: "start_failed" in events.names())

    if kind == "control":
        assert control_of(run) is failure
    else:
        run()
    assert events.names() == ["start_failed"] and ref() is None and probes == []
    automatic = mode == "raise_after_popen"
    assert (loop.count("sdk.close"), loop.count("sdk.kill")) == ((1, 1) if automatic else (0, 0))
    assert loop.count("transport.close") == 0 and loop.count("transport.kill") == 0
    assert pump.close() is False  # START_FAILED without started is not quiescent
    assert loop.count("loop.close") == 0


def test_r3e_late_connection_after_start_failed_still_delivers_every_fact() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    script = ProcScript(
        stdout=[base.terminate_line()],
        exec_mode="raise_with_live_connect",
        exec_exc=OSError(CANARY),
    )
    loop.push_script("act-term-0", script)
    events, _auth, _ref = schedule(pump, loop, 1)
    pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())
    assert events.names() == [
        "start_failed",
        "started",
        "data",
        "pipe_lost",
        "pipe_lost",
        "exited",
        "closed",
    ]


def test_r3g_control_after_started_is_only_the_latch() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    probes: list[str] = []
    ctl = BoomCtl(probes)
    script = ProcScript(stdout=[base.terminate_line()], exec_mode="raise_after_connected")
    script.exec_exc = ctl
    loop.push_script("act-term-0", script)
    events, _auth, _ref = schedule(pump, loop, 1)
    assert control_of(lambda: pump.run_until(loop.t + 1.0, never)) is ctl
    assert events.names() == ["started"]
    pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())
    assert "start_failed" not in events.names() and probes == []


def test_r3f_exec_pending_forever_retains_request_and_refuses_close() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    loop.push_script("act-term-0", ProcScript(exec_mode="connect_fail"))
    events, auth, ref = schedule(pump, loop, 1)
    pump.run_until(loop.t + 1.0, never)
    assert events.seen == [] and auth.calls == 1
    assert ref() is not None  # honest retention while S4 stays suspended
    assert loop.count("sdk.close") == 1 and loop.count("transport.kill") == 0
    assert pump.close() is False and loop.count("loop.close") == 0


def test_r3h_foreign_transport_is_a_fault_without_extra_event() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    script = ProcScript(stdout=[base.terminate_line()], exec_mode="foreign_transport")
    loop.push_script("act-term-0", script)
    events, _auth, _ref = schedule(pump, loop, 1)
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))
    assert events.names() == ["started"]


def test_r3_partial_startup_keeps_owner_custody_and_refuses_pump_close(core: Any) -> None:
    pm = pump_module()
    loop = FakeLoop()
    script = ProcScript(never_exit=True, exec_mode="raise_with_live_connect")
    script.exec_exc = OSError(CANARY)
    loop.push_script(GATEWAY_KEY, script)
    h = ProHarness(core, loop=loop)
    m = h.m
    assert pm.ProactorPump is not None
    slot = h.spawn_slot()
    assert slot.op.outcome().ok is False
    spawn = h.first_of("SPAWN")
    assert spawn.protocol is m.ProtocolState.UNKNOWN and m.FaultKind.START in spawn.faults
    assert spawn.physical is m.PhysicalState.UNKNOWN and spawn.uncertain is True
    h.owner.seal()
    h.owner.settle(loop.t + 1.0)
    late = h.first_of("SPAWN")
    assert any(fact.kind is m.LateKind.STARTED for fact in late.late)
    assert late.physical is m.PhysicalState.OPEN and m.Retained.TRANSPORT in late.retained
    assert slot.op.outcome().ok is False  # the published outcome never changes
    for kind in ("transport.close", "transport.kill", "sdk.kill", "loop.close"):
        assert loop.count(kind) == 0
    assert h.pump.close() is False


# ---------------------------------------------------------------- R4 paused EOF and close states


def assert_state_refusal(h: ProHarness, kind_name: str, target: int) -> None:
    kind = getattr(h.m.DisposeKind, kind_name)
    with pytest.raises(h.m.OwnershipRefusal) as caught:
        h.owner.begin_dispose(kind, target, h.loop.t + 1.0)
    base.assert_refusal(h.m, caught.value, "STATE")


def test_r4a_child_cap_pauses_reading_retains_eof_and_refuses_disposal(core: Any) -> None:
    pm = pump_module()
    loop = FakeLoop()
    loop.push_script("act-term-0", ProcScript(stdout=[b"x" * base.CHILD_STDOUT_CAP]))
    h = ProHarness(core, loop=loop)
    assert pm.ProactorPump is not None
    slot = h.run_act(h.make_act("TERMINATE_ONE_BACKEND", 20, window=1.0))
    assert slot.op.done() is False
    assert ("pause_reading", "act-term-0", 1) in loop.trace
    assert ("read.held", "act-term-0", 1, True) in loop.trace  # no fabricated EOF
    h.owner.seal()
    h.owner.settle(loop.t + 1.0)
    child = h.first_of("CHILD")
    assert child.accepted_total == base.CHILD_STDOUT_CAP and child.exited is True
    assert child.pipes_lost == (None, None, False) and child.returncode == 0
    assert child.physical is h.m.PhysicalState.OPEN
    assert_state_refusal(h, "CLOSE_HANDLE", child.record_id)
    assert_state_refusal(h, "TERMINATE_PROCESS", child.record_id)
    assert h.pump.close() is False and h.pump.close() is False
    assert loop.count("resume_reading") == 0 and loop.count("loop.close") == 0


def test_r4b_gateway_cap_then_kill_exits_without_eof_and_close_is_refused(core: Any) -> None:
    pm = pump_module()
    h = ProHarness(core)
    loop, m = h.loop, h.m
    assert pm.ProactorPump is not None
    loop.gateway_emit_guard = False
    h.spawn_gateway()
    loop.gateway_transport().pipes[1].feed(b"x" * base.GATEWAY_STDOUT_CAP)
    h.owner.seal()
    h.owner.settle(loop.t + 4 * DT)
    assert ("pause_reading", GATEWAY_KEY, 1) in loop.trace
    spawn_id = h.first_of("SPAWN").record_id
    term_id = h.owner.begin_dispose(m.DisposeKind.TERMINATE_PROCESS, spawn_id, loop.t + 1.0)
    h.owner.settle(loop.t + 1.0)
    assert ("transport.kill", GATEWAY_KEY) in loop.trace
    assert ("read.held", GATEWAY_KEY, 1, True) in loop.trace
    spawn = h.first_of("SPAWN")
    assert (spawn.exited, spawn.returncode, spawn.pipes_lost) == (True, 1, (False, None, None))
    assert spawn.physical is m.PhysicalState.OPEN
    term = next(r for r in h.owner.records() if r.record_id == term_id)
    assert term.protocol is not m.ProtocolState.SUCCEEDED
    assert_state_refusal(h, "CLOSE_HANDLE", spawn_id)
    assert_state_refusal(h, "TERMINATE_PROCESS", spawn_id)
    assert h.pump.close() is False and loop.count("resume_reading") == 0


@pytest.mark.parametrize("kind", ["exception", "control"])
def test_r4d_failed_loop_close_is_broken_and_never_repeated(kind: str) -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    probes: list[str] = []
    failure = failure_object(kind, probes)
    loop.close_fault = failure
    if kind == "exception":
        assert pump.close() is False
    else:
        assert control_of(pump.close) is failure
    assert pump.close() is False and loop.count("loop.close") == 1
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))
    assert probes == []


def test_r4e_close_inside_run_or_with_pending_latch_is_refused() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    results: list[object] = []

    def stop() -> bool:
        results.append(pump.close())
        return True

    pump.run_until(loop.t + 1.0, stop)
    assert results == [False] and loop.count("loop.close") == 0
    loop.call_exception_handler({"exception": ValueError(CANARY)})
    assert pump.close() is False and loop.count("loop.close") == 0
    assert fault_of(pm, lambda: pump.run_until(loop.t + 1.0, never))
    assert pump.close() is True and loop.count("loop.close") == 1


# ---------------------------------------------------------------- X12 / X13 / X14


def test_x12_repr_and_faults_never_carry_argv_bytes_or_messages() -> None:
    pm = pump_module()
    loop = FakeLoop()
    pump = make_pump(pm, loop)
    script = ProcScript(stdout=[CANARY.encode("ascii") + b"\n"])
    loop.push_script("act-term-0", script)
    events, _auth, _ref = schedule(pump, loop, 1)
    pump.run_until(loop.t + 1.0, lambda: "closed" in events.names())
    texts = [repr(pump), str(pump), repr(events.handle), str(events.handle)]
    loop.call_at_fault = ("before", OSError(CANARY))
    req = request_for(loop, 2)[0]
    try:
        pump.schedule_start(req)
    except pm.PumpFault as error:
        texts.extend([str(error), repr(error)])
        assert error.__cause__ is None and error.__context__ is None and error.args == ()
    assert len(texts) == 6
    assert all(secret not in text for text in texts for secret in SECRET_TEXTS)


FORBIDDEN_TOP_IMPORTS = {
    "asyncio",
    "subprocess",
    "signal",
    "socket",
    "threading",
    "logging",
    "warnings",
    "gc",
}
BINDING_IMPORTS = {"asyncio", "subprocess", "sys", "threading"}
FORBIDDEN_ATTRS = {
    "set_event_loop",
    "get_event_loop",
    "new_event_loop",
    "set_event_loop_policy",
    "get_event_loop_policy",
    "run_until_complete",
    "set_task_factory",
    "wait_for",
    "ensure_future",
    "call_soon_threadsafe",
    "shutdown_asyncgens",
    "shutdown_default_executor",
    "set_wakeup_fd",
    "addaudithook",
    "abort",
}
SDK_PRIVATE_ATTRS = {
    "_ready",
    "_scheduled",
    "_stopping",
    "_pending_calls",
    "_proc",
    "_pipes",
    "_returncode",
    "_buffer",
    "_paused",
    "_pending_data_length",
    "_protocol",
    "_task_factory",
    "_exception_handler",
    "_debug",
    "_thread_id",
    "_selector",
    "_proactor",
    "_write_fut",
    "_read_fut",
    "_conn_lost",
    "_high_water",
    "_low_water",
}


def module_names(node: ast.Import | ast.ImportFrom) -> set[str]:
    if isinstance(node, ast.ImportFrom):
        return {(node.module or "").split(".")[0]}
    return {alias.name.split(".")[0] for alias in node.names}


def enclosing_functions(tree: ast.Module) -> dict[int, str]:
    owner_of: dict[int, str] = {}
    for func in ast.walk(tree):
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(func):
                owner_of.setdefault(id(sub), func.name)
    return owner_of


def test_x13_imports_apis_private_attributes_and_effect_calls() -> None:
    pm = pump_module()
    assert pm.ProactorPump is not None
    tree = pump_tree()
    owner_of = enclosing_functions(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = module_names(node)
            assert "docs" not in names and not any("ownership" in n for n in names)
            if names & FORBIDDEN_TOP_IMPORTS or "sys" in names:
                assert owner_of.get(id(node)) == "bind_proactor_pump"
                assert names <= BINDING_IMPORTS
        if isinstance(node, ast.Attribute):
            assert node.attr not in FORBIDDEN_ATTRS
            receiver = node.value
            is_self = isinstance(receiver, ast.Name) and receiver.id in ("self", "cls")
            assert is_self or node.attr not in SDK_PRIVATE_ATTRS
            is_asyncio = isinstance(receiver, ast.Name) and receiver.id == "asyncio"
            assert not (is_asyncio and node.attr == "run")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver_text = ast.unparse(node.func.value)
            if node.func.attr == "cancel":
                assert "timer" in receiver_text.lower()
            if node.func.attr == "kill":
                assert owner_of.get(id(node)) == "kill"


@pytest.mark.parametrize("code", [300, -1])
def test_x14_exit_code_outside_owner_domain_stays_open_and_retained(core: Any, code: int) -> None:
    pm = pump_module()
    loop = FakeLoop()
    loop.push_script("act-term-0", ProcScript(stdout=[base.terminate_line()], exit_code=code))
    h = ProHarness(core, loop=loop)
    assert pm.ProactorPump is not None
    slot = h.run_act(h.make_act("TERMINATE_ONE_BACKEND", 20, window=1.0))
    assert slot.op.done() is False
    child = h.first_of("CHILD")
    assert child.returncode is None and h.m.FaultKind.CALLBACK in child.faults
    assert child.physical is h.m.PhysicalState.OPEN and child.uncertain is True
    assert ("exited", "act-term-0", code) in loop.trace
    h.owner.seal()
    h.owner.settle(loop.t + 1.0)
    assert h.first_of("CHILD").physical is h.m.PhysicalState.OPEN
    assert h.pump.close() is False
