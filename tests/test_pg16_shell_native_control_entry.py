"""Fake-only tests for the private, uninvoked native control entry.

The real runner run() is never called. Only the entry's own seams are
replaced (_read_runner, _execute, _install, _pids, _pause, and a counting
_hold tripwire). Held logic is tested through finite units only; main is
called only on paths that must exit. The production catches are not weakened
for tests: a parking regression on such a path would loop, never pass. The
actual infinite hold loop is checked by AST. No real signal handler,
WinDLL, process, thread, directory creation or .venv read.
"""

import ast
import builtins
import ctypes
import gc
import hashlib
import json
import os
import runpy
import signal
import subprocess
import threading
import weakref
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
ENTRY = REPO / "docs/poc/pg16_shell_native_control_entry.py"
RUNNER = REPO / "docs/poc/pg16_shell_native_control.py"
RUNNER_SHA = "b4198fe1606120e1e2df4fe9bff6a52fce4601a67074fdd7e922ef528341a496"
NONCE = "0123456789abcdef0123456789abcdef"
FAKE_RAW = b"# fictitious runner bytes\n"
SUMMARY_KIND = "MASKGW_PG16_NATIVE_CONTROL_SUMMARY_V1"
CASE_NAMES = ("NORMAL", "TERMINATE", "LAST_CLOSE")
CODES = frozenset(
    (
        "CONTROL_PERSISTENCE",
        "CONTROL_COMMIT_INDETERMINATE",
        "CONTROL_HELD",
        "CONTROL_RETAINED",
        "CONTROL_NONCE",
    )
)
CHILD_PID = 4242
EVENT_KEYS = {
    "IDENTITY": {"kind", "event", "nonce12", "controller_pid", "parent_pid"},
    "FINAL": {"kind", "event", "nonce12", "controller_pid", "code", "outcome", "refusal"},
    "PARKED": {"kind", "event", "nonce12", "controller_pid", "reason", "retained"},
}


class Signal(BaseException):
    """A fictitious control interruption."""


class Tripwire(BaseException):
    """Raised by the test-only _hold replacement: parking on a positive path."""


class FakeRunError(Exception):
    pass


class Owner:
    """A weakref-able stand-in for a retained owner (exact list/dict are not)."""

    pid = CHILD_PID


class World:
    def __init__(self) -> None:
        self.live: Any = []
        self.calls: list[Any] = []
        self.installs: list[Any] = []
        self.result: Any = None
        self.raised: Any = None
        self.before_live: Any = None
        self.after_live: Any = None
        self.during: Any = None
        self.namespace: Any = None
        self.keep: Any = None
        self.executed = 0
        self.pauses = 0
        self.held = 0
        self.pause_error: Any = None
        self.armed = False
        self.post_io: list[str] = []

    def execute(self, raw: bytes, namespace: Any) -> None:
        self.executed += 1
        assert raw == FAKE_RAW
        assert any(item is namespace for item in self.keep)  # held before exec
        self.namespace = namespace
        if self.before_live is not None:
            raise self.before_live
        namespace["_LIVE"] = self.live
        namespace["RunError"] = FakeRunError
        namespace["CODES"] = CODES
        namespace["run"] = self.run
        if self.after_live is not None:
            raise self.after_live

    def run(self, nonce: str) -> Any:
        self.calls.append((nonce, tuple(self.installs)))
        if self.during is not None:
            self.during(self)
        self.armed = True  # from here no filesystem I/O is allowed
        if self.raised is not None:
            raise self.raised
        return self.result

    def pause(self, _seconds: float) -> None:
        self.pauses += 1
        if self.pause_error is not None:
            raise self.pause_error


def summary(outcome: str = "APPROVED", labels: Any = None) -> Any:
    if labels is None:
        labels = ["APPROVED"] * 3 if outcome == "APPROVED" else ["REJECTED", "NOT_RUN", "NOT_RUN"]
    return {
        "kind": SUMMARY_KIND,
        "nonce": NONCE,
        "outcome": outcome,
        "scope": "BENIGN_CONTROL_ONLY",
        "admission_3s": "NOT_MEASURED",
        "cases": [
            {"case": name, "outcome": label} for name, label in zip(CASE_NAMES, labels, strict=True)
        ],
    }


def no_runtime_read(real: Any) -> Any:
    def guard(self: Path, *args: Any, **kwargs: Any) -> Any:
        if ".venv" in self.parts:
            raise AssertionError("runtime read attempted")
        return real(self, *args, **kwargs)

    return guard


def recorder(world: World, name: str, real: Any) -> Any:
    def spy(*args: Any, **kwargs: Any) -> Any:
        if world.armed:
            world.post_io.append(name)
        return real(*args, **kwargs)

    return spy


@pytest.fixture
def lab(monkeypatch: Any) -> Any:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("native, process, thread, signal or directory effect attempted")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(threading.Thread, "start", forbidden)
    monkeypatch.setattr(signal, "signal", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(os, "mkdir", forbidden)
    monkeypatch.setattr(os, "makedirs", forbidden)
    for name in ("open", "lstat", "stat"):
        monkeypatch.setattr(Path, name, no_runtime_read(getattr(Path, name)))
    module = runpy.run_path(str(ENTRY))
    glob = module["main"].__globals__
    world = World()
    world.keep = glob["KEEP"]

    def install(signum: Any, handler: Any) -> None:
        world.installs.append((signum, handler))

    def hold() -> None:
        world.held += 1
        raise Tripwire()

    # Seams of this module copy only; the real run() is never reachable.
    monkeypatch.setitem(glob, "_read_runner", lambda: FAKE_RAW)
    monkeypatch.setitem(glob, "_execute", world.execute)
    monkeypatch.setitem(glob, "_install", install)
    monkeypatch.setitem(glob, "_pids", lambda: (111, 222))
    monkeypatch.setitem(glob, "_pause", world.pause)
    monkeypatch.setitem(glob, "_hold", hold)
    return type("Lab", (), {"module": module, "glob": glob, "world": world})


def events(capsys: Any) -> list[Any]:
    captured = capsys.readouterr()
    assert captured.err == ""
    lines = [line for line in captured.out.split("\n") if line]
    parsed = [json.loads(line) for line in lines]
    for line, record in zip(lines, parsed, strict=True):
        assert line.isascii()
        assert set(record) == EVENT_KEYS[record["event"]]
        assert record["kind"] == "MASKGW_PG16_NATIVE_CONTROL_ENTRY_V1"
    return parsed


def first_pass(lab: Any) -> Any:
    """The finite part of the driver: one forward pass and one settle."""
    progress = lab.glob["_progress"](NONCE)
    decision = lab.glob["_advance"](progress, FAKE_RAW)
    return progress, decision, lab.glob["settle"](decision, progress)


def kept(lab: Any, item: Any) -> bool:
    return any(entry is item for entry in lab.glob["KEEP"])


def spy_io(lab: Any, monkeypatch: Any) -> None:
    world = lab.world
    for name in ("open", "lstat", "stat", "iterdir", "exists", "unlink", "rmdir"):
        monkeypatch.setattr(Path, name, recorder(world, "Path." + name, getattr(Path, name)))
    for name in ("open", "stat", "lstat", "listdir", "scandir", "remove", "replace", "rename"):
        monkeypatch.setattr(os, name, recorder(world, "os." + name, getattr(os, name)))
    monkeypatch.setattr(builtins, "open", recorder(world, "open", builtins.open))


# -- import, S0 and S1 -----------------------------------------------------------------


def test_import_is_pure(monkeypatch: Any) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("effect at import")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "lstat", forbidden)
    monkeypatch.setattr(signal, "signal", forbidden)
    module = runpy.run_path(str(ENTRY))
    assert module["KEEP"] == []
    assert module["_STATE"] == {
        "active": False,
        "parked": False,
        "announced": False,
        "attempted": False,
    }


@pytest.mark.parametrize(
    "argv",
    [[], [NONCE, NONCE], [NONCE.upper()], [NONCE[:-1]], [NONCE + "\n"], [NONCE.encode()], None],
)
def test_bad_arguments_are_pure_refusals(lab: Any, capsys: Any, argv: Any) -> None:
    def never() -> Any:
        raise AssertionError("read before argument validation")

    lab.glob["_read_runner"] = never
    code = lab.glob["main"](argv)
    assert type(code) is int and code == 2
    (final,) = events(capsys)
    assert (final["event"], final["refusal"], final["nonce12"]) == ("FINAL", "ENTRY_ARGV", None)
    assert final["controller_pid"] is None and final["outcome"] == "REFUSED"
    assert lab.glob["KEEP"] == [] and lab.world.installs == [] and lab.world.executed == 0


def test_source_refusal_creates_no_namespace(lab: Any, capsys: Any) -> None:
    lab.glob["_read_runner"] = lambda: None
    assert lab.glob["main"]([NONCE]) == 2
    (final,) = events(capsys)
    assert (final["refusal"], final["nonce12"]) == ("ENTRY_SOURCE", NONCE[:12])
    assert lab.glob["KEEP"] == [] and lab.world.executed == 0 and lab.world.installs == []


def test_real_pinned_loader_defines_runner_without_calling_run(lab: Any) -> None:
    raw = lab.module["_read_runner"]()
    assert type(raw) is bytes and hashlib.sha256(raw).hexdigest() == RUNNER_SHA
    assert hashlib.sha256(RUNNER.read_bytes()).hexdigest() == RUNNER_SHA
    assert lab.glob["RUNNER"][1] == RUNNER_SHA
    namespace: dict[str, Any] = {"__name__": "_entry_loader_test", "__file__": str(RUNNER)}
    lab.module["_execute"](raw, namespace)  # definitions only; run is never called
    assert type(namespace["_LIVE"]) is list and namespace["_LIVE"] == []
    assert callable(namespace["run"]) and issubclass(namespace["RunError"], Exception)


def test_real_loader_refuses_a_different_pin(lab: Any, monkeypatch: Any) -> None:
    monkeypatch.setitem(lab.glob, "RUNNER", (lab.glob["RUNNER"][0], "0" * 64))
    assert lab.module["_read_runner"]() is None


# -- positive exits with a trusted empty registry -------------------------------------


@pytest.mark.parametrize(("outcome", "expected"), [("APPROVED", 0), ("REJECTED", 1)])
def test_returned_summary_exits_with_exact_code(
    lab: Any, capsys: Any, monkeypatch: Any, outcome: str, expected: int
) -> None:
    spy_io(lab, monkeypatch)
    lab.world.result = summary(outcome)
    code = lab.glob["main"]([NONCE])
    observed, lab.world.armed = list(lab.world.post_io), False
    assert type(code) is int and code == expected
    assert observed == []  # no filesystem I/O after the runner call
    identity, final = events(capsys)
    assert identity == {
        "kind": "MASKGW_PG16_NATIVE_CONTROL_ENTRY_V1",
        "event": "IDENTITY",
        "nonce12": NONCE[:12],
        "controller_pid": 111,
        "parent_pid": 222,
    }
    assert (final["code"], final["outcome"], final["refusal"]) == (expected, outcome, None)
    assert final["controller_pid"] == 111
    # Exactly one call, after both handlers were installed.
    assert len(lab.world.calls) == 1
    nonce, installs = lab.world.calls[0]
    assert nonce == NONCE
    handler = lab.glob["_on_console"]
    assert installs == ((signal.SIGINT, handler), (signal.SIGBREAK, handler))
    assert kept(lab, lab.world.namespace) and kept(lab, lab.world.live)
    assert lab.glob["_STATE"]["parked"] is False and lab.glob["_STATE"]["active"] is False


@pytest.mark.parametrize(
    "result",
    [
        None,
        True,
        1,
        {"outcome": "APPROVED"},
        {**summary(), "kind": "OTHER"},
        {**summary(), "scope": "ADMISSION"},
        {**summary(), "admission_3s": "WITHIN_3S"},
        {**summary(), "cases": summary()["cases"][:2]},
        summary("APPROVED", ["APPROVED", "REJECTED", "NOT_RUN"]),
        summary("REJECTED", ["APPROVED", "APPROVED", "APPROVED"]),
        {**summary(), "outcome": True},
    ],
)
def test_malformed_returned_result_never_approves(lab: Any, capsys: Any, result: Any) -> None:
    lab.world.result = result
    assert lab.glob["main"]([NONCE]) == 2
    final = events(capsys)[-1]
    assert (final["code"], final["outcome"], final["refusal"]) == (2, "REFUSED", "ENTRY_RESULT")


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (FakeRunError("CONTROL_PERSISTENCE"), (2, "REFUSED", "CONTROL_PERSISTENCE")),
        (FakeRunError("CONTROL_COMMIT_INDETERMINATE"), (4, "COMMIT_INDETERMINATE", None)),
        (FakeRunError("CONTROL_UNLISTED"), (2, "REFUSED", "ENTRY_INTERNAL")),
        (FakeRunError(7), (2, "REFUSED", "ENTRY_INTERNAL")),
        (ValueError("secret-detail"), (2, "REFUSED", "ENTRY_INTERNAL")),
        (Signal("secret-detail"), (5, "INTERRUPTED", None)),
    ],
)
def test_raised_outcomes_with_empty_registry(
    lab: Any, capsys: Any, raised: Any, expected: Any
) -> None:
    code, outcome, refusal = expected
    lab.world.raised = raised
    assert lab.glob["main"]([NONCE]) == code
    out = capsys.readouterr().out
    assert "secret-detail" not in out and str(REPO) not in out
    final = json.loads(out.strip().split("\n")[-1])
    assert (final["code"], final["outcome"], final["refusal"]) == (code, outcome, refusal)
    assert kept(lab, raised)  # the original is held, by identity
    assert len(lab.world.calls) == 1


def test_console_control_during_run_is_an_interruption(lab: Any, capsys: Any) -> None:
    def press(world: World) -> None:
        world.installs[0][1](signal.SIGINT, None)

    lab.world.during = press
    lab.world.result = summary()
    assert lab.glob["main"]([NONCE]) == 5
    assert events(capsys)[-1]["outcome"] == "INTERRUPTED"
    handler = lab.world.installs[1][1]
    assert handler(signal.SIGBREAK, None) is None  # inactive again after the call


# -- S2 and S3 ------------------------------------------------------------------------


def test_load_failure_with_trusted_empty_registry_refuses(lab: Any, capsys: Any) -> None:
    lab.world.after_live = ValueError("secret-detail")
    assert lab.glob["main"]([NONCE]) == 2
    final = events(capsys)[-1]
    assert final["refusal"] == "ENTRY_LOAD" and lab.world.calls == []
    assert lab.world.installs == []


def test_interrupt_during_load_with_trusted_empty_registry_refuses(lab: Any, capsys: Any) -> None:
    lab.world.after_live = Signal("load")
    assert lab.glob["main"]([NONCE]) == 2
    assert events(capsys)[-1]["refusal"] == "ENTRY_INTERRUPTED"
    assert lab.world.executed == 1 and lab.world.calls == []


@pytest.mark.parametrize("live", ["missing", "tuple", "non-empty", "error-before"])
def test_unknown_registry_at_load_parks(lab: Any, capsys: Any, live: str) -> None:
    owner = Owner()
    if live == "missing":
        lab.world.live = None
        lab.world.before_live = ValueError("partial")
    elif live == "tuple":
        lab.world.live = ()
    elif live == "non-empty":
        lab.world.live = [owner]
    else:
        lab.world.before_live = ValueError("partial")
    progress, _decision, verdict = first_pass(lab)
    assert verdict[0] == "PARK" and lab.glob["_STATE"]["parked"] is True
    assert lab.world.calls == [] and lab.world.installs == []
    assert kept(lab, progress["namespace"])
    (parked,) = events(capsys)
    assert parked["event"] == "PARKED" and parked["reason"] == "UNKNOWN_REGISTRY"
    assert parked["retained"] == (1 if live == "non-empty" else None)


def test_interrupt_before_registry_definition_parks_without_reexecution(
    lab: Any, capsys: Any
) -> None:
    signal_object = Signal("partial")
    lab.world.before_live = signal_object
    progress = lab.glob["_progress"](NONCE)
    with pytest.raises(Signal):
        lab.glob["_advance"](progress, FAKE_RAW)
    lab.glob["_fault"](progress, signal_object)
    decision = lab.glob["_advance"](progress, FAKE_RAW)
    assert lab.glob["settle"](decision, progress)[0] == "PARK"
    assert lab.world.executed == 1 and lab.world.calls == []
    assert kept(lab, signal_object) and kept(lab, progress["namespace"])
    assert events(capsys)[-1]["reason"] == "UNKNOWN_REGISTRY"


def test_handler_install_failure_never_reaches_run(lab: Any, capsys: Any) -> None:
    def failing(_signum: Any, _handler: Any) -> None:
        raise ValueError("not main thread")

    lab.glob["_install"] = failing
    assert lab.glob["main"]([NONCE]) == 2
    assert events(capsys)[-1]["refusal"] == "ENTRY_ARM" and lab.world.calls == []


def test_identity_write_failure_never_reaches_run(lab: Any, capsys: Any) -> None:
    real = lab.glob["_emit"]

    def broken(record: Any) -> None:
        if record["event"] == "IDENTITY":
            raise OSError("broken pipe")
        real(record)

    lab.glob["_emit"] = broken
    assert lab.glob["main"]([NONCE]) == 2
    assert events(capsys)[-1]["refusal"] == "ENTRY_ARM" and lab.world.calls == []


# -- retained or unknown ownership parks, sticky --------------------------------------


def retain(world: World) -> Owner:
    owner = Owner()
    world.live.append(owner)
    return owner


@pytest.mark.parametrize(
    ("label", "reason"),
    [
        ("held", "HELD"),
        ("interrupted", "INTERRUPTED"),
        ("returned", "INTERNAL"),
        ("replaced", "UNKNOWN_REGISTRY"),
        ("held-empty", "HELD"),
        ("retained-code", "HELD"),
    ],
)
def test_retained_or_unknown_ownership_parks(
    lab: Any, capsys: Any, monkeypatch: Any, label: str, reason: str
) -> None:
    spy_io(lab, monkeypatch)
    world = lab.world
    holder: list[Any] = []

    def during(item: World) -> None:
        if label in ("held", "interrupted", "returned", "replaced"):
            holder.append(weakref.ref(retain(item)))
        if label == "replaced":
            item.namespace["_LIVE"] = []

    world.during = during
    world.result = summary()
    if label in ("held", "held-empty"):
        world.raised = FakeRunError("CONTROL_HELD")
    elif label == "retained-code":
        world.raised = FakeRunError("CONTROL_RETAINED")
    elif label == "interrupted":
        world.raised = Signal("original")
    original = world.live
    progress, _decision, verdict = first_pass(lab)
    observed, world.armed = list(world.post_io), False
    assert verdict == ("PARK", reason) and lab.glob["_STATE"]["parked"] is True
    assert observed == []
    assert len(world.calls) == 1
    assert kept(lab, original) and progress["live"] is original
    if world.raised is not None:
        assert kept(lab, world.raised)
    if holder:
        gc.collect()
        assert holder[0]() is not None  # retained owner still alive
    (identity, parked) = events(capsys)
    assert identity["event"] == "IDENTITY" and parked["reason"] == reason
    if label in ("held", "interrupted", "returned"):
        assert parked["retained"] == 1
    # Sticky: no later decision, registry change or helper result exits.
    world.live.clear()
    assert lab.glob["settle"](("EXIT", 0, "APPROVED"), progress)[0] == "PARK"
    assert lab.glob["_advance"](progress, FAKE_RAW)[0] == "PARK"
    assert len(world.calls) == 1 and capsys.readouterr().out == ""


def test_reserved_attempt_is_never_retried(lab: Any) -> None:
    lab.glob["_STATE"]["attempted"] = True  # reserved, then interrupted before the call
    progress, decision, verdict = first_pass(lab)
    assert lab.world.calls == []
    assert decision == ("EXIT", 5, "INTERRUPTED") and verdict == decision
    lab.glob["_advance"](progress, FAKE_RAW)
    assert lab.world.calls == []


def test_completed_main_never_calls_run_again(lab: Any) -> None:
    lab.world.result = summary()
    assert lab.glob["main"]([NONCE]) == 0
    progress = lab.glob["_progress"](NONCE)
    lab.glob["_advance"](progress, FAKE_RAW)
    assert len(lab.world.calls) == 1


@pytest.mark.parametrize(
    "decision",
    [
        ("EXIT", True, "APPROVED"),
        ("EXIT", 3, "APPROVED"),
        ("EXIT", 0),
        ("EXIT", 0.0, "APPROVED"),
        "EXIT",
        None,
        ("PARK", "OTHER"),
    ],
)
def test_malformed_decisions_park(lab: Any, capsys: Any, decision: Any) -> None:
    lab.world.result = summary()
    progress = lab.glob["_progress"](NONCE)
    lab.glob["_advance"](progress, FAKE_RAW)
    capsys.readouterr()
    assert lab.glob["settle"](decision, progress) == ("PARK", "INTERNAL")
    assert lab.glob["_STATE"]["parked"] is True
    assert [record["event"] for record in events(capsys)] == ["PARKED"]


def test_exit_is_revalidated_against_the_original_registry(lab: Any) -> None:
    lab.world.result = summary()
    progress = lab.glob["_progress"](NONCE)
    decision = lab.glob["_advance"](progress, FAKE_RAW)
    assert decision == ("EXIT", 0, "APPROVED")
    lab.world.live.append(Owner())  # changed after the decision
    assert lab.glob["settle"](decision, progress)[0] == "PARK"


def test_broken_park_announcement_keeps_parking(lab: Any) -> None:
    def broken(_record: Any) -> None:
        raise OSError("broken pipe")

    lab.world.raised = FakeRunError("CONTROL_HELD")
    progress = lab.glob["_progress"](NONCE)
    decision = lab.glob["_advance"](progress, FAKE_RAW)
    lab.glob["_emit"] = broken
    assert lab.glob["settle"](decision, progress) == ("PARK", "HELD")
    assert lab.glob["_STATE"]["parked"] is True and lab.glob["_STATE"]["announced"] is True


def test_decide_is_total_for_uninspectable_state(lab: Any) -> None:
    progress = lab.glob["_progress"](NONCE)
    progress["namespace"] = object()
    assert lab.glob["decide"](progress)[0] == "PARK"


# -- console handler and cycle ----------------------------------------------------------


def test_handler_raises_only_while_active(lab: Any, capsys: Any) -> None:
    handler = lab.glob["_on_console"]
    before = dict(lab.glob["_STATE"])
    assert handler(signal.SIGINT, None) is None and handler(signal.SIGBREAK, None) is None
    assert lab.glob["_STATE"] == before and capsys.readouterr().out == ""
    lab.glob["_STATE"]["active"] = True
    with pytest.raises(KeyboardInterrupt):
        handler(signal.SIGBREAK, None)


@pytest.mark.parametrize("error", [None, Signal("ctrl"), MemoryError(), KeyboardInterrupt()])
def test_cycle_is_one_pause_and_swallows(lab: Any, error: Any) -> None:
    lab.world.pause_error = error
    assert lab.glob["cycle"]() is None
    assert lab.world.pauses == 1


# -- structure of the protected driver (never executed in held mode) --------------------


def entry_tree() -> Any:
    return ast.parse(ENTRY.read_bytes())


def function(tree: Any, name: str) -> Any:
    return next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_hold_and_driver_structure() -> None:
    tree = entry_tree()
    hold = function(tree, "_hold")
    assert not any(isinstance(node, (ast.Return, ast.Break)) for node in ast.walk(hold))
    loops = [node for node in ast.walk(hold) if isinstance(node, ast.While)]
    assert loops and all(ast.unparse(loop.test) == "True" for loop in loops)
    drive = function(tree, "_drive")
    returns = [node for node in ast.walk(drive) if isinstance(node, ast.Return)]
    assert len(returns) == 1
    guards = [
        ast.unparse(node.test)
        for node in ast.walk(drive)
        if isinstance(node, ast.If) and any(item is returns[0] for item in ast.walk(node))
    ]
    assert any(
        "not _STATE['parked']" in guard and "_trusted(progress)" in guard for guard in guards
    )
    outer = [node for node in drive.body if isinstance(node, ast.While)]
    assert len(outer) == 1 and ast.unparse(outer[0].test) == "True"
    handlers = [node for node in ast.walk(outer[0]) if isinstance(node, ast.ExceptHandler)]
    assert any(ast.unparse(node.type) == "BaseException" for node in handlers if node.type)


def test_latches_run_call_and_forbidden_names() -> None:
    tree = entry_tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "_STATE"
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value in ("parked", "attempted", "announced")
                ):
                    assert isinstance(node.value, ast.Constant) and node.value.value is True
    run_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Subscript)
        and isinstance(node.func.slice, ast.Constant)
        and node.func.slice.value == "run"
    ]
    assert len(run_calls) == 1
    assert any(item is run_calls[0] for item in ast.walk(function(tree, "_invoke")))
    invokes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_invoke"
    ]
    assert len(invokes) == 1
    assert any(item is invokes[0] for item in ast.walk(function(tree, "_advance")))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imported & {"traceback", "threading", "subprocess", "ctypes", "logging"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not names & {"input", "_forever"} and "stdin" not in attributes
    assert not attributes & {"alarm", "setitimer", "Timer", "monotonic"}
    mains = [
        node
        for node in tree.body
        if isinstance(node, ast.If) and "__main__" in ast.unparse(node.test)
    ]
    assert len(mains) == 1 and len(mains[0].body) == 1
    assert ast.unparse(mains[0].body[0]) == "raise SystemExit(main(sys.argv[1:]))"


# -- regressions for the review of entry a3620eba (written before any fix) --------------


class FragileKeep(list[Any]):
    """KEEP replacement: recording any exception object fails (models an
    allocation failure, or a control or ordinary failure, while recording)."""

    def __init__(self, failure: BaseException) -> None:
        super().__init__()
        self.failure = failure

    def append(self, item: Any) -> None:
        if isinstance(item, BaseException):
            raise self.failure
        super().append(item)


def fragile(lab: Any, monkeypatch: Any, failure: BaseException) -> FragileKeep:
    keep = FragileKeep(failure)
    monkeypatch.setitem(lab.glob, "KEEP", keep)
    lab.world.keep = keep
    return keep


def test_original_control_is_captured_before_fallible_recording(lab: Any, monkeypatch: Any) -> None:
    fragile(lab, monkeypatch, MemoryError())
    original = Signal("original")
    lab.world.during = retain
    lab.world.raised = original
    progress = lab.glob["_progress"](NONCE)
    decision = lab.glob["_advance"](progress, FAKE_RAW)  # must not raise
    # The entry-owned progress, not only the fake world, holds the original.
    assert progress["outcome"][0] == "RAISED" and progress["outcome"][1] is original
    assert decision == ("PARK", "INTERRUPTED")
    assert lab.glob["settle"](decision, progress) == ("PARK", "INTERRUPTED")
    assert lab.glob["_STATE"]["parked"] is True
    assert type(progress["live"]) is list and len(progress["live"]) == 1


@pytest.mark.parametrize(
    "failure", [ValueError("ordinary"), Signal("control"), MemoryError()], ids=str
)
def test_fault_recording_never_raises(lab: Any, monkeypatch: Any, failure: Any) -> None:
    fragile(lab, monkeypatch, failure)
    progress = lab.glob["_progress"](NONCE)
    first, later = Signal("first"), MemoryError()
    real_fault = lab.module["_fault"]
    real_fault(progress, first)  # must not raise
    real_fault(progress, later)
    assert progress["fault"] is first  # the first one is kept by the entry


def test_parking_stays_sticky_when_recording_fails(lab: Any, monkeypatch: Any) -> None:
    lab.world.during = retain
    lab.world.raised = FakeRunError("CONTROL_HELD")
    progress = lab.glob["_progress"](NONCE)
    decision = lab.glob["_advance"](progress, FAKE_RAW)
    assert lab.glob["settle"](decision, progress) == ("PARK", "HELD")
    fragile(lab, monkeypatch, MemoryError())
    lab.module["_fault"](progress, Signal("late"))  # must not raise
    assert lab.glob["_STATE"]["parked"] is True
    assert lab.glob["settle"](("EXIT", 0, "APPROVED"), progress)[0] == "PARK"
    assert lab.glob["decide"](progress)[0] == "PARK"
    assert len(lab.world.calls) == 1


def protected_calls(node: Any) -> list[Any]:
    """Calls lexically inside a try body that has an `except BaseException`."""
    calls: list[Any] = []
    for item in ast.walk(node):
        if isinstance(item, ast.Try) and any(
            handler.type is not None and ast.unparse(handler.type) == "BaseException"
            for handler in item.handlers
        ):
            for statement in item.body:
                calls.extend(call for call in ast.walk(statement) if isinstance(call, ast.Call))
    return calls


def keep_appends(node: Any) -> list[Any]:
    return [
        item
        for item in ast.walk(node)
        if isinstance(item, ast.Call) and ast.unparse(item.func) == "KEEP.append"
    ]


def test_recording_is_protected_and_after_original_capture() -> None:
    tree = entry_tree()
    # _fault: every recording is protected, so it can never raise.
    fault = function(tree, "_fault")
    protected = protected_calls(fault)
    assert keep_appends(fault)
    assert all(any(call is item for item in protected) for call in keep_appends(fault))
    # _drive: the outer catch only reaches the recorder through a protection.
    drive = function(tree, "_drive")
    outer = next(node for node in drive.body if isinstance(node, ast.While))
    catches = [
        handler
        for node in outer.body
        if isinstance(node, ast.Try)
        for handler in node.handlers
        if handler.type is not None and ast.unparse(handler.type) == "BaseException"
    ]
    assert len(catches) == 1
    inner = protected_calls(catches[0])
    calls = [item for statement in catches[0].body for item in ast.walk(statement)]
    assert all(any(call is item for item in inner) for call in calls if isinstance(call, ast.Call))
    # _invoke: the original is saved in progress before any fallible recording.
    invoke = function(tree, "_invoke")
    handler = next(
        node
        for node in ast.walk(invoke)
        if isinstance(node, ast.ExceptHandler)
        and node.type is not None
        and ast.unparse(node.type) == "BaseException"
    )
    assert ast.unparse(handler.body[0]).startswith("progress['outcome'] =")
    invoke_protected = protected_calls(handler)
    assert all(any(call is item for item in invoke_protected) for call in keep_appends(handler))


@pytest.mark.parametrize(
    "pids",
    [
        (None, -1),
        (True, 222),
        (111, False),
        (0, 222),
        (111, 0),
        (-5, 222),
        (111, -1),
        (1 << 32, 222),
        (111, 1 << 32),
        (111, 111),
        ("111", 222),
        (111.0, 222),
        (111,),
        None,
    ],
    ids=str,
)
def test_invalid_identity_refuses_before_identity_and_run(lab: Any, capsys: Any, pids: Any) -> None:
    lab.glob["_pids"] = lambda: pids
    lab.world.result = summary()
    code = lab.glob["main"]([NONCE])
    assert type(code) is int and code == 2
    records = events(capsys)
    assert [record["event"] for record in records] == ["FINAL"]
    assert records[0]["refusal"] == "ENTRY_ARM" and records[0]["controller_pid"] is None
    assert lab.world.calls == []


def test_identity_accepts_the_32_bit_boundary(lab: Any, capsys: Any) -> None:
    top = (1 << 32) - 1
    lab.glob["_pids"] = lambda: (top, 4)
    lab.world.result = summary()
    assert lab.glob["main"]([NONCE]) == 0
    identity, final = events(capsys)
    assert (identity["controller_pid"], identity["parent_pid"]) == (top, 4)
    assert final["controller_pid"] == top and len(lab.world.calls) == 1


class Hostile:
    """A label whose equality always answers True and records every use."""

    def __init__(self, seen: list[Any]) -> None:
        self.seen = seen

    def __eq__(self, other: object) -> bool:
        self.seen.append(other)
        return True

    def __hash__(self) -> int:
        return id(self)


class SneakyStr(str):
    def __eq__(self, other: object) -> bool:
        return True

    def __hash__(self) -> int:
        return str.__hash__(self)


@pytest.mark.parametrize("field", ["scope", "admission_3s", "kind", "outcome", "case"])
@pytest.mark.parametrize("flavour", ["object", "str-subclass"])
def test_hostile_labels_never_approve(lab: Any, capsys: Any, field: str, flavour: str) -> None:
    seen: list[Any] = []
    value: Any = Hostile(seen) if flavour == "object" else SneakyStr("x")
    result = summary()
    if field == "case":
        result["cases"][0]["outcome"] = value
    else:
        result[field] = value
    lab.world.result = result
    code = lab.glob["main"]([NONCE])
    assert type(code) is int and code == 2
    final = events(capsys)[-1]
    assert (final["outcome"], final["refusal"]) == ("REFUSED", "ENTRY_RESULT")
    assert seen == []  # hostile equality never invoked
