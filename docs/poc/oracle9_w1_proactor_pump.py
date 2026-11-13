"""W1 Proactor pump (PROACTOR-DESIGN P3 + PROACTOR-REVIEW R8): the owner's Pump over a loop.

Implements the narrow ``Pump`` / ``ProcessHandle`` / ``ProcessEvents`` seam of the fixed
owner (PORT-DESIGN section 2.2) over the PUBLIC surface of an exclusive event loop
(``LoopSeam`` below): ``call_at``, ``create_task`` with the default non-eager factory,
``run_forever``/``stop``, ``subprocess_exec`` and the public transport/pipe methods. The
pump never reads private SDK attributes, never exposes its loop, never cancels a Task or
Future, and never calls close/kill outside the owner's explicit DISPOSE paths.

The module imports no asyncio/subprocess/signal/socket/threading/logging/warnings/gc at
top level; only ``bind_proactor_pump`` (the trusted real binding) imports asyncio,
subprocess, sys and threading, and it is never invoked by the fake-SDK oracles.

Facts are delivered to the owner only inside ``run_until``; the first control
(BaseException that is not Exception) is kept by identity and re-raised at the boundary;
every other failure becomes a closed ``PumpFault`` with no arguments and no chained
original. ``close()`` releases the loop only when every entry is locally quiescent and
otherwise retains everything. Nothing here is native proof of process, pipe or handle
cleanup (design N1..N16 remain OPEN).
"""

from __future__ import annotations

import enum
import math
from collections import deque
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Final, Protocol

IDLE_SEGMENTS_MAX: Final = 64
_MAX_STARTS: Final = 512
_MAX_RECORD_ID: Final = (1 << 31) - 1
_MAX_ARGV: Final = 64
_MAX_COUNTER: Final = (1 << 63) - 1
_FAILED_LIMITS: Final = (-1, -1)
_EVENT_NAMES: Final = (
    "started",
    "start_failed",
    "not_started",
    "data",
    "pipe_lost",
    "exited",
    "write_resumed",
    "closed",
)
_FAULT: Final = object()  # latch sentinel: records a fault, never a control


def _bump(value: int) -> int:
    return value + 1 if value < _MAX_COUNTER else _MAX_COUNTER


class PumpFault(Exception):
    """Closed pump refusal: ``args == ()``; always raised outside any except block."""

    def __init__(self) -> None:
        super().__init__()


# ---------------------------------------------------------------- public SDK seam (typing only)


class TimerSeam(Protocol):
    def cancel(self) -> None: ...


class TaskSeam(Protocol):
    def done(self) -> bool: ...


class PipeSeam(Protocol):
    def write(self, data: bytes) -> None: ...
    def get_write_buffer_size(self) -> int: ...
    def get_write_buffer_limits(self) -> tuple[int, int]: ...
    def set_write_buffer_limits(self, high: int | None = None, low: int | None = None) -> None: ...
    def is_closing(self) -> bool: ...
    def pause_reading(self) -> None: ...
    def resume_reading(self) -> None: ...


class TransportSeam(Protocol):
    def get_pid(self) -> object: ...
    def get_returncode(self) -> object: ...
    def get_pipe_transport(self, fd: int) -> PipeSeam | None: ...
    def is_closing(self) -> bool: ...
    def close(self) -> None: ...
    def kill(self) -> None: ...


class LoopSeam(Protocol):
    def time(self) -> object: ...
    def call_at(self, when: float, callback: Callable[..., object], *args: object) -> Any: ...
    def create_task(self, coro: Coroutine[Any, Any, None]) -> Any: ...
    def run_forever(self) -> None: ...
    def stop(self) -> None: ...
    def is_running(self) -> bool: ...
    def is_closed(self) -> bool: ...
    def close(self) -> None: ...
    def get_debug(self) -> bool: ...
    def set_debug(self, enabled: bool) -> None: ...
    def get_task_factory(self) -> object: ...
    def set_exception_handler(self, handler: Callable[[Any, Any], object] | None) -> None: ...
    def get_exception_handler(self) -> object: ...
    def subprocess_exec(
        self,
        protocol_factory: Callable[[], object],
        *args: str,
        stdin: int,
        stdout: int,
        stderr: int,
    ) -> Awaitable[object]: ...


# ---------------------------------------------------------------- closed local states


class _State(enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    BROKEN = "BROKEN"


class _Gate(enum.Enum):
    """Start ADMISSION only: SPENT never suppresses protocol facts (R8.3)."""

    OPEN = "OPEN"
    SPENT = "SPENT"
    CLOSED = "CLOSED"


class _Phase(enum.Enum):
    QUEUED = "QUEUED"
    TASKED = "TASKED"
    EXEC = "EXEC"
    EXEC_DONE = "EXEC_DONE"
    START_FAILED = "START_FAILED"
    DEFERRED = "DEFERRED"
    NOT_STARTED = "NOT_STARTED"


class _Start:
    """Per-record start entry; retained for the pump's life (bounded by max_starts)."""

    __slots__ = (
        "argv",
        "authorize",
        "closed_delivered",
        "coro",
        "coro_done",
        "explicit_close_ok",
        "gate",
        "handle",
        "limits_failed",
        "lost",
        "phase",
        "protocol",
        "record_id",
        "request",
        "sinks",
        "started",
        "stdin_pipe",
        "task",
        "timer",
        "transport",
        "write_paused",
    )

    def __init__(self, request: Any, admission: _Admission) -> None:
        self.record_id = admission.record_id
        # The original request is retained (P3 section 6/10) but NEVER read again: every
        # later phase uses the immutable admission snapshot below.
        self.request: Any = request
        self.argv: tuple[str, ...] | None = admission.argv
        self.authorize: Callable[[], object] | None = admission.authorize
        self.sinks: dict[str, Callable[..., object]] | None = admission.sinks
        self.stdin_pipe = admission.stdin_pipe
        self.phase = _Phase.QUEUED
        self.gate = _Gate.OPEN
        self.timer: Any = None
        self.coro: Coroutine[Any, Any, None] | None = None
        self.task: Any = None
        self.protocol: _PumpProtocol | None = None
        self.transport: Any = None
        self.handle: _Handle | None = None
        self.started = False
        self.limits_failed = False
        self.lost = False
        self.explicit_close_ok = False
        self.closed_delivered = False
        self.coro_done = False
        self.write_paused = False

    def __repr__(self) -> str:
        return "_Start(<redacted>)"

    def release_request(self) -> None:
        self.request = None
        self.argv = None
        self.authorize = None


class _Admission:
    """Validated immutable snapshot: each request field and event method read ONCE."""

    __slots__ = ("argv", "authorize", "not_before", "record_id", "sinks", "stdin_pipe")

    def __init__(
        self,
        record_id: int,
        argv: tuple[str, ...],
        stdin_pipe: bool,
        not_before: float,
        sinks: dict[str, Callable[..., object]],
        authorize: Callable[[], object],
    ) -> None:
        self.record_id = record_id
        self.argv = argv
        self.stdin_pipe = stdin_pipe
        self.not_before = not_before
        self.sinks = sinks
        self.authorize = authorize

    def __repr__(self) -> str:
        return "_Admission(<redacted>)"


def _read_admission(request: object) -> _Admission | None:
    """Reads each field once; invalid shape -> None. Exceptions are left to the caller."""
    record_id = getattr(request, "record_id")
    if not isinstance(record_id, int) or type(record_id) is not int:
        return None
    if not 1 <= record_id <= _MAX_RECORD_ID:
        return None
    argv = getattr(request, "argv")
    if not isinstance(argv, tuple) or type(argv) is not tuple:
        return None
    if not 1 <= len(argv) <= _MAX_ARGV or not all(type(item) is str for item in argv):
        return None
    stdin_pipe = getattr(request, "stdin_pipe")
    if not isinstance(stdin_pipe, bool) or type(stdin_pipe) is not bool:
        return None
    not_before = getattr(request, "not_before")
    if not _finite_number(not_before) or not isinstance(not_before, (int, float)):
        return None
    authorize = getattr(request, "authorize")
    if not callable(authorize):
        return None
    events = getattr(request, "events")
    if events is None:
        return None
    sinks: dict[str, Callable[..., object]] = {}
    for name in _EVENT_NAMES:
        sink = getattr(events, name)
        if not callable(sink):
            return None
        sinks[name] = sink
    return _Admission(record_id, argv, stdin_pipe, float(not_before), sinks, authorize)


def _admission_snapshot(request: object) -> _Admission | None:
    """Closed S0 boundary: any Exception -> None (caller raises PumpFault, no chain);
    a control (BaseException that is not Exception) propagates by identity, untouched."""
    failed = False
    admission: _Admission | None = None
    try:
        admission = _read_admission(request)
    except Exception:
        failed = True
    return None if failed else admission


def _quiescent(entry: _Start) -> bool:
    if entry.phase is _Phase.NOT_STARTED:
        return entry.task is None or entry.coro_done is True
    return (
        entry.started is True
        and entry.lost is True
        and entry.explicit_close_ok is True
        and entry.closed_delivered is True
        and entry.coro_done is True
    )


def _finite_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _sdk_call(fn: Callable[..., Any], *args: Any) -> Any:
    """Handle-side SDK call: Exception -> PumpFault() with no chain; controls pass through."""
    failed = False
    value: Any = None
    try:
        value = fn(*args)
    except Exception:
        failed = True
    if failed:
        raise PumpFault()
    return value


def _pipe_of(transport: Any, fd: int) -> Any:
    return transport.get_pipe_transport(fd)


def _zero_write_limits(pipe: Any) -> None:
    pipe.set_write_buffer_limits(high=0, low=0)


def _returncode_of(transport: Any) -> Any:
    return transport.get_returncode()


# ---------------------------------------------------------------- protocol and handle


class _PumpProtocol:
    """SubprocessProtocol by duck typing; every fact goes through the pump's _deliver."""

    __slots__ = ("_entry", "_pump")

    def __init__(self, pump: ProactorPump, entry: _Start) -> None:
        self._pump = pump
        self._entry = entry

    def connection_made(self, transport: Any) -> None:
        self._pump._on_connection_made(self._entry, transport)

    def pipe_data_received(self, fd: int, data: Any) -> None:
        self._pump._on_data(self._entry, fd, data)

    def pipe_connection_lost(self, fd: int, exc: BaseException | None) -> None:
        self._pump._on_pipe_lost(self._entry, fd, exc is not None)  # exc is never retained

    def process_exited(self) -> None:
        self._pump._on_exited(self._entry)

    def connection_lost(self, _exc: BaseException | None) -> None:
        self._pump._on_connection_lost(self._entry)

    def pause_writing(self) -> None:
        self._entry.write_paused = True  # synchronous inside write(): never an owner event

    def resume_writing(self) -> None:
        self._entry.write_paused = False
        self._pump._on_write_resumed(self._entry)

    def __repr__(self) -> str:
        return "_PumpProtocol(<redacted>)"


class _Handle:
    """ProcessHandle 1:1 over public transport/pipe methods; valid inside owner callbacks."""

    __slots__ = ("_entry", "_pump")

    def __init__(self, pump: ProactorPump, entry: _Start) -> None:
        self._pump = pump
        self._entry = entry

    def _transport(self) -> Any:
        transport = self._entry.transport
        if self._pump._state is not _State.OPEN or transport is None:
            raise PumpFault()
        return transport

    def _stdin(self, transport: Any) -> Any:
        if self._entry.stdin_pipe is not True:
            raise PumpFault()
        pipe = _sdk_call(_pipe_of, transport, 0)
        if pipe is None:
            raise PumpFault()
        return pipe

    def pid(self) -> Any:
        return _sdk_call(self._transport().get_pid)

    def returncode(self) -> Any:
        return _sdk_call(_returncode_of, self._transport())

    def write_limits(self) -> Any:
        transport = self._transport()
        if self._entry.limits_failed is True:
            return _FAILED_LIMITS  # constant: the SDK is never re-read after a failed set
        return _sdk_call(self._stdin(transport).get_write_buffer_limits)

    def write(self, data: bytes) -> None:
        pipe = self._stdin(self._transport())
        _sdk_call(pipe.write, data)

    def is_closing(self) -> bool:
        transport = self._transport()
        if _sdk_call(transport.is_closing) is not False:
            return True
        if self._entry.stdin_pipe is not True:
            return False
        return _sdk_call(self._stdin(transport).is_closing) is not False

    def buffer_size(self) -> Any:
        return _sdk_call(self._stdin(self._transport()).get_write_buffer_size)

    def pause_reading(self, fd: int) -> None:
        pipe = _sdk_call(_pipe_of, self._transport(), fd)
        if pipe is None:
            raise PumpFault()
        _sdk_call(pipe.pause_reading)

    def resume_reading(self, fd: int) -> None:
        pipe = _sdk_call(_pipe_of, self._transport(), fd)
        if pipe is None:
            raise PumpFault()
        _sdk_call(pipe.resume_reading)

    def close(self) -> None:
        _sdk_call(self._transport().close)
        self._pump._after_explicit_close(self._entry)

    def kill(self) -> None:
        _sdk_call(self._transport().kill)

    def __repr__(self) -> str:
        return "_Handle(<redacted>)"


# ---------------------------------------------------------------- ProactorPump


class ProactorPump:
    """Pump of the fixed owner over one exclusive, never-exposed loop."""

    def __init__(
        self,
        *,
        loop: Any,
        pipe: object,
        devnull: object,
        ident: object,
        max_starts: object = _MAX_STARTS,
    ) -> None:
        if not isinstance(max_starts, int) or type(max_starts) is not int:
            raise PumpFault()
        if not 1 <= max_starts <= _MAX_STARTS:
            raise PumpFault()
        if not isinstance(pipe, int) or type(pipe) is not int:
            raise PumpFault()
        if not isinstance(devnull, int) or type(devnull) is not int or pipe == devnull:
            raise PumpFault()
        if not callable(ident):
            raise PumpFault()
        self._loop: LoopSeam = loop
        self._ident: Callable[[], object] = ident
        self._pipe = pipe
        self._devnull = devnull
        self._max_starts = max_starts
        self._state = _State.OPEN
        self._in_run = False
        self._in_stop = False
        self._stop_busy = False
        self._stop_requested = False
        self._gen = 0
        self._delivered = 0
        self._stop: Callable[[], object] | None = None
        self._ctl: BaseException | None = None
        self._fault = False
        self._faults = 0
        self._ctl_dropped = 0
        self._dropped_events = 0
        self._stale_callbacks = 0
        self._entries: dict[int, _Start] = {}
        self._deferred: deque[_Start] = deque()
        self._last_time: float | None = None
        self._owner = self._first_identity()
        self._configure_loop()

    def __repr__(self) -> str:
        return "ProactorPump(<redacted>)"

    # ------------------------------------------------------------ construction

    def _first_identity(self) -> int:
        failed = False
        value: object = None
        try:
            value = self._ident()
        except Exception:
            failed = True
        if failed or not isinstance(value, int) or type(value) is not int:
            raise PumpFault()
        return value

    def _configure_loop(self) -> None:
        loop = self._loop
        clean = False
        try:
            clean = (
                loop.is_running() is False
                and loop.is_closed() is False
                and loop.get_task_factory() is None
            )
        except Exception:
            clean = False
        if not clean:
            raise PumpFault()
        configured = False
        try:
            loop.set_debug(False)
            loop.set_exception_handler(self._on_sdk_error)
            configured = (
                loop.get_debug() is False and loop.get_exception_handler() == self._on_sdk_error
            )
        except Exception:
            configured = False
        if not configured:
            raise PumpFault()

    # ------------------------------------------------------------ boundaries and clock

    def _ident_ok(self) -> None:
        failed = False
        value: object = None
        try:
            value = self._ident()
        except Exception:
            failed = True
        if failed or type(value) is not int or value != self._owner:
            raise PumpFault()

    def _gate(self, *, reentry_ok: bool) -> None:
        self._ident_ok()
        if self._state is not _State.OPEN:
            raise PumpFault()
        if not reentry_ok and self._in_run:
            raise PumpFault()

    def _check_time(self, value: object) -> float | None:
        if not _finite_number(value) or not isinstance(value, (int, float)):
            return None
        moment = float(value)
        if moment < 0:
            return None
        if self._last_time is not None and moment < self._last_time:
            return None
        self._last_time = moment  # the first VALID reading initializes the baseline (R8.1)
        return moment

    def now(self) -> float:
        self._gate(reentry_ok=True)
        failed = False
        value: object = None
        try:
            value = self._loop.time()
        except Exception:
            failed = True
        moment = None if failed else self._check_time(value)
        if moment is None:
            raise PumpFault()
        return moment

    def _time(self) -> float | None:
        caught: BaseException | None = None
        value: object = None
        try:
            value = self._loop.time()
        except BaseException as error:
            caught = error
        if caught is not None:
            self._latch(caught)
            return None
        moment = self._check_time(value)
        if moment is None:
            self._latch(_FAULT)
        return moment

    # ------------------------------------------------------------ latches (identity, never bool)

    def _latch(self, item: object, *, stop: bool = True) -> None:
        if isinstance(item, BaseException) and not isinstance(item, Exception):
            if self._ctl is None:
                self._ctl = item
            else:
                self._ctl_dropped = _bump(self._ctl_dropped)
        else:
            self._fault = True
            self._faults = _bump(self._faults)
        if stop:
            self._stop_loop()

    def _stop_loop(self) -> None:
        if not self._in_run or self._stop_busy:
            return
        self._stop_busy = True
        caught: BaseException | None = None
        try:
            if self._loop.is_running() is True:
                self._loop.stop()
        except BaseException as error:
            caught = error
        finally:
            self._stop_busy = False
        if caught is not None:
            self._latch(caught, stop=False)

    def _guard(self, fn: Callable[..., Any], *args: Any) -> tuple[bool, Any]:
        caught: BaseException | None = None
        try:
            return True, fn(*args)
        except BaseException as error:
            caught = error
        self._latch(caught)
        return False, None

    def _pending(self) -> bool:
        return self._ctl is not None or self._fault is True

    def _report(self) -> None:
        control = self._ctl
        if control is not None:
            self._ctl = None
            raise control
        if self._fault is True:
            self._fault = False
            raise PumpFault()

    def _on_sdk_error(self, _loop: object, context: object) -> None:
        """Closed exception handler: nothing escapes to the SDK default-handler fallback."""
        caught: BaseException | None = None
        try:
            exc: object = None
            if type(context) is dict:  # exact dict only: its methods cannot be overridden
                exc = dict.get(context, "exception")
            if isinstance(exc, BaseException) and not isinstance(exc, Exception):
                self._latch(exc)  # a real control forwarded by Handle._run
            else:
                self._latch(_FAULT)
        except BaseException as error:
            caught = error
        if caught is not None:
            self._latch(caught)

    # ------------------------------------------------------------ admission (schedule_start)

    def schedule_start(self, request: Any) -> None:
        """Inert: validates one snapshot, registers one entry and one start timer; no effect."""
        self._gate(reentry_ok=True)
        admission = _admission_snapshot(request)  # a control propagates here, unregistered
        if admission is None:
            raise PumpFault()
        record_id = admission.record_id
        if record_id in self._entries or len(self._entries) >= self._max_starts:
            raise PumpFault()
        entry = _Start(request, admission)
        self._entries[record_id] = entry
        failed = False
        control: BaseException | None = None
        try:
            entry.timer = self._loop.call_at(admission.not_before, self._due, entry)
        except Exception:
            failed = True
        except BaseException as caught:
            control = caught
        if not failed and control is None:
            return
        # Before or after insertion, indistinguishably: close the local gate for good, so a
        # late callback can never authorize, and defer the TRUE fact not_started (R6).
        entry.gate = _Gate.CLOSED
        entry.phase = _Phase.DEFERRED
        entry.release_request()
        entry.timer = None
        self._deferred.append(entry)
        del request
        if control is not None:
            raise control
        raise PumpFault()

    def _due(self, entry: _Start) -> None:
        if entry.gate is not _Gate.OPEN or entry.phase is not _Phase.QUEUED:
            self._stale_callbacks = _bump(self._stale_callbacks)
            return
        entry.timer = None
        coro = self._start(entry)
        entry.coro = coro
        failed = False
        control: BaseException | None = None
        task: Any = None
        try:
            task = self._loop.create_task(coro)
        except Exception:
            failed = True
        except BaseException as caught:
            control = caught
        if not failed and control is None:
            entry.task = task
            entry.coro = None
            entry.phase = _Phase.TASKED
            return
        # The public API cannot tell whether the step was queued: close the gate, keep the
        # coroutine (closed only after a successful loop.close) and defer not_started.
        entry.gate = _Gate.CLOSED
        entry.phase = _Phase.DEFERRED
        entry.release_request()
        self._deferred.append(entry)
        self._latch(control if control is not None else _FAULT)

    async def _start(self, entry: _Start) -> None:
        try:
            authorize = entry.authorize
            if entry.gate is not _Gate.OPEN or authorize is None:
                self._stale_callbacks = _bump(self._stale_callbacks)
                return
            entry.gate = _Gate.SPENT  # at most one authorization per entry
            entry.phase = _Phase.EXEC
            ok, allowed = self._guard(authorize)
            del authorize
            if not ok or allowed is not True:
                self._not_started(entry)
                return
            await self._exec(entry)  # same task step as authorize until the first suspension
        finally:
            entry.coro_done = True
            self._maybe_release(entry)  # only now may S4-held references be released

    def _not_started(self, entry: _Start) -> None:
        entry.phase = _Phase.NOT_STARTED
        entry.release_request()
        sinks = entry.sinks
        entry.sinks = None
        if sinks is None:
            self._latch(_FAULT)
        else:
            self._deliver(sinks["not_started"])

    async def _exec(self, entry: _Start) -> None:
        argv = entry.argv
        if argv is None:
            self._latch(_FAULT)
            return
        stdin_pipe = entry.stdin_pipe is True
        protocol = _PumpProtocol(self, entry)
        entry.protocol = protocol
        made = [False]

        def factory() -> _PumpProtocol:
            if made[0]:
                raise PumpFault()
            made[0] = True
            return protocol

        failed = False
        control: BaseException | None = None
        outcome: object = None
        try:
            outcome = await self._loop.subprocess_exec(
                factory,
                *argv,
                stdin=self._pipe if stdin_pipe else self._devnull,
                stdout=self._pipe,
                stderr=self._devnull if stdin_pipe else self._pipe,
            )
        except Exception:
            failed = True
        except BaseException as caught:
            control = caught
        del argv
        entry.release_request()  # terminal phase of S4: release the request and its snapshot
        if control is not None:
            self._latch(control)
            if entry.started is not True:
                entry.phase = _Phase.START_FAILED
                self._deliver_event(entry, "start_failed")
            return
        if failed:
            if entry.started is not True:
                entry.phase = _Phase.START_FAILED
            self._deliver_event(entry, "start_failed")
            return
        entry.phase = _Phase.EXEC_DONE
        transport = outcome[0] if isinstance(outcome, tuple) and len(outcome) == 2 else None
        if entry.started is not True or transport is None or transport is not entry.transport:
            self._latch(_FAULT)

    # ------------------------------------------------------------ protocol facts

    def _deliver(self, fn: Callable[..., object], *args: object) -> None:
        if not self._in_run or self._in_stop:
            self._dropped_events = _bump(self._dropped_events)
            self._latch(_FAULT)
            return
        ok, _value = self._guard(fn, *args)
        self._delivered = _bump(self._delivered)
        if ok and self._eval_stop():
            self._stop_requested = True
            self._stop_loop()

    def _deliver_event(self, entry: _Start, name: str, *args: object) -> None:
        sinks = entry.sinks
        if sinks is None:
            self._latch(_FAULT)
            return
        self._deliver(sinks[name], *args)  # the event method read once at admission

    def _on_connection_made(self, entry: _Start, transport: Any) -> None:
        if entry.transport is not None or entry.started is True or entry.sinks is None:
            self._latch(_FAULT)
            return
        entry.transport = transport
        entry.started = True
        if entry.stdin_pipe is True:  # helpers without stdin never touch fd 0 (R7)
            ok, pipe = self._guard(_pipe_of, transport, 0)
            if not ok or pipe is None:
                entry.limits_failed = True
            else:
                set_ok, _unused = self._guard(_zero_write_limits, pipe)
                entry.limits_failed = set_ok is not True  # persists even if values changed
        handle = _Handle(self, entry)
        entry.handle = handle
        self._deliver_event(entry, "started", handle)

    def _on_data(self, entry: _Start, fd: int, data: object) -> None:
        ok, chunk = self._guard(bytes, data)
        if ok:
            self._deliver_event(entry, "data", fd, chunk)

    def _on_pipe_lost(self, entry: _Start, fd: int, failed: bool) -> None:
        self._deliver_event(entry, "pipe_lost", fd, failed)

    def _on_exited(self, entry: _Start) -> None:
        transport = entry.transport
        if transport is None:
            self._latch(_FAULT)
            return
        ok, code = self._guard(_returncode_of, transport)
        if ok:
            self._deliver_event(entry, "exited", code)

    def _on_write_resumed(self, entry: _Start) -> None:
        self._deliver_event(entry, "write_resumed")

    def _on_connection_lost(self, entry: _Start) -> None:
        entry.lost = True
        self._deliver_event(entry, "closed")
        entry.closed_delivered = True
        self._maybe_release(entry)

    def _after_explicit_close(self, entry: _Start) -> None:
        entry.explicit_close_ok = True
        self._maybe_release(entry)

    def _maybe_release(self, entry: _Start) -> None:
        # S4 must have validated the transport returned by subprocess_exec first (coro_done):
        # a close inside closed() before that point keeps every reference retained.
        if (
            entry.started is True
            and entry.lost is True
            and entry.explicit_close_ok is True
            and entry.closed_delivered is True
            and entry.coro_done is True
        ):
            entry.protocol = None
            entry.transport = None
            entry.handle = None

    # ------------------------------------------------------------ driving

    def run_until(self, target: object, stop: Callable[[], object]) -> float:
        self._gate(reentry_ok=False)
        if self._pending():
            self._report()  # a latch observed outside run_until is reported without driving
        if not _finite_number(target) or not isinstance(target, (int, float)):
            raise PumpFault()
        self._in_run = True
        self._gen += 1
        self._stop = stop
        self._stop_requested = False
        result: float | None = None
        broken: BaseException | None = None
        try:
            result = self._drive(float(target))
        except BaseException as error:  # defense against a defect of the pump itself
            broken = error
        self._in_run = False
        self._stop = None
        if broken is not None:
            self._latch(broken)
        if self._pending():
            self._report()
        if result is None:
            raise PumpFault()
        return result

    def _drive(self, target: float) -> float | None:
        if not self._invariants_ok() or self._pending():
            return None
        if self._eval_stop():
            return self._time()
        now = self._time()
        if now is None:
            return None
        if now >= target:
            return now  # target reached: no loop, no start, no deferred delivery
        self._flush_deferred()
        if self._pending():
            return None  # barrier (R5): nothing runs before the report
        if self._eval_stop():
            return self._time()
        now = self._time()  # fresh time after deferred delivery (R8.2)
        if now is None:
            return None
        if now >= target:
            return now
        idle = 0
        while True:
            seg_start, delivered_before = now, self._delivered
            self._segment(target)
            if self._pending():
                return None
            if self._eval_stop():
                return self._time()
            now = self._time()
            if now is None:
                return None
            if now >= target:
                return now
            progressed = self._delivered != delivered_before or now != seg_start
            idle = 0 if progressed else idle + 1
            if idle >= IDLE_SEGMENTS_MAX:
                self._latch(_FAULT)
                return None

    def _invariants_ok(self) -> bool:
        loop = self._loop
        ok, clean = self._guard(_loop_invariants, loop, self._on_sdk_error)
        if not ok:
            return False
        if clean is not True:
            self._latch(_FAULT)
            return False
        return True

    def _flush_deferred(self) -> None:
        """Delivers only the snapshot present at entry (R8.4); later items wait."""
        for _ in range(len(self._deferred)):
            if not self._deferred:
                return
            entry = self._deferred.popleft()
            entry.phase = _Phase.NOT_STARTED
            sinks = entry.sinks
            entry.sinks = None
            if sinks is None:
                self._latch(_FAULT)
            else:
                self._deliver(sinks["not_started"])
            if self._pending() or self._stop_requested:
                return

    def _segment(self, target: float) -> None:
        ok, timer = self._guard(self._loop.call_at, target, self._wake, self._gen)
        if not ok:
            return
        raw: BaseException | None = None
        try:
            self._loop.run_forever()
        except BaseException as error:
            raw = error
        if raw is not None:
            self._latch(raw)  # registered BEFORE the cancel, which never replaces it
        self._guard(timer.cancel)

    def _wake(self, gen: int) -> None:
        if gen == self._gen and self._in_run:
            self._stop_loop()

    def _eval_stop(self) -> bool:
        stop = self._stop
        if stop is None or self._in_stop:
            self._latch(_FAULT)  # recursion or missing predicate is a violation
            return True
        self._in_stop = True
        try:
            ok, value = self._guard(stop)
        finally:
            self._in_stop = False
        if not ok:
            return True
        if type(value) is not bool:
            self._latch(_FAULT)
            return True
        return value is True

    # ------------------------------------------------------------ close

    def close(self) -> bool:
        self._ident_ok()
        if self._state is _State.CLOSED:
            return True
        if self._state is not _State.OPEN or self._in_run or self._pending():
            return False
        if self._deferred or not all(_quiescent(e) for e in self._entries.values()):
            return False  # incomplete: everything stays retained
        failed = False
        control: BaseException | None = None
        try:
            self._loop.close()
        except Exception:
            failed = True
        except BaseException as caught:
            control = caught
        if failed or control is not None:
            self._state = _State.BROKEN  # a partial SDK close is never repeated
            if control is not None:
                raise control
            return False
        self._state = _State.CLOSED
        for entry in self._entries.values():
            coro = entry.coro
            entry.coro = None
            if coro is not None:
                coro.close()  # only this pump's own never-scheduled/finished start coroutines
            entry.protocol = None
            entry.transport = None
            entry.handle = None
            entry.task = None
            entry.timer = None
            entry.sinks = None
        return True


def _loop_invariants(loop: LoopSeam, handler: object) -> bool:
    return (
        loop.is_running() is False
        and loop.is_closed() is False
        and loop.get_debug() is False
        and loop.get_exception_handler() == handler
        and loop.get_task_factory() is None
    )


def _bind_over(loop_class: object, *, pipe: object, devnull: object, ident: object) -> ProactorPump:
    """Builds the pump over ``loop_class()`` (BIND-DESIGN B2 + BIND-REVIEW B4).

    ``loop_class`` is both the no-argument factory and the exact expected type. A factory
    that returns nothing leaves no known loop (unobservable partial effects are possible
    and nothing is claimed). For a returned loop refused by exact type or by the pump
    constructor, ONE explicit ``close()`` is attempted outside the primary ``except`` in
    its own guarded ``try``; that is a call attempt, never proof of physical release. The
    first non-Exception control wins; ordinary failures become a new empty PumpFault. Every
    raise happens from THIS frame with the known loop kept in the local ``loop``; keeping
    the raised throwable (a prospective duty of the future caller) keeps that reference.
    """
    if not isinstance(loop_class, type):
        raise PumpFault()  # F0: never called
    factory_failed = False
    loop: Any = None
    try:
        loop = loop_class()  # a control propagates untouched: no loop is known then
    except Exception:
        factory_failed = True
    if factory_failed:
        raise PumpFault()  # F1: nothing returned, so no known resource or cleanup claim
    primary_control: BaseException | None = None
    pump: ProactorPump | None = None
    if type(loop) is loop_class:
        try:
            pump = ProactorPump(loop=loop, pipe=pipe, devnull=devnull, ident=ident)
        except Exception:
            pump = None  # primary fault, reported below as a new PumpFault
        except BaseException as caught:
            primary_control = caught
    if pump is not None:
        return pump  # success: the pump alone owns the loop
    close_control: BaseException | None = None
    try:
        loop.close()  # the single explicit attempt, outside the primary except
    except Exception:
        close_control = None  # an ordinary close failure never replaces the outcome
    except BaseException as caught:
        close_control = caught
    if primary_control is not None:
        raise primary_control  # the first control wins over any later failure
    if close_control is not None:
        raise close_control  # after only a fault, the close control becomes the first
    raise PumpFault()


def bind_proactor_pump() -> ProactorPump:
    """Trusted real binding (design P3 section 2); NOT invoked by the fake-SDK oracles."""
    import asyncio
    import subprocess
    import sys
    import threading

    if sys.platform != "win32" or threading.current_thread() is not threading.main_thread():
        raise PumpFault()
    running = True
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        running = False
    if running:
        raise PumpFault()
    return _bind_over(
        asyncio.ProactorEventLoop,
        pipe=subprocess.PIPE,
        devnull=subprocess.DEVNULL,
        ident=threading.get_ident,
    )
