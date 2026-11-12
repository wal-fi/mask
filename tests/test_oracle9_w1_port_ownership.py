"""W1 port ownership and concrete adapter oracles (PORT-DESIGN V4 + PORT-REVIEW); RED-first.

Contract for the FUTURE ``docs/poc/oracle9_w1_port_ownership.py``. The module stays
absent until the root reviews these oracles and freezes RED; it is loaded lazily inside
feature cases only (``ownership_module()``), so absence fails per case with
``FileNotFoundError`` at execution and never breaks pytest collection. The
``test_sanity_*`` cases never load the absent module: they validate this file's own
fixtures, canonical helper payloads, ``FakePump``/``FakeHandle`` mechanics, and the
published ``HostReactor`` (e86f8e32) and ``DuplexBridge`` (5a09be1c) bindings over the
published trusted core (4c155d76).

Only the narrow ``Pump`` / ``ProcessHandle`` seam is faked over an exact dyadic clock.
Every positive process event is scheduled on the ``FakePump`` timeline and delivered only
inside ``FakePump.run_until`` (design section 2.2). The protocol engine is the real
published ``HostReactor`` driven by the real published ``DuplexBridge``; ``_facts_ok`` and
protocol outcomes are never faked or reimplemented. Nothing here touches asyncio, an
event loop, subprocesses, sockets, threads, signals, Linux guards, Docker, PostgreSQL,
SQL, or operational configuration. Model ``Done`` and ``quiet_scoped`` are scoped model
observations only, never physical release proof or native ``ProactorEventLoop``
validation.

Provenance: the first draft (67ea9838) was authored by the authorized Gemini fallback.
Claude2 (session 51ea0d85) applied the PORT-OWNERSHIP-TEST-REVIEW corrections only:
constant-repr proof without typed Trap construction, plan DTO validation inside
``pytest.raises``, events delivered through the pump, exact-module ``__getattr__``
namespaces, late overflow from unique events of a live child, the reachable
max_acts/max_audits/max_disposals/retained-take oracles, and static-gate cleanups.
"""

from __future__ import annotations

import ast
import dataclasses
import enum
import functools
import json
import runpy
import types
from collections import deque
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests import test_oracle9_w1_driver as d1
from tests import test_oracle9_w1_duplex_bridge as bt
from tests import test_oracle9_w1_host_reactor as ht

core = ht.core  # published load_pure fixture over the pinned 4c155d76 controller bytes

REPO = Path(__file__).resolve().parents[1]
OWNERSHIP_FILE = REPO / "docs/poc/oracle9_w1_port_ownership.py"
PACKET = ht.PACKET
GO, STOP, NOSTOP, ACK = ht.GO, ht.STOP, ht.NOSTOP, ht.ACK

T0 = 100.0
DT = 2.0**-6  # exact dyadic step
SPAWN_S, SILENCE_S, DRAIN_S, OVERALL_S = 5.0, 10.0, 10.0, 120.0
GATEWAY_STDOUT_CAP = 28673
CHILD_STDOUT_CAP = 4096
MAX_RECORDS_DEFAULT = 512
P1_CONSERVATIVE_BOUND = 137  # root review: a conservative ceiling, not a required count

SCOPE_ID = "scope-w1-01"
GATEWAY_NAME = "maskgw-lab-gw"
SCOPE_LABEL = "io.senff.maskgw.scope=scope-w1-01"
PG_NAME = "maskgw-lab-pg"
TARGET_ROLE = "maskgw_reader"
OBSERVER_ROLE = "maskgw_observer"
STDERR_CANARY = "SYNTHETIC-STDERR-CANARY-DO-NOT-RETAIN"
ARGV_CANARY = "SYNTHETIC-ARGV-TOKEN-scope-w1-01"
SECRET_TEXTS = (
    *ht.SECRETS,
    repr(PACKET),
    STDERR_CANARY,
    ARGV_CANARY,
    GATEWAY_NAME,
    PG_NAME,
)

OWNERSHIP_ENUMS: dict[str, frozenset[str]] = {
    "OwnershipFault": frozenset(
        {"CAPACITY", "REENTRY", "STATE", "PLAN", "PUMP", "PORT", "SEALED", "NAMESPACE"}
    ),
    "FaultKind": frozenset(
        {
            "START",
            "CALLBACK",
            "WRITE",
            "WRITE_LIMITS",
            "DECODE",
            "OVERFLOW",
            "CONTROL",
            "PUMP",
        }
    ),
    "InvocationKind": frozenset({"SPAWN", "WRITE", "WAIT", "ACT", "CHILD", "AUDIT", "DISPOSE"}),
    "Gate": frozenset({"RESERVED", "BOUND", "ARMED", "NOT_ARMED"}),
    "ProtocolState": frozenset({"PENDING", "SUCCEEDED", "FAILED_KNOWN", "NOT_STARTED", "UNKNOWN"}),
    "PhysicalState": frozenset(
        {"NOT_STARTED", "OPEN", "SETTLED_RETAINED", "RELEASED_LOCAL", "UNKNOWN"}
    ),
    "Retained": frozenset({"TRANSPORT", "PROCESS_HANDLE", "PIPE_0", "PIPE_1", "PIPE_2", "BUFFER"}),
    "AuditKind": frozenset({"GATEWAY_ABSENT", "BACKENDS_ZERO"}),
    "AbsenceVerdict": frozenset({"NOT_RUN", "ABSENT_OBSERVED", "PRESENT", "STALE", "UNKNOWN"}),
    "DisposeKind": frozenset({"CLOSE_HANDLE", "TERMINATE_PROCESS", "REMOVE_GATEWAY_CONTAINER"}),
    "DisposeOutcome": frozenset({"DONE_OBSERVED", "NOT_DONE", "UNKNOWN"}),
    "DecodeReason": frozenset(
        {"OK", "EXIT_NONZERO", "SHAPE", "SCOPE", "TRUNCATED", "PREDICATE", "MISSING"}
    ),
    "LateKind": frozenset(
        {
            "STARTED",
            "EXITED",
            "PIPE_LOST",
            "HANDOFF_ZERO",
            "WRITE_FAULT",
            "CHILD_DONE",
            "CLOSED",
            "CONTROL",
        }
    ),
}

OWNERSHIP_DTOS: dict[str, tuple[str, ...]] = {
    "StartRequest": (
        "record_id",
        "argv",
        "stdin_pipe",
        "not_before",
        "authorize",
        "events",
    ),
    "Scope": (
        "scope_id",
        "gateway_name",
        "scope_label",
        "pg_name",
        "target_role",
        "observer_role",
    ),
    "HelperPlan": ("argv",),
    "CliPlan": ("scope", "gateway_argv", "acts", "audits", "remove_gateway"),
    "OwnerLimits": (
        "max_records",
        "max_children",
        "max_writes",
        "max_acts",
        "max_audits",
        "max_disposals",
        "gateway_stdout_cap",
        "child_stdout_cap",
        "max_late",
        "max_retained_takes",
    ),
    "LateFact": ("at", "kind", "code", "fault"),
    "HelperRaw": ("index", "code", "stdout", "stdout_dropped", "stderr_bytes"),
    "ActDecode": ("status", "facts", "reason"),
    "AuditDecode": ("verdict", "reason"),
    "DisposeDecode": ("outcome", "reason"),
    "RecordView": (
        "record_id",
        "kind",
        "parent",
        "plan_index",
        "scope_id",
        "act_kind",
        "case",
        "token",
        "gate",
        "reserved_at",
        "armed_at",
        "deadline",
        "epoch",
        "protocol",
        "protocol_at",
        "pid",
        "returncode",
        "exited",
        "pipes_lost",
        "payload_len",
        "handoff_zero",
        "received_total",
        "accepted_total",
        "resident",
        "dropped_total",
        "stderr_bytes",
        "faults",
        "uncertain",
        "late",
        "late_overflow",
        "physical",
        "retained",
        "settled_at",
    ),
    "WorkFence": ("sealed_at", "work_ids", "open_ids", "unknown_ids", "work_settled_at"),
    "AuditResult": (
        "record_id",
        "kind",
        "epoch",
        "armed_at",
        "verdict",
        "reason",
        "helpers_settled",
    ),
    "AuditReport": (
        "fence",
        "records",
        "gateway",
        "backends",
        "epoch",
        "control_history",
        "quiet_scoped",
    ),
    "CustodyView": ("entries",),
}

DEFAULT_LIMITS: dict[str, int] = {
    "max_records": 512,
    "max_children": 24,
    "max_writes": 51,
    "max_acts": 7,
    "max_audits": 8,
    "max_disposals": 64,
    "gateway_stdout_cap": 28673,
    "child_stdout_cap": 4096,
    "max_late": 16,
    "max_retained_takes": 2,
}

BRIDGE_REQUIRED_CLASSES = (
    "SpawnOutcome",
    "ReadOutcome",
    "WriteOutcome",
    "ActOutcome",
    "WaitOutcome",
    "OperationSlot",
)
REACTOR_REQUIRED_CLASSES = (
    "Act",
    "TerminateFacts",
    "PauseFacts",
    "RestoreFacts",
    "ObserveFacts",
    "ZeroFacts",
    "KillFacts",
)
REACTOR_REQUIRED_ENUMS: dict[str, frozenset[str]] = {
    "ActKind": ht.ENUMS["ActKind"],
    "ActStatus": ht.ENUMS["ActStatus"],
    "Delivery": ht.ENUMS["Delivery"],
    "ExitStatus": ht.ENUMS["ExitStatus"],
}


# ---------------------------------------------------------------- lazy loading & namespaces


@functools.cache
def _ownership_namespace() -> dict[str, Any]:
    return runpy.run_path(str(OWNERSHIP_FILE), run_name="_port_ownership_test")


def ownership_module() -> Any:
    return SimpleNamespace(**_ownership_namespace())


def bridge_variant(**changes: object) -> types.ModuleType:
    """Published bridge namespace bound into a plain ModuleType for vars(ns) checks."""
    module = types.ModuleType("_port_ownership_bridge_ns")
    module.__dict__.update(bt._bridge_namespace())
    for name, value in changes.items():
        if value is ht.DROP:
            del module.__dict__[name]
        else:
            module.__dict__[name] = value
    return module


def reactor_variant(**changes: object) -> types.ModuleType:
    """Published reactor namespace bound into a plain ModuleType for vars(ns) checks."""
    module = types.ModuleType("_port_ownership_reactor_ns")
    module.__dict__.update(ht._reactor_namespace())
    for name, value in changes.items():
        if value is ht.DROP:
            del module.__dict__[name]
        else:
            module.__dict__[name] = value
    return module


@functools.cache
def bridge_mod() -> types.ModuleType:
    return bridge_variant()


@functools.cache
def reactor_mod() -> types.ModuleType:
    return reactor_variant()


def exact_getattr_module(
    base: types.ModuleType, missing: str, calls: list[str]
) -> types.ModuleType:
    """EXACT ModuleType copy with ``missing`` absent from vars and a live module __getattr__."""

    def hostile_getattr(name: str) -> Any:
        calls.append(name)
        raise AssertionError("module __getattr__ invoked")

    module = types.ModuleType("_exact_getattr_module")
    module.__dict__.update(vars(base))
    del module.__dict__[missing]
    module.__dict__["__getattr__"] = hostile_getattr
    return module


class SubModule(types.ModuleType):
    """ModuleType subclass: refused by exact-type validation, never inspected further."""


class HostileSubModule(types.ModuleType):
    """ModuleType subclass whose class-level __getattr__ must never be reached."""

    calls: list[str]

    def __getattr__(self, name: str) -> Any:
        self.calls.append(name)
        raise AssertionError("module subclass __getattr__ invoked")


def sub_module(base: types.ModuleType) -> types.ModuleType:
    module = SubModule("_sub_module")
    module.__dict__.update(vars(base))
    return module


def hostile_sub_module(base: types.ModuleType, missing: str, calls: list[str]) -> types.ModuleType:
    module = HostileSubModule("_hostile_sub_module")
    module.__dict__.update(vars(base))
    del module.__dict__[missing]
    module.calls = calls
    return module


# ---------------------------------------------------------------- helper JSON recipes


def jline(payload: dict[str, object]) -> bytes:
    """Canonical ASCII JSON line ending in a single LF (<= 512 bytes)."""
    return d1.canonical(payload) + b"\n"


def terminate_line(*, found: int = 1, terminated: bool = True, scope: str = SCOPE_ID) -> bytes:
    return jline({"found": found, "scope": scope, "terminated": terminated})


def pause_line(*, paused: bool = True, running: bool = True, scope: str = SCOPE_ID) -> bytes:
    return jline({"paused": paused, "running": running, "scope": scope})


def restore_ready_line(*, ready: bool = True, scope: str = SCOPE_ID) -> bytes:
    return jline({"ready": ready, "scope": scope})


def observe_line(*, active: bool = True, scope: str = SCOPE_ID) -> bytes:
    return jline({"active": active, "scope": scope})


def zero_line(
    *,
    backends: int = 0,
    observer_excluded: object = True,
    role: str = TARGET_ROLE,
    scope: str = SCOPE_ID,
) -> bytes:
    return jline(
        {
            "backends": backends,
            "observer_excluded": observer_excluded,
            "role": role,
            "scope": scope,
        }
    )


def kill_line(
    *,
    oom: bool = False,
    pid: int = 0,
    running: bool = False,
    scope: str = SCOPE_ID,
) -> bytes:
    return jline({"oom": oom, "pid": pid, "running": running, "scope": scope})


def names_line(names: list[str], *, scope: str = SCOPE_ID) -> bytes:
    return jline({"names": names, "scope": scope})


def observer_control_line(
    *, observer: object = True, role: str = OBSERVER_ROLE, scope: str = SCOPE_ID
) -> bytes:
    return jline({"observer": observer, "role": role, "scope": scope})


# ---------------------------------------------------------------- plan builders


def make_scope(m: Any, **overrides: object) -> Any:
    fields: dict[str, object] = {
        "scope_id": SCOPE_ID,
        "gateway_name": GATEWAY_NAME,
        "scope_label": SCOPE_LABEL,
        "pg_name": PG_NAME,
        "target_role": TARGET_ROLE,
        "observer_role": OBSERVER_ROLE,
    }
    fields.update(overrides)
    return m.Scope(**fields)


def make_helper(m: Any, tag: str, *, scope_id: str = SCOPE_ID) -> Any:
    return m.HelperPlan(argv=("helper", tag, f"--scope={scope_id}", ARGV_CANARY))


def default_acts(m: Any, r_ns: types.ModuleType, sid: str, observe_children: int) -> Any:
    ak: Any = vars(r_ns)["ActKind"]

    def helpers(*tags: str) -> tuple[Any, ...]:
        return tuple(make_helper(m, tag, scope_id=sid) for tag in tags)

    observe_tags = tuple(f"act-observe-{idx}" for idx in range(observe_children))
    return (
        (ak.TERMINATE_ONE_BACKEND, helpers("act-term-0")),
        (ak.PAUSE_PG, helpers("act-pause-0", "act-pause-1")),
        (ak.RESTORE_PG, helpers("act-restore-0", "act-restore-1", "act-restore-2")),
        (ak.OBSERVE_HEAVY, helpers(*observe_tags)),
        (ak.ZERO_BACKENDS, helpers("act-zero-0")),
        (ak.KILL_GATEWAY, helpers("act-kill-0", "act-kill-1")),
    )


def default_audits(m: Any, sid: str) -> Any:
    return (
        (
            m.AuditKind.GATEWAY_ABSENT,
            (
                make_helper(m, "audit-gw-control", scope_id=sid),
                make_helper(m, "audit-gw-target", scope_id=sid),
            ),
        ),
        (
            m.AuditKind.BACKENDS_ZERO,
            (
                make_helper(m, "audit-bg-control", scope_id=sid),
                make_helper(m, "audit-bg-target", scope_id=sid),
            ),
        ),
    )


def make_plan(m: Any, r_ns: types.ModuleType, *, observe_children: int = 20, **over: Any) -> Any:
    """Valid CliPlan; ``over`` replaces scope/gateway_argv/acts/audits/remove_gateway."""
    chosen_scope = over.get("scope")
    if chosen_scope is None:
        chosen_scope = make_scope(m)
    sid = chosen_scope.scope_id if isinstance(chosen_scope.scope_id, str) else SCOPE_ID
    fields: dict[str, Any] = {
        "scope": chosen_scope,
        "gateway_argv": ("gateway-cli", f"--scope={sid}", ARGV_CANARY),
        "acts": default_acts(m, r_ns, sid, observe_children),
        "audits": default_audits(m, sid),
        "remove_gateway": (
            make_helper(m, "dispose-rm-0", scope_id=sid),
            make_helper(m, "dispose-rm-1", scope_id=sid),
        ),
    }
    fields.update({key: value for key, value in over.items() if key != "scope"})
    return m.CliPlan(**fields)


def assert_refusal(m: Any, error: BaseException, fault_name: str) -> None:
    refusal: Any = error
    assert type(refusal) is m.OwnershipRefusal
    assert refusal.category is getattr(m.OwnershipFault, fault_name)
    assert refusal.args == (fault_name,)
    assert refusal.__cause__ is None and refusal.__context__ is None
    text = str(refusal) + repr(refusal)
    assert all(secret not in text for secret in SECRET_TEXTS)


ATOMIC_MODEL_TYPES = (
    bool,
    int,
    float,
    str,
    bytes,
    bytearray,
    memoryview,
    enum.Enum,
    types.ModuleType,
    type,
    types.FunctionType,
    types.MethodType,
    types.BuiltinFunctionType,
    types.CodeType,
)


def _model_children(node: object) -> list[object]:
    if node is None or isinstance(node, ATOMIC_MODEL_TYPES):
        return []
    if isinstance(node, dict):
        return [*node.keys(), *node.values()]
    if isinstance(node, (list, tuple, set, frozenset, deque)):
        return list(node)
    children: list[object] = []
    if hasattr(node, "__dict__"):
        children.extend(vars(node).values())
    for cls in type(node).__mro__:
        raw_slots = vars(cls).get("__slots__")
        slots = (raw_slots,) if isinstance(raw_slots, str) else (raw_slots or ())
        for name in slots:
            if name not in ("__dict__", "__weakref__") and hasattr(node, name):
                children.append(getattr(node, name))
    return children


def walk_model_state(root: object, *, max_depth: int = 32, max_nodes: int = 4096) -> list[object]:
    """Walks the simple model/fake state graph; not a closure, native, or global memory proof.

    Tracks visited nodes by identity and fails explicitly if ``max_depth`` or ``max_nodes``
    is exhausted, never omitting reachable state by silent depth truncation.
    """
    visited: set[int] = {id(root)}
    out: list[object] = [root]
    queue: deque[tuple[object, int]] = deque([(root, 0)])
    while queue:
        node, depth = queue.popleft()
        for child in _model_children(node):
            if id(child) in visited:
                continue
            next_depth = depth + 1
            assert next_depth <= max_depth, f"model state walk exceeded max_depth={max_depth}"
            visited.add(id(child))
            out.append(child)
            assert len(out) <= max_nodes, f"model state walk exceeded max_nodes={max_nodes}"
            queue.append((child, next_depth))
    return out


# ---------------------------------------------------------------- FakePump and FakeHandle


@dataclasses.dataclass
class ChildScript:
    """Deterministic behavior of one spawned helper child process."""

    stdout_chunks: list[bytes] = dataclasses.field(default_factory=list)
    stderr_chunks: list[bytes] = dataclasses.field(default_factory=list)
    exit_code: object = 0
    start_mode: str = "ok"  # "ok", "fail_before", "fail_after", "late_settle", "never_settle"
    write_limits: tuple[int, int] = (0, 0)
    settle_pipes: bool = True
    exit_without_pipes: bool = False
    late_start_at: float | None = None
    on_started: Callable[[FakePump, FakeHandle, Any], None] | None = None


class FakeHandle:
    """1:1 deterministic model of the public ProcessHandle protocol (section 2.2)."""

    def __init__(self, pump: FakePump, request: Any, *, limits: tuple[int, int]) -> None:
        self._pump = pump
        self.record_id: int = request.record_id
        self.events: Any = request.events
        self.stdin_pipe: bool = request.stdin_pipe
        self._pid: int | None = (1000 if self.stdin_pipe else 3000) + self.record_id
        self._returncode: int | None = None
        self._limits = limits
        self._closing = False
        self._buffer_size = 0
        self.paused_fds: set[int] = set()
        self.resumed_fds: set[int] = set()
        self.writes: list[bytes] = []
        self.close_calls = 0
        self.kill_calls = 0
        self.write_raises: BaseException | None = None
        self.close_after_write = False
        self.retain_buffer_on_write = False
        self.defer_write_resume_dt: float | None = None
        self.close_raises: BaseException | None = None
        self.defer_closed_event = False
        self.kill_raises: BaseException | None = None
        self.kill_settles_target = True

    def pid(self) -> int | None:
        self._pump.trace.append(("handle.pid", self.record_id, self._pump.t))
        return self._pid

    def returncode(self) -> int | None:
        self._pump.trace.append(("handle.returncode", self.record_id, self._pump.t))
        return self._returncode

    def write_limits(self) -> tuple[int, int]:
        self._pump.trace.append(("handle.write_limits", self.record_id, self._pump.t))
        return self._limits

    def is_closing(self) -> bool:
        self._pump.trace.append(("handle.is_closing", self.record_id, self._pump.t))
        return self._closing

    def buffer_size(self) -> int:
        self._pump.trace.append(("handle.buffer_size", self.record_id, self._pump.t))
        return self._buffer_size

    def write(self, data: bytes) -> None:
        p = self._pump
        p.trace.append(("handle.write", self.record_id, len(data), p.t))
        if p.on_direct_write is not None:
            p.on_direct_write(p, self, data)
        if self.write_raises is not None:
            exc = self.write_raises
            self.write_raises = None
            raise exc
        self.writes.append(data)
        if self.close_after_write:
            self._closing = True
            return
        if self.retain_buffer_on_write:
            self._buffer_size += len(data)
            if self.defer_write_resume_dt is not None:
                dt = self.defer_write_resume_dt
                p.schedule_at(p.t + dt, lambda: self._complete_deferred_write(data))
            return
        self._buffer_size = 0
        p.on_gateway_write(self, data)

    def _complete_deferred_write(self, data: bytes) -> None:
        self._buffer_size = 0
        self.events.write_resumed()
        self._pump.on_gateway_write(self, data)

    def pause_reading(self, fd: int) -> None:
        self._pump.trace.append(("handle.pause_reading", self.record_id, fd, self._pump.t))
        self.paused_fds.add(fd)

    def resume_reading(self, fd: int) -> None:
        self._pump.trace.append(("handle.resume_reading", self.record_id, fd, self._pump.t))
        self.paused_fds.discard(fd)
        self.resumed_fds.add(fd)

    def close(self) -> None:
        p = self._pump
        p.trace.append(("handle.close", self.record_id, p.t))
        self.close_calls += 1
        if p.on_direct_close is not None:
            p.on_direct_close(p, self)
        if self.close_raises is not None:
            exc = self.close_raises
            self.close_raises = None
            raise exc
        self._closing = True
        if not self.defer_closed_event:
            p.schedule_at(p.t + DT, self.events.closed)

    def kill(self) -> None:
        p = self._pump
        p.trace.append(("handle.kill", self.record_id, p.t))
        self.kill_calls += 1
        if p.on_direct_kill is not None:
            p.on_direct_kill(p, self)
        if self.kill_raises is not None:
            exc = self.kill_raises
            self.kill_raises = None
            raise exc
        self._closing = True
        if self.kill_settles_target:
            p.schedule_at(p.t + DT, self.settle_killed)

    def settle_killed(self) -> None:
        """One exit plus one loss per existing pipe, scheduled once by kill()."""
        self._returncode = 137
        self.events.exited(137)
        for fd in (0, 1) if self.stdin_pipe else (1, 2):
            self.events.pipe_lost(fd, False)

    def settle_exit(self, code: int = 0) -> None:
        """Natural exit plus one loss per existing pipe; scheduled on the pump timeline."""
        self._returncode = code
        self.events.exited(code)
        for fd in (0, 1) if self.stdin_pipe else (1, 2):
            self.events.pipe_lost(fd, False)


def default_child_outputs() -> dict[str, list[bytes]]:
    return {
        "act-term-0": [terminate_line()],
        "act-pause-1": [pause_line(paused=True, running=True)],
        "act-restore-1": [pause_line(paused=False, running=True)],
        "act-restore-2": [restore_ready_line(ready=True)],
        "act-zero-0": [zero_line(backends=0)],
        "act-kill-1": [kill_line(oom=False, pid=0, running=False)],
        "audit-gw-control": [names_line([PG_NAME])],
        "audit-gw-target": [names_line([])],
        "dispose-rm-1": [names_line([])],
        "audit-bg-control": [observer_control_line()],
        "audit-bg-target": [zero_line(backends=0)],
    }


class FakePump:
    """Deterministic synchronous Pump over an exact dyadic timeline (section 2.2)."""

    def __init__(self, start_t: float = T0) -> None:
        self.t = start_t
        self.trace: list[tuple[Any, ...]] = []
        self.requests: list[Any] = []
        self.handles: dict[int, FakeHandle] = {}
        self.gateway_handle: FakeHandle | None = None
        self._scheduled: list[tuple[float, int, Callable[[], None]]] = []
        self._seq = 0
        self.in_run_until = False
        self.live_ms = ht.LIVE_MS
        # Gateway spawn mode: "ok", "fail_before", "fail_after", "late_settle", "late_none"
        self.gateway_start_mode = "ok"
        self.gateway_write_limits: tuple[int, int] = (0, 0)
        self.gateway_emit_guard = True
        self.gateway_auto_respond = True
        self.gateway_kill_exits_cli = True
        self.gateway_exit_without_pipes = False
        self.child_scripts: dict[str, deque[ChildScript]] = {}
        self.default_observe_found = True
        self.default_observe_true_at = 2  # 0-based index (3 observations by default)
        self.on_now: Callable[[FakePump], Any] | None = None
        self.on_run_until: Callable[[FakePump, float, Callable[[], bool]], float | None] | None
        self.on_run_until = None
        self.on_direct_write: Callable[[FakePump, FakeHandle, bytes], None] | None = None
        self.on_direct_close: Callable[[FakePump, FakeHandle], None] | None = None
        self.on_direct_kill: Callable[[FakePump, FakeHandle], None] | None = None

    def advance(self, dt: float = DT) -> float:
        self.t += dt
        return self.t

    def schedule_at(self, when: float, callback: Callable[[], None]) -> None:
        """Test and fake events only ever run later, inside run_until."""
        self._seq += 1
        self._scheduled.append((max(self.t, when), self._seq, callback))
        self._scheduled.sort(key=lambda item: (item[0], item[1]))

    def push_child_script(self, tag: str, *scripts: ChildScript) -> None:
        queue = self.child_scripts.setdefault(tag, deque())
        queue.extend(scripts)

    def now(self) -> Any:
        self.trace.append(("pump.now", self.t))
        if self.on_now is not None:
            return self.on_now(self)
        return self.t

    def schedule_start(self, request: Any) -> None:
        """Never executes an effect or callback synchronously (section 2.2)."""
        self.trace.append(
            (
                "pump.schedule_start",
                request.record_id,
                request.argv,
                request.stdin_pipe,
                request.not_before,
                self.t,
            )
        )
        self.requests.append(request)
        when = max(self.t, request.not_before)
        self.schedule_at(when, lambda: self._run_start(request))

    def run_until(self, target: float, stop: Callable[[], bool]) -> Any:
        self.trace.append(("pump.run_until.enter", target, self.t))
        if self.on_run_until is not None:
            forced = self.on_run_until(self, target, stop)
            if forced is not None:
                return forced
        self.in_run_until = True
        try:
            while not stop():
                if not self._scheduled or self._scheduled[0][0] > target:
                    self.t = max(self.t, target)
                    break
                when, _, callback = self._scheduled.pop(0)
                self.t = max(self.t, when)
                callback()
        finally:
            self.in_run_until = False
        self.trace.append(("pump.run_until.exit", target, self.t))
        return self.t

    def _run_start(self, request: Any) -> None:
        self.trace.append(("pump.authorize", request.record_id, self.t))
        allowed = request.authorize()
        self.trace.append(("pump.authorized", request.record_id, allowed, self.t))
        if not allowed:
            request.events.not_started()
            return
        if request.stdin_pipe:
            self._start_gateway(request)
        else:
            self._start_child(request)

    def _late_gateway(self, request: Any) -> None:
        handle = FakeHandle(self, request, limits=(0, 0))
        handle._pid = 2000 + request.record_id
        self.handles[request.record_id] = handle
        self.gateway_handle = handle
        request.events.started(handle)
        handle.settle_exit(0)

    def _start_gateway(self, request: Any) -> None:
        mode = self.gateway_start_mode
        if mode in ("fail_before", "late_none", "late_settle"):
            request.events.start_failed()
            if mode == "late_settle":
                self.schedule_at(self.t + 4 * DT, lambda: self._late_gateway(request))
            return
        handle = FakeHandle(self, request, limits=self.gateway_write_limits)
        self.handles[request.record_id] = handle
        self.gateway_handle = handle
        request.events.started(handle)
        if mode == "fail_after":
            request.events.start_failed()
            return
        if self.gateway_emit_guard and self.gateway_write_limits == (0, 0):
            guard = ht.line_bytes(ht.GUARD)
            self.schedule_at(self.t + DT, lambda: request.events.data(1, guard))

    def on_gateway_write(self, handle: FakeHandle, payload: bytes) -> None:
        if not self.gateway_auto_respond:
            return
        lines = bt.respond(payload, self.live_ms)
        raw = b"".join(ht.line_bytes(event) for event in lines)
        self.schedule_at(self.t + DT, lambda: handle.events.data(1, raw))

    def _default_child_script(self, tag: str) -> ChildScript:
        if tag.startswith("act-observe-"):
            idx = int(tag.rsplit("-", 1)[1])
            active = self.default_observe_found and idx == self.default_observe_true_at
            return ChildScript(stdout_chunks=[observe_line(active=active)])
        return ChildScript(stdout_chunks=list(default_child_outputs().get(tag, [])))

    def _late_child(self, request: Any, script: ChildScript) -> None:
        handle = FakeHandle(self, request, limits=script.write_limits)
        self.handles[request.record_id] = handle
        request.events.started(handle)
        handle.settle_exit(0)

    def _start_child(self, request: Any) -> None:
        tag = request.argv[1] if len(request.argv) > 1 else "unknown"
        queue = self.child_scripts.get(tag)
        script = queue.popleft() if queue else self._default_child_script(tag)
        if script.start_mode == "fail_before":
            request.events.start_failed()
            return
        if script.start_mode == "late_settle":
            request.events.start_failed()
            when = self.t + 4 * DT if script.late_start_at is None else script.late_start_at
            self.schedule_at(when, lambda: self._late_child(request, script))
            return
        handle = FakeHandle(self, request, limits=script.write_limits)
        self.handles[request.record_id] = handle
        request.events.started(handle)
        if script.on_started is not None:
            script.on_started(self, handle, request.events)
        if script.start_mode == "fail_after":
            request.events.start_failed()
            return
        if script.start_mode != "never_settle":
            self.schedule_at(self.t + DT, lambda: self._child_io(tag, handle, script))

    def _child_io(self, tag: str, handle: FakeHandle, script: ChildScript) -> None:
        events = handle.events
        for chunk in script.stderr_chunks:
            events.data(2, chunk)
        for chunk in script.stdout_chunks:
            events.data(1, chunk)
        if isinstance(script.exit_code, int):
            handle._returncode = script.exit_code
        events.exited(script.exit_code)
        if script.settle_pipes and not script.exit_without_pipes:
            events.pipe_lost(1, False)
            events.pipe_lost(2, False)
        gateway = self.gateway_handle
        if tag == "act-kill-1" and self.gateway_kill_exits_cli and gateway is not None:
            gateway._returncode = 137
            gateway.events.exited(137)
            if not self.gateway_exit_without_pipes:
                gateway.events.pipe_lost(0, False)
                gateway.events.pipe_lost(1, False)


class Harness:
    """Wires one FakePump, one PortOwnership, one real HostReactor, and one DuplexBridge."""

    def __init__(
        self,
        core_mod: types.ModuleType,
        *,
        pump: FakePump | None = None,
        observe_children: int = 20,
        limits_changes: dict[str, object] | None = None,
        plan: Any = None,
    ) -> None:
        self.m = ownership_module()
        self.b_ns = bridge_mod()
        self.r_ns = reactor_mod()
        self.pump = FakePump() if pump is None else pump
        self.limits = (
            self.m.OwnerLimits()
            if not limits_changes
            else self.m.OwnerLimits(**{**DEFAULT_LIMITS, **limits_changes})
        )
        self.plan = (
            make_plan(self.m, self.r_ns, observe_children=observe_children)
            if plan is None
            else plan
        )
        self.owner = self.m.PortOwnership(
            self.pump,
            self.plan,
            self.limits,
            bridge_ns=self.b_ns,
            reactor_ns=self.r_ns,
        )
        self.policy = ht.policy_for(self.r_ns)
        self.host = self.r_ns.HostReactor(core_mod, PACKET, self.policy)
        self.budget = self.b_ns.DuplexBudget(
            spawn_s=SPAWN_S, silence_s=SILENCE_S, drain_s=DRAIN_S, overall_s=OVERALL_S
        )
        self.bridge = self.b_ns.DuplexBridge(
            self.r_ns,
            self.host,
            self.owner.clock(),
            self.owner.gateway(),
            self.owner.acts(),
            self.budget,
        )

    def assert_pure_reads(self) -> None:
        """records(), first_control(), audit(), and custody() are pure reads (section 3)."""
        before = len(self.pump.trace)
        r1, r2 = self.owner.records(), self.owner.records()
        c1, c2 = self.owner.first_control(), self.owner.first_control()
        a1, a2 = self.owner.audit(), self.owner.audit()
        k1, k2 = self.owner.custody(), self.owner.custody()
        assert len(self.pump.trace) == before
        assert r1 == r2 and c1 is c2 and a1 == a2 and k1 == k2

    def records_of(self, kind_name: str) -> list[Any]:
        kind = getattr(self.m.InvocationKind, kind_name)
        return [record for record in self.owner.records() if record.kind is kind]

    def first_of(self, kind_name: str) -> Any:
        kind = getattr(self.m.InvocationKind, kind_name)
        return next(record for record in self.owner.records() if record.kind is kind)

    def record(self, record_id: int) -> Any:
        return next(r for r in self.owner.records() if r.record_id == record_id)

    def spawn_gateway(self) -> tuple[Any, FakeHandle]:
        """Spawn through the public port; the GUARD line arrives later via the pump."""
        slot = self.b_ns.OperationSlot("spawn")
        self.owner.gateway().begin_spawn_into(slot, self.pump.t + 5.0)
        self.owner.clock().poll((slot,), self.pump.t + 5.0)
        process = slot.op.outcome().process
        handle = self.pump.gateway_handle
        assert handle is not None
        return process, handle

    def make_act(self, kind_name: str, case: int, *, token: int = 1, window: float = 2.0) -> Any:
        return self.r_ns.Act(
            token=token,
            kind=getattr(self.r_ns.ActKind, kind_name),
            case=case,
            issued_at=self.pump.t,
            deadline=self.pump.t + window,
        )

    def run_act(self, act: Any) -> Any:
        slot = self.b_ns.OperationSlot("act")
        self.owner.acts().begin_act_into(slot, act, act.deadline)
        self.owner.clock().poll((slot,), act.deadline)
        return slot

    def run_both_audits(self) -> None:
        self.owner.begin_audit(self.m.AuditKind.GATEWAY_ABSENT, self.pump.t + 5.0)
        self.owner.settle(self.pump.t + 5.0)
        self.owner.begin_audit(self.m.AuditKind.BACKENDS_ZERO, self.pump.t + 5.0)
        self.owner.settle(self.pump.t + 5.0)

    def close_all_settled_processes(self) -> int:
        m = self.m
        settled = [
            r
            for r in self.owner.records()
            if r.kind in (m.InvocationKind.SPAWN, m.InvocationKind.CHILD)
            and r.physical is m.PhysicalState.SETTLED_RETAINED
        ]
        for record in settled:
            deadline = self.pump.t + 5.0
            self.owner.begin_dispose(m.DisposeKind.CLOSE_HANDLE, record.record_id, deadline)
            self.owner.settle(deadline)
        return len(settled)


# ---------------------------------------------------------------- sanity cases (no future module)


def test_sanity_real_reactor_and_bridge_namespaces(core: types.ModuleType) -> None:
    b_ns = bridge_mod()
    r_ns = reactor_mod()
    assert type(b_ns) is types.ModuleType and type(r_ns) is types.ModuleType
    b_vars = vars(b_ns)
    r_vars = vars(r_ns)
    for name in BRIDGE_REQUIRED_CLASSES:
        assert isinstance(b_vars.get(name), type)
    for name in REACTOR_REQUIRED_CLASSES:
        assert isinstance(r_vars.get(name), type)
    for enum_name, expected_members in REACTOR_REQUIRED_ENUMS.items():
        cls = r_vars.get(enum_name)
        assert isinstance(cls, type) and issubclass(cls, enum.Enum)
        assert {member.name for member in cls} == expected_members
    facts_ok = r_vars["_facts_ok"]
    ak = r_vars["ActKind"]
    st = r_vars["ActStatus"]
    assert facts_ok(ak.OBSERVE_HEAVY, st.OK, r_vars["ObserveFacts"](found=False, observations=20))
    assert facts_ok(ak.OBSERVE_HEAVY, st.OK, r_vars["ObserveFacts"](found=True, observations=1))
    assert not facts_ok(ak.ZERO_BACKENDS, st.FAILED, r_vars["ZeroFacts"](backends=1))
    assert facts_ok(ak.ZERO_BACKENDS, st.FAILED, None)
    host = r_vars["HostReactor"](core, PACKET, ht.policy_for(r_ns))
    assert host.status().phase is r_vars["HostPhase"].AWAIT_GUARD


def test_sanity_helper_json_lines_are_canonical_and_bounded() -> None:
    samples = [
        terminate_line(),
        pause_line(paused=True, running=True),
        pause_line(paused=False, running=True),
        restore_ready_line(ready=True),
        observe_line(active=False),
        observe_line(active=True),
        zero_line(backends=0),
        kill_line(oom=False, pid=0, running=False),
        names_line([PG_NAME]),
        names_line([]),
        observer_control_line(),
    ]
    for raw in samples:
        assert type(raw) is bytes and 0 < len(raw) <= 512
        assert raw.endswith(b"\n") and raw.count(b"\n") == 1 and raw.isascii()
        parsed = json.loads(raw[:-1].decode("ascii"))
        assert parsed["scope"] == SCOPE_ID
        assert d1.canonical(parsed) + b"\n" == raw


class DummyEvents:
    """ProcessEvents stand-in for the pump sanity case (no owner module)."""

    def __init__(self, seen: list[str]) -> None:
        self.seen = seen

    def started(self, handle: FakeHandle) -> None:
        assert handle.write_limits() == (0, 0)
        self.seen.append("started")

    def start_failed(self) -> None:
        self.seen.append("start_failed")

    def not_started(self) -> None:
        self.seen.append("not_started")

    def data(self, fd: int, chunk: bytes) -> None:
        self.seen.append(f"data:{fd}:{len(chunk)}")

    def pipe_lost(self, fd: int, failed: bool) -> None:
        self.seen.append(f"pipe_lost:{fd}:{failed}")

    def exited(self, code: object) -> None:
        self.seen.append(f"exited:{code}")

    def write_resumed(self) -> None:
        self.seen.append("write_resumed")

    def closed(self) -> None:
        self.seen.append("closed")


def test_sanity_fake_pump_and_dyadic_timeline_without_owner() -> None:
    pump = FakePump()
    events_seen: list[str] = []
    req = SimpleNamespace(
        record_id=1,
        argv=("helper", "act-term-0", f"--scope={SCOPE_ID}"),
        stdin_pipe=False,
        not_before=T0 + DT,
        authorize=lambda: True,
        events=DummyEvents(events_seen),
    )
    pump.schedule_start(req)
    assert events_seen == []  # schedule_start never runs an effect synchronously
    end = pump.run_until(T0 + 4 * DT, lambda: "pipe_lost:2:False" in events_seen)
    assert end == T0 + 2 * DT
    assert events_seen == [
        "started",
        f"data:1:{len(terminate_line())}",
        "exited:0",
        "pipe_lost:1:False",
        "pipe_lost:2:False",
    ]
    # Events scheduled by a test are also delivered only inside run_until.
    pump.schedule_at(pump.t + DT, lambda: events_seen.append("late"))
    assert events_seen[-1] != "late"
    pump.run_until(pump.t + 2 * DT, lambda: False)
    assert events_seen[-1] == "late"
    assert events_seen in walk_model_state(pump)
    with pytest.raises(AssertionError, match="max_depth"):
        walk_model_state(pump, max_depth=1)


def test_sanity_exact_module_getattr_hook_is_live_for_missing_names() -> None:
    calls: list[str] = []
    module = exact_getattr_module(bridge_mod(), "SpawnOutcome", calls)
    assert type(module) is types.ModuleType  # exact type, not a subclass
    assert "SpawnOutcome" not in vars(module)
    assert vars(module).get("SpawnOutcome") is None and calls == []
    missing = "SpawnOutcome"
    with pytest.raises(AssertionError):
        getattr(module, missing)  # attribute lookup DOES reach the module-level hook
    assert calls == ["SpawnOutcome"]


# ---------------------------------------------------------------- types, DTOs, namespaces, limits


@pytest.mark.parametrize("name", sorted(OWNERSHIP_ENUMS))
def test_types_enums_are_closed(name: str) -> None:
    m = ownership_module()
    cls = getattr(m, name)
    assert isinstance(cls, type) and issubclass(cls, enum.Enum)
    assert {member.name for member in cls} == OWNERSHIP_ENUMS[name]


@pytest.mark.parametrize("name", sorted(OWNERSHIP_DTOS))
def test_types_dtos_are_frozen_slotted_with_exact_fields(name: str) -> None:
    m = ownership_module()
    cls = getattr(m, name)
    assert isinstance(cls, type) and dataclasses.is_dataclass(cls)
    namespace: dict[str, Any] = dict(vars(cls))
    assert tuple(field.name for field in dataclasses.fields(cls)) == OWNERSHIP_DTOS[name]
    assert namespace["__dataclass_params__"].frozen is True
    assert "__slots__" in namespace


VALID_DTO_FACTORIES: dict[str, Callable[[Any], Any]] = {
    "Scope": make_scope,
    "HelperPlan": lambda m: make_helper(m, "repr-probe"),
    "CliPlan": lambda m: make_plan(m, reactor_mod()),
    "OwnerLimits": lambda m: m.OwnerLimits(),
}


@pytest.mark.parametrize("name", sorted(OWNERSHIP_DTOS))
def test_types_dto_repr_is_constant_and_never_inspects_fields(name: str) -> None:
    """Repr proof is separate from typed validation: the instance is never constructed.

    ``object.__new__`` gives an UNINITIALIZED instance used only to show that repr/str
    are constant and never touch field values; typed constructors are not asked to
    accept foreign values.
    """
    m = ownership_module()
    cls = getattr(m, name)
    blank: Any = object.__new__(cls)
    blank_text = repr(blank)
    assert isinstance(blank_text, str) and isinstance(str(blank), str)
    touched: list[str] = []
    probe: Any = object.__new__(cls)
    for field in OWNERSHIP_DTOS[name]:
        object.__setattr__(probe, field, bt.Trap(touched))
    assert repr(probe) == blank_text and str(probe) == str(blank)
    assert touched == []
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(probe, OWNERSHIP_DTOS[name][0], None)
    factory = VALID_DTO_FACTORIES.get(name)
    if factory is not None:
        valid = factory(m)
        assert repr(valid) == blank_text  # constant redacted repr for real values too
        assert all(secret not in repr(valid) + str(valid) for secret in SECRET_TEXTS)


def test_types_ownership_refusal_is_closed_exception() -> None:
    m = ownership_module()
    for fault in m.OwnershipFault:
        err = m.OwnershipRefusal(fault)
        assert issubclass(type(err), Exception)
        assert_refusal(m, err, fault.name)


NAMESPACE_CASES = (
    "bridge-not-module",
    "reactor-not-module",
    "bridge-module-subclass",
    "reactor-module-subclass",
    "bridge-hostile-subclass-missing-SpawnOutcome",
    "reactor-hostile-subclass-missing-Act",
    "swapped-namespaces",
    "bridge-missing-OperationSlot",
    "bridge-SpawnOutcome-not-type",
    "reactor-missing-Act",
    "reactor-ZeroFacts-not-type",
    "reactor-Delivery-not-enum",
    "reactor-ActKind-missing-member",
    "reactor-ActKind-extra-member",
    "reactor-ActStatus-extra-member",
    "reactor-ExitStatus-missing-member",
    "bridge-exact-module-getattr-missing-SpawnOutcome",
    "reactor-exact-module-getattr-missing-Act",
)


def mutated_namespaces(case: str, calls: list[str]) -> tuple[Any, Any]:
    b_ns, r_ns = bridge_mod(), reactor_mod()
    builders: dict[str, Callable[[], tuple[Any, Any]]] = {
        "bridge-not-module": lambda: (SimpleNamespace(**vars(b_ns)), r_ns),
        "reactor-not-module": lambda: (b_ns, SimpleNamespace(**vars(r_ns))),
        "bridge-module-subclass": lambda: (sub_module(b_ns), r_ns),
        "reactor-module-subclass": lambda: (b_ns, sub_module(r_ns)),
        "bridge-hostile-subclass-missing-SpawnOutcome": lambda: (
            hostile_sub_module(b_ns, "SpawnOutcome", calls),
            r_ns,
        ),
        "reactor-hostile-subclass-missing-Act": lambda: (
            b_ns,
            hostile_sub_module(r_ns, "Act", calls),
        ),
        "swapped-namespaces": lambda: (r_ns, b_ns),
        "bridge-missing-OperationSlot": lambda: (bridge_variant(OperationSlot=ht.DROP), r_ns),
        "bridge-SpawnOutcome-not-type": lambda: (bridge_variant(SpawnOutcome=123), r_ns),
        "reactor-missing-Act": lambda: (b_ns, reactor_variant(Act=ht.DROP)),
        "reactor-ZeroFacts-not-type": lambda: (b_ns, reactor_variant(ZeroFacts="not-a-type")),
        "reactor-Delivery-not-enum": lambda: (
            b_ns,
            reactor_variant(Delivery=type("FakeDelivery", (), {})),
        ),
        "reactor-ActKind-missing-member": lambda: (
            b_ns,
            reactor_variant(ActKind=enum.Enum("ActKind", ["TERMINATE_ONE_BACKEND", "PAUSE_PG"])),
        ),
        "reactor-ActKind-extra-member": lambda: (
            b_ns,
            reactor_variant(
                ActKind=enum.Enum("ActKind", [*sorted(ht.ENUMS["ActKind"]), "EXTRA_KIND"])
            ),
        ),
        "reactor-ActStatus-extra-member": lambda: (
            b_ns,
            reactor_variant(
                ActStatus=enum.Enum("ActStatus", ["OK", "FAILED", "UNKNOWN", "PARTIAL"])
            ),
        ),
        "reactor-ExitStatus-missing-member": lambda: (
            b_ns,
            reactor_variant(ExitStatus=enum.Enum("ExitStatus", ["EXITED", "UNKNOWN"])),
        ),
        "bridge-exact-module-getattr-missing-SpawnOutcome": lambda: (
            exact_getattr_module(b_ns, "SpawnOutcome", calls),
            r_ns,
        ),
        "reactor-exact-module-getattr-missing-Act": lambda: (
            b_ns,
            exact_getattr_module(r_ns, "Act", calls),
        ),
    }
    return builders[case]()


@pytest.mark.parametrize("case", NAMESPACE_CASES)
def test_a_ns_namespace_validation_uses_vars_without_module_getattr(case: str) -> None:
    m = ownership_module()
    pump = FakePump()
    plan = make_plan(m, reactor_mod())
    limits = m.OwnerLimits()
    getattr_calls: list[str] = []
    b_ns, r_ns = mutated_namespaces(case, getattr_calls)
    if "exact-module-getattr" in case:
        assert type(b_ns) is types.ModuleType and type(r_ns) is types.ModuleType
    with pytest.raises(m.OwnershipRefusal) as caught:
        m.PortOwnership(pump, plan, limits, bridge_ns=b_ns, reactor_ns=r_ns)
    assert_refusal(m, caught.value, "NAMESPACE")
    assert getattr_calls == []  # neither the exact-module hook nor a subclass hook ran
    assert pump.trace == []


BAD_LIMITS: list[tuple[str, object]] = [
    ("max_records", 0),
    ("max_records", 513),
    ("max_records", True),
    ("max_records", 512.0),
    ("max_records", ht.IntSub(10)),
    ("max_children", 0),
    ("max_children", 25),
    ("max_children", False),
    ("max_writes", 0),
    ("max_writes", 52),
    ("max_acts", 0),
    ("max_acts", 8),
    ("max_audits", 0),
    ("max_audits", 9),
    ("max_disposals", 0),
    ("max_disposals", 65),
    ("gateway_stdout_cap", 0),
    ("gateway_stdout_cap", 28674),
    ("child_stdout_cap", 0),
    ("child_stdout_cap", 4097),
    ("max_late", 0),
    ("max_late", 17),
    ("max_retained_takes", 1),
    ("max_retained_takes", 3),
    ("max_retained_takes", "2"),
]


@pytest.mark.parametrize(
    ("field", "bad_value"),
    BAD_LIMITS,
    ids=[f"{field}-{idx}" for idx, (field, _) in enumerate(BAD_LIMITS)],
)
def test_a_limits_owner_limits_defaults_and_domain_validation(
    field: str, bad_value: object
) -> None:
    m = ownership_module()
    defaults = m.OwnerLimits()
    for key, val in DEFAULT_LIMITS.items():
        assert getattr(defaults, key) == val and type(getattr(defaults, key)) is int
    assert "<" in repr(defaults)  # redacted constant repr

    pump = FakePump()
    b_ns, r_ns = bridge_mod(), reactor_mod()
    plan = make_plan(m, r_ns, observe_children=1)
    kwargs: dict[str, object] = {**DEFAULT_LIMITS, field: bad_value}
    with pytest.raises(m.OwnershipRefusal) as caught:
        limits = m.OwnerLimits(**kwargs)  # the DTO may refuse first: also accepted
        m.PortOwnership(pump, plan, limits, bridge_ns=b_ns, reactor_ns=r_ns)
    assert_refusal(m, caught.value, "PLAN")
    assert pump.trace == []


PLAN_REFUSAL_CASES = (
    "same-gateway-and-pg-name",
    "same-observer-and-target-role",
    "empty-scope-label",
    "uppercase-scope-id",
    "empty-scope-id",
    "overlong-scope-id",
    "gateway-argv-missing-scope-id",
    "helper-argv-missing-scope-id",
    "missing-act-kind",
    "duplicate-act-kind",
    "terminate-two-children",
    "observe-zero-children",
    "observe-21-children",
    "observe-exceeds-max-children",
    "missing-audit-kind",
    "remove-gateway-one-child",
)


def scope_plan(m: Any, r_ns: types.ModuleType, **scope_changes: object) -> Any:
    return make_plan(m, r_ns, scope=make_scope(m, **scope_changes))


def invalid_plan_and_limits(m: Any, r_ns: types.ModuleType, case: str) -> tuple[Any, Any]:
    """Builds the invalid input; MUST be called inside pytest.raises (early DTO refusal ok)."""
    ak: Any = vars(r_ns)["ActKind"]
    base = make_plan(m, r_ns)
    limits = m.OwnerLimits()
    two_term = (ak.TERMINATE_ONE_BACKEND, (make_helper(m, "t0"), make_helper(m, "t1")))
    builders: dict[str, Callable[[], tuple[Any, Any]]] = {
        "same-gateway-and-pg-name": lambda: (scope_plan(m, r_ns, pg_name=GATEWAY_NAME), limits),
        "same-observer-and-target-role": lambda: (
            scope_plan(m, r_ns, observer_role=TARGET_ROLE),
            limits,
        ),
        "empty-scope-label": lambda: (scope_plan(m, r_ns, scope_label=""), limits),
        "uppercase-scope-id": lambda: (scope_plan(m, r_ns, scope_id="Scope-W1"), limits),
        "empty-scope-id": lambda: (scope_plan(m, r_ns, scope_id=""), limits),
        "overlong-scope-id": lambda: (scope_plan(m, r_ns, scope_id="a" * 65), limits),
        "gateway-argv-missing-scope-id": lambda: (
            make_plan(m, r_ns, gateway_argv=("gateway-cli", "--no-scope")),
            limits,
        ),
        "helper-argv-missing-scope-id": lambda: (
            make_plan(
                m,
                r_ns,
                remove_gateway=(
                    m.HelperPlan(argv=("rm", "--no-scope")),
                    make_helper(m, "dispose-rm-1"),
                ),
            ),
            limits,
        ),
        "missing-act-kind": lambda: (make_plan(m, r_ns, acts=base.acts[:-1]), limits),
        "duplicate-act-kind": lambda: (
            make_plan(m, r_ns, acts=(*base.acts[:-1], base.acts[0])),
            limits,
        ),
        "terminate-two-children": lambda: (
            make_plan(m, r_ns, acts=(two_term, *base.acts[1:])),
            limits,
        ),
        "observe-zero-children": lambda: (make_plan(m, r_ns, observe_children=0), limits),
        "observe-21-children": lambda: (make_plan(m, r_ns, observe_children=21), limits),
        "observe-exceeds-max-children": lambda: (
            make_plan(m, r_ns, observe_children=6),
            m.OwnerLimits(**{**DEFAULT_LIMITS, "max_children": 5}),
        ),
        "missing-audit-kind": lambda: (make_plan(m, r_ns, audits=base.audits[:1]), limits),
        "remove-gateway-one-child": lambda: (
            make_plan(m, r_ns, remove_gateway=(make_helper(m, "dispose-rm-0"),)),
            limits,
        ),
    }
    return builders[case]()


@pytest.mark.parametrize("case", PLAN_REFUSAL_CASES)
def test_plan_validation_scope_coherence_and_argv_rules(case: str) -> None:
    m = ownership_module()
    pump = FakePump()
    b_ns, r_ns = bridge_mod(), reactor_mod()
    with pytest.raises(m.OwnershipRefusal) as caught:
        plan, limits = invalid_plan_and_limits(m, r_ns, case)
        m.PortOwnership(pump, plan, limits, bridge_ns=b_ns, reactor_ns=r_ns)
    assert_refusal(m, caught.value, "PLAN")
    assert pump.trace == []


# ---------------------------------------------------------------- P1 full COMPLETE_CANDIDATE path


def assert_p1_work_records(h: Harness) -> None:
    m = h.m
    writes = h.records_of("WRITE")
    acts = h.records_of("ACT")
    spawns = h.records_of("SPAWN")
    assert len(spawns) == 1 and len(h.records_of("WAIT")) == 1
    assert len(writes) == 51 and all(
        w.protocol is m.ProtocolState.SUCCEEDED and w.handoff_zero is True for w in writes
    )
    assert len(acts) == 7 and all(a.protocol is m.ProtocolState.SUCCEEDED for a in acts)
    assert spawns[0].physical is m.PhysicalState.SETTLED_RETAINED


def assert_absence_pair(m: Any, report: Any) -> None:
    assert report.gateway is not None and report.backends is not None
    for result in (report.gateway, report.backends):
        assert result.verdict is m.AbsenceVerdict.ABSENT_OBSERVED
        assert result.reason is m.DecodeReason.OK
        assert result.helpers_settled is True
    assert report.quiet_scoped is True


def test_p1_full_complete_candidate_audits_and_close_handle_disposals(
    core: types.ModuleType,
) -> None:
    h = Harness(core, observe_children=20)
    m, owner, pump = h.m, h.owner, h.pump
    result = h.bridge.run()
    h.assert_pure_reads()

    assert result.done.outcome.name == "COMPLETE_CANDIDATE"
    assert ht.names(result.done.verdicts) == ["PASS"] * 25
    assert (result.status.phase.name, result.status.retained) == ("DONE", False)
    assert owner.first_control() is None
    assert_p1_work_records(h)

    fence = owner.seal()
    assert owner.seal() == fence  # seal() is idempotent
    assert fence.open_ids == () and fence.unknown_ids == ()
    assert fence.work_settled_at is not None

    # All work records are already SETTLED_RETAINED, so settle() stops early without advancing
    before_settle = pump.t
    assert owner.settle(before_settle + 10.0) == before_settle

    # Advance past work_settled_at to run the two positive-control scoped audits
    pump.advance(DT)
    gw_audit_id = owner.begin_audit(m.AuditKind.GATEWAY_ABSENT, pump.t + 5.0)
    owner.settle(pump.t + 5.0)
    bg_audit_id = owner.begin_audit(m.AuditKind.BACKENDS_ZERO, pump.t + 5.0)
    owner.settle(pump.t + 5.0)
    assert gw_audit_id != bg_audit_id

    report_before = owner.audit()
    custody_before = owner.custody()
    assert report_before.fence == fence
    assert report_before.epoch == 0 and report_before.control_history is False
    assert_absence_pair(m, report_before)
    assert len(custody_before.entries) > 0

    # Dispose every SETTLED_RETAINED process handle (SPAWN, ACT children, and AUDIT children)
    assert h.close_all_settled_processes() >= 15

    # V4 precision 2: CLOSE_HANDLE keeps epoch unchanged, audit helpers stay settled,
    # quiet_scoped stays True, and custody decreases to empty.
    report_after = owner.audit()
    assert report_after.epoch == 0
    assert report_after.gateway == report_before.gateway
    assert report_after.backends == report_before.backends
    assert_absence_pair(m, report_after)
    assert report_after.control_history is False
    custody_after = owner.custody()
    assert len(custody_after.entries) < len(custody_before.entries)
    assert custody_after.entries == ()
    assert all(
        r.physical is m.PhysicalState.RELEASED_LOCAL and r.retained == ()
        for r in [*h.records_of("SPAWN"), *h.records_of("CHILD")]
    )
    assert len(owner.records()) <= P1_CONSERVATIVE_BOUND <= MAX_RECORDS_DEFAULT
    h.assert_pure_reads()


def test_p1_observe_with_20_children_succeeds_under_max_children_24(
    core: types.ModuleType,
) -> None:
    pump = FakePump()
    pump.default_observe_true_at = 19  # spawns all 20 OBSERVE_HEAVY children (0..19)
    h = Harness(core, pump=pump, observe_children=20)
    result = h.bridge.run()
    assert result.done.outcome.name == "COMPLETE_CANDIDATE"
    observe_act = next(r for r in h.records_of("ACT") if r.act_kind.name == "OBSERVE_HEAVY")
    observe_children = [r for r in h.records_of("CHILD") if r.parent == observe_act.record_id]
    assert len(observe_children) == 20
    assert len(h.records_of("CHILD")) == 30 > h.limits.max_children  # per-invocation limit


# ---------------------------------------------------------------- P2 & section 5.3 writes


def test_p2_write_sent_immediate_and_via_write_resumed(core: types.ModuleType) -> None:
    h = Harness(core)
    m, owner, pump, b_ns, r_ns = h.m, h.owner, h.pump, h.b_ns, h.r_ns
    proc, gw_handle = h.spawn_gateway()
    pump.gateway_auto_respond = False

    # 1. Immediate SENT (buffer_size() == 0 synchronously after write)
    w_slot1 = b_ns.OperationSlot("write")
    frame1 = d1.frame(GO, 1, 1)
    proc.begin_write_into(w_slot1, frame1, pump.t + 5.0)
    assert w_slot1.op.done() is True
    out1 = w_slot1.op.outcome()
    assert out1 == b_ns.WriteOutcome(delivery=r_ns.Delivery.SENT, bytes_written=len(frame1))

    # 2. Deferred SENT via write_resumed(), delivered only inside run_until
    gw_handle.retain_buffer_on_write = True
    gw_handle.defer_write_resume_dt = 2 * DT
    w_slot2 = b_ns.OperationSlot("write")
    frame2 = d1.frame(ACK, 1, 2)
    proc.begin_write_into(w_slot2, frame2, pump.t + 5.0)
    assert w_slot2.op.done() is False
    owner.clock().poll((w_slot2,), pump.t + 5.0)
    assert w_slot2.op.done() is True
    out2 = w_slot2.op.outcome()
    assert out2 == b_ns.WriteOutcome(delivery=r_ns.Delivery.SENT, bytes_written=len(frame2))

    write_recs = h.records_of("WRITE")
    assert len(write_recs) == 2
    assert all(
        r.protocol is m.ProtocolState.SUCCEEDED
        and r.handoff_zero is True
        and r.payload_len == 16
        and r.uncertain is False
        for r in write_recs
    )


def test_p2_write_after_spawn_startup_deadline_succeeds_on_live_gateway(
    core: types.ModuleType,
) -> None:
    """Startup deadline governs SPAWN only, not the live session lifetime of later WRITEs."""
    h = Harness(core)
    m, pump, b_ns, r_ns = h.m, h.pump, h.b_ns, h.r_ns
    proc, gw_handle = h.spawn_gateway()
    pump.gateway_auto_respond = False
    spawn_rec = h.first_of("SPAWN")
    assert spawn_rec.protocol is m.ProtocolState.SUCCEEDED
    assert spawn_rec.physical is m.PhysicalState.OPEN
    assert gw_handle.returncode() is None

    # Advance fake clock past the completed SPAWN startup deadline without resetting time
    pump.advance(SPAWN_S + 10.0)
    assert pump.t > spawn_rec.deadline

    w_slot = b_ns.OperationSlot("write")
    frame = d1.frame(GO, 1, 1)
    write_deadline = pump.t + 5.0
    proc.begin_write_into(w_slot, frame, write_deadline)
    assert w_slot.op.done() is True
    assert w_slot.op.outcome() == b_ns.WriteOutcome(
        delivery=r_ns.Delivery.SENT, bytes_written=len(frame)
    )
    assert len(h.records_of("SPAWN")) == 1  # SPAWN is never reopened
    assert h.first_of("SPAWN").deadline == spawn_rec.deadline
    write_rec = h.first_of("WRITE")
    assert write_rec.parent == spawn_rec.record_id
    assert write_rec.armed_at > spawn_rec.deadline
    assert write_rec.deadline == write_deadline
    assert write_rec.protocol is m.ProtocolState.SUCCEEDED


def prepare_write_failure(h: Harness, proc: Any, gw_handle: FakeHandle, mode: str) -> None:
    pump, b_ns, r_ns = h.pump, h.b_ns, h.r_ns
    if mode == "closing":
        gw_handle._closing = True
    elif mode == "pipe_lost_0":
        wait_slot = b_ns.OperationSlot("wait")
        proc.begin_wait_into(wait_slot, pump.t + 5.0)
        pump.schedule_at(pump.t + DT, lambda: gw_handle.events.pipe_lost(0, True))
        h.owner.clock().poll((wait_slot,), pump.t + 2 * DT)
    elif mode == "prior_write_fault":
        gw_handle.write_raises = OSError("disk full")
        first_slot = b_ns.OperationSlot("write")
        proc.begin_write_into(first_slot, d1.frame(GO, 1, 1), pump.t + 5.0)
        assert first_slot.op.outcome().delivery is r_ns.Delivery.UNKNOWN
        gw_handle.writes.clear()


@pytest.mark.parametrize(
    "failure_mode",
    ["closing", "pipe_lost_0", "prior_write_fault", "expired_deadline"],
)
def test_write_precondition_and_authorize_refusal_are_not_sent_without_write_call(
    core: types.ModuleType, failure_mode: str
) -> None:
    h = Harness(core)
    m, pump, b_ns, r_ns = h.m, h.pump, h.b_ns, h.r_ns
    proc, gw_handle = h.spawn_gateway()
    pump.gateway_auto_respond = False
    prepare_write_failure(h, proc, gw_handle, failure_mode)

    writes_before = len(gw_handle.writes)
    slot = b_ns.OperationSlot("write")
    deadline = pump.t - DT if failure_mode == "expired_deadline" else pump.t + 5.0
    proc.begin_write_into(slot, d1.frame(GO, 2, 3), deadline)
    assert len(gw_handle.writes) == writes_before  # h.write is NEVER called
    assert slot.op.done() is True
    out = slot.op.outcome()
    assert out == b_ns.WriteOutcome(delivery=r_ns.Delivery.NOT_SENT, bytes_written=0)
    rec = h.records_of("WRITE")[-1]
    expected_proto = (
        m.ProtocolState.NOT_STARTED
        if failure_mode == "expired_deadline"
        else m.ProtocolState.FAILED_KNOWN
    )
    assert rec.protocol is expected_proto and rec.uncertain is False


@pytest.mark.parametrize("fault_kind", ["write_exception", "closing_after_write"])
def test_write_exception_or_synchronous_closing_is_unknown_zero(
    core: types.ModuleType, fault_kind: str
) -> None:
    h = Harness(core)
    m, pump, b_ns, r_ns = h.m, h.pump, h.b_ns, h.r_ns
    proc, gw_handle = h.spawn_gateway()
    pump.gateway_auto_respond = False

    if fault_kind == "write_exception":
        gw_handle.write_raises = OSError("broken pipe")
    else:
        gw_handle.close_after_write = True

    slot = b_ns.OperationSlot("write")
    payload = d1.frame(GO, 1, 1)
    proc.begin_write_into(slot, payload, pump.t + 5.0)
    assert slot.op.done() is True
    out = slot.op.outcome()
    assert out == b_ns.WriteOutcome(delivery=r_ns.Delivery.UNKNOWN, bytes_written=0)
    rec = h.records_of("WRITE")[-1]
    assert rec.protocol is m.ProtocolState.UNKNOWN
    assert rec.payload_len == len(payload)
    assert rec.uncertain is True
    assert m.FaultKind.WRITE in rec.faults


def test_write_peer_never_reads_expires_unknown_and_late_handoff_zero_resolves_uncertain(
    core: types.ModuleType,
) -> None:
    h = Harness(core)
    m, owner, pump, b_ns = h.m, h.owner, h.pump, h.b_ns
    proc, gw_handle = h.spawn_gateway()
    pump.gateway_auto_respond = False
    gw_handle.retain_buffer_on_write = True
    gw_handle.defer_write_resume_dt = None  # peer never drains before deadline

    w_slot = b_ns.OperationSlot("write")
    deadline = pump.t + 1.0
    proc.begin_write_into(w_slot, PACKET, deadline)
    owner.clock().poll((w_slot,), deadline)
    rec_expired = h.first_of("WRITE")
    assert rec_expired.protocol is m.ProtocolState.UNKNOWN
    assert rec_expired.uncertain is True
    assert rec_expired.handoff_zero is False

    owner.seal()

    def late_drain() -> None:  # one drain, one exit, one loss per pipe, inside settle()
        gw_handle._buffer_size = 0
        gw_handle.events.write_resumed()
        gw_handle.settle_exit(0)

    pump.schedule_at(pump.t + 2 * DT, late_drain)
    owner.settle(pump.t + 5.0)

    rec_after = h.first_of("WRITE")
    assert rec_after.protocol is m.ProtocolState.UNKNOWN  # protocol outcome stays immutable
    assert rec_after.uncertain is False  # resolved by physical late handoff_zero
    assert any(lf.kind is m.LateKind.HANDOFF_ZERO for lf in rec_after.late)


# ---------------------------------------------------------------- P3 & section 5.2 takes, buffers


@pytest.mark.parametrize("eof_failed", [False, True], ids=["clean-eof", "pipe-error"])
def test_p3_read_takes_are_immutable_fifo_before_eof_and_error(
    core: types.ModuleType, eof_failed: bool
) -> None:
    pump = FakePump()
    pump.gateway_emit_guard = False
    h = Harness(core, pump=pump)
    m, owner, b_ns = h.m, h.owner, h.b_ns
    proc, gw_handle = h.spawn_gateway()

    def data_then_loss() -> None:
        gw_handle.events.data(1, b"ABCDEF")
        gw_handle.events.pipe_lost(1, eof_failed)

    # Take 1 is pending; data then the pipe loss arrive in ONE pump step.
    s1 = b_ns.OperationSlot("read")
    proc.begin_read_into(s1, 4, pump.t + 5.0)
    pump.schedule_at(pump.t + DT, data_then_loss)
    owner.clock().poll((s1,), pump.t + 5.0)
    op1 = s1.op
    assert isinstance(op1, m.ReadTake) and op1.size == 4
    assert op1.done() is True
    out1 = op1.outcome()
    assert out1 == b_ns.ReadOutcome(ok=True, data=b"ABCD")  # data precedes the pipe loss
    assert op1.outcome() is out1  # outcome frozen once

    # Take 2: consumes remaining 2 resident bytes
    s2 = b_ns.OperationSlot("read")
    proc.begin_read_into(s2, 4, pump.t + 5.0)
    op2 = s2.op
    assert op2.take_id != op1.take_id
    assert op2.done() is True
    assert op2.outcome() == b_ns.ReadOutcome(ok=True, data=b"EF")
    assert op1.outcome() == b_ns.ReadOutcome(ok=True, data=b"ABCD")  # earlier take untouched

    # Take 3: resident == 0 now surfaces EOF (True, b"") or error (False, b"")
    s3 = b_ns.OperationSlot("read")
    proc.begin_read_into(s3, 4, pump.t + 5.0)
    op3 = s3.op
    assert op3.done() is True
    assert op3.outcome() == b_ns.ReadOutcome(ok=not eof_failed, data=b"")

    spawn_rec = h.first_of("SPAWN")
    assert spawn_rec.protocol is m.ProtocolState.SUCCEEDED
    assert (spawn_rec.received_total, spawn_rec.accepted_total, spawn_rec.resident) == (6, 6, 0)


def counters(record: Any) -> tuple[int, int, int, int]:
    return (record.received_total, record.accepted_total, record.resident, record.dropped_total)


def test_stdout_prefix_cut_before_copy_room_arithmetic_and_pause_reading(
    core: types.ModuleType,
) -> None:
    pump = FakePump()
    pump.gateway_emit_guard = False
    h = Harness(core, pump=pump, limits_changes={"gateway_stdout_cap": 100})
    owner, b_ns = h.owner, h.b_ns
    proc, gw_handle = h.spawn_gateway()
    wait_slot = b_ns.OperationSlot("wait")
    proc.begin_wait_into(wait_slot, pump.t + 10.0)

    # 77-byte chunk with room 100 -> take 77, dropped 0 (never negative)
    pump.schedule_at(pump.t + DT, lambda: gw_handle.events.data(1, b"a" * 77))
    owner.clock().poll((wait_slot,), pump.t + 2 * DT)
    assert counters(h.first_of("SPAWN")) == (77, 77, 77, 0)
    assert 1 not in gw_handle.paused_fds

    # Drain 50 bytes via ReadTake -> resident 27, accepted_total stays 77, room stays 23
    r_slot = b_ns.OperationSlot("read")
    proc.begin_read_into(r_slot, 50, pump.t + 5.0)
    assert r_slot.op.outcome() == b_ns.ReadOutcome(ok=True, data=b"a" * 50)

    # Next chunk of 40 bytes with room 23 -> take 23, dropped 17, pause_reading(1) called
    pump.schedule_at(pump.t + DT, lambda: gw_handle.events.data(1, b"b" * 23 + b"Z" * 17))
    owner.clock().poll((wait_slot,), pump.t + 2 * DT)
    assert counters(h.first_of("SPAWN")) == (117, 100, 50, 17)
    assert 1 in gw_handle.paused_fds

    # Saturated: a later chunk is counted and dropped, never stored
    pump.schedule_at(pump.t + DT, lambda: gw_handle.events.data(1, b"Q" * 9))
    owner.clock().poll((wait_slot,), pump.t + 2 * DT)
    assert counters(h.first_of("SPAWN")) == (126, 100, 50, 26)

    r_slot2 = b_ns.OperationSlot("read")
    proc.begin_read_into(r_slot2, 100, pump.t + 5.0)
    assert r_slot2.op.outcome() == b_ns.ReadOutcome(ok=True, data=b"a" * 27 + b"b" * 23)


def test_child_stderr_is_count_only_and_never_retained(core: types.ModuleType) -> None:
    pump = FakePump()
    stderr_payload = (STDERR_CANARY.encode("ascii") + b"\n") * 200
    pump.push_child_script(
        "act-term-0",
        ChildScript(stdout_chunks=[terminate_line()], stderr_chunks=[stderr_payload]),
    )
    h = Harness(core, pump=pump)
    m, b_ns, r_ns = h.m, h.b_ns, h.r_ns
    slot = h.run_act(h.make_act("TERMINATE_ONE_BACKEND", 20))
    assert slot.op.outcome() == b_ns.ActOutcome(
        status=r_ns.ActStatus.OK,
        facts=r_ns.TerminateFacts(found=1, terminated=True),
    )
    child_rec = h.first_of("CHILD")
    assert child_rec.stderr_bytes == len(stderr_payload)
    assert child_rec.accepted_total == len(terminate_line())
    assert child_rec.resident == 0
    assert m.Retained.BUFFER not in child_rec.retained
    for obj in walk_model_state(h.owner):
        if isinstance(obj, (bytes, bytearray)):
            assert STDERR_CANARY.encode("ascii") not in obj
        elif isinstance(obj, str):
            assert STDERR_CANARY not in obj


# ---------------------------------------------------------------- P4 distinct records, helpers


def test_p4_zero24_kill25_and_zero25_have_distinct_immutable_records(
    core: types.ModuleType,
) -> None:
    h = Harness(core)
    result = h.bridge.run()
    assert result.done.outcome.name == "COMPLETE_CANDIDATE"

    acts = h.records_of("ACT")
    zero24 = [r for r in acts if r.act_kind.name == "ZERO_BACKENDS" and r.case == 24]
    kill25 = [r for r in acts if r.act_kind.name == "KILL_GATEWAY" and r.case == 25]
    zero25 = [r for r in acts if r.act_kind.name == "ZERO_BACKENDS" and r.case == 25]
    assert len(zero24) == 1 and len(kill25) == 1 and len(zero25) == 1
    ids = {zero24[0].record_id, kill25[0].record_id, zero25[0].record_id}
    tokens = {zero24[0].token, kill25[0].token, zero25[0].token}
    assert len(ids) == 3 and len(tokens) == 3
    assert zero24[0].reserved_at < kill25[0].reserved_at < zero25[0].reserved_at


def test_gateway_exit_never_settles_live_action_child(core: types.ModuleType) -> None:
    pump = FakePump()
    pump.push_child_script("act-term-0", ChildScript(start_mode="never_settle"))
    h = Harness(core, pump=pump)
    m, owner, b_ns = h.m, h.owner, h.b_ns
    _, gw = h.spawn_gateway()

    act = h.make_act("TERMINATE_ONE_BACKEND", 20)
    act_slot = b_ns.OperationSlot("act")
    owner.acts().begin_act_into(act_slot, act, act.deadline)
    # Kill/reap of the gateway CLI is delivered inside run_until while the ACT child lives
    pump.schedule_at(pump.t + 2 * DT, lambda: gw.settle_exit(137))
    owner.clock().poll((act_slot,), act.deadline)

    assert h.first_of("SPAWN").physical is m.PhysicalState.SETTLED_RETAINED
    child_rec = h.first_of("CHILD")
    assert child_rec.physical is m.PhysicalState.OPEN
    assert child_rec.retained != ()


# ---------------------------------------------------------------- P5 all six action decoders


def run_single_act(
    core_mod: types.ModuleType,
    kind_name: str,
    case: int,
    scripts: dict[str, list[ChildScript]],
) -> tuple[Any, Any, Harness]:
    pump = FakePump()
    for tag, tag_scripts in scripts.items():
        pump.push_child_script(tag, *tag_scripts)
    h = Harness(core_mod, pump=pump)
    act = h.make_act(kind_name, case, token=7)
    slot = h.run_act(act)
    return slot.op.outcome(), act, h


def test_p5_all_six_action_decoders_ok_including_observe_found_false(
    core: types.ModuleType,
) -> None:
    r_ns = reactor_mod()
    facts_ok = vars(r_ns)["_facts_ok"]

    # OBSERVE_HEAVY with found=False across all 20 observations -> coherent OK in HostReactor
    obs_false_scripts = {
        f"act-observe-{idx}": [ChildScript(stdout_chunks=[observe_line(active=False)])]
        for idx in range(20)
    }
    out_obs_false, act_obs, _ = run_single_act(core, "OBSERVE_HEAVY", 23, obs_false_scripts)
    assert out_obs_false.status is r_ns.ActStatus.OK
    assert out_obs_false.facts == r_ns.ObserveFacts(found=False, observations=20)
    assert facts_ok(act_obs.kind, out_obs_false.status, out_obs_false.facts) is True

    ok_cases = [
        ("TERMINATE_ONE_BACKEND", 20, r_ns.TerminateFacts(found=1, terminated=True)),
        ("PAUSE_PG", 21, r_ns.PauseFacts(paused=True)),
        ("RESTORE_PG", 21, r_ns.RestoreFacts(running=True, paused=False, ready=True)),
        ("OBSERVE_HEAVY", 23, r_ns.ObserveFacts(found=True, observations=3)),
        ("ZERO_BACKENDS", 24, r_ns.ZeroFacts(backends=0)),
        ("KILL_GATEWAY", 25, r_ns.KillFacts(stop_confirmed=True, oom_killed=False)),
    ]
    for kind_name, case, expected_facts in ok_cases:
        out, act, h = run_single_act(core, kind_name, case, {})
        assert out.status is r_ns.ActStatus.OK
        assert out.facts == expected_facts
        assert facts_ok(act.kind, out.status, out.facts) is True
        assert h.first_of("ACT").protocol is h.m.ProtocolState.SUCCEEDED


def script_case(tag: str, chunk: bytes, **script: Any) -> dict[str, list[ChildScript]]:
    return {tag: [ChildScript(stdout_chunks=[chunk], **script)]}


PREDICATE_FAIL_CASES: list[tuple[str, int, dict[str, list[ChildScript]]]] = [
    ("TERMINATE_ONE_BACKEND", 20, script_case("act-term-0", terminate_line(found=0))),
    ("TERMINATE_ONE_BACKEND", 20, script_case("act-term-0", terminate_line(terminated=False))),
    ("PAUSE_PG", 21, script_case("act-pause-1", pause_line(paused=False, running=True))),
    ("RESTORE_PG", 21, script_case("act-restore-1", pause_line(paused=True, running=True))),
    ("RESTORE_PG", 21, script_case("act-restore-2", restore_ready_line(ready=False))),
    ("ZERO_BACKENDS", 24, script_case("act-zero-0", zero_line(backends=2))),
    ("KILL_GATEWAY", 25, script_case("act-kill-1", kill_line(oom=True, pid=0, running=False))),
    ("KILL_GATEWAY", 25, script_case("act-kill-1", kill_line(oom=False, pid=9, running=False))),
]


@pytest.mark.parametrize(
    ("kind_name", "case", "scripts"),
    PREDICATE_FAIL_CASES,
    ids=[f"{k}-{i}" for i, (k, _, _) in enumerate(PREDICATE_FAIL_CASES)],
)
def test_p5_action_decoder_predicate_false_is_failed_with_none_facts(
    core: types.ModuleType,
    kind_name: str,
    case: int,
    scripts: dict[str, list[ChildScript]],
) -> None:
    out, act, h = run_single_act(core, kind_name, case, scripts)
    r_ns = h.r_ns
    assert out.status is r_ns.ActStatus.FAILED
    assert out.facts is None
    assert vars(r_ns)["_facts_ok"](act.kind, out.status, out.facts) is True
    assert h.first_of("ACT").protocol is h.m.ProtocolState.FAILED_KNOWN


NON_CANONICAL_TERMINATE = b'{"found": 1,"scope":"scope-w1-01","terminated":true}\n'
UNKNOWN_DECODE_CASES: list[tuple[str, int, dict[str, list[ChildScript]]]] = [
    ("TERMINATE_ONE_BACKEND", 20, script_case("act-term-0", terminate_line(), exit_code=1)),
    ("PAUSE_PG", 21, {"act-pause-0": [ChildScript(stdout_chunks=[], exit_code=2)]}),
    ("PAUSE_PG", 21, script_case("act-pause-0", b"unexpected\n")),
    (
        "TERMINATE_ONE_BACKEND",
        20,
        script_case("act-term-0", b"x" * (CHILD_STDOUT_CAP + 10) + b"\n"),
    ),
    ("TERMINATE_ONE_BACKEND", 20, script_case("act-term-0", NON_CANONICAL_TERMINATE)),
    ("TERMINATE_ONE_BACKEND", 20, script_case("act-term-0", terminate_line(scope="wrong-scope"))),
    ("ZERO_BACKENDS", 24, script_case("act-zero-0", zero_line(role=OBSERVER_ROLE))),
    ("ZERO_BACKENDS", 24, script_case("act-zero-0", zero_line(observer_excluded=False))),
]


@pytest.mark.parametrize(
    ("kind_name", "case", "scripts"),
    UNKNOWN_DECODE_CASES,
    ids=[f"unknown-{i}" for i in range(len(UNKNOWN_DECODE_CASES))],
)
def test_p5_action_decoder_unknown_reasons_have_none_facts(
    core: types.ModuleType,
    kind_name: str,
    case: int,
    scripts: dict[str, list[ChildScript]],
) -> None:
    out, act, h = run_single_act(core, kind_name, case, scripts)
    r_ns = h.r_ns
    assert out.status is r_ns.ActStatus.UNKNOWN
    assert out.facts is None
    assert vars(r_ns)["_facts_ok"](act.kind, out.status, out.facts) is True
    assert h.first_of("ACT").protocol is h.m.ProtocolState.UNKNOWN


def test_settle_after_child1_of_act_unknown_never_starts_child2(core: types.ModuleType) -> None:
    """V2.2 / section 11: child 0 settles late during settle(); child 1 stays NOT_STARTED."""
    pump = FakePump()
    pump.push_child_script("act-pause-0", ChildScript(start_mode="never_settle"))
    h = Harness(core, pump=pump)
    m, owner = h.m, h.owner
    h.run_act(h.make_act("PAUSE_PG", 21, window=1.0))

    act_rec = h.first_of("ACT")
    assert act_rec.protocol is m.ProtocolState.PENDING  # live child at deadline: op stays pending
    children_before = h.records_of("CHILD")
    assert len(children_before) == 1 and children_before[0].physical is m.PhysicalState.OPEN

    owner.seal()
    child0_handle = pump.handles[children_before[0].record_id]
    pump.schedule_at(pump.t + DT, lambda: child0_handle.settle_exit(0))
    owner.settle(pump.t + 5.0)

    children_after = h.records_of("CHILD")
    assert children_after[0].physical is m.PhysicalState.SETTLED_RETAINED
    late_kinds = {
        lf.kind
        for r in owner.records()
        if r.record_id in (act_rec.record_id, children_after[0].record_id)
        for lf in r.late
    }
    assert m.LateKind.CHILD_DONE in late_kinds
    assert h.record(act_rec.record_id).protocol is act_rec.protocol  # never reopened
    # Child 1 never received start authorization or a live handle after parent deadline
    child0_id = children_before[0].record_id
    assert all(r.physical is m.PhysicalState.NOT_STARTED for r in children_after[1:])
    authorized_ids = [
        entry[1] for entry in pump.trace if entry[0] == "pump.authorized" and entry[2] is True
    ]
    assert authorized_ids == [child0_id]
    assert set(pump.handles) == {child0_id}
    assert all(
        req.record_id not in pump.handles for req in pump.requests if req.record_id != child0_id
    )


def test_act_parent_deadline_blocks_next_helper_without_seal_and_refuses_inert_request(
    core: types.ModuleType,
) -> None:
    """Expired ACT deadline blocks helpers without seal; queued inert requests do not start."""
    pump = FakePump()
    pump.push_child_script("act-pause-0", ChildScript(start_mode="never_settle"))
    h = Harness(core, pump=pump)
    m, owner, b_ns = h.m, h.owner, h.b_ns
    act1 = h.make_act("PAUSE_PG", 21, token=1, window=1.0)
    slot1 = h.run_act(act1)

    act1_rec = h.first_of("ACT")
    child0_id = h.first_of("CHILD").record_id
    assert act1_rec.protocol is m.ProtocolState.PENDING  # live child at deadline: op stays pending

    # Without seal() and without extending act1.deadline, child 0 exits after act1.deadline
    child0_handle = pump.handles[child0_id]
    pump.schedule_at(pump.t + DT, lambda: child0_handle.settle_exit(0))
    owner.clock().poll((slot1,), act1.deadline + 2 * DT)
    assert h.record(act1_rec.record_id).deadline == act1.deadline
    assert h.record(child0_id).physical is m.PhysicalState.SETTLED_RETAINED
    assert all(r.physical is m.PhysicalState.NOT_STARTED for r in h.records_of("CHILD")[1:])
    assert [
        entry[1] for entry in pump.trace if entry[0] == "pump.authorized" and entry[2] is True
    ] == [child0_id]
    assert set(pump.handles) == {child0_id}

    # Queuing an inert StartRequest before deadline does not start a process once deadline passes
    def expire_before_start() -> None:
        pump.advance(2 * DT)

    pump.schedule_at(pump.t, expire_before_start)
    act2 = h.make_act("TERMINATE_ONE_BACKEND", 20, token=2, window=DT)
    slot2 = b_ns.OperationSlot("act")
    owner.acts().begin_act_into(slot2, act2, act2.deadline)
    owner.clock().poll((slot2,), act2.deadline + 2 * DT)

    term_reqs = [req for req in pump.requests if "act-term-0" in req.argv]
    assert len(term_reqs) == 1  # inert StartRequest was enqueued in pump.requests
    term_id = term_reqs[0].record_id
    assert term_id not in pump.handles  # no real handle created in the fake
    assert ("pump.authorized", term_id, False, act2.issued_at + 2 * DT) in pump.trace
    assert [
        entry[1] for entry in pump.trace if entry[0] == "pump.authorized" and entry[2] is True
    ] == [child0_id]
    assert h.record(term_id).physical is m.PhysicalState.NOT_STARTED


# ---------------------------------------------------------------- P6 control recovery and seal


def test_p6_control_interrupt_preserves_first_identity_and_allows_postseal_recovery(
    core: types.ModuleType,
) -> None:
    pump = FakePump()
    control = KeyboardInterrupt("operator-abort")
    raised: list[bool] = []

    def interrupt_after_first_write(p: FakePump, _target: float, _stop: Callable[[], bool]) -> None:
        if not raised and p.gateway_handle is not None and len(p.gateway_handle.writes) >= 1:
            raised.append(True)
            raise control

    pump.on_run_until = interrupt_after_first_write
    h = Harness(core, pump=pump)
    m, owner, b_ns = h.m, h.owner, h.b_ns

    with pytest.raises(KeyboardInterrupt) as caught:
        h.bridge.run()
    assert caught.value is control
    assert owner.first_control() is control

    # Work dispatch is permanently closed after first control: no record, no request
    extra_slot = b_ns.OperationSlot("act")
    extra_act = h.make_act("ZERO_BACKENDS", 24, token=99)
    requests_before, records_before = len(pump.requests), len(owner.records())
    with pytest.raises(m.OwnershipRefusal):
        owner.acts().begin_act_into(extra_slot, extra_act, extra_act.deadline)
    assert extra_slot.occupied is False
    assert (len(pump.requests), len(owner.records())) == (requests_before, records_before)

    # Post-seal recovery remains open despite control_history
    pump.on_run_until = None
    fence = owner.seal()
    assert fence.open_ids != ()
    gw_rec = h.first_of("SPAWN")
    term_id = owner.begin_dispose(m.DisposeKind.TERMINATE_PROCESS, gw_rec.record_id, pump.t + 5.0)
    owner.settle(pump.t + 5.0)
    assert term_id > 0
    assert owner.audit().epoch == 1

    # Advance past work_settled_at, run both audits in epoch 1, close all settled handles
    pump.advance(DT)
    h.run_both_audits()
    h.close_all_settled_processes()

    report = owner.audit()
    assert report.control_history is True
    assert owner.first_control() is control
    assert report.quiet_scoped is True
    assert owner.custody().entries == ()


def test_control_between_bind_and_arm_is_not_armed_and_never_started(
    core: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = Harness(core)
    m, owner, pump, b_ns = h.m, h.owner, h.pump, h.b_ns
    control = KeyboardInterrupt("at-bind")

    def raising_bind(_self: Any, _op: object) -> None:
        raise control

    monkeypatch.setattr(b_ns.OperationSlot, "bind", raising_bind)
    with pytest.raises(KeyboardInterrupt) as caught:
        owner.gateway().begin_spawn_into(b_ns.OperationSlot("spawn"), pump.t + 5.0)
    assert caught.value is control
    rec = owner.records()[0]
    assert rec.gate is m.Gate.NOT_ARMED
    assert rec.physical is m.PhysicalState.NOT_STARTED
    assert pump.requests == []


def test_control_between_arm_and_direct_write_is_unknown_and_uncertain(
    core: types.ModuleType,
) -> None:
    h = Harness(core)
    m, pump, b_ns = h.m, h.pump, h.b_ns
    proc, _ = h.spawn_gateway()
    control = SystemExit(9)

    def raise_in_write(_p: FakePump, _h: FakeHandle, _data: bytes) -> None:
        raise control

    pump.on_direct_write = raise_in_write
    w_slot = b_ns.OperationSlot("write")
    with pytest.raises(SystemExit) as caught:
        proc.begin_write_into(w_slot, d1.frame(GO, 1, 1), pump.t + 5.0)
    assert caught.value is control
    w_rec = h.first_of("WRITE")
    assert w_rec.protocol is m.ProtocolState.UNKNOWN
    assert w_rec.uncertain is True
    assert m.FaultKind.CONTROL in w_rec.faults


# ---------------------------------------------------------------- P7 uncertain spawn, V4 settle


def test_p7_uncertain_spawn_resolved_by_late_started_exit_and_pipes_during_settle(
    core: types.ModuleType,
) -> None:
    pump = FakePump()
    pump.gateway_start_mode = "late_settle"
    h = Harness(core, pump=pump)
    m, owner = h.m, h.owner

    with pytest.raises(h.b_ns.BridgeRefusal) as caught:
        h.bridge.run()
    assert caught.value.category is h.b_ns.BridgeFault.SPAWN

    spawn_before = h.first_of("SPAWN")
    assert spawn_before.protocol is m.ProtocolState.UNKNOWN
    assert spawn_before.physical is m.PhysicalState.UNKNOWN
    assert spawn_before.uncertain is True

    fence = owner.seal()
    assert spawn_before.record_id in fence.unknown_ids
    assert fence.work_settled_at is None

    # V4 precision 1: settle() does NOT stop early on PhysicalState.UNKNOWN; it pumps late facts
    owner.settle(pump.t + 2.0)

    spawn_after = h.first_of("SPAWN")
    assert spawn_after.protocol is m.ProtocolState.UNKNOWN  # protocol stays immutable
    assert spawn_after.physical is m.PhysicalState.SETTLED_RETAINED
    assert spawn_after.uncertain is False
    late_kinds = {lf.kind for lf in spawn_after.late}
    assert m.LateKind.STARTED in late_kinds and m.LateKind.EXITED in late_kinds


def test_p7_uncertain_spawn_without_late_events_pumps_until_target_and_stays_unknown_retained(
    core: types.ModuleType,
) -> None:
    pump = FakePump()
    pump.gateway_start_mode = "late_none"
    h = Harness(core, pump=pump)
    m, owner = h.m, h.owner

    with pytest.raises(h.b_ns.BridgeRefusal):
        h.bridge.run()

    owner.seal()
    target = pump.t + 3.0
    assert owner.settle(target) == target  # pumped all the way to target

    spawn_rec = h.first_of("SPAWN")
    assert spawn_rec.physical is m.PhysicalState.UNKNOWN
    assert spawn_rec.uncertain is True
    assert owner.audit().quiet_scoped is False


@pytest.mark.parametrize("mode", ["bad_write_limits", "start_failed_after_started"])
def test_spawn_write_limits_failure_or_late_start_failure_keeps_handle_open(
    core: types.ModuleType, mode: str
) -> None:
    pump = FakePump()
    if mode == "bad_write_limits":
        pump.gateway_write_limits = (65536, 16384)
    else:
        pump.gateway_start_mode = "fail_after"
    h = Harness(core, pump=pump)
    m, owner, b_ns = h.m, h.owner, h.b_ns

    slot = b_ns.OperationSlot("spawn")
    owner.gateway().begin_spawn_into(slot, pump.t + 5.0)
    owner.clock().poll((slot,), pump.t + 5.0)
    assert pump.gateway_handle is not None
    assert slot.op.outcome() == b_ns.SpawnOutcome(ok=False, process=None)  # never exposed
    rec = owner.records()[0]
    assert rec.protocol is m.ProtocolState.UNKNOWN
    assert rec.physical is m.PhysicalState.OPEN
    if mode == "bad_write_limits":
        assert m.FaultKind.WRITE_LIMITS in rec.faults
    assert owner.custody().entries != ()


def test_spawn_exit_before_pipes_stays_open_until_every_pipe_is_lost(
    core: types.ModuleType,
) -> None:
    h = Harness(core)
    m, owner, pump = h.m, h.owner, h.pump
    _, gw = h.spawn_gateway()
    owner.seal()

    def exit_only() -> None:
        gw._returncode = 0
        gw.events.exited(0)

    pump.schedule_at(pump.t + DT, exit_only)
    owner.settle(pump.t + 2 * DT)
    assert owner.records()[0].physical is m.PhysicalState.OPEN  # still OPEN before pipes

    pump.schedule_at(pump.t + DT, lambda: gw.events.pipe_lost(0, False))
    owner.settle(pump.t + 2 * DT)
    assert owner.records()[0].physical is m.PhysicalState.OPEN

    pump.schedule_at(pump.t + DT, lambda: gw.events.pipe_lost(1, False))
    owner.settle(pump.t + 2 * DT)
    assert owner.records()[0].physical is m.PhysicalState.SETTLED_RETAINED


# ---------------------------------------------------------------- sections 8 & 9 audits, disposals


def test_audit_preconditions_and_epoch_invalidation_only_on_target_changing_dispose(
    core: types.ModuleType,
) -> None:
    h = Harness(core)
    m, owner, pump = h.m, h.owner, h.pump
    h.bridge.run()

    # Before seal() -> SEALED refusal
    with pytest.raises(m.OwnershipRefusal) as before_seal:
        owner.begin_audit(m.AuditKind.GATEWAY_ABSENT, pump.t + 5.0)
    assert_refusal(m, before_seal.value, "SEALED")

    fence = owner.seal()
    assert fence.work_settled_at is not None

    # At now() == work_settled_at (requires strict now() > work_settled_at) -> STATE refusal
    with pytest.raises(m.OwnershipRefusal) as at_settled:
        owner.begin_audit(m.AuditKind.GATEWAY_ABSENT, pump.t + 5.0)
    assert_refusal(m, at_settled.value, "STATE")

    pump.advance(DT)
    h.run_both_audits()
    assert owner.audit().quiet_scoped is True
    assert owner.audit().epoch == 0

    # REMOVE_GATEWAY_CONTAINER increments epoch on child 0 authorize and makes audits STALE
    owner.begin_dispose(m.DisposeKind.REMOVE_GATEWAY_CONTAINER, None, pump.t + 5.0)
    owner.settle(pump.t + 5.0)
    stale_report = owner.audit()
    assert stale_report.epoch == 1
    assert stale_report.gateway.verdict is m.AbsenceVerdict.STALE
    assert stale_report.backends.verdict is m.AbsenceVerdict.STALE
    assert stale_report.quiet_scoped is False


@dataclasses.dataclass
class AuditScenario:
    audit_kind: str
    ctrl_script: ChildScript
    tgt_script: ChildScript
    expected_verdict: str
    expected_settled: bool


AUDIT_SCENARIOS = (
    AuditScenario(
        "GATEWAY_ABSENT",
        ChildScript(stdout_chunks=[names_line([PG_NAME])]),
        ChildScript(stdout_chunks=[names_line([GATEWAY_NAME])]),
        "PRESENT",
        True,
    ),
    AuditScenario(
        "BACKENDS_ZERO",
        ChildScript(stdout_chunks=[observer_control_line()]),
        ChildScript(stdout_chunks=[zero_line(backends=3)]),
        "PRESENT",
        True,
    ),
    AuditScenario(
        "GATEWAY_ABSENT",
        ChildScript(stdout_chunks=[names_line([])]),  # control fails positive check
        ChildScript(stdout_chunks=[names_line([])]),
        "UNKNOWN",
        True,
    ),
    AuditScenario(
        "BACKENDS_ZERO",
        ChildScript(stdout_chunks=[observer_control_line(role=TARGET_ROLE)]),
        ChildScript(stdout_chunks=[zero_line(backends=0)]),
        "UNKNOWN",
        True,
    ),
    AuditScenario(
        "GATEWAY_ABSENT",
        ChildScript(start_mode="fail_before"),  # helper UNKNOWN / unsettled
        ChildScript(stdout_chunks=[names_line([])]),
        "UNKNOWN",
        False,
    ),
)


@pytest.mark.parametrize(
    "scenario",
    AUDIT_SCENARIOS,
    ids=[f"{s.audit_kind}-{s.expected_verdict}-{i}" for i, s in enumerate(AUDIT_SCENARIOS)],
)
def test_audit_present_and_unsettled_or_divergent_helpers_never_prove_absence(
    core: types.ModuleType, scenario: AuditScenario
) -> None:
    h = Harness(core)
    m, owner, pump = h.m, h.owner, h.pump
    h.bridge.run()
    owner.seal()
    pump.advance(DT)

    prefix = "audit-gw" if scenario.audit_kind == "GATEWAY_ABSENT" else "audit-bg"
    pump.push_child_script(f"{prefix}-control", scenario.ctrl_script)
    pump.push_child_script(f"{prefix}-target", scenario.tgt_script)

    owner.begin_audit(getattr(m.AuditKind, scenario.audit_kind), pump.t + 2.0)
    owner.settle(pump.t + 2.0)

    report = owner.audit()
    res = report.gateway if scenario.audit_kind == "GATEWAY_ABSENT" else report.backends
    assert res is not None
    assert res.verdict is getattr(m.AbsenceVerdict, scenario.expected_verdict)
    assert res.helpers_settled is scenario.expected_settled
    assert report.quiet_scoped is False


def test_dispose_preconditions_outcomes_and_custody_retention_on_failure(
    core: types.ModuleType,
) -> None:
    h = Harness(core)
    m, owner, pump = h.m, h.owner, h.pump
    h.bridge.run()
    owner.seal()

    gw_rec = h.first_of("SPAWN")
    gw_handle = pump.gateway_handle
    assert gw_handle is not None

    # TERMINATE_PROCESS on an already exited/settled process is refused (STATE), no kill
    with pytest.raises(m.OwnershipRefusal) as bad_term:
        owner.begin_dispose(m.DisposeKind.TERMINATE_PROCESS, gw_rec.record_id, pump.t + 5.0)
    assert_refusal(m, bad_term.value, "STATE")
    assert gw_handle.kill_calls == 0

    # CLOSE_HANDLE where closed() never arrives before deadline -> NOT_DONE, stays retained
    gw_handle.defer_closed_event = True
    owner.begin_dispose(m.DisposeKind.CLOSE_HANDLE, gw_rec.record_id, pump.t + 1.0)
    owner.settle(pump.t + 1.0)
    assert h.record(gw_rec.record_id).physical is m.PhysicalState.SETTLED_RETAINED
    assert any(rid == gw_rec.record_id for rid, _ in owner.custody().entries)


# ---------------------------------------------------------------- section 13 adversarial cases


def test_a_ord_exact_seven_step_order_before_every_effect(
    core: types.ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = Harness(core)
    m, owner, pump, b_ns = h.m, h.owner, h.pump, h.b_ns
    order_log: list[str] = []
    genuine_bind = b_ns.OperationSlot.bind

    def recording_bind(slot: Any, op: object) -> None:
        # At step 3 (bind), step 1 (reserve) must already have created the record
        recs = owner.records()
        assert len(recs) >= 1
        order_log.append(f"bind:{slot.name}:gate={recs[-1].gate.name}")
        genuine_bind(slot, op)

    monkeypatch.setattr(b_ns.OperationSlot, "bind", recording_bind)
    proc, _ = h.spawn_gateway()
    pump.gateway_auto_respond = False
    assert order_log[0].startswith("bind:spawn:")

    pump.trace.clear()
    proc.begin_write_into(b_ns.OperationSlot("write"), d1.frame(GO, 1, 1), pump.t + 5.0)

    events = [item[0] for item in pump.trace]
    write_idx = events.index("handle.write")
    last_now = max(i for i, name in enumerate(events[:write_idx]) if name == "pump.now")
    precondition_idx = max(
        i
        for i, name in enumerate(events[:write_idx])
        if name in ("handle.write_limits", "handle.is_closing")
    )
    # 5 pre-conditions < 6 authorize (fresh now) < 7 effect, with nothing in between
    assert precondition_idx < last_now < write_idx
    assert events[last_now + 1 : write_idx] == []
    assert order_log[-1].startswith("bind:write:")
    assert m.Gate.RESERVED.name in order_log[-1]


def test_a_limits_max_writes_refused_in_reserve_before_bind_or_write(
    core: types.ModuleType,
) -> None:
    h = Harness(core, limits_changes={"max_writes": 1})
    m, owner, pump, b_ns = h.m, h.owner, h.pump, h.b_ns
    proc, gw = h.spawn_gateway()
    pump.gateway_auto_respond = False

    proc.begin_write_into(b_ns.OperationSlot("write"), d1.frame(GO, 1, 1), pump.t + 5.0)
    records_before = len(owner.records())
    writes_before = len(gw.writes)

    w2 = b_ns.OperationSlot("write")
    with pytest.raises(m.OwnershipRefusal) as cap_err:
        proc.begin_write_into(w2, d1.frame(ACK, 1, 2), pump.t + 5.0)
    assert_refusal(m, cap_err.value, "CAPACITY")
    assert w2.occupied is False
    assert len(owner.records()) == records_before
    assert len(gw.writes) == writes_before


def test_a_limits_max_records_child_capacity_concludes_parent_missing(
    core: types.ModuleType,
) -> None:
    # ACT takes record 1, child 0 takes record 2, child 1 hits CAPACITY at reserve:
    # the parent concludes UNKNOWN (MISSING) and no third request is ever scheduled.
    h = Harness(core, limits_changes={"max_records": 2})
    b_ns, r_ns = h.b_ns, h.r_ns
    slot = h.run_act(h.make_act("PAUSE_PG", 21))
    assert slot.op.outcome() == b_ns.ActOutcome(status=r_ns.ActStatus.UNKNOWN, facts=None)
    assert len(h.owner.records()) == 2
    assert len(h.pump.requests) == 1
    assert not any("act-pause-1" in req.argv for req in h.pump.requests)


def test_a_limits_late_history_cap_from_unique_events_of_live_child(
    core: types.ModuleType,
) -> None:
    """max_late=2: direct port ACT stays PENDING at deadline with a LIVE child; after seal
    the child's exit and its two pipe losses are each delivered ONCE inside settle()."""
    pump = FakePump()
    pump.push_child_script("act-term-0", ChildScript(start_mode="never_settle"))
    h = Harness(core, pump=pump, limits_changes={"max_late": 2})
    m, owner = h.m, h.owner

    slot = h.run_act(h.make_act("TERMINATE_ONE_BACKEND", 20, window=1.0))
    assert slot.op.done() is False  # live child at the parent deadline: op stays pending
    act_before = h.first_of("ACT")
    live_child = h.first_of("CHILD")
    assert live_child.physical is m.PhysicalState.OPEN
    assert live_child.late == ()

    owner.seal()
    child_handle = pump.handles[live_child.record_id]
    pump.schedule_at(pump.t + DT, lambda: child_handle.settle_exit(0))  # three unique facts
    owner.settle(pump.t + 5.0)

    child_rec = h.record(live_child.record_id)
    assert len(child_rec.late) == 2  # history capped at max_late
    assert child_rec.late_overflow is True
    assert child_rec.physical is m.PhysicalState.SETTLED_RETAINED  # facts still known
    assert h.first_of("ACT").protocol is act_before.protocol  # protocol never reopened
    assert len(pump.requests) == 1  # no new child after the parent deadline
    assert set(pump.handles) == {live_child.record_id}


def test_a_limits_max_acts_refused_without_new_effect(core: types.ModuleType) -> None:
    h = Harness(core, limits_changes={"max_acts": 1})
    m, owner, pump, b_ns, r_ns = h.m, h.owner, h.pump, h.b_ns, h.r_ns

    first = h.run_act(h.make_act("TERMINATE_ONE_BACKEND", 20))  # positive at the cap
    assert first.op.outcome().status is r_ns.ActStatus.OK
    requests_before, records_before = len(pump.requests), len(owner.records())

    second_slot = b_ns.OperationSlot("act")
    act2 = h.make_act("ZERO_BACKENDS", 24, token=2)
    with pytest.raises(m.OwnershipRefusal) as act_cap:
        owner.acts().begin_act_into(second_slot, act2, act2.deadline)
    assert_refusal(m, act_cap.value, "CAPACITY")
    assert second_slot.occupied is False
    assert (len(pump.requests), len(owner.records())) == (requests_before, records_before)


def sealed_after_one_act(h: Harness) -> None:
    h.run_act(h.make_act("TERMINATE_ONE_BACKEND", 20))
    h.owner.seal()
    h.pump.advance(DT)


def test_a_limits_max_audits_refused_without_new_effect(core: types.ModuleType) -> None:
    h = Harness(core, limits_changes={"max_audits": 1})
    m, owner, pump = h.m, h.owner, h.pump
    sealed_after_one_act(h)

    owner.begin_audit(m.AuditKind.GATEWAY_ABSENT, pump.t + 5.0)  # positive at the cap
    owner.settle(pump.t + 5.0)
    assert owner.audit().gateway.verdict is m.AbsenceVerdict.ABSENT_OBSERVED
    requests_before, records_before = len(pump.requests), len(owner.records())

    with pytest.raises(m.OwnershipRefusal) as audit_cap:
        owner.begin_audit(m.AuditKind.BACKENDS_ZERO, pump.t + 5.0)
    assert_refusal(m, audit_cap.value, "CAPACITY")
    assert (len(pump.requests), len(owner.records())) == (requests_before, records_before)
    assert owner.audit().backends is None


def test_a_limits_max_disposals_refused_keeps_custody(core: types.ModuleType) -> None:
    h = Harness(core, limits_changes={"max_disposals": 1})
    m, owner, pump = h.m, h.owner, h.pump
    sealed_after_one_act(h)
    h.run_both_audits()
    settled = [r for r in h.records_of("CHILD") if r.physical is m.PhysicalState.SETTLED_RETAINED]
    assert len(settled) >= 2
    first_id, second_id = settled[0].record_id, settled[1].record_id

    owner.begin_dispose(m.DisposeKind.CLOSE_HANDLE, first_id, pump.t + 5.0)  # at the cap
    owner.settle(pump.t + 5.0)
    assert h.record(first_id).physical is m.PhysicalState.RELEASED_LOCAL
    records_before = len(owner.records())

    with pytest.raises(m.OwnershipRefusal) as disp_cap:
        owner.begin_dispose(m.DisposeKind.CLOSE_HANDLE, second_id, pump.t + 5.0)
    assert_refusal(m, disp_cap.value, "CAPACITY")
    assert pump.handles[second_id].close_calls == 0
    assert len(owner.records()) == records_before
    assert h.record(second_id).physical is m.PhysicalState.SETTLED_RETAINED
    assert any(rid == second_id for rid, _ in owner.custody().entries)


def retained_takes(m: Any, owner: Any) -> list[Any]:
    return [item for item in walk_model_state(owner) if type(item) is m.ReadTake]


def test_a_limits_successful_takes_released_and_last_failed_take_retained(
    core: types.ModuleType,
) -> None:
    pump = FakePump()
    pump.gateway_emit_guard = False
    h = Harness(core, pump=pump)
    m, owner, b_ns = h.m, h.owner, h.b_ns
    slots: list[Any] = []
    proc, gw = h.spawn_gateway()

    def take(size: int) -> Any:
        slot = b_ns.OperationSlot("read")
        proc.begin_read_into(slot, size, pump.t + 5.0)
        if not slot.op.done():
            owner.clock().poll((slot,), pump.t + 5.0)
        op = slot.op
        op.outcome()
        assert slot.occupied is True and slot.op is op
        slots.append(slot)
        return op

    pump.schedule_at(pump.t + DT, lambda: gw.events.data(1, b"ABCDEF"))
    ok1 = take(3)
    ok2 = take(3)  # a new take is born: the successful ok1 is no longer retained
    assert ok1.outcome() == b_ns.ReadOutcome(ok=True, data=b"ABC")
    assert all(item is not ok1 for item in retained_takes(m, owner))

    pump.schedule_at(pump.t + DT, lambda: gw.events.pipe_lost(1, True))
    failed1 = take(4)
    failed2 = take(4)
    assert failed1.outcome() == failed2.outcome() == b_ns.ReadOutcome(ok=False, data=b"")
    kept = retained_takes(m, owner)
    assert any(item is failed2 for item in kept)  # the last failed take stays in custody
    assert all(item is not ok1 and item is not ok2 for item in kept)
    assert 1 <= len(kept) <= h.limits.max_retained_takes == 2
    assert len(slots) == 4 and all(s.occupied is True for s in slots)
    with pytest.raises(AssertionError, match="max_depth"):
        walk_model_state(owner, max_depth=1)


def test_clock_reentry_and_foreign_input_faults(core: types.ModuleType) -> None:
    h = Harness(core)
    m, owner, pump, b_ns = h.m, h.owner, h.pump, h.b_ns

    # Foreign Act class -> PORT refusal without creating a record
    bad_act_slot = b_ns.OperationSlot("act")
    with pytest.raises(m.OwnershipRefusal) as bad_act:
        owner.acts().begin_act_into(bad_act_slot, SimpleNamespace(kind="X", case=20), pump.t + 1.0)
    assert_refusal(m, bad_act.value, "PORT")
    assert owner.records() == ()

    # Foreign op inside an ORIGINAL OperationSlot given to poll() -> PORT refusal
    foreign_slot = b_ns.OperationSlot("read")
    foreign_slot.bind(bt.InertOp())
    with pytest.raises(m.OwnershipRefusal) as bad_poll:
        owner.clock().poll((foreign_slot,), pump.t + 1.0)
    assert_refusal(m, bad_poll.value, "PORT")

    # Early return from pump.run_until (now() < target while stop() is False) -> PUMP refusal
    spawn_slot = b_ns.OperationSlot("spawn")
    owner.gateway().begin_spawn_into(spawn_slot, pump.t + 5.0)
    pump.on_run_until = lambda p, _target, _stop: p.t + DT
    with pytest.raises(m.OwnershipRefusal) as early_pump:
        owner.clock().poll((spawn_slot,), pump.t + 5.0)
    assert_refusal(m, early_pump.value, "PUMP")


def test_clock_regression_is_pump_fault(core: types.ModuleType) -> None:
    h = Harness(core)
    m, owner, pump = h.m, h.owner, h.pump
    assert owner.clock().now() == T0
    pump.on_now = lambda p: p.t - 1.0
    with pytest.raises(m.OwnershipRefusal) as regressed:
        owner.clock().now()
    assert_refusal(m, regressed.value, "PUMP")


def test_reentry_inside_run_until_is_refused(core: types.ModuleType) -> None:
    h = Harness(core)
    m, owner, pump, b_ns = h.m, h.owner, h.pump, h.b_ns
    reentry_seen: list[str] = []

    def try_reenter(p: FakePump, target: float, _stop: Callable[[], bool]) -> float:
        with pytest.raises(m.OwnershipRefusal) as re_err:
            owner.seal()
        reentry_seen.append(re_err.value.category.name)
        p.t = target
        return p.t

    spawn_slot = b_ns.OperationSlot("spawn")
    owner.gateway().begin_spawn_into(spawn_slot, pump.t + 5.0)
    pump.on_run_until = try_reenter
    owner.clock().poll((spawn_slot,), pump.t + 1.0)
    assert reentry_seen == ["REENTRY"]


def test_a_redact_repr_and_errors_never_leak_payload_argv_stdout_or_secrets(
    core: types.ModuleType,
) -> None:
    h = Harness(core)
    h.bridge.run()
    h.owner.seal()
    h.pump.advance(DT)
    h.owner.begin_audit(h.m.AuditKind.GATEWAY_ABSENT, h.pump.t + 5.0)
    h.owner.settle(h.pump.t + 5.0)

    inspected: list[object] = [
        h.owner,
        h.owner.clock(),
        h.owner.gateway(),
        h.owner.acts(),
        h.plan,
        h.plan.scope,
        h.limits,
        h.owner.audit(),
        h.owner.audit().fence,
        h.owner.custody(),
        *h.owner.records(),
    ]
    for item in inspected:
        text = repr(item) + str(item)
        assert all(secret not in text for secret in SECRET_TEXTS)

    for rec in h.owner.records():
        for obj in walk_model_state(rec):
            if isinstance(obj, str):
                assert ARGV_CANARY not in obj and STDERR_CANARY not in obj


FORBIDDEN_OWNERSHIP_IMPORTS = frozenset(
    {
        "asyncio",
        "subprocess",
        "socket",
        "threading",
        "signal",
        "select",
        "multiprocessing",
        "ctypes",
        "runpy",
        "importlib",
        "time",
        "os",
    }
)
FORBIDDEN_OWNERSHIP_NAMES = (
    "BudgetLedger",
    "CleanupConfirmation",
    "ProactorEventLoop",
    "oracle9_w1_host_reactor",
    "oracle9_w1_duplex_bridge",
    "oracle9_w1_driver",
    "oracle9_w1_controller",
)


def imported_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        assert all(alias.name not in FORBIDDEN_OWNERSHIP_NAMES for alias in node.names)
        return [node.module or ""]
    return []


def test_a_ast_static_import_and_cleanup_invariants() -> None:
    tree = ast.parse(OWNERSHIP_FILE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        for mod_name in imported_names(node):
            assert mod_name.split(".")[0] not in FORBIDDEN_OWNERSHIP_IMPORTS
            assert not mod_name.startswith("docs.poc")
            assert "budget" not in mod_name
        if isinstance(node, ast.Name):
            assert node.id not in FORBIDDEN_OWNERSHIP_NAMES
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ht.FORBIDDEN_CALLS | {"compile"}
        if isinstance(node, ast.Attribute):
            assert node.attr not in ht.CLOCK_ATTRS
        if isinstance(node, ast.Try):
            for final_stmt in node.finalbody:
                for sub in ast.walk(final_stmt):
                    if isinstance(sub, ast.Attribute):
                        assert sub.attr not in {"close", "kill"}
