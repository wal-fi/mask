"""First fake-only oracles for the linear host caller (HOST-RUN-DESIGN H3 7e230883 + HR5).

Contract for the FUTURE ``docs/poc/oracle9_w1_host_run.py``. The module stays ABSENT until
the root reviews these oracles and freezes RED; ``host_run_module()`` is the FIRST action
of every feature case, never inside an expected Exception/control catch, so its absence
fails per case (FileNotFoundError) and cannot make a negative oracle pass. The single
``test_sanity_*`` case validates only this file's fixtures and never loads the module.

Only the real reviewed engines are composed by the future ``run_host``: ProactorPump with
``_bind_over`` (3cb74292), PortOwnership (a5d233ae), DuplexBridge (5a09be1c) and
HostReactor (e86f8e32), over the FROZEN fake SDK (``FakeLoop``/``ProcScript``). Test-only
loop subclasses script timing of the fake SDK (a monotonically ticking clock, a delayed
gateway stdin loss); no product method, module or private state is patched. Synthetic
readers/classes are used ONLY for the private seam ``_collect_snapshots`` (H14), because
the real pure reads cannot be made to fail through public APIs. Nothing here calls the
native ``bind_proactor_pump``, creates a real loop/process, or proves any native fact:
``closed_handles``/``pump_close`` are local model observations, never physical release.

Known limitation (HOST-RUN-TEST-REVIEW HT2): H14 exercises only the seam, which does not
receive the bridge result; it does NOT cover the ``done_outcome`` validation nor the
``report_complete`` conjunction inside ``run_host``. That remains a source-review
obligation under HR5; no extra seam or public class replacement is added to simulate an
invalid result the admitted real composition cannot produce.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium, from H3 and normative HR5.
Senff policy: AI-generated tests require human and security review before merge.
"""

from __future__ import annotations

import ast
import dataclasses
import functools
import math
import runpy
import types
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests import test_oracle9_w1_host_reactor as ht
from tests import test_oracle9_w1_port_ownership as base
from tests import test_oracle9_w1_proactor_bind as bb
from tests import test_oracle9_w1_proactor_pump as pt

core = base.core  # published load_pure fixture over the pinned trusted core

REPO = Path(__file__).resolve().parents[1]
HOST_RUN_FILE = REPO / "docs/poc/oracle9_w1_host_run.py"
TICK = 2.0**-12  # exact dyadic advance of the ticking fake clock per time() read
WINDOW_S = 5.0
REACTOR_CATEGORIES = frozenset(
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
)  # oracle9_w1_duplex_bridge.py:66-81
CUSTODY_FIELDS = (
    "claimed",
    "stage",
    "bind_result",
    "bind_throwable",
    "bind_candidate",
    "pump",
    "owner",
    "host",
    "bridge",
    "result",
    "first_control",
    "report",
)
_ABSENT = object()


# ---------------------------------------------------------------- lazy loading and namespaces


@functools.cache
def _host_run_namespace() -> dict[str, Any]:
    return runpy.run_path(str(HOST_RUN_FILE), run_name="_host_run_test")


def host_run_module() -> Any:
    """FIRST action of every feature case; never inside an expected catch."""
    return SimpleNamespace(**_host_run_namespace())


def module_from(name: str, namespace: dict[str, Any], drop: str | None = None) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(namespace)
    if drop is not None:
        del module.__dict__[drop]
    return module


@functools.cache
def owner_ns() -> types.ModuleType:
    return module_from("_host_run_owner_ns", base._ownership_namespace())


@functools.cache
def pump_ns() -> types.ModuleType:
    return module_from("_host_run_pump_ns", pt._pump_namespace())


def tick(loop: pt.FakeLoop) -> object:
    loop.t += TICK  # a monotonic clock that advances on every read
    return loop.t


def owner_ident() -> int:
    return pt.OWNER_THREAD


def scripted_loop_class(
    born: list[pt.FakeLoop], setup: Callable[[pt.FakeLoop], None] | None, ticking: bool
) -> type[pt.FakeLoop]:
    class ScriptedLoop(pt.FakeLoop):
        def __init__(self) -> None:
            super().__init__()
            born.append(self)
            if ticking:
                self.time_script = tick
            if setup is not None:
                setup(self)

    return ScriptedLoop


def late_stdin_loop_class(born: list[pt.FakeLoop], delay: float) -> type[pt.FakeLoop]:
    """Fake-SDK timing only: after the KILL helper, the gateway exits and reaches stdout EOF
    as usual, but the loss of its stdin pipe is observed ``delay`` seconds later."""

    class LateStdinLoop(pt.FakeLoop):
        def __init__(self) -> None:
            super().__init__()
            born.append(self)
            self.time_script = tick

        def kill_gateway(self) -> None:
            gateway = self.gateway_transport()
            if gateway.returncode is not None or gateway.dying:
                return
            gateway.dying = True
            self.sdk_at(self.t + pt.DT, gateway.process_exited, 137)
            gateway.pipes[1].feed(None)
            self.sdk_at(self.t + delay, gateway.pipes[0].peer_closed)

    return LateStdinLoop


# ---------------------------------------------------------------- run kit (inputs + custody)


@dataclasses.dataclass
class KitSpec:
    ticking: bool = True
    setup: Callable[[pt.FakeLoop], None] | None = None
    loop_class: type[pt.FakeLoop] | None = None
    born: list[pt.FakeLoop] | None = None
    ident: Callable[[], object] = owner_ident
    limits_changes: dict[str, int] = dataclasses.field(default_factory=dict)
    plan: object = _ABSENT
    policy: object = _ABSENT
    budget: object = _ABSENT


@dataclasses.dataclass
class RunKit:
    hr: Any
    m: Any
    pm: Any
    b_ns: types.ModuleType
    r_ns: types.ModuleType
    inputs: Any
    custody: Any
    born: list[pt.FakeLoop]
    bind_calls: list[str]


def make_kit(hr: Any, core_mod: Any, spec: KitSpec) -> RunKit:
    m = base.ownership_module()
    b_ns, r_ns, pm = base.bridge_mod(), base.reactor_mod(), pt.pump_module()
    born: list[pt.FakeLoop] = [] if spec.born is None else spec.born
    loop_class = spec.loop_class
    if loop_class is None:
        loop_class = scripted_loop_class(born, spec.setup, spec.ticking)
    bind_calls: list[str] = []

    def bind() -> object:
        bind_calls.append("bind")
        return pm._bind_over(
            loop_class, pipe=pt.FAKE_PIPE, devnull=pt.FAKE_DEVNULL, ident=spec.ident
        )

    budget = spec.budget
    if budget is _ABSENT:
        budget = b_ns.DuplexBudget(
            spawn_s=base.SPAWN_S,
            silence_s=base.SILENCE_S,
            drain_s=base.DRAIN_S,
            overall_s=base.OVERALL_S,
        )
    inputs = hr.HostRunInputs(
        owner_ns=owner_ns(),
        bridge_ns=b_ns,
        reactor_ns=r_ns,
        pump_ns=pump_ns(),
        core=core_mod,
        packet=base.PACKET,
        policy=ht.policy_for(r_ns) if spec.policy is _ABSENT else spec.policy,
        plan=base.make_plan(m, r_ns, observe_children=20) if spec.plan is _ABSENT else spec.plan,
        limits=m.OwnerLimits(**{**base.DEFAULT_LIMITS, **spec.limits_changes}),
        budget=budget,
        windows=hr.HostRunWindows(settle_s=WINDOW_S, audit_s=WINDOW_S, dispose_s=WINDOW_S),
        bind=bind,
    )
    return RunKit(hr, m, pm, b_ns, r_ns, inputs, hr.HostCustody(), born, bind_calls)


def custody_snapshot(custody: object) -> tuple[object, ...]:
    return tuple(getattr(custody, name, _ABSENT) for name in CUSTODY_FIELDS)


def fault_at(report: Any, step: Any) -> Any:
    found = [fault for fault in report.faults if fault.step is step]
    return found[0] if found else None


def records_of(k: RunKit, kind_name: str) -> list[Any]:
    kind = getattr(k.m.InvocationKind, kind_name)
    return [record for record in k.custody.owner.records() if record.kind is kind]


def assert_report_shape(k: RunKit, report: Any) -> None:
    """Closed report domains of H3 section 2/9, checked on every run_host result."""
    hr, m = k.hr, k.m
    assert type(report) is hr.HostRunReport
    assert type(report.stage) is hr.HostRunStage and type(report.bind_result) is hr.BindResult
    assert type(report.faults) is tuple and len(report.faults) <= len(hr.HostRunStep)
    steps = [fault.step for fault in report.faults]
    assert len(steps) == len(set(steps))  # at most ONE fault per step
    domains = {
        hr.FaultSource.OWNER: {member.value for member in m.OwnershipFault},
        hr.FaultSource.BRIDGE: {member.value for member in vars(k.b_ns)["BridgeFault"]},
        hr.FaultSource.HOST: REACTOR_CATEGORIES,
        hr.FaultSource.PUMP: {"PUMP"},
        hr.FaultSource.BOUNDARY: {"BOUNDARY"},
    }
    for fault in report.faults:
        assert type(fault) is hr.HostFault and type(fault.step) is hr.HostRunStep
        assert type(fault.source) is hr.FaultSource and type(fault.category) is str
        assert fault.category in domains[fault.source]
    if report.reactor_refusal is not None:  # exact str, never an equal subclass
        assert type(report.reactor_refusal) is str
        assert report.reactor_refusal in REACTOR_CATEGORIES
    assert report.done_outcome is None or type(report.done_outcome) is vars(k.r_ns)["Outcome"]
    status_type = vars(k.b_ns)["BridgeStatus"]
    assert report.bridge_status is None or type(report.bridge_status) is status_type
    assert report.audit is None or type(report.audit) is m.AuditReport
    assert report.fence is None or type(report.fence) is m.WorkFence
    if report.audit is None:
        assert report.fence is None
    else:
        assert report.fence is report.audit.fence
    assert report.custody_view is None or type(report.custody_view) is m.CustodyView
    assert type(report.audit_ready) is bool and type(report.report_complete) is bool
    assert type(report.dispose_attempts) is int and type(report.closed_handles) is int
    assert 0 <= report.closed_handles <= report.dispose_attempts
    assert type(report.pump_close) is hr.PumpCloseResult
    if report.stage is hr.HostRunStage.RUN_DONE:
        assert report.faults == () and report.report_complete is True
    assert all(fault.step is not hr.HostRunStep.REPORT for fault in report.faults) or (
        report.report_complete is False
    )
    text = repr(report) + str(report)
    assert all(secret not in text for secret in pt.SECRET_TEXTS)


def test_sanity_ticking_clock_is_monotonic_and_late_stdin_is_scripted_on_the_fake_sdk() -> None:
    born: list[pt.FakeLoop] = []
    loop = scripted_loop_class(born, None, ticking=True)()
    first, second = loop.time(), loop.time()
    assert born == [loop] and type(first) is float and second == first + TICK
    late = late_stdin_loop_class(born, 2.0)()
    assert born[-1] is late and late.time() == pt.T0 + TICK


# ---------------------------------------------------------------- H1 positive


def test_h1_complete_candidate_audited_quiet_and_confirmed_local_close(core: Any) -> None:
    hr = host_run_module()
    k = make_kit(hr, core, KitSpec())
    report = hr.run_host(k.inputs, k.custody)
    assert_report_shape(k, report)
    assert report.stage is hr.HostRunStage.RUN_DONE and report.faults == ()
    assert report.bind_result is hr.BindResult.PUMP
    assert report.done_outcome is vars(k.r_ns)["Outcome"].COMPLETE_CANDIDATE
    assert report.audit_ready is True and report.audit is not None
    assert report.audit.quiet_scoped is True and report.audit.control_history is False
    assert report.fence is not None and report.fence.work_settled_at is not None
    assert report.closed_handles >= 15 and report.closed_handles == report.dispose_attempts
    assert report.pump_close is hr.PumpCloseResult.RETURNED_TRUE
    assert report.report_complete is True and report.custody_view is not None
    assert report.custody_view.entries == ()
    (loop,) = k.born
    assert loop.count("loop.close") == 1
    assert loop.count("transport.kill") == 0 and loop.count("sdk.kill") == 0
    c = k.custody
    assert c.claimed is True and c.stage is hr.HostRunStage.RUN_DONE and c.report is report
    assert type(c.pump) is k.pm.ProactorPump and c.owner is not None and c.bridge is not None
    assert c.bind_throwable is None and c.first_control is None and k.bind_calls == ["bind"]
    assert_observed_record_order_and_confirmed_closes(k, report)


def assert_observed_record_order_and_confirmed_closes(k: RunKit, report: Any) -> None:
    """Runtime order of the real owner records: WORK (fence) < AUDIT < DISPOSE, and every
    accepted CLOSE_HANDLE confirmed locally through its parent's state (not a counter)."""
    m = k.m
    records = k.custody.owner.records()
    by_id = {record.record_id: record for record in records}
    audits = [r for r in records if r.kind is m.InvocationKind.AUDIT]
    disposals = [r for r in records if r.kind is m.InvocationKind.DISPOSE]
    assert report.fence is not None and len(audits) == 2 and disposals != []
    assert max(report.fence.work_ids) < min(a.record_id for a in audits)
    assert max(a.record_id for a in audits) < min(d.record_id for d in disposals)
    assert len(disposals) == report.dispose_attempts  # accepted attempts
    process_kinds = (m.InvocationKind.SPAWN, m.InvocationKind.CHILD)
    assert all(d.parent in by_id and by_id[d.parent].kind in process_kinds for d in disposals)
    confirmed = [
        d
        for d in disposals
        if d.protocol is m.ProtocolState.SUCCEEDED
        and by_id[d.parent].physical is m.PhysicalState.RELEASED_LOCAL
    ]
    assert len(confirmed) == report.closed_handles == len(disposals)  # local conclusions
    assert len({d.parent for d in disposals}) == len(disposals)  # one close per process
    assert all(
        r.physical is m.PhysicalState.RELEASED_LOCAL for r in records if r.kind in process_kinds
    )


# ---------------------------------------------------------------- single pre-bind capture (HT2.3)


def test_inputs_and_namespaces_are_captured_once_before_bind(core: Any) -> None:
    """The binder returns a REAL pump over the fake SDK but, before returning, poisons ONLY
    per-test COPIES of owner_ns/pump_ns and public fields of this test's own frozen input.
    The run must keep using the references it captured before bind."""
    hr = host_run_module()
    k = make_kit(hr, core, KitSpec())
    owner_copy = module_from("_host_run_owner_copy", base._ownership_namespace())
    pump_copy = module_from("_host_run_pump_copy", pt._pump_namespace())
    real_bind = k.inputs.bind
    box: list[Any] = []
    calls: list[str] = []

    def poisoning_bind() -> object:
        calls.append("bind")
        pump = real_bind()
        for name in ("PortOwnership", "AuditKind", "DisposeKind", "AuditReport", "WorkFence"):
            owner_copy.__dict__[name] = object()  # copy only; real namespaces untouched
        pump_copy.__dict__["ProactorPump"] = object()
        own_input = box[0]
        object.__setattr__(own_input, "plan", object())  # this test's own input only
        object.__setattr__(own_input, "windows", raw_windows(hr, 0.0, 0.0, 0.0))
        object.__setattr__(own_input, "budget", object())
        return pump

    inputs = dataclasses.replace(
        k.inputs, owner_ns=owner_copy, pump_ns=pump_copy, bind=poisoning_bind
    )
    box.append(inputs)
    report = hr.run_host(inputs, k.custody)
    assert calls == ["bind"] and k.bind_calls == ["bind"]
    assert_report_shape(k, report)
    assert report.stage is hr.HostRunStage.RUN_DONE and report.faults == ()
    assert report.done_outcome is vars(k.r_ns)["Outcome"].COMPLETE_CANDIDATE
    assert report.audit is not None and report.audit.quiet_scoped is True
    assert report.pump_close is hr.PumpCloseResult.RETURNED_TRUE
    assert type(k.custody.pump) is k.pm.ProactorPump
    assert type(k.custody.owner) is k.m.PortOwnership  # the class captured BEFORE bind
    assert_observed_record_order_and_confirmed_closes(k, report)


# ---------------------------------------------------------------- H2-H4 bind failures and B4


def bind_kit(hr: Any, core_mod: Any, spec: bb.LoopSpec, ident: Callable[[], object]) -> RunKit:
    return make_kit(hr, core_mod, KitSpec(loop_class=bb.loop_class_for(spec), ident=ident))


def assert_bind_refusal_report(k: RunKit, report: Any, result: Any) -> None:
    hr = k.hr
    assert_report_shape(k, report)
    assert report.bind_result is result and report.pump_close is hr.PumpCloseResult.NOT_ATTEMPTED
    assert report.audit is None and report.custody_view is None and report.bridge_status is None
    assert report.done_outcome is None and report.report_complete is True
    assert fault_at(report, hr.HostRunStep.REPORT) is None  # legitimate absence: no fault
    c = k.custody
    assert c.pump is None and c.owner is None and c.host is None and c.bridge is None
    assert c.report is report and k.bind_calls == ["bind"]


@pytest.mark.parametrize("phase", ["factory-exception", "foreign-type"])
def test_h2_bind_fault_retains_exact_throwable_and_known_loop_frame(core: Any, phase: str) -> None:
    hr = host_run_module()
    spec = (
        bb.LoopSpec(init_failure=OSError(pt.CANARY))
        if phase == "factory-exception"
        else (bb.LoopSpec(foreign=True))
    )
    k = bind_kit(hr, core, spec, owner_ident)
    report = hr.run_host(k.inputs, k.custody)
    assert report.stage is hr.HostRunStage.BIND_REFUSED
    assert_bind_refusal_report(k, report, hr.BindResult.FAULT)
    thrown = k.custody.bind_throwable
    assert thrown is not None and type(thrown) is k.pm.PumpFault
    pt.assert_pump_fault(k.pm, thrown)
    helper = pt._pump_namespace()["_bind_over"]
    if phase == "factory-exception":
        assert spec.born == []  # F1: no known loop; no retention is claimed
    else:
        loop = bb.known_loop(spec)
        assert bb.helper_frames_hold(thrown, helper.__code__, loop) is True


@pytest.mark.parametrize("site", ["factory-control", "ident-control"])
def test_h3_bind_control_propagates_by_identity_and_is_retained(core: Any, site: str) -> None:
    hr = host_run_module()
    probes: list[str] = []
    ctl, origin = bb.controlled(pt.BoomCtl(probes), "preexisting-context")
    if site == "factory-control":
        spec, ident = bb.LoopSpec(init_failure=ctl), owner_ident
    else:
        spec, ident = bb.LoopSpec(), pt.raiser(ctl)
    k = bind_kit(hr, core, spec, ident)
    raised = pt.control_of(lambda: hr.run_host(k.inputs, k.custody))
    assert raised is ctl and ctl.__context__ is origin and probes == []
    c = k.custody
    assert c.bind_throwable is ctl and c.first_control is ctl
    assert c.bind_result is hr.BindResult.CONTROL and c.stage is hr.HostRunStage.CONTROL
    assert c.report is not None and c.report.stage is hr.HostRunStage.CONTROL
    assert_bind_refusal_report(k, c.report, hr.BindResult.CONTROL)
    if site == "ident-control":
        loop = bb.known_loop(spec)
        helper = pt._pump_namespace()["_bind_over"]
        assert loop.count("loop.close") == 1
        assert bb.helper_frames_hold(ctl, helper.__code__, loop) is True


@pytest.mark.parametrize("close", ["close-exception", "close-control"])
def test_h4_bind_close_failure_keeps_first_outcome(core: Any, close: str) -> None:
    hr = host_run_module()
    probes: list[str] = []
    close_ctl = pt.FalseCtl(probes)
    fault: BaseException = OSError(pt.CANARY) if close == "close-exception" else close_ctl
    spec = bb.LoopSpec(task_factory=object(), close_fault=fault)
    k = bind_kit(hr, core, spec, owner_ident)
    helper = pt._pump_namespace()["_bind_over"]
    if close == "close-exception":
        report = hr.run_host(k.inputs, k.custody)
        assert report.stage is hr.HostRunStage.BIND_REFUSED
        assert_bind_refusal_report(k, report, hr.BindResult.FAULT)
        assert type(k.custody.bind_throwable) is k.pm.PumpFault
    else:
        raised = pt.control_of(lambda: hr.run_host(k.inputs, k.custody))
        assert raised is close_ctl and k.custody.bind_throwable is close_ctl
        assert k.custody.first_control is close_ctl and close_ctl.__context__ is None
        assert_bind_refusal_report(k, k.custody.report, hr.BindResult.CONTROL)
    loop = bb.known_loop(spec)
    assert loop.count("loop.close") == 1 and probes == []
    assert bb.helper_frames_hold(k.custody.bind_throwable, helper.__code__, loop) is True


# ---------------------------------------------------------------- H5 invalid binder return


def test_h5_invalid_bind_return_is_retained_never_closed(core: Any) -> None:
    hr = host_run_module()
    k = make_kit(hr, core, KitSpec())
    candidate = pt.FakeLoop()  # not a ProactorPump: unknown type, retained, never closed
    calls: list[str] = []

    def bind_foreign() -> object:
        calls.append("bind")
        return candidate

    inputs = dataclasses.replace(k.inputs, bind=bind_foreign)
    report = hr.run_host(inputs, k.custody)
    assert report.stage is hr.HostRunStage.BIND_REFUSED and calls == ["bind"]
    assert report.bind_result is hr.BindResult.INVALID_RETURN
    assert k.custody.bind_candidate is candidate and k.custody.pump is None
    assert k.custody.owner is None and candidate.count("loop.close") == 0
    assert report.pump_close is hr.PumpCloseResult.NOT_ATTEMPTED
    assert_report_shape(k, report)


# ---------------------------------------------------------------- H6 / H6b admission and custody


def raw_windows(hr: Any, settle: object, audit: object, dispose: object) -> object:
    """An UNVALIDATED HostRunWindows instance, so run_host's own admission is exercised."""
    windows = object.__new__(hr.HostRunWindows)
    object.__setattr__(windows, "settle_s", settle)
    object.__setattr__(windows, "audit_s", audit)
    object.__setattr__(windows, "dispose_s", dispose)
    return windows


INPUT_REFUSALS = (
    "inputs-not-dataclass",
    "windows-not-type",
    "window-zero",
    "window-over-30",
    "window-nan",
    "window-bool",
    "window-int",
    "bind-not-callable",
    "owner-ns-not-module",
    "owner-ns-missing-WorkFence",
    "bridge-ns-missing-BridgeRunResult",
    "reactor-ns-missing-Done",
    "pump-ns-missing-PumpFault",
    "plan-wrong-type",
    "limits-wrong-type",
    "budget-wrong-type",
)


def refused_inputs(k: RunKit, case: str) -> object:
    hr, good = k.hr, k.inputs
    windows = {
        "window-zero": (0.0, WINDOW_S, WINDOW_S),
        "window-over-30": (WINDOW_S, 30.5, WINDOW_S),
        "window-nan": (WINDOW_S, WINDOW_S, math.nan),
        "window-bool": (True, WINDOW_S, WINDOW_S),
        "window-int": (5, WINDOW_S, WINDOW_S),
    }
    if case == "inputs-not-dataclass":
        return SimpleNamespace(**{f.name: getattr(good, f.name) for f in dataclasses.fields(good)})
    if case in windows:
        return dataclasses.replace(good, windows=raw_windows(hr, *windows[case]))
    changes: dict[str, Callable[[], object]] = {
        "windows-not-type": lambda: SimpleNamespace(settle_s=5.0, audit_s=5.0, dispose_s=5.0),
        "bind-not-callable": lambda: None,
        "owner-ns-not-module": lambda: SimpleNamespace(**vars(owner_ns())),
        "owner-ns-missing-WorkFence": lambda: module_from(
            "_bad_owner", base._ownership_namespace(), "WorkFence"
        ),
        "bridge-ns-missing-BridgeRunResult": lambda: module_from(
            "_bad_bridge", dict(vars(k.b_ns)), "BridgeRunResult"
        ),
        "reactor-ns-missing-Done": lambda: module_from("_bad_r", dict(vars(k.r_ns)), "Done"),
        "pump-ns-missing-PumpFault": lambda: module_from(
            "_bad_pump", pt._pump_namespace(), "PumpFault"
        ),
        "plan-wrong-type": object,
        "limits-wrong-type": lambda: SimpleNamespace(**base.DEFAULT_LIMITS),
        "budget-wrong-type": lambda: SimpleNamespace(spawn_s=5.0),
    }
    field = {
        "windows-not-type": "windows",
        "bind-not-callable": "bind",
        "owner-ns-not-module": "owner_ns",
        "owner-ns-missing-WorkFence": "owner_ns",
        "bridge-ns-missing-BridgeRunResult": "bridge_ns",
        "reactor-ns-missing-Done": "reactor_ns",
        "pump-ns-missing-PumpFault": "pump_ns",
        "plan-wrong-type": "plan",
        "limits-wrong-type": "limits",
        "budget-wrong-type": "budget",
    }[case]
    return dataclasses.replace(good, **{field: changes[case]()})


@pytest.mark.parametrize("case", INPUT_REFUSALS)
def test_h6_input_refusal_claims_custody_without_bind_then_reuse_is_refused(
    core: Any, case: str
) -> None:
    hr = host_run_module()
    k = make_kit(hr, core, KitSpec())
    bad = refused_inputs(k, case)
    report = hr.run_host(bad, k.custody)
    assert report.stage is hr.HostRunStage.REFUSED_INPUT and k.bind_calls == []
    assert report.bind_result is hr.BindResult.NOT_CALLED
    assert report.pump_close is hr.PumpCloseResult.NOT_ATTEMPTED
    assert fault_at(report, hr.HostRunStep.REPORT) is None
    c = k.custody
    assert c.claimed is True and c.stage is hr.HostRunStage.REFUSED_INPUT and c.report is report
    assert c.pump is None and c.owner is None and c.bind_throwable is None
    before = custody_snapshot(c)
    again = hr.run_host(k.inputs, c)  # valid inputs, but the custody is already used
    assert again.stage is hr.HostRunStage.REFUSED_CUSTODY and k.bind_calls == []
    assert again is not report and c.report is report
    after = custody_snapshot(c)
    assert all(x is y for x, y in zip(before, after, strict=True))


CORRUPT_CUSTODY = ("claimed-int", "claimed-false-pump-preset", "subclass", "foreign-object")


def corrupt_custody(hr: Any, case: str) -> object:
    if case == "foreign-object":
        return SimpleNamespace(**dict.fromkeys(CUSTODY_FIELDS))
    if case == "subclass":
        sub = type("SubCustody", (hr.HostCustody,), {"__slots__": ()})
        return sub()
    custody = hr.HostCustody()
    if case == "claimed-int":
        custody.claimed = 1
    else:
        custody.pump = object()
    return custody


@pytest.mark.parametrize("case", CORRUPT_CUSTODY)
def test_h6b_corrupt_or_foreign_custody_is_refused_without_any_write(core: Any, case: str) -> None:
    hr = host_run_module()
    k = make_kit(hr, core, KitSpec())
    custody = corrupt_custody(hr, case)
    before = custody_snapshot(custody)
    report = hr.run_host(k.inputs, custody)
    assert report.stage is hr.HostRunStage.REFUSED_CUSTODY and k.bind_calls == []
    assert report.bind_result is hr.BindResult.NOT_CALLED
    after = custody_snapshot(custody)
    assert all(x is y for x, y in zip(before, after, strict=True))  # no write at all


# ---------------------------------------------------------------- H6c incomplete own carriers (HS2)


INCOMPLETE_CUSTODY = ("raw-custody-no-fields", "custody-missing-report")


def incomplete_custody(hr: Any, case: str) -> object:
    if case == "raw-custody-no-fields":
        return object.__new__(hr.HostCustody)  # own carrier, no slot ever assigned
    custody = hr.HostCustody()
    del custody.report  # own carrier, one public slot absent
    return custody


@pytest.mark.parametrize("case", INCOMPLETE_CUSTODY)
def test_h6c_incomplete_custody_is_refused_without_any_write(core: Any, case: str) -> None:
    hr = host_run_module()
    k = make_kit(hr, core, KitSpec())
    custody = incomplete_custody(hr, case)
    before = custody_snapshot(custody)
    assert _ABSENT in before  # the carrier really is incomplete
    report = hr.run_host(k.inputs, custody)
    assert type(report) is hr.HostRunReport
    assert report.stage is hr.HostRunStage.REFUSED_CUSTODY and k.bind_calls == []
    assert report.bind_result is hr.BindResult.NOT_CALLED
    assert report.pump_close is hr.PumpCloseResult.NOT_ATTEMPTED
    after = custody_snapshot(custody)
    assert all(x is y for x, y in zip(before, after, strict=True))  # no write at all


INCOMPLETE_INPUTS = ("raw-inputs-no-fields", "own-windows-missing-audit_s")


def incomplete_inputs(k: RunKit, case: str) -> object:
    hr = k.hr
    if case == "raw-inputs-no-fields":
        return object.__new__(hr.HostRunInputs)  # own carrier, no slot ever assigned
    windows = object.__new__(hr.HostRunWindows)
    object.__setattr__(windows, "settle_s", WINDOW_S)
    object.__setattr__(windows, "dispose_s", WINDOW_S)  # audit_s left absent
    return dataclasses.replace(k.inputs, windows=windows)


@pytest.mark.parametrize("case", INCOMPLETE_INPUTS)
def test_h6c_incomplete_inputs_claim_custody_and_report_refusal_without_bind(
    core: Any, case: str
) -> None:
    hr = host_run_module()
    k = make_kit(hr, core, KitSpec())
    bad = incomplete_inputs(k, case)
    report = hr.run_host(bad, k.custody)
    assert type(report) is hr.HostRunReport
    assert report.stage is hr.HostRunStage.REFUSED_INPUT and k.bind_calls == []
    assert report.bind_result is hr.BindResult.NOT_CALLED
    assert report.pump_close is hr.PumpCloseResult.NOT_ATTEMPTED
    assert fault_at(report, hr.HostRunStep.REPORT) is None
    c = k.custody
    assert c.claimed is True and c.stage is hr.HostRunStage.REFUSED_INPUT and c.report is report
    assert c.pump is None and c.owner is None and c.bind_throwable is None


# ---------------------------------------------------------------- H7 construction refusals


@pytest.mark.parametrize("case", ["owner-plan-content", "host-policy", "bridge-budget"])
def test_h7_construction_refusal_closes_empty_pump_and_reports_category(
    core: Any, case: str
) -> None:
    hr = host_run_module()
    m, r_ns, b_ns = base.ownership_module(), base.reactor_mod(), base.bridge_mod()
    spec = KitSpec()
    if case == "owner-plan-content":
        spec.plan = base.make_plan(m, r_ns, gateway_argv=("gateway-cli", "--no-scope"))
    elif case == "host-policy":
        spec.policy = object()
    else:
        spec.budget = b_ns.DuplexBudget(spawn_s=0.0, silence_s=1.0, drain_s=1.0, overall_s=2.0)
    k = make_kit(hr, core, spec)
    report = hr.run_host(k.inputs, k.custody)
    assert_report_shape(k, report)
    expected = {
        "owner-plan-content": (hr.HostRunStage.OWNER_REFUSED, hr.HostRunStep.OWNER),
        "host-policy": (hr.HostRunStage.HOST_REFUSED, hr.HostRunStep.HOST),
        "bridge-budget": (hr.HostRunStage.BRIDGE_REFUSED, hr.HostRunStep.BRIDGE),
    }[case]
    assert report.stage is expected[0]
    fault = fault_at(report, expected[1])
    assert fault is not None and report.faults == (fault,)
    if case == "owner-plan-content":
        assert (fault.source, fault.category) == (hr.FaultSource.OWNER, "PLAN")
    elif case == "host-policy":
        assert fault.source is hr.FaultSource.HOST and fault.category in REACTOR_CATEGORIES
    else:
        assert (fault.source, fault.category) == (hr.FaultSource.BRIDGE, "BUDGET")
    assert report.pump_close is hr.PumpCloseResult.RETURNED_TRUE  # pump without records
    assert report.report_complete is True and report.done_outcome is None
    assert report.bridge_status is None  # absent bridge: legitimately not read
    assert (report.audit is None) is (case == "owner-plan-content")
    assert report.fence is None  # never sealed


# ---------------------------------------------------------------- H8 run refusal continues 6-12


def spawn_fails(loop: pt.FakeLoop) -> None:
    exc = OSError(pt.CANARY)
    loop.push_script(pt.GATEWAY_KEY, pt.ProcScript(exec_mode="raise_before", exec_exc=exc))


def test_h8_spawn_refusal_still_seals_settles_and_retains_custody(core: Any) -> None:
    hr = host_run_module()
    k = make_kit(hr, core, KitSpec(setup=spawn_fails, ticking=False))
    report = hr.run_host(k.inputs, k.custody)
    assert_report_shape(k, report)
    assert report.stage is hr.HostRunStage.RUN_REFUSED and report.done_outcome is None
    run_fault = fault_at(report, hr.HostRunStep.RUN)
    assert run_fault is not None and run_fault.source is hr.FaultSource.BRIDGE
    assert run_fault.category == "SPAWN" and report.bridge_status is not None
    assert report.fence is not None and report.fence.work_settled_at is None  # sealed, unsettled
    assert report.audit_ready is False and report.dispose_attempts == 0
    assert report.pump_close is hr.PumpCloseResult.RETURNED_FALSE  # START_FAILED retained
    assert report.report_complete is True
    assert type(k.custody.pump) is k.pm.ProactorPump and k.custody.result is None
    (spawn,) = records_of(k, "SPAWN")
    assert spawn.protocol is k.m.ProtocolState.UNKNOWN


# ---------------------------------------------------------------- H9 late fact refreshes fence


def test_h9_late_stdin_loss_after_done_is_observed_and_refreshed_fence_admits_audits(
    core: Any,
) -> None:
    hr = host_run_module()
    born: list[pt.FakeLoop] = []
    loop_class = late_stdin_loop_class(born, delay=2.0)
    k = make_kit(hr, core, KitSpec(loop_class=loop_class, born=born))
    report = hr.run_host(k.inputs, k.custody)
    assert_report_shape(k, report)
    assert report.done_outcome is not None  # a real Done from the real reactor/bridge
    (spawn,) = records_of(k, "SPAWN")
    late = [f for f in spawn.late if f.kind is k.m.LateKind.PIPE_LOST and f.code == 0]
    assert late != []  # stdin loss observed only AFTER seal(): during settle
    assert report.fence is not None and report.fence.work_settled_at is not None
    assert report.fence.work_settled_at >= late[0].at
    assert report.audit_ready is True and report.audit is not None
    audits = records_of(k, "AUDIT")
    assert len(audits) == 2
    assert all(a.armed_at > report.fence.work_settled_at for a in audits)  # refreshed fence


# ---------------------------------------------------------------- H10 paused EOF retention


def capped_child(loop: pt.FakeLoop) -> None:
    loop.push_script("act-term-0", pt.ProcScript(stdout=[b"x" * base.CHILD_STDOUT_CAP]))


def test_h10_paused_eof_keeps_resources_without_terminate(core: Any) -> None:
    hr = host_run_module()
    k = make_kit(hr, core, KitSpec(setup=capped_child))
    report = hr.run_host(k.inputs, k.custody)
    assert_report_shape(k, report)
    assert report.stage is not hr.HostRunStage.CONTROL and k.custody.first_control is None
    assert report.audit is not None and report.audit.quiet_scoped is False
    assert report.pump_close is hr.PumpCloseResult.RETURNED_FALSE
    (loop,) = k.born
    assert ("read.held", "act-term-0", 1, True) in loop.trace
    assert loop.count("transport.kill") == 0 and loop.count("resume_reading") == 0
    child = next(r for r in records_of(k, "CHILD") if r.plan_index == 0 and r.pipes_lost[1] is None)
    assert child.physical is k.m.PhysicalState.OPEN
    assert type(k.custody.pump) is k.pm.ProactorPump


# ---------------------------------------------------------------- H11 coarse clock refusal


def test_h11_frozen_clock_refuses_audit_honestly_without_retry(core: Any) -> None:
    hr = host_run_module()
    k = make_kit(hr, core, KitSpec(ticking=False))
    report = hr.run_host(k.inputs, k.custody)
    assert_report_shape(k, report)
    audit_fault = fault_at(report, hr.HostRunStep.AUDIT)
    assert audit_fault is not None
    assert (audit_fault.source, audit_fault.category) == (hr.FaultSource.OWNER, "STATE")
    assert report.audit_ready is False and records_of(k, "AUDIT") == []  # no retry
    assert report.stage is hr.HostRunStage.CLEANUP_FAULT
    assert report.done_outcome is vars(k.r_ns)["Outcome"].COMPLETE_CANDIDATE
    assert report.audit is not None and report.audit.quiet_scoped is False
    # local disposal still proceeds: exactly one accepted CLOSE_HANDLE per actual process
    m = k.m
    records = k.custody.owner.records()
    by_id = {record.record_id: record for record in records}
    assert len(by_id) == len(records)  # record ids unique
    process_kinds = (m.InvocationKind.SPAWN, m.InvocationKind.CHILD)
    processes = [r for r in records if r.kind in process_kinds]
    disposals = [r for r in records if r.kind is m.InvocationKind.DISPOSE]
    assert processes != []
    assert all(d.parent in by_id and by_id[d.parent].kind in process_kinds for d in disposals)
    parents = [d.parent for d in disposals]
    assert len(set(parents)) == len(parents)  # never two closes for one process
    assert set(parents) == {p.record_id for p in processes}  # no process missing
    assert all(d.protocol is m.ProtocolState.SUCCEEDED for d in disposals)
    assert all(p.physical is m.PhysicalState.RELEASED_LOCAL for p in processes)
    assert len(disposals) == len(processes) == report.dispose_attempts == report.closed_handles


# ---------------------------------------------------------------- H12 pump close outcomes


def test_h12_loop_close_exception_returns_false_without_fault(core: Any) -> None:
    hr = host_run_module()

    def failing_close(loop: pt.FakeLoop) -> None:
        loop.close_fault = OSError(pt.CANARY)

    k = make_kit(hr, core, KitSpec(setup=failing_close))
    report = hr.run_host(k.inputs, k.custody)
    assert_report_shape(k, report)
    assert report.pump_close is hr.PumpCloseResult.RETURNED_FALSE
    assert report.stage is hr.HostRunStage.RUN_DONE and report.audit is not None
    assert report.audit.quiet_scoped is True  # scoped quiet is not physical release
    (loop,) = k.born
    assert loop.count("loop.close") == 1


def test_h12_identity_change_before_close_is_a_pump_fault(core: Any) -> None:
    hr = host_run_module()
    holder: dict[str, list[pt.FakeLoop]] = {}

    def ident() -> int:
        loops = holder.get("born", [])
        if loops and ("transport.close", pt.GATEWAY_KEY) in loops[0].trace:
            return pt.OTHER_THREAD  # identity changed after the gateway handle was closed
        return pt.OWNER_THREAD

    k = make_kit(hr, core, KitSpec(ident=ident))
    holder["born"] = k.born
    report = hr.run_host(k.inputs, k.custody)
    assert_report_shape(k, report)
    assert report.pump_close is hr.PumpCloseResult.FAULT
    close_fault = fault_at(report, hr.HostRunStep.CLOSE)
    assert close_fault is not None
    assert (close_fault.source, close_fault.category) == (hr.FaultSource.PUMP, "PUMP")
    assert report.stage is hr.HostRunStage.CLEANUP_FAULT


def test_h12_close_control_is_reraised_by_identity_with_report(core: Any) -> None:
    hr = host_run_module()
    probes: list[str] = []
    ctl = pt.FalseCtl(probes)

    def control_close(loop: pt.FakeLoop) -> None:
        loop.close_fault = ctl

    k = make_kit(hr, core, KitSpec(setup=control_close))
    raised = pt.control_of(lambda: hr.run_host(k.inputs, k.custody))
    assert raised is ctl and ctl.__context__ is None and probes == []
    c = k.custody
    assert c.first_control is ctl and c.stage is hr.HostRunStage.CONTROL
    assert c.report is not None and c.report.pump_close is hr.PumpCloseResult.CONTROL
    assert_report_shape(k, c.report)


# ---------------------------------------------------------------- H13 control before seal


def test_h13_control_during_run_reports_with_pure_reads_and_no_clock(core: Any) -> None:
    hr = host_run_module()
    probes: list[str] = []
    interrupt = pt.FalseInterrupt(probes)
    reads_after: list[str] = []

    def counting_time(loop: pt.FakeLoop) -> object:
        if loop.raw_after is None:
            reads_after.append("time")  # any clock read after the raw control was raised
        return loop.t

    def arm(loop: pt.FakeLoop) -> None:
        loop.raw_after = ("connection_made", interrupt)
        loop.time_script = counting_time

    k = make_kit(hr, core, KitSpec(setup=arm, ticking=False))
    raised = pt.control_of(lambda: hr.run_host(k.inputs, k.custody))
    assert raised is interrupt and probes == [] and reads_after == []
    c = k.custody
    assert c.first_control is interrupt and c.stage is hr.HostRunStage.CONTROL
    report = c.report
    assert report is not None and report.stage is hr.HostRunStage.CONTROL
    assert_report_shape(k, report)
    assert report.audit is not None and report.audit.fence is None and report.fence is None
    assert report.bridge_status is not None and report.done_outcome is None
    assert report.pump_close is hr.PumpCloseResult.NOT_ATTEMPTED
    assert records_of(k, "AUDIT") == [] and records_of(k, "DISPOSE") == []
    (loop,) = k.born
    assert loop.count("loop.close") == 0


# ---------------------------------------------------------------- H14 seam _collect_snapshots


class SynFence:
    """Synthetic WorkFence-domain class."""


class SynAudit:
    def __init__(self, fence: object) -> None:
        self.fence = fence


class SynCustody:
    """Synthetic CustodyView-domain class."""


class SynStatus:
    """Synthetic BridgeStatus-domain class."""


class GetterAudit:
    """Audit-domain class whose ``fence`` getter fails (HR5)."""

    def __init__(self, failure: BaseException, reads: list[str]) -> None:
        self.failure = failure
        self.reads = reads

    @property
    def fence(self) -> object:
        self.reads.append("fence")
        raise self.failure


DOMAINS = (SynAudit, SynFence, SynCustody, SynStatus)


def reader(value: object, calls: list[str], name: str) -> Callable[[], object]:
    def read() -> object:
        calls.append(name)
        return value

    return read


def raising_reader(failure: BaseException, calls: list[str], name: str) -> Callable[[], object]:
    def read() -> object:
        calls.append(name)
        raise failure

    return read


def seam() -> tuple[Any, Callable[..., Any]]:
    hr = host_run_module()
    collect: Callable[..., Any] = vars(hr)["_collect_snapshots"]
    return hr, collect


def test_h14_absent_readers_are_legitimate_none_without_fault() -> None:
    hr, collect = seam()
    snap = collect((None, None, None), DOMAINS, None)
    assert type(snap) is hr._Snapshots
    assert (snap.audit, snap.fence, snap.custody_view, snap.bridge_status) == (None,) * 4
    assert snap.complete is True and snap.report_fault is False and snap.first_control is None


def test_h14_valid_reads_once_each_with_fence_from_audit_or_none() -> None:
    _hr, collect = seam()
    calls: list[str] = []
    fence, view, status = SynFence(), SynCustody(), SynStatus()
    audit = SynAudit(fence)
    readers = (reader(audit, calls, "a"), reader(view, calls, "c"), reader(status, calls, "s"))
    snap = collect(readers, DOMAINS, None)
    assert calls == ["a", "c", "s"]
    assert snap.audit is audit and snap.fence is fence
    assert snap.custody_view is view and snap.bridge_status is status
    assert snap.complete is True and snap.report_fault is False
    unsealed = collect((reader(SynAudit(None), calls, "a"), None, None), DOMAINS, None)
    assert unsealed.fence is None and unsealed.complete is True and unsealed.report_fault is False


@pytest.mark.parametrize(
    "case", ["audit-exception", "custody-wrong-type", "status-subclass", "fence-wrong-type"]
)
def test_h14_ordinary_failures_are_report_faults_and_reads_continue(case: str) -> None:
    _hr, collect = seam()
    calls: list[str] = []
    audit = SynAudit(object() if case == "fence-wrong-type" else SynFence())
    sub_status = type("SubStatus", (SynStatus,), {})
    readers = (
        raising_reader(ValueError(pt.CANARY), calls, "a")
        if case == "audit-exception"
        else reader(audit, calls, "a"),
        reader(SynStatus() if case == "custody-wrong-type" else SynCustody(), calls, "c"),
        reader(sub_status() if case == "status-subclass" else SynStatus(), calls, "s"),
    )
    snap = collect(readers, DOMAINS, None)
    assert calls == ["a", "c", "s"]  # every reader exactly once
    assert snap.complete is False and snap.report_fault is True and snap.first_control is None
    if case == "audit-exception":
        assert snap.audit is None and snap.fence is None
    elif case == "custody-wrong-type":
        assert snap.custody_view is None and snap.audit is audit
    elif case == "status-subclass":
        assert snap.bridge_status is None
    else:
        assert snap.audit is audit and snap.fence is None


@pytest.mark.parametrize("prior", ["no-prior", "prior-control"])
def test_h14_reader_control_keeps_first_identity_and_continues(prior: str) -> None:
    _hr, collect = seam()
    probes: list[str] = []
    calls: list[str] = []
    first = pt.BoomCtl(probes) if prior == "prior-control" else None
    ctl = pt.FalseCtl(probes)
    readers = (
        reader(SynAudit(SynFence()), calls, "a"),
        raising_reader(ctl, calls, "c"),
        reader(SynStatus(), calls, "s"),
    )
    snap = collect(readers, DOMAINS, first)
    assert calls == ["a", "c", "s"]  # following readers still called
    assert snap.first_control is (ctl if first is None else first)
    assert snap.custody_view is None and snap.complete is False and snap.report_fault is False
    assert probes == []


@pytest.mark.parametrize("failure", ["exception", "control-no-prior", "control-prior"])
def test_h14_fence_getter_failure_is_protected(failure: str) -> None:
    _hr, collect = seam()
    probes: list[str] = []
    reads: list[str] = []
    first = pt.BoomCtl(probes) if failure == "control-prior" else None
    raised: BaseException = ValueError(pt.CANARY) if failure == "exception" else pt.FalseCtl(probes)
    audit = GetterAudit(raised, reads)
    domains = (GetterAudit, SynFence, SynCustody, SynStatus)
    snap = collect((reader(audit, [], "a"), None, None), domains, first)
    assert reads == ["fence"]  # audit.fence read exactly once
    assert snap.fence is None and snap.complete is False
    if failure == "exception":
        assert snap.report_fault is True and snap.first_control is None
    else:
        assert snap.report_fault is False
        assert snap.first_control is (raised if first is None else first)
    assert probes == []


# ---------------------------------------------------------------- H15 finite disposal capacity


def test_h15_disposal_capacity_ends_the_single_pass_with_exact_counts(core: Any) -> None:
    hr = host_run_module()
    k = make_kit(hr, core, KitSpec(limits_changes={"max_disposals": 3}))
    report = hr.run_host(k.inputs, k.custody)
    assert_report_shape(k, report)
    dispose_fault = fault_at(report, hr.HostRunStep.DISPOSE)
    assert dispose_fault is not None
    assert (dispose_fault.source, dispose_fault.category) == (hr.FaultSource.OWNER, "CAPACITY")
    assert report.dispose_attempts == 3 and report.closed_handles == 3
    assert len(records_of(k, "DISPOSE")) == 3
    assert report.pump_close is hr.PumpCloseResult.RETURNED_FALSE  # other handles retained
    assert report.stage is hr.HostRunStage.CLEANUP_FAULT


# ---------------------------------------------------------------- H16 AST of the future source


def host_run_tree() -> ast.Module:
    return ast.parse(HOST_RUN_FILE.read_text(encoding="utf-8"))


def call_lines(tree: ast.AST, attr: str) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attr
    ]


def test_h16_static_shape_of_the_future_module() -> None:
    hr = host_run_module()
    assert callable(vars(hr)["run_host"])
    tree = host_run_tree()
    forbidden = {"asyncio", "subprocess", "socket", "threading", "signal", "os", "docs"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not {a.name.split(".")[0] for a in node.names} & forbidden
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden
        assert not isinstance(node, ast.While)
        if isinstance(node, ast.Name):
            assert node.id != "bind_proactor_pump"
        if isinstance(node, ast.Attribute):
            assert node.attr not in {
                "bind_proactor_pump",
                "TERMINATE_PROCESS",
                "REMOVE_GATEWAY_CONTAINER",
            }
    collect = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_collect_snapshots"
    )
    assert call_lines(collect, "seal") == [] and call_lines(collect, "now") == []
    for attr in ("audit", "custody", "status"):
        assert call_lines(tree, attr) == []  # only bound readers passed to the seam
    # Static references only (direct call or bound method passed to a guard); execution
    # order is proven by the owner records in H1 and the refreshed fence in H9.
    referenced = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert {"seal", "settle", "begin_audit", "begin_dispose", "close"} <= referenced


def test_h16_this_module_never_calls_the_native_binding() -> None:
    hr = host_run_module()
    assert callable(vars(hr)["_collect_snapshots"])
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    names = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not any(name.endswith("bind_proactor_pump") for name in names)


# ---------------------------------------------------------------- redaction


def test_reprs_of_inputs_report_and_custody_are_redacted(core: Any) -> None:
    hr = host_run_module()
    k = make_kit(hr, core, KitSpec())
    report = hr.run_host(k.inputs, k.custody)
    texts = [repr(k.inputs), repr(k.inputs.windows), repr(report), repr(k.custody)]
    texts.extend(repr(fault) for fault in report.faults)
    assert all(secret not in text for text in texts for secret in pt.SECRET_TEXTS)
    assert all("<redacted>" in text for text in texts[:4])
