"""Linear host-side caller (HOST-RUN-DESIGN H3 7e230883 + HOST-RUN-REVIEW HR5).

Composes ALREADY-LOADED, caller-pinned namespaces of the reviewed engines in the order
already exercised by the Harness: bind -> PortOwnership -> HostReactor -> DuplexBridge ->
bridge.run -> seal -> one settle -> refreshed fence -> scoped audits -> finite local
CLOSE_HANDLE dispositions -> pump.close -> final pure snapshots. It adds no protocol
engine, port, OS layer, loader, registry or entry point and imports no native module.

The report separates four conclusions: protocol (``done_outcome``), the owner's scoped
quiet (``audit.quiet_scoped``), local disposition (``closed_handles``/``pump_close``) and
physical release, which is never claimed. Logical deadlines bound only owner/pump
scheduling; bind, close and synchronous SDK calls have no wall-clock bound here. The
caller keeps ``HostCustody`` until an admitted recovery (native gate, NOT_PREPARED).
"""

from __future__ import annotations

import enum
import math
import types
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

_MAX_WINDOW_S: Final = 30.0
_REACTOR_CATEGORIES: Final = frozenset(
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
)  # the closed HostRefusal labels accepted by the published bridge
_NAMESPACE_NAMES: Final = (
    (
        "owner",
        (
            "PortOwnership",
            "CliPlan",
            "OwnerLimits",
            "AuditKind",
            "DisposeKind",
            "PhysicalState",
            "InvocationKind",
            "ProtocolState",
            "OwnershipRefusal",
            "OwnershipFault",
            "WorkFence",
            "AuditReport",
            "CustodyView",
        ),
    ),
    (
        "bridge",
        (
            "DuplexBridge",
            "DuplexBudget",
            "BridgeRefusal",
            "BridgeFault",
            "BridgeStatus",
            "BridgeRunResult",
        ),
    ),
    ("reactor", ("HostReactor", "HostRefusal", "Done", "Outcome")),
    ("pump", ("ProactorPump", "PumpFault")),
)
_OK: Final = 0
_FAILED: Final = 1
_CONTROL: Final = 2


# ---------------------------------------------------------------- closed enums


class HostRunStep(enum.Enum):
    ADMISSION = "ADMISSION"
    BIND = "BIND"
    OWNER = "OWNER"
    HOST = "HOST"
    BRIDGE = "BRIDGE"
    RUN = "RUN"
    SEAL = "SEAL"
    SETTLE = "SETTLE"
    AUDIT = "AUDIT"
    DISPOSE = "DISPOSE"
    CLOSE = "CLOSE"
    REPORT = "REPORT"


class HostRunStage(enum.Enum):
    REFUSED_CUSTODY = "REFUSED_CUSTODY"
    REFUSED_INPUT = "REFUSED_INPUT"
    BIND_REFUSED = "BIND_REFUSED"
    OWNER_REFUSED = "OWNER_REFUSED"
    HOST_REFUSED = "HOST_REFUSED"
    BRIDGE_REFUSED = "BRIDGE_REFUSED"
    RUN_REFUSED = "RUN_REFUSED"
    CLEANUP_FAULT = "CLEANUP_FAULT"
    RUN_DONE = "RUN_DONE"
    CONTROL = "CONTROL"


class BindResult(enum.Enum):
    NOT_CALLED = "NOT_CALLED"
    PUMP = "PUMP"
    FAULT = "FAULT"
    CONTROL = "CONTROL"
    INVALID_RETURN = "INVALID_RETURN"


class PumpCloseResult(enum.Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    RETURNED_TRUE = "RETURNED_TRUE"
    RETURNED_FALSE = "RETURNED_FALSE"
    INVALID_RETURN = "INVALID_RETURN"
    FAULT = "FAULT"
    CONTROL = "CONTROL"


class FaultSource(enum.Enum):
    OWNER = "OWNER"
    HOST = "HOST"
    BRIDGE = "BRIDGE"
    PUMP = "PUMP"
    BOUNDARY = "BOUNDARY"


_POST_RUN_STEPS: Final = frozenset(
    {
        HostRunStep.SEAL,
        HostRunStep.SETTLE,
        HostRunStep.AUDIT,
        HostRunStep.DISPOSE,
        HostRunStep.CLOSE,
        HostRunStep.REPORT,
    }
)
_REFUSAL_STAGES: Final = frozenset(
    {
        HostRunStage.REFUSED_INPUT,
        HostRunStage.BIND_REFUSED,
        HostRunStage.OWNER_REFUSED,
        HostRunStage.HOST_REFUSED,
        HostRunStage.BRIDGE_REFUSED,
        HostRunStage.RUN_REFUSED,
    }
)


# ---------------------------------------------------------------- carriers (redacted repr)


@dataclass(frozen=True, slots=True, repr=False)
class HostRunWindows:
    """Plain carrier: ``run_host`` admits each value (float, finite, 0 < x <= 30)."""

    settle_s: float
    audit_s: float
    dispose_s: float

    def __repr__(self) -> str:
        return "HostRunWindows(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class HostRunInputs:
    """Plain carrier of already-loaded, caller-pinned inputs; admitted by ``run_host``."""

    owner_ns: object
    bridge_ns: object
    reactor_ns: object
    pump_ns: object
    core: object
    packet: object
    policy: object
    plan: object
    limits: object
    budget: object
    windows: object
    bind: object

    def __repr__(self) -> str:
        return "HostRunInputs(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class HostFault:
    step: HostRunStep
    source: FaultSource
    category: str

    def __repr__(self) -> str:
        return "HostFault(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class HostRunReport:
    stage: HostRunStage
    bind_result: BindResult
    faults: tuple[HostFault, ...]
    reactor_refusal: str | None
    done_outcome: object | None
    bridge_status: object | None
    fence: object | None
    audit: object | None
    custody_view: object | None
    audit_ready: bool
    dispose_attempts: int
    closed_handles: int
    pump_close: PumpCloseResult
    report_complete: bool

    def __repr__(self) -> str:
        return "HostRunReport(<redacted>)"


@dataclass(slots=True, repr=False)
class HostCustody:
    """Caller-owned, created EMPTY before run_host; one invocation per custody."""

    claimed: bool = False
    stage: HostRunStage | None = None
    bind_result: BindResult = BindResult.NOT_CALLED
    bind_throwable: BaseException | None = None
    bind_candidate: object | None = None
    pump: object | None = None
    owner: object | None = None
    host: object | None = None
    bridge: object | None = None
    result: object | None = None
    first_control: BaseException | None = None
    report: HostRunReport | None = None

    def __repr__(self) -> str:
        return "HostCustody(<redacted>)"


@dataclass(frozen=True, slots=True, repr=False)
class _Snapshots:
    audit: object | None
    fence: object | None
    custody_view: object | None
    bridge_status: object | None
    complete: bool
    report_fault: bool
    first_control: BaseException | None

    def __repr__(self) -> str:
        return "_Snapshots(<redacted>)"


# ---------------------------------------------------------------- protected pure reads (seam)


def _guarded(call: Callable[[], object]) -> tuple[int, object]:
    """One protected call: never raises; a control is RETURNED by identity, never inspected."""
    try:
        return _OK, call()
    except Exception:
        return _FAILED, None
    except BaseException as control:
        return _CONTROL, control


def _fence_of(audit: object) -> object:
    return getattr(audit, "fence")


def _collect_snapshots(
    readers: tuple[
        Callable[[], object] | None, Callable[[], object] | None, Callable[[], object] | None
    ],
    domains: tuple[type, type, type, type],
    first_control: BaseException | None,
) -> _Snapshots:
    """Final snapshot reads (audit, custody, status, then ``audit.fence``), each guarded.

    Only the given pure readers are called, once each; no seal, clock, pump or SDK. An
    ordinary failure or a type outside the exact domain is a report fault; a control is
    kept only if none exists yet, and the remaining pure reads still run.
    """
    audit_type, fence_type, custody_type, status_type = domains
    control = first_control
    complete = True
    report_fault = False
    values: list[object | None] = []
    for reader, expected in zip(readers, (audit_type, custody_type, status_type), strict=True):
        if reader is None:
            values.append(None)  # legitimate absence: no call, no fault
            continue
        kind, value = _guarded(reader)
        if kind == _CONTROL:
            complete = False
            if control is None and isinstance(value, BaseException):
                control = value
            values.append(None)
        elif kind == _FAILED or type(value) is not expected:
            complete = False
            report_fault = True
            values.append(None)
        else:
            values.append(value)
    audit, custody_view, bridge_status = values
    fence: object | None = None
    if audit is not None:
        held = audit
        kind, value = _guarded(lambda: _fence_of(held))
        if kind == _CONTROL:
            complete = False
            if control is None and isinstance(value, BaseException):
                control = value
        elif kind == _FAILED or (value is not None and type(value) is not fence_type):
            complete = False
            report_fault = True
        else:
            fence = value  # None means not sealed yet: accepted
    return _Snapshots(
        audit=audit,
        fence=fence,
        custody_view=custody_view,
        bridge_status=bridge_status,
        complete=complete,
        report_fault=report_fault,
        first_control=control,
    )


# ---------------------------------------------------------------- admission (before bind)


@dataclass(frozen=True, slots=True, repr=False)
class _Admitted:
    names: dict[str, Any]
    bridge_ns: types.ModuleType
    reactor_ns: types.ModuleType
    core: object
    packet: object
    policy: object
    plan: object
    limits: object
    budget: object
    settle_s: float
    audit_s: float
    dispose_s: float
    bind: Callable[[], object]

    def __repr__(self) -> str:
        return "_Admitted(<redacted>)"


def _window(value: object) -> float | None:
    if type(value) is not float or not math.isfinite(value):
        return None
    return value if 0.0 < value <= _MAX_WINDOW_S else None


def _custody_is_fresh(custody: object) -> bool:
    """Called only through ``_guarded``: an unassigned slot of an own carrier raises."""
    if type(custody) is not HostCustody:
        return False
    return (
        custody.claimed is False
        and custody.stage is None
        and custody.bind_result is BindResult.NOT_CALLED
        and custody.bind_throwable is None
        and custody.bind_candidate is None
        and custody.pump is None
        and custody.owner is None
        and custody.host is None
        and custody.bridge is None
        and custody.result is None
        and custody.first_control is None
        and custody.report is None
    )


def _admit(inputs: object) -> _Admitted | None:
    """Reads every field ONCE into locals and captures the needed identities ONCE.

    Called only through ``_guarded``: any ordinary failure of these reads (e.g. an
    unassigned slot of an own carrier) is a refusal, never an escaping exception.
    """
    if type(inputs) is not HostRunInputs:
        return None
    spaces = {
        "owner": inputs.owner_ns,
        "bridge": inputs.bridge_ns,
        "reactor": inputs.reactor_ns,
        "pump": inputs.pump_ns,
    }
    core, packet, policy = inputs.core, inputs.packet, inputs.policy
    plan, limits, budget = inputs.plan, inputs.limits, inputs.budget
    windows, bind = inputs.windows, inputs.bind
    if type(windows) is not HostRunWindows or not callable(bind):
        return None
    settle_s = _window(windows.settle_s)
    audit_s = _window(windows.audit_s)
    dispose_s = _window(windows.dispose_s)
    if settle_s is None or audit_s is None or dispose_s is None:
        return None
    names: dict[str, Any] = {}
    for label, wanted in _NAMESPACE_NAMES:
        space = spaces[label]
        if type(space) is not types.ModuleType:
            return None
        table = vars(space)
        for name in wanted:
            found = table.get(name)
            if not isinstance(found, type):
                return None
            names[name] = found
    if (
        type(plan) is not names["CliPlan"]
        or type(limits) is not names["OwnerLimits"]
        or type(budget) is not names["DuplexBudget"]
    ):
        return None
    bridge_ns, reactor_ns = spaces["bridge"], spaces["reactor"]
    assert type(bridge_ns) is types.ModuleType and type(reactor_ns) is types.ModuleType
    return _Admitted(
        names=names,
        bridge_ns=bridge_ns,
        reactor_ns=reactor_ns,
        core=core,
        packet=packet,
        policy=policy,
        plan=plan,
        limits=limits,
        budget=budget,
        settle_s=settle_s,
        audit_s=audit_s,
        dispose_s=dispose_s,
        bind=bind,
    )


def _empty_report(stage: HostRunStage) -> HostRunReport:
    """Pre-admission exits: no admitted domain and no live object, so nothing is read."""
    return HostRunReport(
        stage=stage,
        bind_result=BindResult.NOT_CALLED,
        faults=(),
        reactor_refusal=None,
        done_outcome=None,
        bridge_status=None,
        fence=None,
        audit=None,
        custody_view=None,
        audit_ready=False,
        dispose_attempts=0,
        closed_handles=0,
        pump_close=PumpCloseResult.NOT_ATTEMPTED,
        report_complete=True,
    )


# ---------------------------------------------------------------- one invocation


class _Run:
    """State of ONE invocation; never shared, never global."""

    __slots__ = (
        "audit_ready",
        "bind_result",
        "complete",
        "control",
        "custody",
        "dispose_ids",
        "faults",
        "names",
        "pump_close",
        "reactor_refusal",
    )

    def __init__(self, custody: HostCustody, names: dict[str, Any]) -> None:
        self.custody = custody
        self.names = names
        self.faults: dict[HostRunStep, HostFault] = {}
        self.control: BaseException | None = None
        self.bind_result = BindResult.NOT_CALLED
        self.pump_close = PumpCloseResult.NOT_ATTEMPTED
        self.reactor_refusal: str | None = None
        self.audit_ready = False
        self.complete = True
        self.dispose_ids: list[int] = []

    def fault(self, step: HostRunStep, source: FaultSource, category: str) -> None:
        if step not in self.faults:  # only the FIRST fault of each step is kept
            self.faults[step] = HostFault(step=step, source=source, category=category)

    def stopped(self) -> bool:
        """Re-read after every call that may record a control (no attribute narrowing)."""
        return self.control is not None

    def take_control(self, control: BaseException) -> None:
        if self.control is None:  # the first control wins, compared by identity only
            self.control = control
            self.custody.first_control = control

    def classify(self, step: HostRunStep, error: BaseException) -> None:
        if not isinstance(error, Exception):
            self.take_control(error)
            return
        kind = type(error)
        n = self.names
        if kind is n["OwnershipRefusal"]:
            category = getattr(error, "category", None)
            label = _member_value(category, n["OwnershipFault"])
            self._labelled(step, FaultSource.OWNER, label)
        elif kind is n["HostRefusal"]:
            category = getattr(error, "category", None)
            label = category if type(category) is str else None
            if label not in _REACTOR_CATEGORIES:
                label = None
            self._labelled(step, FaultSource.HOST, label)
        elif kind is n["BridgeRefusal"]:
            category = getattr(error, "category", None)
            label = _member_value(category, n["BridgeFault"])
            refusal = getattr(error, "reactor_refusal", None)
            if type(refusal) is str and refusal in _REACTOR_CATEGORIES:
                self.reactor_refusal = refusal
            self._labelled(step, FaultSource.BRIDGE, label)
        elif kind is n["PumpFault"]:
            self.fault(step, FaultSource.PUMP, "PUMP")
        else:
            self.fault(step, FaultSource.BOUNDARY, "BOUNDARY")

    def _labelled(self, step: HostRunStep, source: FaultSource, label: object) -> None:
        if type(label) is str:
            self.fault(step, source, label)
        else:
            self.fault(step, FaultSource.BOUNDARY, "BOUNDARY")

    def call(self, step: HostRunStep, fn: Callable[[], object]) -> tuple[bool, object]:
        """One effect: an Exception becomes a closed fault, a control the first control."""
        caught: BaseException | None = None
        try:
            return True, fn()
        except BaseException as error:
            caught = error
        self.classify(step, caught)
        return False, None

    # -------------------------------------------------------- steps 6-10, in design order

    def after_run(self, owner: Any, admitted: _Admitted) -> None:
        n = self.names
        ok, _ = self.call(HostRunStep.SEAL, owner.seal)  # explicit first seal
        if not ok or self.stopped():
            return
        clock = owner.clock()
        ok, now = self.call(HostRunStep.SETTLE, clock.now)
        if ok and not self.stopped():
            settle_deadline = _plus(now, admitted.settle_s)  # computed once, never renewed
            self.call(HostRunStep.SETTLE, lambda: owner.settle(settle_deadline))
        if self.stopped():
            return
        ok, fence = self.call(HostRunStep.SEAL, owner.seal)  # REFRESH after observing
        if self.stopped():
            return
        settled = (
            ok and type(fence) is n["WorkFence"] and getattr(fence, "work_settled_at") is not None
        )
        if settled:
            self._audits(owner, clock, admitted.audit_s)
        if self.stopped():
            return
        self._dispositions(owner, clock, admitted.dispose_s)

    def _audits(self, owner: Any, clock: Any, audit_s: float) -> None:
        ok, now = self.call(HostRunStep.AUDIT, clock.now)
        if not ok or self.stopped():
            return
        audit_deadline = _plus(now, audit_s)  # one deadline shared by both audits

        def begin(chosen: object) -> Callable[[], object]:
            return lambda: owner.begin_audit(chosen, audit_deadline)

        started = 0
        audit_kind = self.names["AuditKind"]
        for kind in (audit_kind.GATEWAY_ABSENT, audit_kind.BACKENDS_ZERO):
            ok, _ = self.call(HostRunStep.AUDIT, begin(kind))
            if not ok or self.stopped():
                break  # the first refusal ends the audits: no retry
            started += 1
            ok, _ = self.call(HostRunStep.AUDIT, lambda: owner.settle(audit_deadline))
            if not ok or self.stopped():
                break
        self.audit_ready = started == 2 and not self.stopped()

    def _dispositions(self, owner: Any, clock: Any, dispose_s: float) -> None:
        n = self.names
        ok, records = self.call(HostRunStep.DISPOSE, owner.records)
        if not ok or self.stopped() or type(records) is not tuple:
            return
        processes = (n["InvocationKind"].SPAWN, n["InvocationKind"].CHILD)
        settled = n["PhysicalState"].SETTLED_RETAINED
        targets = [r.record_id for r in records if r.kind in processes and r.physical is settled]
        if not targets:
            return
        ok, now = self.call(HostRunStep.DISPOSE, clock.now)
        if not ok or self.stopped():
            return
        dispose_deadline = _plus(now, dispose_s)  # one deadline for the single pass
        close_handle = n["DisposeKind"].CLOSE_HANDLE  # the ONLY authorized disposition

        def begin(chosen: object) -> Callable[[], object]:
            return lambda: owner.begin_dispose(close_handle, chosen, dispose_deadline)

        for target in targets:  # one pass over a finite snapshot
            ok, record_id = self.call(HostRunStep.DISPOSE, begin(target))
            if not ok or self.stopped() or type(record_id) is not int:
                break  # the first refusal (e.g. CAPACITY) ends the pass
            self.dispose_ids.append(record_id)
        if self.dispose_ids and not self.stopped():
            self.call(HostRunStep.DISPOSE, lambda: owner.settle(dispose_deadline))

    # -------------------------------------------------------- step 11

    def close_pump(self, pump: Any) -> None:
        caught: BaseException | None = None
        value: object = None
        try:
            value = pump.close()
        except BaseException as error:
            caught = error
        if caught is not None:
            if isinstance(caught, Exception):
                self.pump_close = PumpCloseResult.FAULT
                self.classify(HostRunStep.CLOSE, caught)
            else:
                self.pump_close = PumpCloseResult.CONTROL
                self.take_control(caught)
        elif value is True:
            self.pump_close = PumpCloseResult.RETURNED_TRUE
        elif value is False:
            self.pump_close = PumpCloseResult.RETURNED_FALSE
        else:
            self.pump_close = PumpCloseResult.INVALID_RETURN

    # -------------------------------------------------------- step 12

    def finish(self, stage: HostRunStage | None) -> HostRunReport:
        """Builds the report from the three pure reads only; re-raises the first control."""
        n, c = self.names, self.custody
        owner, bridge = c.owner, c.bridge
        snap = _collect_snapshots(
            (
                getattr(owner, "audit") if owner is not None else None,
                getattr(owner, "custody") if owner is not None else None,
                getattr(bridge, "status") if bridge is not None else None,
            ),
            (n["AuditReport"], n["WorkFence"], n["CustodyView"], n["BridgeStatus"]),
            self.control,
        )
        if snap.first_control is not None:
            self.take_control(snap.first_control)
        complete = snap.complete and self.complete
        if snap.report_fault:
            self.fault(HostRunStep.REPORT, FaultSource.BOUNDARY, "BOUNDARY")
        done_outcome = self._done_outcome(c.result)
        if c.result is not None and done_outcome is None:
            complete = False
            self.fault(HostRunStep.REPORT, FaultSource.BOUNDARY, "BOUNDARY")
        self.complete = complete  # a failed check is never overwritten back to True
        report = HostRunReport(
            stage=self._stage(stage),
            bind_result=self.bind_result,
            faults=tuple(self.faults.values()),
            reactor_refusal=self.reactor_refusal,
            done_outcome=done_outcome,
            bridge_status=snap.bridge_status,
            fence=snap.fence,
            audit=snap.audit,
            custody_view=snap.custody_view,
            audit_ready=self.audit_ready,
            dispose_attempts=len(self.dispose_ids),
            closed_handles=self._confirmed_closes(snap.audit),
            pump_close=self.pump_close,
            report_complete=complete,
        )
        c.stage = report.stage
        c.bind_result = self.bind_result
        c.report = report
        control = self.control
        if control is not None:
            raise control  # outside any except: identity and __context__ untouched
        return report

    def _done_outcome(self, result: object) -> object | None:
        n = self.names
        if result is None or type(result) is not n["BridgeRunResult"]:
            return None
        done = getattr(result, "done")
        if type(done) is not n["Done"]:  # exact Done BEFORE reading its outcome
            return None
        outcome = getattr(done, "outcome")
        return outcome if type(outcome) is n["Outcome"] else None

    def _confirmed_closes(self, audit: object | None) -> int:
        if audit is None or not self.dispose_ids:
            return 0
        n = self.names
        by_id = {record.record_id: record for record in getattr(audit, "records")}
        succeeded = n["ProtocolState"].SUCCEEDED
        released = n["PhysicalState"].RELEASED_LOCAL
        confirmed = 0
        for record_id in self.dispose_ids:
            record = by_id.get(record_id)
            target = by_id.get(record.parent) if record is not None else None
            if (
                record is not None
                and target is not None
                and record.protocol is succeeded
                and target.physical is released
            ):
                confirmed += 1
        return confirmed

    def _stage(self, stage: HostRunStage | None) -> HostRunStage:
        if self.control is not None:
            return HostRunStage.CONTROL
        if stage is not None and stage in _REFUSAL_STAGES:
            return stage
        cleanup = (
            any(step in _POST_RUN_STEPS for step in self.faults)
            or self.pump_close
            not in (PumpCloseResult.RETURNED_TRUE, PumpCloseResult.RETURNED_FALSE)
            or not self.complete
            or bool(self.faults)
        )
        return HostRunStage.CLEANUP_FAULT if cleanup else HostRunStage.RUN_DONE


def _member_value(candidate: object, enum_type: object) -> object:
    """``.value`` only of a member of the exact captured enum; anything else is None."""
    if type(candidate) is not enum_type or not isinstance(candidate, enum.Enum):
        return None
    return candidate.value


def _plus(now: object, window: float) -> float:
    if type(now) is not float and type(now) is not int:
        return math.nan  # the owner refuses a non-finite deadline as a closed fault
    return float(now) + window


# ---------------------------------------------------------------- run_host


def run_host(inputs: object, custody: object) -> HostRunReport:
    """One linear invocation over a fresh caller-owned custody (H3 sections 3-10)."""
    if type(custody) is not HostCustody:
        return _empty_report(HostRunStage.REFUSED_CUSTODY)  # no write to that custody
    kind, fresh = _guarded(lambda: _custody_is_fresh(custody))
    if kind == _CONTROL and isinstance(fresh, BaseException):
        raise fresh  # nothing written yet; identity and __context__ untouched
    if kind != _OK or fresh is not True:
        return _empty_report(HostRunStage.REFUSED_CUSTODY)  # no write to that custody
    custody.claimed = True  # one-shot claim before any other validation
    kind, value = _guarded(lambda: _admit(inputs))
    if kind == _CONTROL and isinstance(value, BaseException):
        report = _empty_report(HostRunStage.CONTROL)
        custody.first_control = value
        custody.stage = report.stage
        custody.report = report
        raise value  # outside any except: identity and __context__ untouched
    if not isinstance(value, _Admitted):
        report = _empty_report(HostRunStage.REFUSED_INPUT)
        custody.stage = report.stage
        custody.report = report
        return report
    admitted = value
    n = admitted.names
    run = _Run(custody, n)

    # Step 1: bind (B4: the exact first throwable is retained with its traceback).
    caught: BaseException | None = None
    pump: object = None
    try:
        pump = admitted.bind()
    except BaseException as error:
        custody.bind_throwable = error  # reference only, inside the except
        caught = error
    if caught is not None:
        if isinstance(caught, Exception):
            run.bind_result = BindResult.FAULT
            run.classify(HostRunStep.BIND, caught)
            return run.finish(HostRunStage.BIND_REFUSED)
        run.bind_result = BindResult.CONTROL
        run.take_control(caught)
        return run.finish(None)
    if type(pump) is not n["ProactorPump"]:
        custody.bind_candidate = pump  # unknown object: retained, never closed
        run.bind_result = BindResult.INVALID_RETURN
        return run.finish(HostRunStage.BIND_REFUSED)
    custody.pump = pump
    run.bind_result = BindResult.PUMP
    live: Any = pump

    # Steps 2-4: pure constructions; content is validated by the existing constructors.
    ok, owner = run.call(
        HostRunStep.OWNER,
        lambda: n["PortOwnership"](
            live,
            admitted.plan,
            admitted.limits,
            bridge_ns=admitted.bridge_ns,
            reactor_ns=admitted.reactor_ns,
        ),
    )
    if run.stopped():
        return run.finish(None)
    if not ok:
        run.close_pump(live)
        return run.finish(HostRunStage.OWNER_REFUSED)
    custody.owner = owner
    held_owner: Any = owner
    ok, host = run.call(
        HostRunStep.HOST,
        lambda: n["HostReactor"](admitted.core, admitted.packet, admitted.policy),
    )
    if run.stopped():
        return run.finish(None)
    if not ok:
        run.close_pump(live)
        return run.finish(HostRunStage.HOST_REFUSED)
    custody.host = host
    ok, bridge = run.call(
        HostRunStep.BRIDGE,
        lambda: n["DuplexBridge"](
            admitted.reactor_ns,
            host,
            held_owner.clock(),
            held_owner.gateway(),
            held_owner.acts(),
            admitted.budget,
        ),
    )
    if run.stopped():
        return run.finish(None)
    if not ok:
        run.close_pump(live)
        return run.finish(HostRunStage.BRIDGE_REFUSED)
    custody.bridge = bridge
    held_bridge: Any = bridge

    # Step 5: the single protocol run.
    ok, result = run.call(HostRunStep.RUN, held_bridge.run)
    if run.stopped():
        return run.finish(None)
    run_stage = None if ok else HostRunStage.RUN_REFUSED
    if ok:
        custody.result = result

    # Steps 6-10, then 11 (close) and 12 (report); a control stops every further effect.
    run.after_run(held_owner, admitted)
    if run.stopped():
        return run.finish(None)
    run.close_pump(live)
    return run.finish(run_stage)
