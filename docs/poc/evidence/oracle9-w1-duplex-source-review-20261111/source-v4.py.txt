"""W1 duplex host bridge (DUPLEX-DESIGN a78d1de1 + DUPLEX-REVIEW R8 + TEST-REVIEW R9).

Definitions only. A synchronous owner that drives ONE fresh, caller-trusted HostReactor
(e86f8e32) through injected deterministic ports: a logical clock, the gateway spawn,
the gateway process (read/write/wait) and the six closed host actions. The reactor is
the only protocol decider; this module never parses events, computes sequences,
verdicts or the T6 fence. It never reads a real clock, the environment or a file and
never touches a socket, thread, process, event loop, signal, guard, Docker, PG or SQL.

Ownership: the caller holds the bridge before ``run``; five original slots exist before
any effect and every port binds its inert operation into the original slot BEFORE the
effect. A slot is emptied only by the bridge after a validated, known outcome; any
uncertain, live, malformed or failed operation stays in its original slot with the
first cached observation. A ``Done`` is a protocol candidate only: no release,
quiescence or cleanup is modeled, granted or proven here.
"""

from __future__ import annotations

import enum
import math
import types
from collections import deque
from dataclasses import dataclass
from typing import Any, Final, NoReturn

_READ_CHUNK: Final = 4096
_LINE_CAP: Final = 512
_DIAG_LINE_CAP: Final = 513
_QUEUE_CAP: Final = 57
_MAX_STDOUT_BYTES: Final = 56 * 512
_SPAWN_CAP: Final = 30
_SILENCE_CAP: Final = 60
_DRAIN_CAP: Final = 30
_OVERALL_CAP: Final = 300
_T6_CASE: Final = 25
_SLOT_NAMES: Final = ("spawn", "read", "write", "act", "wait")
_REACTOR_NAMES: Final = (
    "HostReactor",
    "HostRefusal",
    "HostPolicy",
    "HostStatus",
    "Line",
    "Delivered",
    "ActDone",
    "Exited",
    "Send",
    "Act",
    "Wait",
    "Done",
    "TerminateFacts",
    "PauseFacts",
    "RestoreFacts",
    "ObserveFacts",
    "ZeroFacts",
    "KillFacts",
    "Delivery",
    "ActStatus",
    "ExitStatus",
    "Purpose",
    "Verdict",
    "Outcome",
    "HostPhase",
    "ActKind",
)
_REACTOR_REFUSALS: Final = frozenset(
    {
        "CORE",
        "INIT",
        "POLICY",
        "INPUT",
        "TIME",
        "RECEIPT",
        "ORDER",
        "LINE",
        "EVENT",
        "SEQUENCE",
        "SUMMARY",
        "EXIT",
    }
)


class BridgePhase(enum.Enum):
    NEW = "NEW"
    STARTING = "STARTING"
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    DONE = "DONE"
    HELD = "HELD"
    REFUSED = "REFUSED"


class BridgeFault(enum.Enum):
    REACTOR = "REACTOR"
    BUDGET = "BUDGET"
    PORT = "PORT"
    REENTRY = "REENTRY"
    SPAWN = "SPAWN"
    STDOUT_LIMIT = "STDOUT_LIMIT"
    SILENCE = "SILENCE"
    OVERALL_DEADLINE = "OVERALL_DEADLINE"
    REACTOR_REFUSAL = "REACTOR_REFUSAL"
    CONTROL = "CONTROL"


class BridgeRefusal(Exception):
    """Closed category only: args == (category.value,), raised outside any handler."""

    def __init__(self, category: BridgeFault, reactor_refusal: str | None = None) -> None:
        super().__init__(category.value)
        self.category = category
        self.reactor_refusal = reactor_refusal


class _Fault(Exception):
    """Private step signal; always converted to a closed refusal outside handlers."""

    def __init__(self, category: BridgeFault, reactor_refusal: str | None = None) -> None:
        super().__init__(category.value)
        self.category = category
        self.reactor_refusal = reactor_refusal


# ---------------------------------------------------------------- carriers and views


@dataclass(frozen=True, slots=True, repr=False)
class DuplexBudget:
    spawn_s: float
    silence_s: float
    drain_s: float
    overall_s: float

    def __repr__(self) -> str:
        return "DuplexBudget(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class SpawnOutcome:
    ok: bool
    process: object | None

    def __repr__(self) -> str:
        return "SpawnOutcome(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class ReadOutcome:
    ok: bool
    data: bytes

    def __repr__(self) -> str:
        return "ReadOutcome(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class WriteOutcome:
    delivery: object
    bytes_written: int

    def __repr__(self) -> str:
        return "WriteOutcome(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class ActOutcome:
    status: object
    facts: object | None

    def __repr__(self) -> str:
        return "ActOutcome(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class WaitOutcome:
    status: object
    code: int | None
    reaped: bool

    def __repr__(self) -> str:
        return "WaitOutcome(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class SlotView:
    name: str
    occupied: bool
    op: object | None
    done: bool
    outcome: object | None

    def __repr__(self) -> str:
        return "SlotView(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class BridgeStatus:
    phase: BridgePhase
    fault: BridgeFault | None
    reactor_refusal: str | None
    reactor_status: object
    attempt_consumed: bool
    retained: bool
    process: object | None
    total_stdout_bytes: int
    queued_lines: int
    partial_bytes: int
    overflow: bool
    trailing_partial: bool
    stdout_eof: bool
    reaped: bool
    exit_code: int | None
    slots: tuple[SlotView, ...]

    def __repr__(self) -> str:
        return "BridgeStatus(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class BridgeRunResult:
    done: object
    status: BridgeStatus

    def __repr__(self) -> str:
        return "BridgeRunResult(<redacted>)"


# ---------------------------------------------------------------- closed scalars


def _finite_or_none(value: object) -> float | None:
    """Exact int/float (no bool or subclass), finite; a huge int is never finite here."""
    if not isinstance(value, (int, float)) or type(value) not in (int, float):
        return None
    try:
        finite = math.isfinite(value)
    except OverflowError:
        return None
    return value if finite else None


def _instant_or_none(value: object, floor: float | None) -> float | None:
    moment = _finite_or_none(value)
    if moment is None or moment < 0 or (floor is not None and moment < floor):
        return None
    return moment


def _callable_attr(target: object, name: str) -> bool:
    try:
        return callable(getattr(target, name, None))
    except Exception:  # a hostile lookup is only a shape failure
        return False


def _op_shaped(op: object) -> bool:
    return _callable_attr(op, "done") and _callable_attr(op, "outcome")


def _method_or_none(target: object, name: str) -> Any:
    """ONE lookup: the same bound callable is validated and then kept, never re-read."""
    try:
        value = getattr(target, name, None)
    except Exception:  # a hostile lookup is only a shape failure, refused closed later
        return None
    return value if callable(value) else None


# ---------------------------------------------------------------- operation slot


class OperationSlot:
    """Original slot: an inert op is bound once, before its effect; ports cannot clear it."""

    __slots__ = ("_name", "_op")

    def __init__(self, name: str) -> None:
        self._name = name
        self._op: object | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def op(self) -> object | None:
        return self._op

    @property
    def occupied(self) -> bool:
        return self._op is not None

    def bind(self, op: object) -> None:
        if self._op is not None or not _op_shaped(op):
            raise BridgeRefusal(BridgeFault.PORT)  # the original op is never replaced
        self._op = op

    def __repr__(self) -> str:
        return "OperationSlot(<redacted>)"


def _empty_slot(slot: OperationSlot) -> None:
    """Bridge-private: only after a validated, known outcome was absorbed."""
    slot._op = None


class _Cell:
    """Bridge-private cache of one slot's single harvest (first observation wins)."""

    __slots__ = ("done", "error", "harvested", "outcome", "quarantined")

    def __init__(self) -> None:
        self.harvested = False
        self.done = False
        self.outcome: object = None
        self.error: Exception | None = None  # the ORIGINAL done()/outcome() exception
        self.quarantined = False


# ---------------------------------------------------------------- binding checks


def _bound_reactor_or_none(module: object, reactor: object) -> dict[str, Any] | None:
    """Exact fresh binding; shape is never an origin claim (the caller pins the file)."""
    if not isinstance(module, types.ModuleType) or type(module) is not types.ModuleType:
        return None
    try:
        names: dict[str, Any] = {name: getattr(module, name, None) for name in _REACTOR_NAMES}
        if not all(isinstance(value, type) for value in names.values()):
            return None
        if type(reactor) is not names["HostReactor"]:
            return None
        status_fn = _method_or_none(reactor, "status")
        feed_fn = _method_or_none(reactor, "feed")
        if status_fn is None or feed_fn is None:
            return None
        status: Any = status_fn()
        verdicts = status.verdicts
        not_run = names["Verdict"].NOT_RUN
        fresh = (
            type(status) is names["HostStatus"]
            and status.phase is names["HostPhase"].AWAIT_GUARD
            and type(status.lines) is int
            and status.lines == 0
            and type(status.controls_sent) is int
            and status.controls_sent == 0
            and status.last_at is None
            and status.pending is None
            and status.orphan is None
            and status.orphan_receipt is None
            and status.refusal is None
            and type(verdicts) is tuple
            and len(verdicts) == _T6_CASE
            and all(verdict is not_run for verdict in verdicts)
        )
        if not fresh:
            return None
        names["status_fn"] = status_fn
        names["feed_fn"] = feed_fn
        names["initial"] = status  # the validated fresh snapshot, cached for status()
        names["members"] = {
            "SENT": names["Delivery"].SENT,
            "UNKNOWN_DELIVERY": names["Delivery"].UNKNOWN,
            "NOT_SENT": names["Delivery"].NOT_SENT,
            "OK": names["ActStatus"].OK,
            "FAILED": names["ActStatus"].FAILED,
            "UNKNOWN_ACT": names["ActStatus"].UNKNOWN,
            "EXITED": names["ExitStatus"].EXITED,
            "NO_EXIT": names["ExitStatus"].NO_EXIT,
            "UNKNOWN_EXIT": names["ExitStatus"].UNKNOWN,
            "DRAINING": names["HostPhase"].DRAINING,
            "ENDING": names["HostPhase"].ENDING,
            "KILL": names["ActKind"].KILL_GATEWAY,
            "ZERO": names["ActKind"].ZERO_BACKENDS,
        }
    except Exception:  # converted to one closed category by the caller
        return None
    return names


def _budget_or_none(budget: object) -> tuple[float, float, float, float] | None:
    if not isinstance(budget, DuplexBudget) or type(budget) is not DuplexBudget:
        return None
    spawn = _finite_or_none(budget.spawn_s)
    silence = _finite_or_none(budget.silence_s)
    drain = _finite_or_none(budget.drain_s)
    overall = _finite_or_none(budget.overall_s)
    if spawn is None or silence is None or drain is None or overall is None:
        return None
    valid = (
        0 < spawn <= _SPAWN_CAP
        and 0 < silence <= _SILENCE_CAP
        and 0 < drain <= _DRAIN_CAP
        and max(spawn, silence, drain) < overall <= _OVERALL_CAP
    )
    return (spawn, silence, drain, overall) if valid else None


# ---------------------------------------------------------------- bridge


class DuplexBridge:
    """One-shot synchronous owner of the gateway CLI operations and the host actions."""

    def __init__(
        self,
        reactor_mod: types.ModuleType,
        reactor: object,
        clock: object,
        gateway: object,
        acts: object,
        budget: DuplexBudget,
    ) -> None:
        names = _bound_reactor_or_none(reactor_mod, reactor)
        if names is None:
            raise BridgeRefusal(BridgeFault.REACTOR)
        limits = _budget_or_none(budget)
        if limits is None:
            raise BridgeRefusal(BridgeFault.BUDGET)
        now_fn = _method_or_none(clock, "now")
        poll_fn = _method_or_none(clock, "poll")
        spawn_fn = _method_or_none(gateway, "begin_spawn_into")
        act_fn = _method_or_none(acts, "begin_act_into")
        if now_fn is None or poll_fn is None or spawn_fn is None or act_fn is None:
            raise BridgeRefusal(BridgeFault.PORT)
        self._r: dict[str, Any] = names
        self._m: dict[str, Any] = names["members"]
        self._reactor: object = reactor
        self._status_fn: Any = names["status_fn"]
        self._feed_fn: Any = names["feed_fn"]
        self._host_status: Any = names["initial"]
        self._now_fn: Any = now_fn
        self._poll_fn: Any = poll_fn
        self._spawn_fn: Any = spawn_fn
        self._act_fn: Any = act_fn
        self._spawn_s, self._silence_s, self._drain_s, self._overall_s = limits
        self._slots = tuple(OperationSlot(name) for name in _SLOT_NAMES)
        self._cells = {name: _Cell() for name in _SLOT_NAMES}
        self._phase = BridgePhase.NEW
        self._fault: BridgeFault | None = None
        self._reactor_refusal: str | None = None
        self._attempt = False
        self._retained = False
        self._control: BaseException | None = None
        self._process: object | None = None
        self._read_fn: Any = None
        self._write_fn: Any = None
        self._wait_fn: Any = None
        self._total = 0
        self._read_size = 0
        self._queue: deque[bytes] = deque()
        self._partial = bytearray()
        self._overflow = False
        self._trailing = False
        self._eof = False
        self._wait_cache: tuple[object, int | None, bool] | None = None
        self._last_clock: float | None = None
        self._overall = math.inf
        self._silence_deadline: float | None = None
        self._drain_deadline: float | None = None
        self._kill_fed = False
        self._exited_fed = False

    # ------------------------------------------------------------ public

    def status(self) -> BridgeStatus:
        """Pure read of cached observations: never a port, clock or op callback."""
        cache = self._wait_cache
        exited = cache is not None and cache[0] is self._m["EXITED"]
        views = tuple(self._view(slot) for slot in self._slots)
        return BridgeStatus(
            phase=self._phase,
            fault=self._fault,
            reactor_refusal=self._reactor_refusal,
            reactor_status=self._host_status,  # cached snapshot, never a reactor call
            attempt_consumed=self._attempt,
            retained=self._retained,
            process=self._process,
            total_stdout_bytes=self._total,
            queued_lines=len(self._queue),
            partial_bytes=len(self._partial),
            overflow=self._overflow,
            trailing_partial=self._trailing,
            stdout_eof=self._eof,
            reaped=cache is not None and cache[2] is True,
            exit_code=cache[1] if exited and cache is not None else None,
            slots=views,
        )

    def _view(self, slot: OperationSlot) -> SlotView:
        cell = self._cells[slot.name]
        cached = cell.error if cell.error is not None else cell.outcome
        return SlotView(
            name=slot.name, occupied=slot.occupied, op=slot.op, done=cell.done, outcome=cached
        )

    def run(self) -> BridgeRunResult:
        if self._attempt or self._phase is not BridgePhase.NEW:
            raise BridgeRefusal(BridgeFault.REENTRY)  # no callback, no state change
        self._attempt = True  # one-shot, before the first clock or port callback
        self._phase = BridgePhase.STARTING
        try:
            return self._drive()
        except _Fault as signal:
            category, refusal = signal.category, signal.reactor_refusal
        except Exception:  # defensive: an unexpected internal error is a closed port fault
            category, refusal = BridgeFault.PORT, None
        except BaseException as control:
            # First control is kept by identity and re-raised; no new callback here.
            if self._fault is None:
                self._fault = BridgeFault.CONTROL
                self._control = control
            self._retained = True
            self._phase = BridgePhase.HELD
            raise
        self._refuse(category, refusal)

    # ------------------------------------------------------------ faults

    def _refuse(self, category: BridgeFault, refusal: str | None) -> NoReturn:
        if self._fault is None:  # the first fault is sticky
            self._fault = category
            self._reactor_refusal = refusal
        self._retained = True
        refused = category is BridgeFault.REACTOR_REFUSAL
        self._phase = BridgePhase.REFUSED if refused else BridgePhase.HELD
        raise BridgeRefusal(category, refusal)

    def _slot(self, name: str) -> OperationSlot:
        return self._slots[_SLOT_NAMES.index(name)]

    def _port(self, call: Any, *args: object) -> Any:
        failed = False
        result: Any = None
        try:
            result = call(*args)
        except Exception:  # only BaseException controls pass through unchanged
            failed = True
        if failed:
            raise _Fault(BridgeFault.PORT)
        return result

    # ------------------------------------------------------------ clock

    def _now(self) -> float:
        moment = _instant_or_none(self._port(self._now_fn), self._last_clock)
        if moment is None:
            raise _Fault(BridgeFault.PORT)
        self._last_clock = moment
        return moment

    def _fresh(self) -> float:
        """A NEW observation before every feed and every begin; overall wins first."""
        moment = self._now()
        if moment >= self._overall:
            raise _Fault(BridgeFault.OVERALL_DEADLINE)
        return moment

    def _eligible(self, slot: OperationSlot) -> bool:
        cell = self._cells[slot.name]
        return slot.occupied and not cell.harvested and not cell.quarantined

    def _poll(self, names: tuple[str, ...], deadline: float) -> None:
        watched = tuple(
            slot for slot in (self._slot(name) for name in names) if self._eligible(slot)
        )
        if not watched:
            raise _Fault(BridgeFault.PORT)  # nothing can progress: never an empty poll
        previous = self._last_clock
        target = min(deadline, self._overall)
        moment = _instant_or_none(self._port(self._poll_fn, watched, target), previous)
        if moment is None:
            raise _Fault(BridgeFault.PORT)
        self._last_clock = moment
        harvested = [slot for slot in watched if self._harvest(slot)]
        if not harvested and moment < target:
            raise _Fault(BridgeFault.PORT)  # no spurious wakeup, even if time advanced
        if moment >= self._overall:
            raise _Fault(BridgeFault.OVERALL_DEADLINE)  # true observations stay cached
        for slot in harvested:
            if slot.name == "read":
                self._absorb_read()
            elif slot.name == "wait":
                self._absorb_wait()

    def _harvest(self, slot: OperationSlot) -> bool:
        """done() only while pending; outcome() at most once, cached before validation."""
        cell = self._cells[slot.name]
        op: Any = slot.op
        finished: object = None
        try:
            finished = op.done()
        except Exception as error:  # the original error is cached, never re-observed
            cell.error = error
        if cell.error is not None or type(finished) is not bool:
            cell.quarantined = True
            raise _Fault(BridgeFault.PORT)
        if finished is False:
            return False
        cell.harvested = True
        cell.done = True
        value: object = None
        try:
            value = op.outcome()
        except Exception as error:  # cached before any validation; op stays in its slot
            cell.error = error
        if cell.error is not None:
            raise _Fault(BridgeFault.PORT)
        cell.outcome = value
        if slot.name == "spawn" and type(value) is SpawnOutcome and value.process is not None:
            # Adopted at the cache point, before any refusal (overall included); no
            # callback, effect or validation happens here.
            self._process = value.process
        return True

    # ------------------------------------------------------------ effects

    def _begin(self, slot: OperationSlot, call: Any, *args: object) -> None:
        if slot.occupied:
            raise _Fault(BridgeFault.PORT)  # an occupied original slot is never reused
        self._cells[slot.name] = _Cell()
        self._port(call, slot, *args)
        if not slot.occupied:
            raise _Fault(BridgeFault.PORT)  # the port must bind before its effect

    def _release(self, slot: OperationSlot) -> None:
        _empty_slot(slot)
        self._cells[slot.name] = _Cell()

    def _arm_read(self) -> None:
        if self._eof or self._overflow:
            return
        self._read_size = min(_READ_CHUNK, _MAX_STDOUT_BYTES - self._total + 1)
        self._fresh()
        self._begin(self._slot("read"), self._read_fn, self._read_size, self._overall)

    def _arm_wait(self) -> None:
        self._fresh()
        self._begin(self._slot("wait"), self._wait_fn, self._overall)

    def _absorb_spawn(self) -> None:
        out: Any = self._cells["spawn"].outcome
        if type(out) is SpawnOutcome and out.process is not None:
            self._process = out.process  # adopted before any ok/shape validation
        if type(out) is not SpawnOutcome or type(out.ok) is not bool:
            raise _Fault(BridgeFault.PORT)
        if out.ok is False:
            raise _Fault(BridgeFault.SPAWN)
        process: object = out.process
        read_fn = _method_or_none(process, "begin_read_into")
        write_fn = _method_or_none(process, "begin_write_into")
        wait_fn = _method_or_none(process, "begin_wait_into")
        if process is None or read_fn is None or write_fn is None or wait_fn is None:
            raise _Fault(BridgeFault.PORT)
        self._read_fn = read_fn
        self._write_fn = write_fn
        self._wait_fn = wait_fn
        self._release(self._slot("spawn"))

    def _absorb_read(self) -> None:
        out: Any = self._cells["read"].outcome
        valid = (
            type(out) is ReadOutcome
            and type(out.ok) is bool
            and type(out.data) is bytes
            and len(out.data) <= self._read_size
            and out.ok is True
        )
        if not valid:
            raise _Fault(BridgeFault.PORT)  # malformed or failed read stays cached
        data: bytes = out.data
        if not data:
            self._release(self._slot("read"))
            self._eof = True
            self._anchor_drain()  # first observed EOF, even with an effect still pending
            if self._partial:
                self._trailing = True
                self._retained = True
                raw = bytes(self._partial)
                self._partial.clear()
                self._enqueue(raw)
            return
        self._total += len(data)
        if self._total > _MAX_STDOUT_BYTES:
            self._overflow = True
            raise _Fault(BridgeFault.STDOUT_LIMIT)  # the overflowing block stays cached
        self._release(self._slot("read"))
        self._absorb_chunk(data)
        self._arm_read()

    def _absorb_chunk(self, chunk: bytes) -> None:
        """Incremental assembly: the partial never exceeds 513 bytes, no large concat."""
        pos = 0
        size = len(chunk)
        while pos < size:
            room = _DIAG_LINE_CAP - len(self._partial)
            newline = chunk.find(b"\n", pos)
            if newline == -1:
                self._partial.extend(chunk[pos : pos + min(size - pos, room)])
                if len(self._partial) == _DIAG_LINE_CAP:
                    self._overflow = True
                    self._retained = True
                    raw = bytes(self._partial)
                    self._partial.clear()
                    self._enqueue(raw)
                return
            segment = newline + 1 - pos
            whole = len(self._partial) + segment
            self._partial.extend(chunk[pos : pos + min(segment, room)])
            raw = bytes(self._partial)
            self._partial.clear()
            pos = newline + 1
            if whole > _LINE_CAP:
                self._overflow = True
                self._retained = True
                self._enqueue(raw)  # one 513-byte diagnostic, then stop scanning
                return
            self._enqueue(raw)

    def _enqueue(self, raw: bytes) -> None:
        if len(self._queue) >= _QUEUE_CAP:
            self._overflow = True
            raise _Fault(BridgeFault.STDOUT_LIMIT)
        self._queue.append(raw)

    def _absorb_wait(self) -> None:
        out: Any = self._cells["wait"].outcome
        m = self._m
        if type(out) is not WaitOutcome or type(out.status) is not self._r["ExitStatus"]:
            raise _Fault(BridgeFault.PORT)
        if out.status is m["EXITED"]:
            code = out.code
            valid = type(code) is int and 0 <= code <= 255 and out.reaped is True
        else:
            valid = out.code is None and out.reaped is False
        if not valid:
            raise _Fault(BridgeFault.PORT)
        self._wait_cache = (out.status, out.code, out.reaped)
        self._anchor_drain()  # first observed exit fact, even with an effect still pending
        if out.status is m["EXITED"]:
            self._release(self._slot("wait"))
        else:
            self._retained = True  # NO_EXIT/UNKNOWN: the original wait stays in its slot

    # ------------------------------------------------------------ reactor

    def _snapshot(self) -> bool:
        """Refresh the cached reactor view right after a feed (never from status())."""
        try:
            value = self._status_fn()
        except Exception:
            return False
        if type(value) is not self._r["HostStatus"]:
            return False
        self._host_status = value
        return True

    def _anchor_drain(self) -> None:
        """Drain deadline anchored ONCE at the first observed trigger, never renewed."""
        if self._drain_deadline is None and self._last_clock is not None:
            self._drain_deadline = min(self._overall, self._last_clock + self._drain_s)

    def _feed(self, item: object) -> Any:
        failed = False
        refusal: str | None = None
        step: Any = None
        try:
            step = self._feed_fn(item)
        except self._r["HostRefusal"] as error:
            failed = True
            category = getattr(error, "category", None)
            refusal = category if type(category) is str else None
        except Exception:
            failed = True
        if failed:
            self._snapshot()  # the refused reactor view stays accurate in status()
            closed = refusal if refusal in _REACTOR_REFUSALS else None
            raise _Fault(BridgeFault.REACTOR_REFUSAL, closed)
        if not self._snapshot():
            raise _Fault(BridgeFault.REACTOR)
        kinds = (self._r["Send"], self._r["Act"], self._r["Wait"], self._r["Done"])
        if type(step) not in kinds:
            raise _Fault(BridgeFault.REACTOR)
        phase = self._host_status.phase
        if phase is self._m["DRAINING"] or phase is self._m["ENDING"]:
            self._anchor_drain()
        return step

    def _feed_line(self) -> Any:
        raw = self._queue.popleft()
        self._silence_deadline = None
        at = self._fresh()
        return self._feed(self._r["Line"](raw=raw, at=at))

    # ------------------------------------------------------------ loop

    def _drive(self) -> BridgeRunResult:
        start = self._now()
        self._overall = start + self._overall_s
        spawn_deadline = min(start + self._spawn_s, self._overall)
        spawn = self._slot("spawn")
        moment = self._fresh()  # a NEW observation before the first begin; overall first
        if moment >= spawn_deadline:
            raise _Fault(BridgeFault.SPAWN)  # expired before any spawn effect
        self._begin(spawn, self._spawn_fn, spawn_deadline)
        while not self._cells["spawn"].harvested:
            if self._last_clock is not None and self._last_clock >= spawn_deadline:
                self._cells["spawn"].quarantined = True
                raise _Fault(BridgeFault.SPAWN)
            self._poll(("spawn",), spawn_deadline)
        self._absorb_spawn()
        self._phase = BridgePhase.ACTIVE
        self._arm_read()
        self._arm_wait()
        step: Any = None
        while True:
            kind = type(step)
            if kind is self._r["Done"]:
                return self._finish(step)
            if kind is self._r["Send"] or kind is self._r["Act"]:
                if self._may_start(step):
                    step = self._effect(step)
                else:
                    step = None  # cached EOF/exit: no new effect; raw FIFO, then Exited
                continue
            if self._queue:
                step = self._feed_line()
            elif self._draining():
                step = self._drain()
            else:
                self._await_line()
                step = None

    def _may_start(self, step: Any) -> bool:
        zero25 = (
            type(step) is self._r["Act"] and step.kind is self._m["ZERO"] and step.case == _T6_CASE
        )
        return zero25 or not (self._eof or self._wait_cache is not None)

    def _draining(self) -> bool:
        phase = self._host_status.phase  # cached after the last feed
        return (
            self._kill_fed
            or self._eof
            or self._wait_cache is not None
            or phase is self._m["DRAINING"]
            or phase is self._m["ENDING"]
        )

    def _await_line(self) -> None:
        deadline = self._silence_deadline
        if deadline is None:  # anchored once at the first wait, never rebased by wakeups
            deadline = min(self._overall, self._fresh() + self._silence_s)
            self._silence_deadline = deadline
        if self._last_clock is not None and self._last_clock >= deadline:
            raise _Fault(BridgeFault.SILENCE)
        self._poll(("read", "wait"), deadline)

    def _drain(self) -> Any:
        self._anchor_drain()  # no-op when an earlier trigger already anchored it
        deadline = self._drain_deadline
        if deadline is None:
            raise _Fault(BridgeFault.PORT)  # unreachable: a clock observation precedes
        complete = self._eof and self._wait_cache is not None
        reachable = self._last_clock is not None and self._last_clock < deadline
        if not complete and reachable:
            names = tuple(name for name in ("read", "wait") if self._eligible(self._slot(name)))
            if names:
                self._poll(names, deadline)
                return None
        return self._exit()

    def _exit(self) -> Any:
        if self._exited_fed:
            raise _Fault(BridgeFault.PORT)
        m = self._m
        cache = self._wait_cache
        if cache is not None:
            status, code, reaped = cache
            if status is not m["EXITED"] or not self._eof or reaped is not True:
                self._retained = True
        else:
            # No positive port fact: the pending wait is UNKNOWN, never NO_EXIT.
            self._cells["wait"].quarantined = True
            self._retained = True
            status, code, reaped = m["UNKNOWN_EXIT"], None, False
        at = self._fresh()
        self._exited_fed = True
        exited = self._r["Exited"](at=at, status=status, code=code, eof=self._eof, reaped=reaped)
        return self._feed(exited)

    def _effect(self, step: Any) -> Any:
        if type(step) is self._r["Send"]:
            return self._send(step)
        return self._act(step)

    def _send(self, send: Any) -> Any:
        slot = self._slot("write")
        pre = self._fresh()
        deadline = min(send.deadline, self._overall)
        self._begin(slot, self._write_fn, send.payload, deadline)
        cell = self._cells["write"]
        while not cell.harvested:
            if self._last_clock is not None and self._last_clock >= deadline:
                break
            self._poll(("write", "read", "wait"), deadline)
        m = self._m
        if cell.harvested:
            out: Any = cell.outcome
            if type(out) is not WriteOutcome or type(out.delivery) is not self._r["Delivery"]:
                raise _Fault(BridgeFault.PORT)
            count = out.bytes_written
            length = len(send.payload)
            if type(count) is not int:
                raise _Fault(BridgeFault.PORT)
            valid = (
                (out.delivery is m["NOT_SENT"] and count == 0)
                or (out.delivery is m["SENT"] and count == length)
                or (out.delivery is m["UNKNOWN_DELIVERY"] and 0 <= count <= length)
            )
            if not valid:
                raise _Fault(BridgeFault.PORT)
            delivery = out.delivery
            if delivery is m["UNKNOWN_DELIVERY"]:
                self._retained = True
            else:
                self._release(slot)
        else:
            cell.quarantined = True  # live at its deadline: kept, never polled again
            self._retained = True
            delivery = m["UNKNOWN_DELIVERY"]
        post = self._fresh()
        receipt = self._r["Delivered"](token=send.token, delivery=delivery, pre=pre, post=post)
        return self._feed(receipt)

    def _act(self, act: Any) -> Any:
        slot = self._slot("act")
        self._fresh()
        deadline = min(act.deadline, self._overall)
        self._begin(slot, self._act_fn, act, deadline)
        cell = self._cells["act"]
        while not cell.harvested:
            if self._last_clock is not None and self._last_clock >= deadline:
                break
            self._poll(("act", "read", "wait"), deadline)
        m = self._m
        if cell.harvested:
            out: Any = cell.outcome
            if type(out) is not ActOutcome or type(out.status) is not self._r["ActStatus"]:
                raise _Fault(BridgeFault.PORT)
            status, facts = out.status, out.facts
        else:
            cell.quarantined = True
            self._retained = True
            status, facts = m["UNKNOWN_ACT"], None
        at = self._fresh()
        done = self._r["ActDone"](token=act.token, kind=act.kind, status=status, facts=facts, at=at)
        step = self._feed(done)  # the receipt is fed BEFORE the slot is emptied
        if act.kind is m["KILL"]:
            self._kill_fed = True
            self._anchor_drain()  # kill receipt delivered: first drain trigger if none
        if cell.harvested and status in (m["OK"], m["FAILED"]):
            self._release(slot)
        else:
            self._retained = True
        return step

    def _finish(self, done: Any) -> BridgeRunResult:
        if any(slot.occupied for slot in self._slots):
            self._retained = True  # R9: live original operations keep the bridge HELD
        held = self._retained or done.controller_retained is True
        self._phase = BridgePhase.HELD if held else BridgePhase.DONE
        return BridgeRunResult(done=done, status=self.status())
