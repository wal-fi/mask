"""Additive oracles for the private bind helper (PROACTOR-BIND-DESIGN B2 + BIND-REVIEW B4).

Contract for the FUTURE private ``_bind_over(loop_class, *, pipe, devnull, ident)`` in
``docs/poc/oracle9_w1_proactor_pump.py``. The helper is ABSENT until the root reviews
these oracles and freezes RED; it is loaded lazily as the FIRST step of each feature case
(``load_helper()``), never inside ``pytest.raises`` or a control catch, so its absence
fails per case and never lets a negative oracle pass. ``test_sanity_*`` cases never load
it: they validate only the retention witness of this file over its own synthetic frames.

Only fake loop classes (subclasses of the frozen ``FakeLoop``) are used. The public
``bind_proactor_pump`` is NEVER called and no SDK is imported: its platform / main-thread
/ running-loop refusals and the real construction/close effects belong to a separate,
unprepared native gate. One explicit ``close()`` counted on a fake is a call attempt, not
physical release. The retention oracle (B4) proves only that a received throwable keeps
the exact known synthetic loop alive through the helper's own frame; the future caller's
obligation to keep that throwable is prospective and is not a native cleanup claim.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium, from accepted B2 and B4.
V2 applies BIND-TEST-REVIEW BT1-BT3: a contaminating caller frame really present in the
received traceback, the named-fault x close x context matrix, and static fixes.
Senff policy: AI-generated tests require human and security review before merge.
"""

from __future__ import annotations

import ast
import types
import weakref
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

import pytest

from tests import test_oracle9_w1_proactor_pump as pt

MAX_TRACEBACK_FRAMES = 64
THIS_FILE = Path(__file__)
# Fixture label -> expected primary category, fixed independently of fixture branches.
PRIMARY_KIND: dict[str, str] = {
    "fault-task-factory": "fault",
    "fault-ident-exception": "fault",
    "fault-loop-running": "fault",
    "fault-foreign-type": "fault",
    "control-ident": "control",
}
CLOSE_OUTCOMES = ("close-ok", "close-exception", "close-control")
CONTEXT_MODES = ("fresh-context", "preexisting-context")


# ---------------------------------------------------------------- lazy helper loading


def load_helper() -> tuple[Any, Callable[..., Any]]:
    """FIRST step of every feature case; never inside pytest.raises or a control catch."""
    pm = pt.pump_module()
    helper: Callable[..., Any] = vars(pm)["_bind_over"]
    return pm, helper


def catch_any(call: Callable[[], object]) -> BaseException | None:
    """Returns the exact raised throwable (Exception or control), never inspecting it."""
    try:
        call()
    except BaseException as error:
        return error
    return None


def owner_ident() -> int:
    return pt.OWNER_THREAD


# ---------------------------------------------------------------- retention witness (B4)


def helper_frames_hold(throwable: BaseException, code: types.CodeType, known: object) -> bool:
    """True iff a frame whose code IS ``code`` holds ``known`` by identity in its locals.

    Walks at most MAX_TRACEBACK_FRAMES traceback entries of the RECEIVED throwable; frames of
    any other code (test, caller, fake, SDK) are never inspected, so a strong reference
    kept elsewhere can never satisfy it. No f_globals, GC, finalizer or mutation.
    """
    entry = throwable.__traceback__
    walked = 0
    while entry is not None and walked < MAX_TRACEBACK_FRAMES:
        walked += 1
        frame = entry.tb_frame
        if frame.f_code is code and any(value is known for value in frame.f_locals.values()):
            return True
        entry = entry.tb_next
    return False


class SyntheticError(Exception):
    """Sanity-only throwable raised by the synthetic helpers below."""


class SyntheticResource:
    """Sanity-only object standing for a known loop."""


def synthetic_keep(made: list[SyntheticResource]) -> None:
    _held_resource = SyntheticResource()
    made.append(_held_resource)
    raise SyntheticError  # outside any except: the frame keeps its local


def synthetic_drop(made: list[SyntheticResource]) -> None:
    _held_resource = SyntheticResource()
    made.append(_held_resource)
    del _held_resource
    raise SyntheticError


def synthetic_deep(depth: int, made: list[SyntheticResource]) -> None:
    if depth == 0:
        synthetic_keep(made)
        return
    synthetic_deep(depth - 1, made)


def test_sanity_retention_witness_accepts_the_helper_frame_reference() -> None:
    made: list[SyntheticResource] = []
    held = catch_any(lambda: synthetic_keep(made))
    assert type(held) is SyntheticError
    (known,) = made
    made.clear()
    assert helper_frames_hold(held, synthetic_keep.__code__, known) is True
    other = SyntheticResource()
    assert helper_frames_hold(held, synthetic_keep.__code__, other) is False


def test_sanity_retention_witness_rejects_deleted_reference_even_if_test_holds_it() -> None:
    made: list[SyntheticResource] = []
    held: BaseException | None = None
    try:  # caught HERE, so THIS frame is part of the received traceback
        synthetic_drop(made)
    except SyntheticError as error:
        held = error
    assert type(held) is SyntheticError
    known = made.pop()  # contaminant: THIS traceback frame now holds the exact object
    this_function = test_sanity_retention_witness_rejects_deleted_reference_even_if_test_holds_it
    # Presence proof: given THIS frame's own code, the finder does reach the contaminant.
    assert helper_frames_hold(held, this_function.__code__, known) is True
    # Retention check with the HELPER code: the helper deleted its reference, so the
    # contaminating caller frame in the same traceback must NOT satisfy it.
    assert helper_frames_hold(held, synthetic_drop.__code__, known) is False


def test_sanity_retention_witness_is_bounded_to_64_traceback_entries() -> None:
    made: list[SyntheticResource] = []
    held = catch_any(lambda: synthetic_deep(MAX_TRACEBACK_FRAMES + 8, made))
    assert type(held) is SyntheticError
    (known,) = made
    assert helper_frames_hold(held, synthetic_keep.__code__, known) is False  # beyond bound
    near = catch_any(lambda: synthetic_deep(8, made))
    assert type(near) is SyntheticError
    assert helper_frames_hold(near, synthetic_keep.__code__, made[-1]) is True


# ---------------------------------------------------------------- synthetic loop classes


@dataclass
class LoopSpec:
    """Behavior of one synthetic loop class; ``born`` keeps WEAK references only."""

    born: list[weakref.ref[pt.FakeLoop]] = field(default_factory=list)
    init_failure: BaseException | None = None
    task_factory: object = None
    close_fault: BaseException | None = None
    foreign: bool = False
    report_running: bool = False  # public is_running() answers True; close stays scripted
    news: list[str] = field(default_factory=list)


def configure(loop: pt.FakeLoop, spec: LoopSpec) -> None:
    loop.task_factory = spec.task_factory
    loop.close_fault = spec.close_fault
    spec.born.append(weakref.ref(loop))


def loop_class_for(spec: LoopSpec) -> type[pt.FakeLoop]:
    class ForeignLoop(pt.FakeLoop):
        """A different class returned by the factory (F2)."""

    class ProbeLoop(pt.FakeLoop):
        def __new__(cls) -> Any:
            spec.news.append("new")
            if spec.foreign:
                other = ForeignLoop()
                configure(other, spec)
                return other
            return super().__new__(cls)

        def __init__(self) -> None:
            if spec.init_failure is not None:
                raise spec.init_failure
            super().__init__()
            configure(self, spec)

        def is_running(self) -> bool:
            # FakeLoop.close() refuses while ``running`` is set, so the named fault
            # "loop running" is reported through the public query only.
            return spec.report_running or super().is_running()

    return ProbeLoop


def bind_call(
    helper: Callable[..., Any], loop_class: object, ident: Callable[[], object]
) -> Callable[[], Any]:
    def call() -> Any:
        return helper(loop_class, pipe=pt.FAKE_PIPE, devnull=pt.FAKE_DEVNULL, ident=ident)

    return call


def known_loop(spec: LoopSpec) -> pt.FakeLoop:
    (ref,) = spec.born
    loop = ref()
    assert loop is not None
    return loop


# ---------------------------------------------------------------- BD-1 positive


def test_bd1_class_factory_builds_configured_pump_without_close() -> None:
    pm, helper = load_helper()
    spec = LoopSpec()
    loop_class = loop_class_for(spec)
    pump = helper(loop_class, pipe=pt.FAKE_PIPE, devnull=pt.FAKE_DEVNULL, ident=owner_ident)
    assert type(pump) is pm.ProactorPump and spec.news == ["new"]
    loop = known_loop(spec)
    assert type(loop) is loop_class
    assert loop.debug is False and loop.entries("set_debug") == [("set_debug", False)]
    assert getattr(loop.handler, "__self__", None) is pump
    assert loop.count("loop.close") == 0  # success: the pump owns the loop, no close
    assert pump is not None  # success returns the owning pump, never None
    assert pump.now() == pt.T0
    assert pump.close() is True and loop.count("loop.close") == 1
    assert repr(pump) == "ProactorPump(<redacted>)"


# ---------------------------------------------------------------- BD-2 / BD-3 / BD-4


def test_bd2_non_class_factories_are_refused_without_any_construction() -> None:
    pm, helper = load_helper()
    calls: list[str] = []

    def factory_function() -> pt.FakeLoop:
        calls.append("called")
        return pt.FakeLoop()

    instance = pt.FakeLoop()
    for candidate in (instance, factory_function, None):
        raised = catch_any(bind_call(helper, candidate, owner_ident))
        assert raised is not None and type(raised) is pm.PumpFault
        pt.assert_pump_fault(pm, raised)
    assert calls == [] and instance.count("loop.close") == 0
    assert instance.count("set_debug") == 0 and instance.handler is None


def test_bd3_factory_exception_is_closed_fault_without_known_loop() -> None:
    pm, helper = load_helper()
    spec = LoopSpec(init_failure=OSError(pt.CANARY))
    raised = catch_any(bind_call(helper, loop_class_for(spec), owner_ident))
    assert raised is not None and type(raised) is pm.PumpFault
    pt.assert_pump_fault(pm, raised)
    assert spec.born == []  # F1: the factory returned nothing; no loop is known


def test_bd3_factory_control_passes_by_identity_without_known_loop() -> None:
    _pm, helper = load_helper()
    probes: list[str] = []
    control = pt.FalseCtl(probes)
    spec = LoopSpec(init_failure=control)
    raised = catch_any(bind_call(helper, loop_class_for(spec), owner_ident))
    assert raised is control
    assert control.__context__ is None and control.__cause__ is None
    assert spec.born == [] and probes == []


def test_bd4_foreign_returned_type_is_closed_once_and_retained_by_helper_frame() -> None:
    pm, helper = load_helper()
    spec = LoopSpec(foreign=True)
    loop_class = loop_class_for(spec)
    raised = catch_any(bind_call(helper, loop_class, owner_ident))
    assert raised is not None and type(raised) is pm.PumpFault
    pt.assert_pump_fault(pm, raised)
    loop = known_loop(spec)
    assert type(loop) is not loop_class
    assert loop.count("loop.close") == 1  # one EXPLICIT close attempt, not physical proof
    assert loop.count("set_debug") == 0  # never configured as a pump loop
    assert helper_frames_hold(raised, helper.__code__, loop) is True


# ---------------------------------------------------------------- BD-5 / BD-6 / BD-7 matrix


def raise_given(control: BaseException) -> NoReturn:
    raise control


def controlled(
    control: BaseException, context_mode: str
) -> tuple[BaseException, BaseException | None]:
    """Returns the control and its EXPECTED __context__, set only by normal Python raising."""
    if context_mode == "fresh-context":
        return control, None
    if context_mode != "preexisting-context":
        pytest.fail(f"unknown context mode {context_mode}")
    origin = LookupError("synthetic-context-origin")
    try:
        try:
            raise origin
        except LookupError:
            raise_given(control)  # Python records origin as control.__context__
    except BaseException as caught:
        assert caught is control
    assert control.__context__ is origin
    return control, origin


@dataclass
class MatrixCase:
    spec: LoopSpec
    ident: Callable[[], object]
    primary_control: BaseException | None
    primary_origin: BaseException | None
    close_control: BaseException | None
    close_origin: BaseException | None
    probes: list[str]


def matrix_case(primary: str, close: str, context_mode: str) -> MatrixCase:
    probes: list[str] = []
    spec = LoopSpec()
    ident: Callable[[], object] = owner_ident
    primary_control: BaseException | None = None
    primary_origin: BaseException | None = None
    if primary == "fault-task-factory":
        spec.task_factory = object()
    elif primary == "fault-ident-exception":
        ident = pt.raiser(OSError(pt.CANARY))
    elif primary == "fault-loop-running":
        spec.report_running = True
    elif primary == "fault-foreign-type":
        spec.foreign = True
    elif primary == "control-ident":
        primary_control, primary_origin = controlled(pt.BoomCtl(probes), context_mode)
        ident = pt.raiser(primary_control)
    else:
        pytest.fail(f"unknown primary fixture {primary}")
    close_control: BaseException | None = None
    close_origin: BaseException | None = None
    if close == "close-exception":
        spec.close_fault = OSError(pt.CANARY)
    elif close == "close-control":
        close_control, close_origin = controlled(pt.FalseCtl(probes), context_mode)
        spec.close_fault = close_control
    elif close != "close-ok":
        pytest.fail(f"unknown close fixture {close}")
    return MatrixCase(
        spec, ident, primary_control, primary_origin, close_control, close_origin, probes
    )


@pytest.mark.parametrize("context_mode", CONTEXT_MODES)
@pytest.mark.parametrize("close", CLOSE_OUTCOMES)
@pytest.mark.parametrize("primary", sorted(PRIMARY_KIND))
def test_bd5_bd6_bd7_primary_failure_crossed_with_close_outcome(
    primary: str, close: str, context_mode: str
) -> None:
    pm, helper = load_helper()
    case = matrix_case(primary, close, context_mode)
    raised = catch_any(bind_call(helper, loop_class_for(case.spec), case.ident))
    loop = known_loop(case.spec)
    assert loop.count("loop.close") == 1  # exactly one EXPLICIT close attempt
    kind = PRIMARY_KIND[primary]  # expectation independent of the fixture branch taken
    if kind == "control":
        assert case.primary_control is not None
        assert raised is case.primary_control  # the first control always wins (BD-6)
        assert case.primary_control.__context__ is case.primary_origin  # same context kept
    elif close == "close-control":
        assert kind == "fault" and case.close_control is not None
        assert raised is case.close_control  # a close control after a fault becomes first
    else:
        assert kind == "fault"
        assert raised is not None and type(raised) is pm.PumpFault
        pt.assert_pump_fault(pm, raised)  # no args/cause/context, no canary
    if case.close_control is not None:  # close ran outside the primary except
        assert case.close_control.__context__ is case.close_origin
    assert case.probes == []  # no truthiness probe on any control
    assert raised is not None
    assert helper_frames_hold(raised, helper.__code__, loop) is True  # BD-7 (B4)


@pytest.mark.parametrize("primary", sorted(PRIMARY_KIND))
def test_bd7_caller_frame_in_traceback_never_substitutes_helper_retention(primary: str) -> None:
    _pm, helper = load_helper()
    case = matrix_case(primary, "close-ok", "fresh-context")
    call = bind_call(helper, loop_class_for(case.spec), case.ident)
    raised: BaseException | None = None
    try:  # caught HERE: this frame is part of the received traceback
        call()
    except BaseException as error:
        raised = error
    assert raised is not None
    loop = known_loop(case.spec)  # contaminant: this traceback frame holds the exact loop
    this_function = test_bd7_caller_frame_in_traceback_never_substitutes_helper_retention
    assert helper_frames_hold(raised, this_function.__code__, loop) is True  # presence proof
    assert helper_frames_hold(raised, helper.__code__, loop) is True  # the helper's own frame
    assert helper_frames_hold(raised, helper.__code__, pt.FakeLoop()) is False
    assert case.probes == []


# ---------------------------------------------------------------- BD-8 wrapper wiring (AST only)


def pump_tree() -> ast.Module:
    return ast.parse(pt.PUMP_FILE.read_text(encoding="utf-8"))


def top_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    pytest.fail(f"top-level function {name} not found")


def first_line(func: ast.FunctionDef, text: str) -> int:
    lines = [n.lineno for n in ast.walk(func) if isinstance(n, ast.expr) and ast.unparse(n) == text]
    assert lines, f"{text} not found"
    return min(lines)


def test_bd8_helper_signature_and_wrapper_minimum_wiring() -> None:
    _pm, helper = load_helper()
    assert callable(helper)
    tree = pump_tree()
    bind_over = top_function(tree, "_bind_over")
    assert [a.arg for a in (*bind_over.args.posonlyargs, *bind_over.args.args)] == ["loop_class"]
    assert [a.arg for a in bind_over.args.kwonlyargs] == ["pipe", "devnull", "ident"]
    assert not [n for n in ast.walk(bind_over) if isinstance(n, (ast.Import, ast.ImportFrom))]
    wrapper = top_function(tree, "bind_proactor_pump")
    imported = {
        alias.name for n in ast.walk(wrapper) if isinstance(n, ast.Import) for alias in n.names
    }
    assert {"asyncio", "subprocess", "sys", "threading"} <= imported
    calls = [
        n
        for n in ast.walk(wrapper)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_bind_over"
    ]
    assert len(calls) == 1
    (call,) = calls
    assert [ast.unparse(a) for a in call.args] == ["asyncio.ProactorEventLoop"]
    assert {k.arg: ast.unparse(k.value) for k in call.keywords} == {
        "pipe": "subprocess.PIPE",
        "devnull": "subprocess.DEVNULL",
        "ident": "threading.get_ident",
    }
    for preflight in ("sys.platform", "threading.main_thread()", "asyncio.get_running_loop()"):
        assert first_line(wrapper, preflight) < call.lineno
    constructed = [
        n
        for n in ast.walk(wrapper)
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "asyncio.ProactorEventLoop"
    ]
    assert constructed == []  # construction happens only inside the helper


def test_bd8_this_module_never_calls_the_real_binding() -> None:
    _pm, helper = load_helper()
    assert callable(helper)
    tree = ast.parse(THIS_FILE.read_text(encoding="utf-8"))
    names = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not any(name.endswith("bind_proactor_pump") for name in names)
