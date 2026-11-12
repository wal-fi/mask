"""W1 port ownership and concrete adapters (PORT-DESIGN V4 + V4.1 + PORT-REVIEW).

Pure synchronous owner over the narrow ``Pump`` / ``ProcessHandle`` / ``ProcessEvents``
seam. Drives one gateway CLI process and the six closed host actions without importing
or touching ``asyncio``, ``subprocess``, ``socket``, ``threading``, ``signal``, ``os``,
``time``, ``ctypes``, ``importlib``, ``runpy``, or ``docs.poc.*``. Receives the caller-
pinned ``bridge_ns`` and ``reactor_ns`` modules explicitly and inspects them only via
``vars(module).get(name)``. Model ``quiet_scoped`` and ``RELEASED_LOCAL`` are scoped
model observations only, never physical OS release proof or native ``ProactorEventLoop``
validation.
"""

from __future__ import annotations

import enum
import json
import math
import types
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, NoReturn, Protocol

_MAX_COUNTER: Final = (1 << 63) - 1
_MAX_PID: Final = 2147483647
_LINE_CAP: Final = 512

_BRIDGE_CLASSES: Final = (
    "SpawnOutcome",
    "ReadOutcome",
    "WriteOutcome",
    "ActOutcome",
    "WaitOutcome",
    "OperationSlot",
)
_REACTOR_CLASSES: Final = (
    "Act",
    "TerminateFacts",
    "PauseFacts",
    "RestoreFacts",
    "ObserveFacts",
    "ZeroFacts",
    "KillFacts",
)
_REACTOR_ENUMS: Final[dict[str, frozenset[str]]] = {
    "ActKind": frozenset(
        {
            "TERMINATE_ONE_BACKEND",
            "PAUSE_PG",
            "RESTORE_PG",
            "OBSERVE_HEAVY",
            "ZERO_BACKENDS",
            "KILL_GATEWAY",
        }
    ),
    "ActStatus": frozenset({"OK", "FAILED", "UNKNOWN"}),
    "Delivery": frozenset({"NOT_SENT", "SENT", "UNKNOWN"}),
    "ExitStatus": frozenset({"EXITED", "NO_EXIT", "UNKNOWN"}),
}
_LIMIT_BOUNDS: Final[dict[str, tuple[int, int]]] = {
    "max_records": (1, 512),
    "max_children": (1, 24),
    "max_writes": (1, 51),
    "max_acts": (1, 7),
    "max_audits": (1, 8),
    "max_disposals": (1, 64),
    "gateway_stdout_cap": (1, 28673),
    "child_stdout_cap": (1, 4096),
    "max_late": (1, 16),
    "max_retained_takes": (2, 2),
}
_ACT_HELPER_BOUNDS: Final[dict[str, tuple[int, int]]] = {
    "TERMINATE_ONE_BACKEND": (1, 1),
    "PAUSE_PG": (2, 2),
    "RESTORE_PG": (3, 3),
    "OBSERVE_HEAVY": (1, 20),
    "ZERO_BACKENDS": (1, 1),
    "KILL_GATEWAY": (2, 2),
}
_TERM_KEYS: Final = frozenset({"found", "scope", "terminated"})
_PAUSE_KEYS: Final = frozenset({"paused", "running", "scope"})
_READY_KEYS: Final = frozenset({"ready", "scope"})
_OBSERVE_KEYS: Final = frozenset({"active", "scope"})
_ZERO_KEYS: Final = frozenset({"backends", "observer_excluded", "role", "scope"})
_KILL_KEYS: Final = frozenset({"oom", "pid", "running", "scope"})
_NAMES_KEYS: Final = frozenset({"names", "scope"})
_OBS_CTRL_KEYS: Final = frozenset({"observer", "role", "scope"})


# ---------------------------------------------------------------- closed enums and refusal


class OwnershipFault(enum.Enum):
    CAPACITY = "CAPACITY"
    REENTRY = "REENTRY"
    STATE = "STATE"
    PLAN = "PLAN"
    PUMP = "PUMP"
    PORT = "PORT"
    SEALED = "SEALED"
    NAMESPACE = "NAMESPACE"


class OwnershipRefusal(Exception):
    """Closed refusal category only: args == (category.value,), never chained."""

    def __init__(self, category: OwnershipFault) -> None:
        if type(category) is not OwnershipFault:
            category = OwnershipFault.PORT
        super().__init__(category.value)
        self.category = category


class _Signal(Exception):
    """Internal control-flow signal converted to a clean OwnershipRefusal outside handlers."""

    def __init__(self, category: OwnershipFault) -> None:
        super().__init__(category.value)
        self.category = category


class FaultKind(enum.Enum):
    START = "START"
    CALLBACK = "CALLBACK"
    WRITE = "WRITE"
    WRITE_LIMITS = "WRITE_LIMITS"
    DECODE = "DECODE"
    OVERFLOW = "OVERFLOW"
    CONTROL = "CONTROL"
    PUMP = "PUMP"


class InvocationKind(enum.Enum):
    SPAWN = "SPAWN"
    WRITE = "WRITE"
    WAIT = "WAIT"
    ACT = "ACT"
    CHILD = "CHILD"
    AUDIT = "AUDIT"
    DISPOSE = "DISPOSE"


class Gate(enum.Enum):
    RESERVED = "RESERVED"
    BOUND = "BOUND"
    ARMED = "ARMED"
    NOT_ARMED = "NOT_ARMED"


class ProtocolState(enum.Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED_KNOWN = "FAILED_KNOWN"
    NOT_STARTED = "NOT_STARTED"
    UNKNOWN = "UNKNOWN"


class PhysicalState(enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    OPEN = "OPEN"
    SETTLED_RETAINED = "SETTLED_RETAINED"
    RELEASED_LOCAL = "RELEASED_LOCAL"
    UNKNOWN = "UNKNOWN"


class Retained(enum.Enum):
    TRANSPORT = "TRANSPORT"
    PROCESS_HANDLE = "PROCESS_HANDLE"
    PIPE_0 = "PIPE_0"
    PIPE_1 = "PIPE_1"
    PIPE_2 = "PIPE_2"
    BUFFER = "BUFFER"


class AuditKind(enum.Enum):
    GATEWAY_ABSENT = "GATEWAY_ABSENT"
    BACKENDS_ZERO = "BACKENDS_ZERO"


class AbsenceVerdict(enum.Enum):
    NOT_RUN = "NOT_RUN"
    ABSENT_OBSERVED = "ABSENT_OBSERVED"
    PRESENT = "PRESENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class DisposeKind(enum.Enum):
    CLOSE_HANDLE = "CLOSE_HANDLE"
    TERMINATE_PROCESS = "TERMINATE_PROCESS"
    REMOVE_GATEWAY_CONTAINER = "REMOVE_GATEWAY_CONTAINER"


class DisposeOutcome(enum.Enum):
    DONE_OBSERVED = "DONE_OBSERVED"
    NOT_DONE = "NOT_DONE"
    UNKNOWN = "UNKNOWN"


class DecodeReason(enum.Enum):
    OK = "OK"
    EXIT_NONZERO = "EXIT_NONZERO"
    SHAPE = "SHAPE"
    SCOPE = "SCOPE"
    TRUNCATED = "TRUNCATED"
    PREDICATE = "PREDICATE"
    MISSING = "MISSING"


class LateKind(enum.Enum):
    STARTED = "STARTED"
    EXITED = "EXITED"
    PIPE_LOST = "PIPE_LOST"
    HANDOFF_ZERO = "HANDOFF_ZERO"
    WRITE_FAULT = "WRITE_FAULT"
    CHILD_DONE = "CHILD_DONE"
    CLOSED = "CLOSED"
    CONTROL = "CONTROL"


# ---------------------------------------------------------------- narrow pump protocols


class ProcessHandle(Protocol):
    def pid(self) -> int | None: ...
    def returncode(self) -> int | None: ...
    def write_limits(self) -> tuple[int, int]: ...
    def write(self, data: bytes) -> None: ...
    def is_closing(self) -> bool: ...
    def buffer_size(self) -> int: ...
    def pause_reading(self, fd: int) -> None: ...
    def resume_reading(self, fd: int) -> None: ...
    def close(self) -> None: ...
    def kill(self) -> None: ...


class ProcessEvents(Protocol):
    def started(self, handle: ProcessHandle) -> None: ...
    def start_failed(self) -> None: ...
    def not_started(self) -> None: ...
    def data(self, fd: int, chunk: bytes) -> None: ...
    def pipe_lost(self, fd: int, failed: bool) -> None: ...
    def exited(self, code: object) -> None: ...
    def write_resumed(self) -> None: ...
    def closed(self) -> None: ...


class Pump(Protocol):
    def now(self) -> float: ...
    def schedule_start(self, request: StartRequest) -> None: ...
    def run_until(self, target: float, stop: Callable[[], bool]) -> float: ...


# ---------------------------------------------------------------- frozen slotted DTOs


@dataclass(frozen=True, slots=True, repr=False)
class StartRequest:
    record_id: int
    argv: tuple[str, ...]
    stdin_pipe: bool
    not_before: float
    authorize: Callable[[], bool]
    events: ProcessEvents

    def __repr__(self) -> str:
        return "StartRequest(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class Scope:
    scope_id: str
    gateway_name: str
    scope_label: str
    pg_name: str
    target_role: str
    observer_role: str

    def __repr__(self) -> str:
        return "Scope(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class HelperPlan:
    argv: tuple[str, ...]

    def __repr__(self) -> str:
        return "HelperPlan(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class CliPlan:
    scope: Scope
    gateway_argv: tuple[str, ...]
    acts: tuple[tuple[Any, tuple[HelperPlan, ...]], ...]
    audits: tuple[tuple[AuditKind, tuple[HelperPlan, ...]], ...]
    remove_gateway: tuple[HelperPlan, ...]

    def __repr__(self) -> str:
        return "CliPlan(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class OwnerLimits:
    max_records: int = 512
    max_children: int = 24
    max_writes: int = 51
    max_acts: int = 7
    max_audits: int = 8
    max_disposals: int = 64
    gateway_stdout_cap: int = 28673
    child_stdout_cap: int = 4096
    max_late: int = 16
    max_retained_takes: int = 2

    def __post_init__(self) -> None:
        if not _limits_ok(self):
            raise OwnershipRefusal(OwnershipFault.PLAN)

    def __repr__(self) -> str:
        return "OwnerLimits(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class LateFact:
    at: float
    kind: LateKind
    code: int | None
    fault: FaultKind | None

    def __repr__(self) -> str:
        return "LateFact(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class HelperRaw:
    index: int
    code: int | None
    stdout: bytes
    stdout_dropped: int
    stderr_bytes: int

    def __post_init__(self) -> None:
        if (
            not _exact_int_in(self.index, 0, 23)
            or (self.code is not None and not _exact_int_in(self.code, 0, 255))
            or type(self.stdout) is not bytes
            or len(self.stdout) > 4096
            or type(self.stdout_dropped) is not int
            or self.stdout_dropped < 0
            or type(self.stderr_bytes) is not int
            or self.stderr_bytes < 0
        ):
            raise OwnershipRefusal(OwnershipFault.PLAN)

    def __repr__(self) -> str:
        return "HelperRaw(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class ActDecode:
    status: Any
    facts: Any
    reason: DecodeReason

    def __repr__(self) -> str:
        return "ActDecode(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class AuditDecode:
    verdict: AbsenceVerdict
    reason: DecodeReason

    def __repr__(self) -> str:
        return "AuditDecode(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class DisposeDecode:
    outcome: DisposeOutcome
    reason: DecodeReason

    def __repr__(self) -> str:
        return "DisposeDecode(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class RecordView:
    record_id: int
    kind: InvocationKind
    parent: int | None
    plan_index: int
    scope_id: str
    act_kind: Any
    case: int | None
    token: int | None
    gate: Gate
    reserved_at: float
    armed_at: float | None
    deadline: float
    epoch: int
    protocol: ProtocolState
    protocol_at: float | None
    pid: int | None
    returncode: int | None
    exited: bool
    pipes_lost: tuple[bool | None, bool | None, bool | None]
    payload_len: int | None
    handoff_zero: bool
    received_total: int
    accepted_total: int
    resident: int
    dropped_total: int
    stderr_bytes: int
    faults: tuple[FaultKind, ...]
    uncertain: bool
    late: tuple[LateFact, ...]
    late_overflow: bool
    physical: PhysicalState
    retained: tuple[Retained, ...]
    settled_at: float | None

    def __repr__(self) -> str:
        return "RecordView(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class WorkFence:
    sealed_at: float
    work_ids: tuple[int, ...]
    open_ids: tuple[int, ...]
    unknown_ids: tuple[int, ...]
    work_settled_at: float | None

    def __repr__(self) -> str:
        return "WorkFence(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class AuditResult:
    record_id: int
    kind: AuditKind
    epoch: int
    armed_at: float
    verdict: AbsenceVerdict
    reason: DecodeReason
    helpers_settled: bool

    def __repr__(self) -> str:
        return "AuditResult(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class AuditReport:
    fence: WorkFence | None
    records: tuple[RecordView, ...]
    gateway: AuditResult | None
    backends: AuditResult | None
    epoch: int
    control_history: bool
    quiet_scoped: bool

    def __repr__(self) -> str:
        return "AuditReport(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class CustodyView:
    entries: tuple[tuple[int, tuple[Retained, ...]], ...]

    def __repr__(self) -> str:
        return "CustodyView(<redacted>)"


# ---------------------------------------------------------------- scalar & plan validation


def _exact_int_in(value: object, low: int, high: int) -> bool:
    return isinstance(value, int) and type(value) is int and low <= value <= high


def _finite_or_none(value: object) -> float | None:
    if not isinstance(value, (int, float)) or type(value) not in (int, float):
        return None
    try:
        finite = math.isfinite(value)
    except OverflowError:
        return None
    return float(value) if finite else None


def _ascii_printable(value: object, max_len: int) -> bool:
    return (
        isinstance(value, str)
        and type(value) is str
        and 1 <= len(value) <= max_len
        and value.isascii()
        and value.isprintable()
    )


def _valid_scope_id(value: object) -> bool:
    if not isinstance(value, str) or type(value) is not str or not 1 <= len(value) <= 64:
        return False
    return value.isascii() and all(ch.islower() or ch.isdigit() or ch == "-" for ch in value)


def _limits_ok(limits: object) -> bool:
    if not isinstance(limits, OwnerLimits) or type(limits) is not OwnerLimits:
        return False
    for name, (low, high) in _LIMIT_BOUNDS.items():
        if not _exact_int_in(getattr(limits, name, None), low, high):
            return False
    return True


def _validate_namespaces(
    bridge_ns: object, reactor_ns: object
) -> tuple[dict[str, Any], dict[str, Any]]:
    if type(bridge_ns) is not types.ModuleType or type(reactor_ns) is not types.ModuleType:
        raise OwnershipRefusal(OwnershipFault.NAMESPACE)
    b_vars = vars(bridge_ns)
    r_vars = vars(reactor_ns)
    for name in _BRIDGE_CLASSES:
        if not isinstance(b_vars.get(name), type):
            raise OwnershipRefusal(OwnershipFault.NAMESPACE)
    for name in _REACTOR_CLASSES:
        if not isinstance(r_vars.get(name), type):
            raise OwnershipRefusal(OwnershipFault.NAMESPACE)
    for enum_name, expected in _REACTOR_ENUMS.items():
        cls = r_vars.get(enum_name)
        if not isinstance(cls, type) or not issubclass(cls, enum.Enum):
            raise OwnershipRefusal(OwnershipFault.NAMESPACE)
        if set(cls.__members__) != expected or {member.name for member in cls} != expected:
            raise OwnershipRefusal(OwnershipFault.NAMESPACE)
    return dict(b_vars), dict(r_vars)


def _valid_argv(argv: object, scope_id: str) -> bool:
    if not isinstance(argv, tuple) or type(argv) is not tuple or not 1 <= len(argv) <= 64:
        return False
    if not all(_ascii_printable(item, 4096) for item in argv):
        return False
    return any(scope_id in item for item in argv)


def _valid_helper(helper: object, scope_id: str) -> bool:
    return (
        isinstance(helper, HelperPlan)
        and type(helper) is HelperPlan
        and _valid_argv(helper.argv, scope_id)
    )


def _valid_scope(scope: object) -> bool:
    if not isinstance(scope, Scope) or type(scope) is not Scope:
        return False
    if not _valid_scope_id(scope.scope_id):
        return False
    text_fields = (
        scope.gateway_name,
        scope.scope_label,
        scope.pg_name,
        scope.target_role,
        scope.observer_role,
    )
    if not all(_ascii_printable(field, 128) for field in text_fields):
        return False
    return scope.gateway_name != scope.pg_name and scope.observer_role != scope.target_role


def _valid_acts(acts: object, scope_id: str, max_children: int, act_kind_cls: Any) -> bool:
    if not isinstance(acts, tuple) or type(acts) is not tuple or len(acts) != 6:
        return False
    seen: set[Any] = set()
    for entry in acts:
        if not isinstance(entry, tuple) or type(entry) is not tuple or len(entry) != 2:
            return False
        kind, helpers = entry
        if type(kind) is not act_kind_cls or kind in seen:
            return False
        seen.add(kind)
        if not isinstance(helpers, tuple) or type(helpers) is not tuple:
            return False
        low, high = _ACT_HELPER_BOUNDS[kind.name]
        if not low <= len(helpers) <= min(high, max_children):
            return False
        if not all(_valid_helper(hp, scope_id) for hp in helpers):
            return False
    return len(seen) == 6


def _valid_audits(audits: object, scope_id: str, max_children: int) -> bool:
    if not isinstance(audits, tuple) or type(audits) is not tuple or len(audits) != 2:
        return False
    if max_children < 2:
        return False
    seen: set[AuditKind] = set()
    for entry in audits:
        if not isinstance(entry, tuple) or type(entry) is not tuple or len(entry) != 2:
            return False
        kind, helpers = entry
        if type(kind) is not AuditKind or kind in seen:
            return False
        seen.add(kind)
        if not isinstance(helpers, tuple) or type(helpers) is not tuple or len(helpers) != 2:
            return False
        if not all(_valid_helper(hp, scope_id) for hp in helpers):
            return False
    return seen == {AuditKind.GATEWAY_ABSENT, AuditKind.BACKENDS_ZERO}


def _validate_plan(plan: object, limits: OwnerLimits, act_kind_cls: Any) -> CliPlan:
    if not isinstance(plan, CliPlan) or type(plan) is not CliPlan:
        raise OwnershipRefusal(OwnershipFault.PLAN)
    if not _valid_scope(plan.scope):
        raise OwnershipRefusal(OwnershipFault.PLAN)
    sid = plan.scope.scope_id
    if not _valid_argv(plan.gateway_argv, sid):
        raise OwnershipRefusal(OwnershipFault.PLAN)
    if not _valid_acts(plan.acts, sid, limits.max_children, act_kind_cls):
        raise OwnershipRefusal(OwnershipFault.PLAN)
    if not _valid_audits(plan.audits, sid, limits.max_children):
        raise OwnershipRefusal(OwnershipFault.PLAN)
    rm = plan.remove_gateway
    rm_ok = (
        isinstance(rm, tuple)
        and type(rm) is tuple
        and len(rm) == 2 <= limits.max_children
        and all(_valid_helper(hp, sid) for hp in rm)
    )
    if not rm_ok:
        raise OwnershipRefusal(OwnershipFault.PLAN)
    return plan


# ---------------------------------------------------------------- helper decoders


def _parse_helper_json(
    raw: HelperRaw, expected_keys: frozenset[str], scope_id: str
) -> tuple[dict[str, Any] | None, DecodeReason]:
    if raw.code != 0:
        return None, DecodeReason.EXIT_NONZERO
    if raw.stdout_dropped > 0:
        return None, DecodeReason.TRUNCATED
    data = raw.stdout
    framed = (
        0 < len(data) <= _LINE_CAP
        and data.endswith(b"\n")
        and data.count(b"\n") == 1
        and b"\r" not in data
        and data.isascii()
    )
    if not framed:
        return None, DecodeReason.SHAPE
    text = data[:-1].decode("ascii")
    try:
        parsed = json.loads(text)
        canonical = json.dumps(
            parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
    except (ValueError, RecursionError):
        return None, DecodeReason.SHAPE
    if type(parsed) is not dict or canonical != text or frozenset(parsed) != expected_keys:
        return None, DecodeReason.SHAPE
    scope_val = parsed.get("scope")
    if type(scope_val) is not str:
        return None, DecodeReason.SHAPE
    if scope_val != scope_id:
        return None, DecodeReason.SCOPE
    return parsed, DecodeReason.OK


def _command_step_reason(raw: HelperRaw) -> DecodeReason:
    if raw.code != 0:
        return DecodeReason.EXIT_NONZERO
    if raw.stdout_dropped > 0:
        return DecodeReason.TRUNCATED
    return DecodeReason.OK if raw.stdout == b"" else DecodeReason.SHAPE


def _decode_terminate(raws: list[HelperRaw], scope: Scope, r_vars: dict[str, Any]) -> ActDecode:
    st = r_vars["ActStatus"]
    if len(raws) != 1:
        return ActDecode(st.UNKNOWN, None, DecodeReason.MISSING)
    obj, reason = _parse_helper_json(raws[0], _TERM_KEYS, scope.scope_id)
    if obj is None:
        return ActDecode(st.UNKNOWN, None, reason)
    if not _exact_int_in(obj["found"], 0, 64) or type(obj["terminated"]) is not bool:
        return ActDecode(st.UNKNOWN, None, DecodeReason.SHAPE)
    if obj["found"] == 1 and obj["terminated"] is True:
        facts = r_vars["TerminateFacts"](found=1, terminated=True)
        return ActDecode(st.OK, facts, DecodeReason.OK)
    return ActDecode(st.FAILED, None, DecodeReason.PREDICATE)


def _decode_pause(raws: list[HelperRaw], scope: Scope, r_vars: dict[str, Any]) -> ActDecode:
    st = r_vars["ActStatus"]
    if len(raws) != 2:
        return ActDecode(st.UNKNOWN, None, DecodeReason.MISSING)
    cmd_reason = _command_step_reason(raws[0])
    if cmd_reason is not DecodeReason.OK:
        return ActDecode(st.UNKNOWN, None, cmd_reason)
    obj, reason = _parse_helper_json(raws[1], _PAUSE_KEYS, scope.scope_id)
    if obj is None:
        return ActDecode(st.UNKNOWN, None, reason)
    if type(obj["paused"]) is not bool or type(obj["running"]) is not bool:
        return ActDecode(st.UNKNOWN, None, DecodeReason.SHAPE)
    if obj["paused"] is True and obj["running"] is True:
        return ActDecode(st.OK, r_vars["PauseFacts"](paused=True), DecodeReason.OK)
    return ActDecode(st.FAILED, None, DecodeReason.PREDICATE)


def _decode_restore(raws: list[HelperRaw], scope: Scope, r_vars: dict[str, Any]) -> ActDecode:
    st = r_vars["ActStatus"]
    if len(raws) != 3:
        return ActDecode(st.UNKNOWN, None, DecodeReason.MISSING)
    cmd_reason = _command_step_reason(raws[0])
    if cmd_reason is not DecodeReason.OK:
        return ActDecode(st.UNKNOWN, None, cmd_reason)
    obj1, reason1 = _parse_helper_json(raws[1], _PAUSE_KEYS, scope.scope_id)
    if obj1 is None:
        return ActDecode(st.UNKNOWN, None, reason1)
    if type(obj1["paused"]) is not bool or type(obj1["running"]) is not bool:
        return ActDecode(st.UNKNOWN, None, DecodeReason.SHAPE)
    obj2, reason2 = _parse_helper_json(raws[2], _READY_KEYS, scope.scope_id)
    if obj2 is None:
        return ActDecode(st.UNKNOWN, None, reason2)
    if type(obj2["ready"]) is not bool:
        return ActDecode(st.UNKNOWN, None, DecodeReason.SHAPE)
    if obj1["running"] is True and obj1["paused"] is False and obj2["ready"] is True:
        facts = r_vars["RestoreFacts"](running=True, paused=False, ready=True)
        return ActDecode(st.OK, facts, DecodeReason.OK)
    return ActDecode(st.FAILED, None, DecodeReason.PREDICATE)


def _decode_observe(
    raws: list[HelperRaw], planned_count: int, scope: Scope, r_vars: dict[str, Any]
) -> ActDecode:
    st = r_vars["ActStatus"]
    if not raws:
        return ActDecode(st.UNKNOWN, None, DecodeReason.MISSING)
    found = False
    for idx, raw in enumerate(raws):
        obj, reason = _parse_helper_json(raw, _OBSERVE_KEYS, scope.scope_id)
        if obj is None:
            return ActDecode(st.UNKNOWN, None, reason)
        active = obj["active"]
        if type(active) is not bool:
            return ActDecode(st.UNKNOWN, None, DecodeReason.SHAPE)
        if active is True:
            if idx != len(raws) - 1:
                return ActDecode(st.UNKNOWN, None, DecodeReason.SHAPE)
            found = True
    if not found and len(raws) < planned_count:
        return ActDecode(st.UNKNOWN, None, DecodeReason.MISSING)
    facts = r_vars["ObserveFacts"](found=found, observations=len(raws))
    return ActDecode(st.OK, facts, DecodeReason.OK)


def _decode_zero(raws: list[HelperRaw], scope: Scope, r_vars: dict[str, Any]) -> ActDecode:
    st = r_vars["ActStatus"]
    if len(raws) != 1:
        return ActDecode(st.UNKNOWN, None, DecodeReason.MISSING)
    obj, reason = _parse_helper_json(raws[0], _ZERO_KEYS, scope.scope_id)
    if obj is None:
        return ActDecode(st.UNKNOWN, None, reason)
    if (
        not _exact_int_in(obj["backends"], 0, 1024)
        or obj["observer_excluded"] is not True
        or type(obj["role"]) is not str
    ):
        return ActDecode(st.UNKNOWN, None, DecodeReason.SHAPE)
    if obj["role"] != scope.target_role:
        return ActDecode(st.UNKNOWN, None, DecodeReason.SCOPE)
    if obj["backends"] == 0:
        return ActDecode(st.OK, r_vars["ZeroFacts"](backends=0), DecodeReason.OK)
    return ActDecode(st.FAILED, None, DecodeReason.PREDICATE)


def _decode_kill(raws: list[HelperRaw], scope: Scope, r_vars: dict[str, Any]) -> ActDecode:
    st = r_vars["ActStatus"]
    if len(raws) != 2:
        return ActDecode(st.UNKNOWN, None, DecodeReason.MISSING)
    cmd_reason = _command_step_reason(raws[0])
    if cmd_reason is not DecodeReason.OK:
        return ActDecode(st.UNKNOWN, None, cmd_reason)
    obj, reason = _parse_helper_json(raws[1], _KILL_KEYS, scope.scope_id)
    if obj is None:
        return ActDecode(st.UNKNOWN, None, reason)
    if (
        type(obj["oom"]) is not bool
        or not _exact_int_in(obj["pid"], 0, _MAX_PID)
        or type(obj["running"]) is not bool
    ):
        return ActDecode(st.UNKNOWN, None, DecodeReason.SHAPE)
    if obj["running"] is False and obj["pid"] == 0 and obj["oom"] is False:
        facts = r_vars["KillFacts"](stop_confirmed=True, oom_killed=False)
        return ActDecode(st.OK, facts, DecodeReason.OK)
    return ActDecode(st.FAILED, None, DecodeReason.PREDICATE)


def _decode_act(
    kind_name: str,
    raws: list[HelperRaw],
    planned_count: int,
    scope: Scope,
    r_vars: dict[str, Any],
) -> ActDecode:
    if kind_name == "TERMINATE_ONE_BACKEND":
        return _decode_terminate(raws, scope, r_vars)
    if kind_name == "PAUSE_PG":
        return _decode_pause(raws, scope, r_vars)
    if kind_name == "RESTORE_PG":
        return _decode_restore(raws, scope, r_vars)
    if kind_name == "OBSERVE_HEAVY":
        return _decode_observe(raws, planned_count, scope, r_vars)
    if kind_name == "ZERO_BACKENDS":
        return _decode_zero(raws, scope, r_vars)
    return _decode_kill(raws, scope, r_vars)


def _valid_names_list(value: object) -> bool:
    return (
        isinstance(value, list)
        and type(value) is list
        and len(value) <= 16
        and all(_ascii_printable(item, 128) for item in value)
    )


def _decode_gateway_absent(raws: list[HelperRaw], scope: Scope) -> AuditDecode:
    if len(raws) != 2:
        return AuditDecode(AbsenceVerdict.UNKNOWN, DecodeReason.MISSING)
    ctrl, r0 = _parse_helper_json(raws[0], _NAMES_KEYS, scope.scope_id)
    if ctrl is None:
        return AuditDecode(AbsenceVerdict.UNKNOWN, r0)
    if not _valid_names_list(ctrl["names"]):
        return AuditDecode(AbsenceVerdict.UNKNOWN, DecodeReason.SHAPE)
    if ctrl["names"] != [scope.pg_name]:
        return AuditDecode(AbsenceVerdict.UNKNOWN, DecodeReason.PREDICATE)
    tgt, r1 = _parse_helper_json(raws[1], _NAMES_KEYS, scope.scope_id)
    if tgt is None:
        return AuditDecode(AbsenceVerdict.UNKNOWN, r1)
    if not _valid_names_list(tgt["names"]):
        return AuditDecode(AbsenceVerdict.UNKNOWN, DecodeReason.SHAPE)
    if tgt["names"] == []:
        return AuditDecode(AbsenceVerdict.ABSENT_OBSERVED, DecodeReason.OK)
    if scope.gateway_name in tgt["names"]:
        return AuditDecode(AbsenceVerdict.PRESENT, DecodeReason.PREDICATE)
    return AuditDecode(AbsenceVerdict.UNKNOWN, DecodeReason.PREDICATE)


def _decode_backends_zero(raws: list[HelperRaw], scope: Scope) -> AuditDecode:
    if len(raws) != 2:
        return AuditDecode(AbsenceVerdict.UNKNOWN, DecodeReason.MISSING)
    ctrl, r0 = _parse_helper_json(raws[0], _OBS_CTRL_KEYS, scope.scope_id)
    if ctrl is None:
        return AuditDecode(AbsenceVerdict.UNKNOWN, r0)
    if ctrl["observer"] is not True or type(ctrl["role"]) is not str:
        return AuditDecode(AbsenceVerdict.UNKNOWN, DecodeReason.SHAPE)
    if ctrl["role"] != scope.observer_role:
        return AuditDecode(AbsenceVerdict.UNKNOWN, DecodeReason.SCOPE)
    tgt, r1 = _parse_helper_json(raws[1], _ZERO_KEYS, scope.scope_id)
    if tgt is None:
        return AuditDecode(AbsenceVerdict.UNKNOWN, r1)
    if (
        not _exact_int_in(tgt["backends"], 0, 1024)
        or tgt["observer_excluded"] is not True
        or type(tgt["role"]) is not str
    ):
        return AuditDecode(AbsenceVerdict.UNKNOWN, DecodeReason.SHAPE)
    if tgt["role"] != scope.target_role:
        return AuditDecode(AbsenceVerdict.UNKNOWN, DecodeReason.SCOPE)
    if tgt["backends"] == 0:
        return AuditDecode(AbsenceVerdict.ABSENT_OBSERVED, DecodeReason.OK)
    return AuditDecode(AbsenceVerdict.PRESENT, DecodeReason.PREDICATE)


def _decode_audit(kind: AuditKind, raws: list[HelperRaw], scope: Scope) -> AuditDecode:
    if kind is AuditKind.GATEWAY_ABSENT:
        return _decode_gateway_absent(raws, scope)
    return _decode_backends_zero(raws, scope)


def _decode_dispose_remove(raws: list[HelperRaw], scope: Scope) -> DisposeDecode:
    if len(raws) != 2:
        return DisposeDecode(DisposeOutcome.UNKNOWN, DecodeReason.MISSING)
    cmd_reason = _command_step_reason(raws[0])
    if cmd_reason is not DecodeReason.OK:
        return DisposeDecode(DisposeOutcome.UNKNOWN, cmd_reason)
    tgt, reason = _parse_helper_json(raws[1], _NAMES_KEYS, scope.scope_id)
    if tgt is None:
        return DisposeDecode(DisposeOutcome.UNKNOWN, reason)
    if not _valid_names_list(tgt["names"]):
        return DisposeDecode(DisposeOutcome.UNKNOWN, DecodeReason.SHAPE)
    if tgt["names"] == []:
        return DisposeDecode(DisposeOutcome.DONE_OBSERVED, DecodeReason.OK)
    if scope.gateway_name in tgt["names"]:
        return DisposeDecode(DisposeOutcome.NOT_DONE, DecodeReason.PREDICATE)
    return DisposeDecode(DisposeOutcome.UNKNOWN, DecodeReason.PREDICATE)


# ---------------------------------------------------------------- operations and ReadTake


class _OwnerOp:
    """Base for operations bound into caller OperationSlots; outcome is frozen once."""

    __slots__ = ("_concluded", "_outcome", "_owner")

    def __init__(self, owner: PortOwnership) -> None:
        self._owner = owner
        self._concluded = False
        self._outcome: Any = None

    def _finish(self, outcome: Any) -> None:
        if not self._concluded:
            self._concluded = True
            self._outcome = outcome

    def done(self) -> bool:
        return self._concluded

    def outcome(self) -> Any:
        if not self._concluded:
            raise OwnershipRefusal(OwnershipFault.PORT)
        return self._outcome

    def __repr__(self) -> str:
        return "_OwnerOp(<redacted>)"


class ReadTake(_OwnerOp):
    """Per-read operation with its own immutable cached ReadOutcome (section 5.2)."""

    __slots__ = ("_ok", "deadline", "size", "take_id")

    def __init__(self, owner: PortOwnership, take_id: int, size: int, deadline: float) -> None:
        super().__init__(owner)
        self.take_id = take_id
        self.size = size
        self.deadline = deadline
        self._ok: bool | None = None

    def _resolve(self, ok: bool, data: bytes, outcome_cls: Any) -> None:
        if not self._concluded:
            self._ok = ok
            self._concluded = True
            self._outcome = outcome_cls(ok=ok, data=data)

    def __repr__(self) -> str:
        return "ReadTake(<redacted>)"


# ---------------------------------------------------------------- internal record state


class _Record:
    __slots__ = (
        "accepted_total",
        "act_kind",
        "armed_at",
        "audit_kind",
        "case",
        "closed_observed",
        "deadline",
        "dispose_kind",
        "dropped_total",
        "epoch",
        "exited",
        "faults",
        "gate",
        "handle",
        "handoff_zero",
        "has_process_handle",
        "has_transport",
        "helper_plans",
        "kind",
        "late",
        "late_overflow",
        "next_child_idx",
        "not_started_flag",
        "op",
        "open_pipes",
        "parent",
        "payload_len",
        "pending_close_dispose",
        "pending_spawn_at",
        "pending_spawn_proc",
        "pending_term_dispose",
        "pid",
        "pipes_lost",
        "plan_index",
        "protocol",
        "protocol_at",
        "raws",
        "received_total",
        "record_id",
        "released_local",
        "reserved_at",
        "resident",
        "returncode",
        "scope_id",
        "settled_at",
        "stderr_bytes",
        "stdout_buf",
        "token",
        "uncertain",
    )

    def __init__(
        self,
        record_id: int,
        kind: InvocationKind,
        scope_id: str,
        reserved_at: float,
    ) -> None:
        self.record_id = record_id
        self.kind = kind
        self.parent: int | None = None
        self.plan_index = 0
        self.scope_id = scope_id
        self.act_kind: Any = None
        self.audit_kind: AuditKind | None = None
        self.dispose_kind: DisposeKind | None = None
        self.case: int | None = None
        self.token: int | None = None
        self.gate = Gate.RESERVED
        self.reserved_at = reserved_at
        self.armed_at: float | None = None
        self.deadline = reserved_at
        self.epoch = 0
        self.protocol = ProtocolState.PENDING
        self.protocol_at: float | None = None
        self.pid: int | None = None
        self.returncode: int | None = None
        self.exited = False
        self.pipes_lost: list[bool | None] = [None, None, None]
        self.payload_len: int | None = None
        self.handoff_zero = False
        self.received_total = 0
        self.accepted_total = 0
        self.resident = 0
        self.dropped_total = 0
        self.stderr_bytes = 0
        self.faults: list[FaultKind] = []
        self.uncertain = False
        self.late: list[LateFact] = []
        self.late_overflow = False
        self.settled_at: float | None = None
        self.handle: Any = None
        self.has_transport = False
        self.has_process_handle = False
        self.open_pipes: set[int] = set()
        self.stdout_buf = bytearray()
        self.released_local = False
        self.not_started_flag = False
        self.closed_observed = False
        self.op: _OwnerOp | None = None
        self.helper_plans: tuple[HelperPlan, ...] = ()
        self.raws: list[HelperRaw] = []
        self.next_child_idx = 0
        self.pending_close_dispose: _Record | None = None
        self.pending_spawn_at: float | None = None
        self.pending_spawn_proc: GatewayCliProcess | None = None
        self.pending_term_dispose: _Record | None = None

    def retained_tuple(self) -> tuple[Retained, ...]:
        items: list[Retained] = []
        if self.has_transport:
            items.append(Retained.TRANSPORT)
        if self.has_process_handle:
            items.append(Retained.PROCESS_HANDLE)
        if 0 in self.open_pipes:
            items.append(Retained.PIPE_0)
        if 1 in self.open_pipes:
            items.append(Retained.PIPE_1)
        if 2 in self.open_pipes:
            items.append(Retained.PIPE_2)
        if self.resident > 0:
            items.append(Retained.BUFFER)
        return tuple(items)

    def _process_physical(self) -> PhysicalState:
        if self.gate is Gate.NOT_ARMED or self.not_started_flag:
            return PhysicalState.NOT_STARTED
        if self.released_local:
            return PhysicalState.RELEASED_LOCAL
        if self.handle is None:
            return PhysicalState.UNKNOWN if self.uncertain else PhysicalState.OPEN
        if (
            self.exited
            and self.returncode is not None
            and not self.open_pipes
            and not self.uncertain
        ):
            return PhysicalState.SETTLED_RETAINED
        return PhysicalState.OPEN

    def physical_state(self, children: list[_Record] | None = None) -> PhysicalState:
        if self.kind in (InvocationKind.SPAWN, InvocationKind.CHILD):
            return self._process_physical()
        if self.gate is Gate.NOT_ARMED or self.protocol is ProtocolState.NOT_STARTED:
            return PhysicalState.NOT_STARTED
        if self.kind is InvocationKind.WRITE:
            if self.protocol is ProtocolState.FAILED_KNOWN:
                return PhysicalState.NOT_STARTED
            if self.handoff_zero and not self.uncertain:
                return PhysicalState.SETTLED_RETAINED
            return PhysicalState.OPEN if not self.uncertain else PhysicalState.UNKNOWN
        if self.kind is InvocationKind.WAIT:
            return (
                PhysicalState.SETTLED_RETAINED
                if self.settled_at is not None and not self.uncertain
                else PhysicalState.OPEN
            )
        if children:
            if any(c._process_physical() is PhysicalState.OPEN for c in children):
                return PhysicalState.OPEN
            if any(c._process_physical() is PhysicalState.UNKNOWN for c in children):
                return PhysicalState.UNKNOWN
        return (
            PhysicalState.SETTLED_RETAINED
            if self.settled_at is not None and not self.uncertain
            else PhysicalState.OPEN
        )

    def to_view(self, children: list[_Record] | None = None) -> RecordView:
        p0, p1, p2 = self.pipes_lost[0], self.pipes_lost[1], self.pipes_lost[2]
        return RecordView(
            record_id=self.record_id,
            kind=self.kind,
            parent=self.parent,
            plan_index=self.plan_index,
            scope_id=self.scope_id,
            act_kind=self.act_kind,
            case=self.case,
            token=self.token,
            gate=self.gate,
            reserved_at=self.reserved_at,
            armed_at=self.armed_at,
            deadline=self.deadline,
            epoch=self.epoch,
            protocol=self.protocol,
            protocol_at=self.protocol_at,
            pid=self.pid,
            returncode=self.returncode,
            exited=self.exited,
            pipes_lost=(p0, p1, p2),
            payload_len=self.payload_len,
            handoff_zero=self.handoff_zero,
            received_total=self.received_total,
            accepted_total=self.accepted_total,
            resident=self.resident,
            dropped_total=self.dropped_total,
            stderr_bytes=self.stderr_bytes,
            faults=tuple(self.faults),
            uncertain=self.uncertain,
            late=tuple(self.late),
            late_overflow=self.late_overflow,
            physical=self.physical_state(children),
            retained=self.retained_tuple(),
            settled_at=self.settled_at,
        )

    def __repr__(self) -> str:
        return "_Record(<redacted>)"


# ---------------------------------------------------------------- adapters and process handle


class _ProcessEventsAdapter:
    __slots__ = ("_owner", "_rec")

    def __init__(self, owner: PortOwnership, rec: _Record) -> None:
        self._owner = owner
        self._rec = rec

    def started(self, handle: ProcessHandle) -> None:
        self._owner._on_started(self._rec, handle)

    def start_failed(self) -> None:
        self._owner._on_start_failed(self._rec)

    def not_started(self) -> None:
        self._owner._on_not_started(self._rec)

    def data(self, fd: int, chunk: bytes) -> None:
        self._owner._on_data(self._rec, fd, chunk)

    def pipe_lost(self, fd: int, failed: bool) -> None:
        self._owner._on_pipe_lost(self._rec, fd, failed)

    def exited(self, code: object) -> None:
        self._owner._on_exited(self._rec, code)

    def write_resumed(self) -> None:
        self._owner._on_write_resumed(self._rec)

    def closed(self) -> None:
        self._owner._on_closed(self._rec)

    def __repr__(self) -> str:
        return "_ProcessEventsAdapter(<redacted>)"


class GatewayCliProcess:
    """Public gateway process handle exposed to DuplexBridge on successful SPAWN."""

    __slots__ = ("_owner", "_spawn_rec")

    def __init__(self, owner: PortOwnership, spawn_rec: _Record) -> None:
        self._owner = owner
        self._spawn_rec = spawn_rec

    def begin_read_into(self, slot: Any, size: int, deadline: float) -> None:
        self._owner._begin_read_into(self._spawn_rec, slot, size, deadline)

    def begin_write_into(self, slot: Any, payload: bytes, deadline: float) -> None:
        self._owner._begin_write_into(self._spawn_rec, slot, payload, deadline)

    def begin_wait_into(self, slot: Any, deadline: float) -> None:
        self._owner._begin_wait_into(self._spawn_rec, slot, deadline)

    def __repr__(self) -> str:
        return "GatewayCliProcess(<redacted>)"


class ClockAdapter:
    __slots__ = ("_owner",)

    def __init__(self, owner: PortOwnership) -> None:
        self._owner = owner

    def now(self) -> float:
        return self._owner._now()

    def poll(self, watched: Any, target: float) -> float:
        return self._owner._poll(watched, target)

    def __repr__(self) -> str:
        return "ClockAdapter(<redacted>)"


class GatewayAdapter:
    __slots__ = ("_owner",)

    def __init__(self, owner: PortOwnership) -> None:
        self._owner = owner

    def begin_spawn_into(self, slot: Any, deadline: float) -> None:
        self._owner._begin_spawn_into(slot, deadline)

    def __repr__(self) -> str:
        return "GatewayAdapter(<redacted>)"


class ActAdapter:
    __slots__ = ("_owner",)

    def __init__(self, owner: PortOwnership) -> None:
        self._owner = owner

    def begin_act_into(self, slot: Any, act: Any, deadline: float) -> None:
        self._owner._begin_act_into(slot, act, deadline)

    def __repr__(self) -> str:
        return "ActAdapter(<redacted>)"


# ---------------------------------------------------------------- PortOwnership


class PortOwnership:
    """Synchronous custodian of one W1 invocation over a deterministic or Proactor Pump."""

    __slots__ = (
        "_acts_adapter",
        "_audit_results",
        "_b",
        "_by_id",
        "_clock_adapter",
        "_epoch",
        "_first_control",
        "_gateway_adapter",
        "_in_pump",
        "_last_failed_take",
        "_last_now",
        "_limits",
        "_next_take_id",
        "_pending_take",
        "_pending_wait",
        "_pending_write",
        "_plan",
        "_pump",
        "_r",
        "_records",
        "_sealed",
        "_sealed_at",
        "_work_ids",
        "_write_faulted",
    )

    def __init__(
        self,
        pump: Any,
        plan: CliPlan,
        limits: OwnerLimits = OwnerLimits(),
        *,
        bridge_ns: types.ModuleType,
        reactor_ns: types.ModuleType,
    ) -> None:
        b_vars, r_vars = _validate_namespaces(bridge_ns, reactor_ns)
        if not _limits_ok(limits):
            raise OwnershipRefusal(OwnershipFault.PLAN)
        checked_plan = _validate_plan(plan, limits, r_vars["ActKind"])
        if (
            not callable(getattr(pump, "now", None))
            or not callable(getattr(pump, "schedule_start", None))
            or not callable(getattr(pump, "run_until", None))
        ):
            raise OwnershipRefusal(OwnershipFault.PUMP)
        self._pump = pump
        self._plan = checked_plan
        self._limits = limits
        self._b = b_vars
        self._r = r_vars
        self._records: list[_Record] = []
        self._by_id: dict[int, _Record] = {}
        self._last_now: float | None = None
        self._in_pump = False
        self._sealed = False
        self._sealed_at = 0.0
        self._work_ids: tuple[int, ...] = ()
        self._first_control: BaseException | None = None
        self._epoch = 0
        self._write_faulted = False
        self._next_take_id = 0
        self._pending_take: ReadTake | None = None
        self._last_failed_take: ReadTake | None = None
        self._pending_write: _Record | None = None
        self._pending_wait: _Record | None = None
        self._audit_results: dict[AuditKind, tuple[_Record, AuditDecode]] = {}
        self._clock_adapter = ClockAdapter(self)
        self._gateway_adapter = GatewayAdapter(self)
        self._acts_adapter = ActAdapter(self)

    def __repr__(self) -> str:
        return "PortOwnership(<redacted>)"

    # ------------------------------------------------------------ public views and adapters

    def clock(self) -> ClockAdapter:
        return self._clock_adapter

    def gateway(self) -> GatewayAdapter:
        return self._gateway_adapter

    def acts(self) -> ActAdapter:
        return self._acts_adapter

    def records(self) -> tuple[RecordView, ...]:
        return tuple(r.to_view(self._children_of(r.record_id)) for r in self._records)

    def first_control(self) -> BaseException | None:
        return self._first_control

    def custody(self) -> CustodyView:
        entries = tuple(
            (r.record_id, r.retained_tuple()) for r in self._records if r.retained_tuple()
        )
        return CustodyView(entries=entries)

    def audit(self) -> AuditReport:
        fence = self._current_fence() if self._sealed else None
        gw_res = self._build_audit_result(AuditKind.GATEWAY_ABSENT)
        bg_res = self._build_audit_result(AuditKind.BACKENDS_ZERO)
        quiet = self._is_quiet_scoped(fence, gw_res, bg_res)
        return AuditReport(
            fence=fence,
            records=self.records(),
            gateway=gw_res,
            backends=bg_res,
            epoch=self._epoch,
            control_history=self._first_control is not None,
            quiet_scoped=quiet,
        )

    # ------------------------------------------------------------ internal helpers

    def _refuse(self, category: OwnershipFault) -> NoReturn:
        raise OwnershipRefusal(category)

    def _check_not_in_pump(self) -> None:
        if self._in_pump:
            raise OwnershipRefusal(OwnershipFault.REENTRY)

    def _record_control(self, exc: BaseException) -> None:
        if self._first_control is None:
            self._first_control = exc

    def _now(self) -> float:
        failed = False
        raw: object = None
        try:
            raw = self._pump.now()
        except Exception:
            failed = True
        except BaseException as control:
            self._record_control(control)
            raise
        moment = None if failed else _finite_or_none(raw)
        if moment is None or moment < 0 or (self._last_now is not None and moment < self._last_now):
            raise OwnershipRefusal(OwnershipFault.PUMP)
        self._last_now = moment
        return moment

    def _children_of(self, parent_id: int) -> list[_Record]:
        return [r for r in self._records if r.parent == parent_id]

    def _count_kind(self, kind: InvocationKind) -> int:
        return sum(1 for r in self._records if r.kind is kind)

    def _check_work_open(self) -> None:
        if self._sealed:
            raise OwnershipRefusal(OwnershipFault.SEALED)
        if self._first_control is not None:
            raise OwnershipRefusal(OwnershipFault.STATE)

    def _check_capacity(self, kind: InvocationKind) -> None:
        if len(self._records) >= self._limits.max_records:
            raise OwnershipRefusal(OwnershipFault.CAPACITY)
        cap_map = {
            InvocationKind.WRITE: self._limits.max_writes,
            InvocationKind.ACT: self._limits.max_acts,
            InvocationKind.AUDIT: self._limits.max_audits,
            InvocationKind.DISPOSE: self._limits.max_disposals,
        }
        limit = cap_map.get(kind)
        if limit is not None and self._count_kind(kind) >= limit:
            raise OwnershipRefusal(OwnershipFault.CAPACITY)

    def _reserve_record(
        self, kind: InvocationKind, reserved_at: float, deadline: float, plan_index: int = 0
    ) -> _Record:
        self._check_capacity(kind)
        rec = _Record(len(self._records) + 1, kind, self._plan.scope.scope_id, reserved_at)
        rec.deadline = deadline
        rec.plan_index = plan_index
        rec.epoch = self._epoch
        self._records.append(rec)
        self._by_id[rec.record_id] = rec
        return rec

    def _bind_slot(self, rec: _Record, slot: Any, op: _OwnerOp) -> None:
        rec.op = op
        failed = False
        try:
            slot.bind(op)
        except Exception:
            failed = True
        except BaseException as control:
            rec.gate = Gate.NOT_ARMED
            rec.not_started_flag = True
            rec.protocol = ProtocolState.NOT_STARTED
            rec.protocol_at = rec.reserved_at
            rec.settled_at = rec.reserved_at
            self._record_control(control)
            raise
        if failed:
            rec.gate = Gate.NOT_ARMED
            rec.not_started_flag = True
            rec.protocol = ProtocolState.NOT_STARTED
            rec.protocol_at = rec.reserved_at
            rec.settled_at = rec.reserved_at
            raise OwnershipRefusal(OwnershipFault.PORT)
        rec.gate = Gate.BOUND

    def _valid_free_slot(self, slot: Any) -> bool:
        return type(slot) is self._b["OperationSlot"] and slot.occupied is False

    def _append_late(self, rec: _Record, fact: LateFact) -> None:
        if len(rec.late) >= self._limits.max_late:
            rec.late_overflow = True
            return
        rec.late.append(fact)

    def _add_fault(self, rec: _Record, fault: FaultKind) -> None:
        if fault not in rec.faults:
            rec.faults.append(fault)

    def _schedule_start(self, req: StartRequest) -> None:
        failed = False
        try:
            self._pump.schedule_start(req)
        except Exception:
            failed = True
        except BaseException as control:
            self._record_control(control)
            raise
        if failed:
            raise OwnershipRefusal(OwnershipFault.PUMP)

    # ------------------------------------------------------------ clock poll & settle

    def _extract_polled_ops(self, watched: Any) -> list[_OwnerOp]:
        if type(watched) is not tuple or not watched:
            raise OwnershipRefusal(OwnershipFault.PORT)
        slot_cls = self._b["OperationSlot"]
        ops: list[_OwnerOp] = []
        for item in watched:
            if type(item) is not slot_cls:
                raise OwnershipRefusal(OwnershipFault.PORT)
            candidate = item.op
            if not isinstance(candidate, _OwnerOp) or candidate._owner is not self:
                raise OwnershipRefusal(OwnershipFault.PORT)
            ops.append(candidate)
        return ops

    def _poll(self, watched: Any, target: float) -> float:
        self._check_not_in_pump()
        ops = self._extract_polled_ops(watched)
        checked_target = _finite_or_none(target)
        if checked_target is None:
            raise OwnershipRefusal(OwnershipFault.PORT)
        return self._run_pump(checked_target, lambda: any(op._concluded for op in ops))

    def _publish_pending_spawn(self) -> None:
        for rec in self._records:
            if rec.kind is InvocationKind.SPAWN and rec.pending_spawn_proc is not None:
                proc = rec.pending_spawn_proc
                rec.pending_spawn_proc = None
                if rec.protocol is ProtocolState.PENDING:
                    rec.protocol = ProtocolState.SUCCEEDED
                    rec.protocol_at = rec.pending_spawn_at
                    if rec.op is not None:
                        rec.op._finish(self._b["SpawnOutcome"](ok=True, process=proc))

    def _run_pump(self, target: float, stop_fn: Callable[[], bool]) -> float:
        self._now()
        pump_failed = False
        ret_val: object = None
        self._in_pump = True

        def stop_check() -> bool:
            self._publish_pending_spawn()
            return stop_fn()

        try:
            ret_val = self._pump.run_until(target, stop_check)
        except Exception:
            pump_failed = True
        except BaseException as control:
            self._record_control(control)
            raise
        finally:
            self._in_pump = False
        self._publish_pending_spawn()
        if pump_failed or _finite_or_none(ret_val) is None:
            raise OwnershipRefusal(OwnershipFault.PUMP)
        after = self._now()
        self._expire_deadlines(after)
        if not stop_check() and after < target:
            raise OwnershipRefusal(OwnershipFault.PUMP)
        return after

    def _expire_deadlines(self, now: float) -> None:
        if (
            self._pending_take is not None
            and not self._pending_take._concluded
            and now >= self._pending_take.deadline
        ):
            take = self._pending_take
            self._pending_take = None
            take._resolve(False, b"", self._b["ReadOutcome"])
            self._last_failed_take = take
        if (
            self._pending_write is not None
            and self._pending_write.protocol is ProtocolState.PENDING
            and now >= self._pending_write.deadline
        ):
            w = self._pending_write
            self._pending_write = None
            w.protocol = ProtocolState.UNKNOWN
            w.protocol_at = now
            w.uncertain = True
            if w.op is not None:
                w.op._finish(
                    self._b["WriteOutcome"](delivery=self._r["Delivery"].UNKNOWN, bytes_written=0)
                )
        for rec in self._records:
            if rec.kind is InvocationKind.DISPOSE and rec.protocol is ProtocolState.PENDING:
                if now >= rec.deadline and not self._has_open_children(rec.record_id):
                    self._expire_dispose(rec, now)

    def _expire_dispose(self, rec: _Record, now: float) -> None:
        if rec.dispose_kind in (DisposeKind.CLOSE_HANDLE, DisposeKind.TERMINATE_PROCESS):
            rec.protocol = ProtocolState.FAILED_KNOWN
            rec.protocol_at = now
            rec.settled_at = now
            if rec.parent is not None and rec.parent in self._by_id:
                tgt = self._by_id[rec.parent]
                if tgt.pending_close_dispose is rec:
                    tgt.pending_close_dispose = None
                if tgt.pending_term_dispose is rec:
                    tgt.pending_term_dispose = None
        elif rec.dispose_kind is DisposeKind.REMOVE_GATEWAY_CONTAINER:
            rec.protocol = ProtocolState.UNKNOWN
            rec.protocol_at = now
            rec.settled_at = now

    def _has_open_children(self, parent_id: int) -> bool:
        return any(
            c._process_physical() in (PhysicalState.OPEN, PhysicalState.UNKNOWN)
            for c in self._children_of(parent_id)
        )

    # ------------------------------------------------------------ spawn, read, write, wait

    def _begin_spawn_into(self, slot: Any, deadline: float) -> None:
        self._check_not_in_pump()
        self._check_work_open()
        checked_deadline = _finite_or_none(deadline)
        if not self._valid_free_slot(slot) or checked_deadline is None:
            raise OwnershipRefusal(OwnershipFault.PORT)
        if self._count_kind(InvocationKind.SPAWN) > 0:
            raise OwnershipRefusal(OwnershipFault.STATE)
        now = self._now()
        rec = self._reserve_record(InvocationKind.SPAWN, now, checked_deadline, 0)
        op = _OwnerOp(self)
        self._bind_slot(rec, slot, op)
        rec.gate = Gate.ARMED
        rec.armed_at = now
        req = StartRequest(
            record_id=rec.record_id,
            argv=self._plan.gateway_argv,
            stdin_pipe=True,
            not_before=now,
            authorize=lambda: self._authorize_process(rec, None),
            events=_ProcessEventsAdapter(self, rec),
        )
        self._schedule_start(req)

    def _authorize_process(self, rec: _Record, parent: _Record | None) -> bool:
        now = self._now()
        if rec.gate is not Gate.ARMED:
            return False
        if parent is None or parent.kind is InvocationKind.ACT:
            if self._sealed or self._first_control is not None:
                return False
        elif not self._sealed:
            return False
        if now >= rec.deadline:
            return False
        if parent is not None:
            if now >= parent.deadline or parent.protocol is not ProtocolState.PENDING:
                return False
            if (
                parent.kind is InvocationKind.DISPOSE
                and parent.dispose_kind is DisposeKind.REMOVE_GATEWAY_CONTAINER
                and rec.plan_index == 0
            ):
                self._epoch += 1
                parent.epoch = self._epoch
                rec.epoch = self._epoch
        return True

    def _begin_read_into(self, spawn_rec: _Record, slot: Any, size: int, deadline: float) -> None:
        self._check_not_in_pump()
        self._check_work_open()
        checked_deadline = _finite_or_none(deadline)
        if (
            not self._valid_free_slot(slot)
            or not _exact_int_in(size, 1, 4096)
            or checked_deadline is None
        ):
            raise OwnershipRefusal(OwnershipFault.PORT)
        if self._pending_take is not None and not self._pending_take._concluded:
            raise OwnershipRefusal(OwnershipFault.STATE)
        now = self._now()
        self._next_take_id += 1
        take = ReadTake(self, self._next_take_id, size, checked_deadline)
        bind_failed = False
        try:
            slot.bind(take)
        except Exception:
            bind_failed = True
        except BaseException as control:
            self._record_control(control)
            raise
        if bind_failed:
            raise OwnershipRefusal(OwnershipFault.PORT)
        out_cls = self._b["ReadOutcome"]
        if now >= checked_deadline:
            take._resolve(False, b"", out_cls)
            self._last_failed_take = take
            return
        if spawn_rec.resident > 0:
            n = min(size, spawn_rec.resident)
            chunk = bytes(spawn_rec.stdout_buf[:n])
            del spawn_rec.stdout_buf[:n]
            spawn_rec.resident -= n
            take._resolve(True, chunk, out_cls)
            return
        if spawn_rec.pipes_lost[1] is not None:
            failed = spawn_rec.pipes_lost[1]
            ok = failed is False
            take._resolve(ok, b"", out_cls)
            if not ok:
                self._last_failed_take = take
            return
        self._pending_take = take

    def _begin_write_into(
        self, spawn_rec: _Record, slot: Any, payload: bytes, deadline: float
    ) -> None:
        self._check_not_in_pump()
        self._check_work_open()
        checked_deadline = _finite_or_none(deadline)
        if (
            not self._valid_free_slot(slot)
            or type(payload) is not bytes
            or len(payload) == 0
            or checked_deadline is None
        ):
            raise OwnershipRefusal(OwnershipFault.PORT)
        reserved_at = self._last_now if self._last_now is not None else self._now()
        rec = self._reserve_record(InvocationKind.WRITE, reserved_at, checked_deadline, 0)
        rec.parent = spawn_rec.record_id
        rec.payload_len = len(payload)
        op = _OwnerOp(self)
        self._bind_slot(rec, slot, op)
        rec.gate = Gate.ARMED
        if not self._write_preconditions_ok(spawn_rec, rec):
            now_pre = self._now()
            rec.protocol = ProtocolState.FAILED_KNOWN
            rec.protocol_at = now_pre
            rec.settled_at = now_pre
            op._finish(
                self._b["WriteOutcome"](delivery=self._r["Delivery"].NOT_SENT, bytes_written=0)
            )
            return
        now = self._now()
        rec.armed_at = now
        if (
            rec.gate is not Gate.ARMED
            or self._sealed
            or self._first_control is not None
            or now >= rec.deadline
            or spawn_rec.protocol is not ProtocolState.SUCCEEDED
        ):
            rec.gate = Gate.NOT_ARMED
            rec.not_started_flag = True
            rec.protocol = ProtocolState.NOT_STARTED
            rec.protocol_at = now
            rec.settled_at = now
            op._finish(
                self._b["WriteOutcome"](delivery=self._r["Delivery"].NOT_SENT, bytes_written=0)
            )
            return
        self._execute_write(spawn_rec, rec, op, payload, now)

    def _write_preconditions_ok(self, spawn_rec: _Record, rec: _Record) -> bool:
        handle = spawn_rec.handle
        if handle is None:
            return False
        failed = False
        limits: object = None
        closing: object = None
        try:
            limits = handle.write_limits()
            closing = handle.is_closing()
        except Exception:
            failed = True
        except BaseException as control:
            rec.gate = Gate.NOT_ARMED
            rec.not_started_flag = True
            rec.protocol = ProtocolState.NOT_STARTED
            rec.protocol_at = rec.reserved_at
            rec.settled_at = rec.reserved_at
            self._record_control(control)
            raise
        if failed:
            rec.gate = Gate.NOT_ARMED
            rec.not_started_flag = True
            rec.protocol = ProtocolState.NOT_STARTED
            rec.protocol_at = rec.reserved_at
            rec.settled_at = rec.reserved_at
            raise OwnershipRefusal(OwnershipFault.PUMP)
        return (
            limits == (0, 0)
            and closing is False
            and spawn_rec.pipes_lost[0] is None
            and not self._write_faulted
        )

    def _execute_write(
        self, spawn_rec: _Record, rec: _Record, op: _OwnerOp, payload: bytes, now: float
    ) -> None:
        handle = spawn_rec.handle
        write_failed = False
        closing: object = False
        buf_size: object = None
        try:
            handle.write(payload)
            closing = handle.is_closing()
            if closing is False and spawn_rec.pipes_lost[0] is None:
                buf_size = handle.buffer_size()
        except Exception:
            write_failed = True
        except BaseException as control:
            self._write_faulted = True
            self._add_fault(rec, FaultKind.CONTROL)
            rec.uncertain = True
            rec.protocol = ProtocolState.UNKNOWN
            rec.protocol_at = now
            op._finish(
                self._b["WriteOutcome"](delivery=self._r["Delivery"].UNKNOWN, bytes_written=0)
            )
            self._record_control(control)
            raise
        now = self._now()
        if (
            write_failed
            or closing is not False
            or spawn_rec.pipes_lost[0] is not None
            or not _exact_int_in(buf_size, 0, _MAX_COUNTER)
        ):
            self._write_faulted = True
            self._add_fault(rec, FaultKind.WRITE)
            rec.uncertain = True
            rec.protocol = ProtocolState.UNKNOWN
            rec.protocol_at = now
            op._finish(
                self._b["WriteOutcome"](delivery=self._r["Delivery"].UNKNOWN, bytes_written=0)
            )
            return
        if now >= rec.deadline:
            rec.protocol = ProtocolState.UNKNOWN
            rec.protocol_at = now
            op._finish(
                self._b["WriteOutcome"](delivery=self._r["Delivery"].UNKNOWN, bytes_written=0)
            )
            if buf_size == 0:
                rec.handoff_zero = True
                rec.uncertain = False
                rec.settled_at = now
                self._append_late(
                    rec, LateFact(at=now, kind=LateKind.HANDOFF_ZERO, code=None, fault=None)
                )
            else:
                rec.uncertain = True
            return
        if buf_size == 0:
            rec.handoff_zero = True
            rec.uncertain = False
            rec.protocol = ProtocolState.SUCCEEDED
            rec.protocol_at = now
            rec.settled_at = now
            op._finish(
                self._b["WriteOutcome"](
                    delivery=self._r["Delivery"].SENT, bytes_written=len(payload)
                )
            )
            return
        self._pending_write = rec

    def _begin_wait_into(self, spawn_rec: _Record, slot: Any, deadline: float) -> None:
        self._check_not_in_pump()
        self._check_work_open()
        checked_deadline = _finite_or_none(deadline)
        if not self._valid_free_slot(slot) or checked_deadline is None:
            raise OwnershipRefusal(OwnershipFault.PORT)
        if self._count_kind(InvocationKind.WAIT) >= 1:
            raise OwnershipRefusal(OwnershipFault.STATE)
        now = self._now()
        rec = self._reserve_record(InvocationKind.WAIT, now, checked_deadline, 0)
        rec.parent = spawn_rec.record_id
        op = _OwnerOp(self)
        self._bind_slot(rec, slot, op)
        rec.gate = Gate.ARMED
        rec.armed_at = now
        if spawn_rec.exited:
            self._conclude_wait(rec, spawn_rec, now)
        else:
            self._pending_wait = rec

    def _conclude_wait(self, wait_rec: _Record, spawn_rec: _Record, now: float) -> None:
        exit_cls = self._r["ExitStatus"]
        out_cls = self._b["WaitOutcome"]
        if spawn_rec.returncode is not None:
            wait_rec.protocol = ProtocolState.SUCCEEDED
            wait_rec.protocol_at = now
            wait_rec.settled_at = now
            if wait_rec.op is not None:
                wait_rec.op._finish(
                    out_cls(status=exit_cls.EXITED, code=spawn_rec.returncode, reaped=True)
                )
        else:
            wait_rec.protocol = ProtocolState.UNKNOWN
            wait_rec.protocol_at = now
            wait_rec.uncertain = True
            if wait_rec.op is not None:
                wait_rec.op._finish(out_cls(status=exit_cls.UNKNOWN, code=None, reaped=False))

    # ------------------------------------------------------------ actions

    def _begin_act_into(self, slot: Any, act: Any, deadline: float) -> None:
        self._check_not_in_pump()
        self._check_work_open()
        checked_deadline = _finite_or_none(deadline)
        if (
            not self._valid_free_slot(slot)
            or type(act) is not self._r["Act"]
            or type(act.kind) is not self._r["ActKind"]
            or not _exact_int_in(act.case, 1, 25)
            or not _exact_int_in(act.token, 1, _MAX_PID)
            or checked_deadline is None
        ):
            raise OwnershipRefusal(OwnershipFault.PORT)
        plan_idx = next(i for i, (k, _) in enumerate(self._plan.acts) if k is act.kind)
        now = self._now()
        rec = self._reserve_record(InvocationKind.ACT, now, checked_deadline, plan_idx)
        rec.act_kind = act.kind
        rec.case = act.case
        rec.token = act.token
        rec.helper_plans = self._plan.acts[plan_idx][1]
        op = _OwnerOp(self)
        self._bind_slot(rec, slot, op)
        rec.gate = Gate.ARMED
        rec.armed_at = now
        self._launch_next_child(rec, now)

    def _launch_next_child(self, parent: _Record, now: float) -> None:
        if parent.protocol is not ProtocolState.PENDING:
            return
        if now >= parent.deadline:
            return
        j = parent.next_child_idx
        if j >= len(parent.helper_plans):
            return
        if len(self._records) >= self._limits.max_records or j >= self._limits.max_children:
            self._conclude_parent_missing(parent, now)
            return
        child = self._reserve_record(InvocationKind.CHILD, now, parent.deadline, j)
        child.parent = parent.record_id
        child.act_kind = parent.act_kind
        child.case = parent.case
        child.token = parent.token
        child.gate = Gate.ARMED
        child.armed_at = now
        parent.next_child_idx = j + 1
        req = StartRequest(
            record_id=child.record_id,
            argv=parent.helper_plans[j].argv,
            stdin_pipe=False,
            not_before=now,
            authorize=lambda: self._authorize_process(child, parent),
            events=_ProcessEventsAdapter(self, child),
        )
        self._schedule_start(req)

    def _conclude_parent_missing(self, parent: _Record, now: float) -> None:
        parent.protocol = ProtocolState.UNKNOWN
        parent.protocol_at = now
        parent.settled_at = now
        if parent.kind is InvocationKind.ACT and parent.op is not None:
            parent.op._finish(
                self._b["ActOutcome"](status=self._r["ActStatus"].UNKNOWN, facts=None)
            )
        elif parent.kind is InvocationKind.AUDIT and parent.audit_kind is not None:
            self._audit_results[parent.audit_kind] = (
                parent,
                AuditDecode(AbsenceVerdict.UNKNOWN, DecodeReason.MISSING),
            )

    # ------------------------------------------------------------ process event callbacks

    def _on_not_started(self, rec: _Record) -> None:
        now = self._now()
        rec.gate = Gate.NOT_ARMED
        rec.not_started_flag = True
        rec.protocol = ProtocolState.NOT_STARTED
        rec.protocol_at = now
        rec.settled_at = now
        if rec.kind is InvocationKind.SPAWN and rec.op is not None:
            rec.op._finish(self._b["SpawnOutcome"](ok=False, process=None))
        elif rec.kind is InvocationKind.CHILD and rec.parent is not None:
            parent = self._by_id[rec.parent]
            if parent.settled_at is None and not self._has_open_children(parent.record_id):
                parent.settled_at = now

    def _on_started(self, rec: _Record, handle: ProcessHandle) -> None:
        now = self._now()
        rec.handle = handle
        rec.has_transport = True
        rec.has_process_handle = True
        rec.open_pipes = {0, 1} if rec.kind is InvocationKind.SPAWN else {1, 2}
        pid_val: object = None
        pid_failed = False
        try:
            pid_val = handle.pid()
        except Exception:
            pid_failed = True
        except BaseException as control:
            self._record_control(control)
            raise
        if not pid_failed and (pid_val is None or _exact_int_in(pid_val, 1, _MAX_PID)):
            rec.pid = pid_val if type(pid_val) is int else None
        else:
            rec.pid = None
            self._add_fault(rec, FaultKind.CALLBACK)
            rec.uncertain = True
        if rec.protocol is not ProtocolState.PENDING:
            self._append_late(
                rec, LateFact(at=now, kind=LateKind.STARTED, code=rec.pid, fault=None)
            )
            return
        if rec.kind is InvocationKind.SPAWN:
            limits_val: object = None
            limits_failed = False
            try:
                limits_val = handle.write_limits()
            except Exception:
                limits_failed = True
            except BaseException as control:
                self._record_control(control)
                raise
            if not limits_failed and limits_val == (0, 0):
                proc = GatewayCliProcess(self, rec)
                if self._in_pump:
                    rec.pending_spawn_proc = proc
                    rec.pending_spawn_at = now
                else:
                    rec.protocol = ProtocolState.SUCCEEDED
                    rec.protocol_at = now
                    if rec.op is not None:
                        rec.op._finish(self._b["SpawnOutcome"](ok=True, process=proc))
            else:
                self._add_fault(rec, FaultKind.WRITE_LIMITS)
                rec.uncertain = True
                rec.protocol = ProtocolState.UNKNOWN
                rec.protocol_at = now
                if rec.op is not None:
                    rec.op._finish(self._b["SpawnOutcome"](ok=False, process=None))

    def _on_start_failed(self, rec: _Record) -> None:
        now = self._now()
        self._add_fault(rec, FaultKind.START)
        rec.uncertain = True
        rec.pending_spawn_proc = None
        if rec.protocol is ProtocolState.PENDING:
            rec.protocol = ProtocolState.UNKNOWN
            rec.protocol_at = now
            if rec.kind is InvocationKind.SPAWN and rec.op is not None:
                rec.op._finish(self._b["SpawnOutcome"](ok=False, process=None))
            elif rec.kind is InvocationKind.CHILD and rec.parent is not None:
                parent = self._by_id[rec.parent]
                self._conclude_parent_missing(parent, now)

    def _on_data(self, rec: _Record, fd: int, chunk: bytes) -> None:
        if type(chunk) is not bytes or rec.handle is None:
            self._add_fault(rec, FaultKind.CALLBACK)
            rec.uncertain = True
            return
        if fd == 2 and rec.kind is InvocationKind.CHILD:
            total_err = rec.stderr_bytes + len(chunk)
            if total_err > _MAX_COUNTER:
                rec.stderr_bytes = _MAX_COUNTER
                self._add_fault(rec, FaultKind.OVERFLOW)
                rec.uncertain = True
            else:
                rec.stderr_bytes = total_err
            return
        if fd != 1:
            self._add_fault(rec, FaultKind.CALLBACK)
            rec.uncertain = True
            return
        cap = (
            self._limits.gateway_stdout_cap
            if rec.kind is InvocationKind.SPAWN
            else self._limits.child_stdout_cap
        )
        room = max(0, cap - rec.accepted_total)
        take = min(len(chunk), room)
        if take > 0:
            rec.stdout_buf.extend(chunk[:take])
        rec.accepted_total += take
        rec.resident += take
        new_received = rec.received_total + len(chunk)
        new_dropped = rec.dropped_total + (len(chunk) - take)
        if new_received > _MAX_COUNTER or new_dropped > _MAX_COUNTER:
            rec.received_total = min(_MAX_COUNTER, new_received)
            rec.dropped_total = min(_MAX_COUNTER, new_dropped)
            self._add_fault(rec, FaultKind.OVERFLOW)
            rec.uncertain = True
        else:
            rec.received_total = new_received
            rec.dropped_total = new_dropped
        if rec.accepted_total == cap:
            try:
                rec.handle.pause_reading(1)
            except Exception:
                self._add_fault(rec, FaultKind.CALLBACK)
                rec.uncertain = True
            except BaseException as control:
                self._record_control(control)
                raise
        if (
            rec.kind is InvocationKind.SPAWN
            and self._pending_take is not None
            and not self._pending_take._concluded
        ):
            now = self._now()
            self._expire_deadlines(now)
            if (
                self._pending_take is not None
                and not self._pending_take._concluded
                and rec.resident > 0
            ):
                pt = self._pending_take
                self._pending_take = None
                n = min(pt.size, rec.resident)
                data = bytes(rec.stdout_buf[:n])
                del rec.stdout_buf[:n]
                rec.resident -= n
                pt._resolve(True, data, self._b["ReadOutcome"])

    def _is_late_for_process(self, rec: _Record, now: float) -> bool:
        if self._sealed:
            return True
        if rec.kind is InvocationKind.SPAWN:
            return rec.protocol is ProtocolState.UNKNOWN and rec.uncertain
        if now > rec.deadline:
            return True
        if rec.parent is not None and rec.parent in self._by_id:
            parent = self._by_id[rec.parent]
            return now > parent.deadline or parent.protocol is not ProtocolState.PENDING
        return False

    def _on_pipe_lost(self, rec: _Record, fd: int, failed: bool) -> None:
        now = self._now()
        allowed = (0, 1) if rec.kind is InvocationKind.SPAWN else (1, 2)
        if (
            type(failed) is not bool
            or fd not in allowed
            or rec.handle is None
            or rec.pipes_lost[fd] is not None
        ):
            self._add_fault(rec, FaultKind.CALLBACK)
            rec.uncertain = True
            return
        rec.pipes_lost[fd] = failed
        rec.open_pipes.discard(fd)
        if self._is_late_for_process(rec, now):
            self._append_late(rec, LateFact(at=now, kind=LateKind.PIPE_LOST, code=fd, fault=None))
        if rec.kind is InvocationKind.SPAWN:
            self._handle_spawn_pipe_lost(rec, fd, failed, now)
        self._check_process_settled(rec, now)

    def _handle_spawn_pipe_lost(self, rec: _Record, fd: int, failed: bool, now: float) -> None:
        if fd == 1 and self._pending_take is not None and not self._pending_take._concluded:
            pt = self._pending_take
            self._pending_take = None
            if now >= pt.deadline:
                pt._resolve(False, b"", self._b["ReadOutcome"])
                self._last_failed_take = pt
            elif rec.resident > 0:
                n = min(pt.size, rec.resident)
                data = bytes(rec.stdout_buf[:n])
                del rec.stdout_buf[:n]
                rec.resident -= n
                pt._resolve(True, data, self._b["ReadOutcome"])
            else:
                ok = failed is False
                pt._resolve(ok, b"", self._b["ReadOutcome"])
                if not ok:
                    self._last_failed_take = pt
        elif fd == 0:
            if (
                self._pending_write is not None
                and self._pending_write.protocol is ProtocolState.PENDING
            ):
                w = self._pending_write
                self._pending_write = None
                w.protocol = ProtocolState.UNKNOWN
                w.protocol_at = now
                w.uncertain = True
                if w.op is not None:
                    w.op._finish(
                        self._b["WriteOutcome"](
                            delivery=self._r["Delivery"].UNKNOWN, bytes_written=0
                        )
                    )
            for r in self._records:
                if r.kind is InvocationKind.WRITE and r.uncertain:
                    r.uncertain = False
                    r.settled_at = now

    def _on_exited(self, rec: _Record, code: object) -> None:
        now = self._now()
        rec.exited = True
        if _exact_int_in(code, 0, 255) and type(code) is int:
            rec.returncode = code
        else:
            rec.returncode = None
            self._add_fault(rec, FaultKind.CALLBACK)
            rec.uncertain = True
        if self._is_late_for_process(rec, now):
            self._append_late(
                rec, LateFact(at=now, kind=LateKind.EXITED, code=rec.returncode, fault=None)
            )
        if rec.kind is InvocationKind.SPAWN and self._pending_wait is not None:
            wait_rec = self._pending_wait
            self._pending_wait = None
            self._conclude_wait(wait_rec, rec, now)
        self._check_process_settled(rec, now)

    def _on_write_resumed(self, rec: _Record) -> None:
        now = self._now()
        if rec.kind is not InvocationKind.SPAWN or rec.handle is None:
            return
        buf_size: object = None
        closing: object = True
        query_failed = False
        try:
            buf_size = rec.handle.buffer_size()
            closing = rec.handle.is_closing()
        except Exception:
            query_failed = True
        except BaseException as control:
            self._record_control(control)
            raise
        if query_failed or buf_size != 0 or closing is not False:
            return
        self._expire_deadlines(now)
        if (
            self._pending_write is not None
            and self._pending_write.protocol is ProtocolState.PENDING
        ):
            w = self._pending_write
            self._pending_write = None
            w.handoff_zero = True
            w.uncertain = False
            w.protocol = ProtocolState.SUCCEEDED
            w.protocol_at = now
            w.settled_at = now
            if w.op is not None and w.payload_len is not None:
                w.op._finish(
                    self._b["WriteOutcome"](
                        delivery=self._r["Delivery"].SENT, bytes_written=w.payload_len
                    )
                )
            return
        for r in self._records:
            if r.kind is InvocationKind.WRITE and not r.handoff_zero:
                r.handoff_zero = True
                r.uncertain = False
                r.settled_at = now
                self._append_late(
                    r, LateFact(at=now, kind=LateKind.HANDOFF_ZERO, code=None, fault=None)
                )

    def _on_closed(self, rec: _Record) -> None:
        now = self._now()
        rec.closed_observed = True
        disp = rec.pending_close_dispose
        if disp is not None and disp.protocol is ProtocolState.PENDING:
            rec.pending_close_dispose = None
            rec.released_local = True
            rec.has_transport = False
            rec.has_process_handle = False
            rec.open_pipes.clear()
            rec.stdout_buf.clear()
            rec.resident = 0
            rec.handle = None
            disp.protocol = ProtocolState.SUCCEEDED
            disp.protocol_at = now
            disp.settled_at = now

    def _check_process_settled(self, rec: _Record, now: float) -> None:
        if not (rec.exited and rec.returncode is not None and not rec.open_pipes):
            return
        rec.uncertain = False
        if rec.settled_at is None:
            rec.settled_at = now
        if rec.pending_term_dispose is not None:
            term = rec.pending_term_dispose
            rec.pending_term_dispose = None
            if term.protocol is ProtocolState.PENDING:
                term.protocol = ProtocolState.SUCCEEDED
                term.protocol_at = now
                term.settled_at = now
        if rec.kind is InvocationKind.CHILD:
            self._on_child_settled(rec, now)

    def _on_child_settled(self, child: _Record, now: float) -> None:
        raw_bytes = bytes(child.stdout_buf)
        child.stdout_buf.clear()
        child.resident = 0
        raw = HelperRaw(
            index=child.plan_index,
            code=child.returncode,
            stdout=raw_bytes,
            stdout_dropped=child.dropped_total,
            stderr_bytes=child.stderr_bytes,
        )
        if child.parent is None or child.parent not in self._by_id:
            return
        parent = self._by_id[child.parent]
        is_late = (
            parent.protocol is not ProtocolState.PENDING
            or now > parent.deadline
            or (parent.kind is InvocationKind.ACT and self._sealed)
        )
        if is_late:
            self._append_late(
                parent,
                LateFact(at=now, kind=LateKind.CHILD_DONE, code=child.returncode, fault=None),
            )
            if not self._has_open_children(parent.record_id):
                parent.settled_at = now
            return
        child.protocol = (
            ProtocolState.SUCCEEDED if child.returncode == 0 else ProtocolState.FAILED_KNOWN
        )
        child.protocol_at = now
        parent.raws.append(raw)
        self._advance_parent_chain(parent, raw, now)

    def _advance_parent_chain(self, parent: _Record, last_raw: HelperRaw, now: float) -> None:
        if last_raw.code != 0 or last_raw.stdout_dropped > 0:
            self._finalize_parent_decode(parent, now)
            return
        if parent.kind is InvocationKind.ACT and parent.act_kind.name == "OBSERVE_HEAVY":
            obj, _ = _parse_helper_json(last_raw, _OBSERVE_KEYS, self._plan.scope.scope_id)
            if obj is None or type(obj.get("active")) is not bool or obj["active"] is True:
                self._finalize_parent_decode(parent, now)
                return
            if parent.next_child_idx < len(parent.helper_plans):
                self._launch_next_child(parent, now)
            else:
                self._finalize_parent_decode(parent, now)
            return
        if parent.next_child_idx < len(parent.helper_plans):
            if last_raw.index == 0 and self._first_step_is_command(parent) and last_raw.stdout:
                self._finalize_parent_decode(parent, now)
                return
            self._launch_next_child(parent, now)
            return
        self._finalize_parent_decode(parent, now)

    def _first_step_is_command(self, parent: _Record) -> bool:
        if parent.kind is InvocationKind.DISPOSE:
            return True
        if parent.kind is InvocationKind.ACT:
            return parent.act_kind.name in ("PAUSE_PG", "RESTORE_PG", "KILL_GATEWAY")
        return False

    def _finalize_parent_decode(self, parent: _Record, now: float) -> None:
        scope = self._plan.scope
        parent.protocol_at = now
        parent.settled_at = now
        if parent.kind is InvocationKind.ACT:
            dec = _decode_act(
                parent.act_kind.name, parent.raws, len(parent.helper_plans), scope, self._r
            )
            st = self._r["ActStatus"]
            if dec.status is st.OK:
                parent.protocol = ProtocolState.SUCCEEDED
            elif dec.status is st.FAILED:
                parent.protocol = ProtocolState.FAILED_KNOWN
            else:
                parent.protocol = ProtocolState.UNKNOWN
            if parent.op is not None:
                parent.op._finish(self._b["ActOutcome"](status=dec.status, facts=dec.facts))
        elif parent.kind is InvocationKind.AUDIT and parent.audit_kind is not None:
            aud_dec = _decode_audit(parent.audit_kind, parent.raws, scope)
            if aud_dec.verdict is AbsenceVerdict.ABSENT_OBSERVED:
                parent.protocol = ProtocolState.SUCCEEDED
            elif aud_dec.verdict is AbsenceVerdict.PRESENT:
                parent.protocol = ProtocolState.FAILED_KNOWN
            else:
                parent.protocol = ProtocolState.UNKNOWN
            self._audit_results[parent.audit_kind] = (parent, aud_dec)
        elif parent.kind is InvocationKind.DISPOSE:
            disp_dec = _decode_dispose_remove(parent.raws, scope)
            if disp_dec.outcome is DisposeOutcome.DONE_OBSERVED:
                parent.protocol = ProtocolState.SUCCEEDED
            elif disp_dec.outcome is DisposeOutcome.NOT_DONE:
                parent.protocol = ProtocolState.FAILED_KNOWN
            else:
                parent.protocol = ProtocolState.UNKNOWN

    # ------------------------------------------------------------ seal, settle, audit, dispose

    def seal(self) -> WorkFence:
        self._check_not_in_pump()
        if not self._sealed:
            now = self._now()
            self._sealed = True
            self._sealed_at = now
            self._work_ids = tuple(r.record_id for r in self._records)
        return self._current_fence()

    def _current_fence(self) -> WorkFence:
        work_recs = [self._by_id[rid] for rid in self._work_ids]
        open_ids = tuple(
            r.record_id
            for r in work_recs
            if r.physical_state(self._children_of(r.record_id)) is PhysicalState.OPEN
        )
        unknown_ids = tuple(
            r.record_id
            for r in work_recs
            if r.physical_state(self._children_of(r.record_id)) is PhysicalState.UNKNOWN
        )
        settled_states = (
            PhysicalState.NOT_STARTED,
            PhysicalState.SETTLED_RETAINED,
            PhysicalState.RELEASED_LOCAL,
        )
        all_settled = all(
            r.physical_state(self._children_of(r.record_id)) in settled_states and not r.uncertain
            for r in work_recs
        )
        times = [r.settled_at for r in work_recs if r.settled_at is not None]
        work_settled_at = max(times, default=self._sealed_at) if all_settled else None
        return WorkFence(
            sealed_at=self._sealed_at,
            work_ids=self._work_ids,
            open_ids=open_ids,
            unknown_ids=unknown_ids,
            work_settled_at=work_settled_at,
        )

    def _all_records_settled(self) -> bool:
        settled_states = (
            PhysicalState.NOT_STARTED,
            PhysicalState.SETTLED_RETAINED,
            PhysicalState.RELEASED_LOCAL,
        )
        return all(
            r.physical_state(self._children_of(r.record_id)) in settled_states
            for r in self._records
        )

    def settle(self, target: float) -> float:
        self._check_not_in_pump()
        if not self._sealed:
            raise OwnershipRefusal(OwnershipFault.SEALED)
        checked_target = _finite_or_none(target)
        if checked_target is None:
            raise OwnershipRefusal(OwnershipFault.PORT)
        return self._run_pump(checked_target, self._all_records_settled)

    def begin_audit(self, kind: AuditKind, deadline: float) -> int:
        self._check_not_in_pump()
        if not self._sealed:
            raise OwnershipRefusal(OwnershipFault.SEALED)
        checked_deadline = _finite_or_none(deadline)
        if type(kind) is not AuditKind or checked_deadline is None:
            raise OwnershipRefusal(OwnershipFault.PORT)
        fence = self._current_fence()
        if fence.work_settled_at is None or self._has_open_target_dispose():
            raise OwnershipRefusal(OwnershipFault.STATE)
        self._check_capacity(InvocationKind.AUDIT)
        now = self._now()
        if now <= fence.work_settled_at:
            raise OwnershipRefusal(OwnershipFault.STATE)
        plan_idx = next(i for i, (k, _) in enumerate(self._plan.audits) if k is kind)
        rec = self._reserve_record(InvocationKind.AUDIT, now, checked_deadline, plan_idx)
        rec.audit_kind = kind
        rec.helper_plans = self._plan.audits[plan_idx][1]
        rec.gate = Gate.ARMED
        rec.armed_at = now
        self._launch_next_child(rec, now)
        return rec.record_id

    def _has_open_target_dispose(self) -> bool:
        for r in self._records:
            if r.kind is InvocationKind.DISPOSE and r.dispose_kind in (
                DisposeKind.TERMINATE_PROCESS,
                DisposeKind.REMOVE_GATEWAY_CONTAINER,
            ):
                if r.physical_state(self._children_of(r.record_id)) is PhysicalState.OPEN:
                    return True
        return False

    def begin_dispose(self, kind: DisposeKind, target_id: int | None, deadline: float) -> int:
        self._check_not_in_pump()
        if not self._sealed:
            raise OwnershipRefusal(OwnershipFault.SEALED)
        checked_deadline = _finite_or_none(deadline)
        if type(kind) is not DisposeKind or checked_deadline is None:
            raise OwnershipRefusal(OwnershipFault.PORT)
        target = self._validate_dispose_target(kind, target_id)
        self._check_capacity(InvocationKind.DISPOSE)
        now = self._now()
        rec = self._reserve_record(InvocationKind.DISPOSE, now, checked_deadline, 0)
        rec.dispose_kind = kind
        rec.parent = target_id
        rec.gate = Gate.ARMED
        rec.armed_at = now
        if now >= checked_deadline:
            rec.gate = Gate.NOT_ARMED
            rec.not_started_flag = True
            rec.protocol = ProtocolState.NOT_STARTED
            rec.protocol_at = now
            rec.settled_at = now
            return rec.record_id
        if kind is DisposeKind.CLOSE_HANDLE and target is not None:
            self._execute_close_dispose(rec, target, now)
        elif kind is DisposeKind.TERMINATE_PROCESS and target is not None:
            self._execute_terminate_dispose(rec, target, now)
        else:
            rec.helper_plans = self._plan.remove_gateway
            self._launch_next_child(rec, now)
        return rec.record_id

    def _validate_dispose_target(self, kind: DisposeKind, target_id: int | None) -> _Record | None:
        if kind is DisposeKind.REMOVE_GATEWAY_CONTAINER:
            if target_id is not None:
                raise OwnershipRefusal(OwnershipFault.STATE)
            return None
        if not _exact_int_in(target_id, 1, _MAX_PID) or target_id not in self._by_id:
            raise OwnershipRefusal(OwnershipFault.STATE)
        target = self._by_id[target_id]
        if target.kind not in (InvocationKind.SPAWN, InvocationKind.CHILD):
            raise OwnershipRefusal(OwnershipFault.STATE)
        if target.handle is None:
            raise OwnershipRefusal(OwnershipFault.STATE)
        rc_val: object = None
        rc_failed = False
        try:
            rc_val = target.handle.returncode()
        except Exception:
            rc_failed = True
        except BaseException as control:
            self._record_control(control)
            raise
        if rc_failed:
            raise OwnershipRefusal(OwnershipFault.PUMP)
        if kind is DisposeKind.CLOSE_HANDLE:
            if (
                target._process_physical() is not PhysicalState.SETTLED_RETAINED
                or type(rc_val) is not int
            ):
                raise OwnershipRefusal(OwnershipFault.STATE)
        elif rc_val is not None:
            raise OwnershipRefusal(OwnershipFault.STATE)
        return target

    def _execute_close_dispose(self, disp: _Record, target: _Record, now: float) -> None:
        target.pending_close_dispose = disp
        close_failed = False
        try:
            target.handle.close()
        except Exception:
            close_failed = True
        except BaseException as control:
            target.pending_close_dispose = None
            self._add_fault(disp, FaultKind.CONTROL)
            disp.uncertain = True
            disp.protocol = ProtocolState.UNKNOWN
            disp.protocol_at = now
            self._record_control(control)
            raise
        if close_failed:
            target.pending_close_dispose = None
            self._add_fault(disp, FaultKind.CALLBACK)
            disp.protocol = ProtocolState.UNKNOWN
            disp.protocol_at = now
            disp.settled_at = now
            return
        if target.closed_observed and disp.protocol is ProtocolState.PENDING:
            self._on_closed(target)

    def _execute_terminate_dispose(self, disp: _Record, target: _Record, now: float) -> None:
        self._epoch += 1
        disp.epoch = self._epoch
        target.pending_term_dispose = disp
        kill_failed = False
        try:
            target.handle.kill()
        except Exception:
            kill_failed = True
        except BaseException as control:
            target.pending_term_dispose = None
            self._add_fault(disp, FaultKind.CONTROL)
            disp.uncertain = True
            disp.protocol = ProtocolState.UNKNOWN
            disp.protocol_at = now
            self._record_control(control)
            raise
        if kill_failed:
            target.pending_term_dispose = None
            self._add_fault(disp, FaultKind.CALLBACK)
            disp.protocol = ProtocolState.UNKNOWN
            disp.protocol_at = now
            disp.settled_at = now

    def _build_audit_result(self, kind: AuditKind) -> AuditResult | None:
        entry = self._audit_results.get(kind)
        if entry is None:
            return None
        rec, dec = entry
        children = self._children_of(rec.record_id)
        settled_ok = len(children) == 2 and all(
            c._process_physical() in (PhysicalState.SETTLED_RETAINED, PhysicalState.RELEASED_LOCAL)
            and c.settled_at is not None
            for c in children
        )
        verdict = AbsenceVerdict.STALE if rec.epoch < self._epoch else dec.verdict
        if not settled_ok and verdict is AbsenceVerdict.ABSENT_OBSERVED:
            verdict = AbsenceVerdict.UNKNOWN
        return AuditResult(
            record_id=rec.record_id,
            kind=kind,
            epoch=rec.epoch,
            armed_at=rec.armed_at if rec.armed_at is not None else rec.reserved_at,
            verdict=verdict,
            reason=dec.reason,
            helpers_settled=settled_ok,
        )

    def _is_quiet_scoped(
        self,
        fence: WorkFence | None,
        gw: AuditResult | None,
        bg: AuditResult | None,
    ) -> bool:
        if not self._sealed or fence is None or fence.work_settled_at is None:
            return False
        if gw is None or bg is None:
            return False
        for res in (gw, bg):
            if (
                res.verdict is not AbsenceVerdict.ABSENT_OBSERVED
                or res.epoch != self._epoch
                or not res.helpers_settled
                or res.armed_at <= fence.work_settled_at
            ):
                return False
        settled_states = (
            PhysicalState.NOT_STARTED,
            PhysicalState.SETTLED_RETAINED,
            PhysicalState.RELEASED_LOCAL,
        )
        return all(
            r.physical_state(self._children_of(r.record_id)) in settled_states and not r.uncertain
            for r in self._records
        )
