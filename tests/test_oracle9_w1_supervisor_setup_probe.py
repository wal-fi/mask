"""C0 oracles: real Owner setup then close WITHOUT start (root C0 contract, 2026-11-14).

Contract for the FUTURE ``docs/poc/oracle9_w1_supervisor_setup_probe.py``: the concrete C0
entry definitions ``load_qualifier``, ``C0LoadError``, ``run_c0`` and ``encode_c0``. The
module stays absent until the root reads these oracles and freezes RED. It is loaded
lazily as the FIRST statement of each feature case (``probe_module()``), never at
collection, in a fixture or inside ``pytest.raises``. ``test_sanity_*`` cases never load it.

The faithful fake backend and the trusted qualifier namespace are REUSED unchanged from
the frozen ``tests/test_oracle9_w1_supervisor_qualification.py``; nothing in production is
patched. The fake ``close`` already accepts READY, as the backend does. C0 never starts a
child: the only Owner calls allowed are ``setup`` and ``close``. These are fake-only
oracles; nothing here loads a DLL, creates a job or starts a process, except that the
loader cases execute the pinned public qualifier definitions.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium, from the C0 root contract.
Senff policy: AI-generated tests require human and security review before merge.
"""

from __future__ import annotations

import ast
import functools
import hashlib
import itertools
import runpy
import types
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests import test_oracle9_w1_supervisor_qualification as base

REPO = Path(__file__).resolve().parents[1]
PROBE_FILE = REPO / "docs/poc/oracle9_w1_supervisor_setup_probe.py"
QUAL_FILE = base.QUAL_FILE
QUAL_NAME = "oracle9_w1_supervisor_qualification.py"
QUAL_SHA = "999f4a8d627e1550e8c95c6c6fa42aaa7a5edfb7045acbb33ccf51561d5fe015"
QUAL_LIMIT = 65536
ENV = (("W1_NATIVE_PROBE", "1"),)
STATUSES = ("OBSERVED", "REFUSED", "UNKNOWN")
STEPS = ("INPUT", "CUSTODY", "LOAD", "SETUP", "CLOSE", "CONTROL", "INTERNAL", "DONE")
STATES = (
    "EMPTY",
    "NEW",
    "SETUP",
    "READY",
    "SETUP_FAILED",
    "STARTING",
    "LAUNCH_FAILED",
    "RUNNING",
    "HELD",
    "CLOSED",
    "OTHER",
)
FORBIDDEN_OWNER_CALLS = frozenset(
    {
        "start",
        "check_config",
        "wait",
        "exit_code",
        "accounting",
        "members",
        "terminate",
        "available",
    }
)


# ---------------------------------------------------------------- lazy loading of the absent module


@functools.cache
def _probe_namespace() -> dict[str, Any]:
    return runpy.run_path(str(PROBE_FILE), run_name="_w1_supervisor_setup_probe_test")


def probe_module() -> Any:
    """FIRST statement of every feature case; never called inside pytest.raises."""
    return SimpleNamespace(**_probe_namespace())


def error_of(call: Callable[[], object]) -> Exception | None:
    """The ordinary Exception raised by ``call``, or None when it returned."""
    try:
        call()
    except Exception as error:
        return error
    return None


def encode_error(p: Any, record: object) -> Exception | None:
    """The ordinary Exception raised by one synchronous ``encode_c0(record)``, or None."""
    try:
        p.encode_c0(record)
    except Exception as error:
        return error
    return None


def allowed(status: str, step: str, state: str) -> bool:
    """The closed C0 record combinations of the root contract."""
    if status == "OBSERVED":
        return step == "DONE" and state == "CLOSED"
    if status == "REFUSED":
        return step in ("INPUT", "CUSTODY", "LOAD") and state == "EMPTY"
    return step != "DONE"


def fresh_run(script: base.Script) -> tuple[Any, Any, types.ModuleType]:
    q = base.qual_module()
    backend = base.make_backend(script)
    custody = q.QualCustody()
    script.custody = custody
    return q, custody, backend


def assert_retained(custody: Any, script: base.Script, backend: types.ModuleType) -> None:
    assert custody.claimed is True and custody.backend is backend
    assert len(script.requests) == len(script.owners) == 1
    assert custody.request is script.requests[0] and custody.owner is script.owners[0]
    assert custody.report is None  # reserved for QualReport; C0 never fills it
    assert script.violations == []


# ---------------------------------------------------------------- independent fake sanities


def test_sanity_fake_owner_setup_then_close_without_start() -> None:
    script = base.Script()
    backend = base.make_backend(script)
    owner = backend.Owner(backend.Request(base.APP, "cmd", ENV, base.DIR))
    assert owner.setup() is None and owner.state == "READY"
    assert owner.close() is None and owner.state == "CLOSED"
    assert script.calls == ["setup", "close"] and script.violations == []


def test_sanity_published_qualifier_is_the_pinned_sibling() -> None:
    raw = QUAL_FILE.read_bytes()
    assert len(raw) <= QUAL_LIMIT and hashlib.sha256(raw).hexdigest() == QUAL_SHA
    assert QUAL_FILE.name == QUAL_NAME and QUAL_FILE.parent == PROBE_FILE.parent


# ---------------------------------------------------------------- run_c0 positive path


def test_c0_observed_exact_sequence_custody_and_request() -> None:
    p = probe_module()
    script = base.Script()
    q, custody, backend = fresh_run(script)
    result = p.run_c0(q, backend, base.APP, base.DIR, custody)
    assert type(result) is tuple and result == ("OBSERVED", "DONE", "CLOSED")
    assert all(type(item) is str for item in result)
    assert script.calls == ["setup", "close"]  # never start or any other Owner method
    assert script.owned_before_setup is True  # backend, request, owner retained first
    assert_retained(custody, script, backend)
    assert custody.error is None and custody.first_control is None
    assert script.owners[0].state == "CLOSED"
    request = script.requests[0]
    assert type(request.application) is str and request.application == base.APP
    assert type(request.directory) is str and request.directory == base.DIR
    assert type(request.environment) is tuple and request.environment == ENV
    assert all(type(item) is tuple for item in request.environment)
    line = request.command_line  # inert: never started by C0
    assert type(line) is str and line == '"' + base.APP + '" -I -B -S -c "pass"'
    assert len(line) <= 2048
    assert p.encode_c0(result) == b"W1C0 OBSERVED DONE CLOSED\n"


# ---------------------------------------------------------------- setup / close outcomes


def _setup_cases(probes: list[str]) -> dict[str, tuple[base.Script, str, bool]]:
    error = base.FakeWin32Error("WIN32_JOB")
    return {
        "raises-setup-failed": (
            base.Script(raises={"setup": [error]}, fail_states={"setup": "SETUP_FAILED"}),
            "SETUP_FAILED",
            True,
        ),
        "raises-held": (
            base.Script(
                raises={"setup": [base.FakeWin32Error("WIN32_HELD")]},
                fail_states={"setup": "HELD"},
            ),
            "HELD",
            True,
        ),
        "raises-opaque-state": (
            base.Script(
                raises={"setup": [base.FakeWin32Error("WIN32_JOB")]},
                fail_states={"setup": base.Opaque(probes)},
            ),
            "OTHER",
            True,
        ),
        "invalid-return": (base.Script(returns={"setup": [7]}), "NEW", False),
        "opaque-return": (base.Script(returns={"setup": [base.Opaque(probes)]}), "NEW", False),
        "none-but-not-ready": (base.Script(returns={"setup": [None]}), "NEW", False),
    }


@pytest.mark.parametrize(
    "case",
    [
        "raises-setup-failed",
        "raises-held",
        "raises-opaque-state",
        "invalid-return",
        "opaque-return",
        "none-but-not-ready",
    ],
)
def test_setup_uncertainty_is_unknown_with_actual_state_and_never_closes(case: str) -> None:
    p = probe_module()
    probes: list[str] = []
    script, state, raised = _setup_cases(probes)[case]
    original = script.raises["setup"][0] if raised else None
    q, custody, backend = fresh_run(script)
    result = p.run_c0(q, backend, base.APP, base.DIR, custody)
    assert result == ("UNKNOWN", "SETUP", state) and probes == []
    assert script.calls == ["setup"]  # no close after setup uncertainty, no retry
    assert_retained(custody, script, backend)
    assert custody.error is original and custody.first_control is None


def _close_cases(probes: list[str]) -> dict[str, tuple[base.Script, str, bool]]:
    return {
        "raises": (
            base.Script(raises={"close": [base.FakeWin32Error("WIN32_CLOSE")]}),
            "READY",
            True,
        ),
        "raises-held": (
            base.Script(
                raises={"close": [base.FakeWin32Error("WIN32_HELD")]},
                fail_states={"close": "HELD"},
            ),
            "HELD",
            True,
        ),
        "invalid-return": (base.Script(returns={"close": [0]}), "READY", False),
        "opaque-return": (base.Script(returns={"close": [base.Opaque(probes)]}), "READY", False),
        "none-but-not-closed": (base.Script(returns={"close": [None]}), "READY", False),
        "state-running": (base.Script(close_state="RUNNING"), "RUNNING", False),
        "state-opaque": (base.Script(close_state=base.Opaque(probes)), "OTHER", False),
    }


@pytest.mark.parametrize(
    "case",
    [
        "raises",
        "raises-held",
        "invalid-return",
        "opaque-return",
        "none-but-not-closed",
        "state-running",
        "state-opaque",
    ],
)
def test_close_uncertainty_is_unknown_with_actual_state_and_never_retries(case: str) -> None:
    p = probe_module()
    probes: list[str] = []
    script, state, raised = _close_cases(probes)[case]
    original = script.raises["close"][0] if raised else None
    q, custody, backend = fresh_run(script)
    result = p.run_c0(q, backend, base.APP, base.DIR, custody)
    assert result == ("UNKNOWN", "CLOSE", state) and probes == []
    assert script.calls == ["setup", "close"]  # exactly one close, never repeated
    assert_retained(custody, script, backend)
    assert custody.error is original and custody.first_control is None


# ---------------------------------------------------------------- first control


@pytest.mark.parametrize("method", ["setup", "close"])
@pytest.mark.parametrize("ctl_type", [base.FalseCtl, base.BoomCtl])
@pytest.mark.parametrize("held", [False, True])
def test_first_control_is_returned_as_unknown_control_with_identity_and_zero_later_calls(
    method: str, ctl_type: Callable[[list[str]], BaseException], held: bool
) -> None:
    p = probe_module()
    probes: list[str] = []
    ctl = ctl_type(probes)
    script = base.Script(raises={method: [ctl]})
    if held:
        script.fail_states = {method: "HELD"}
    q, custody, backend = fresh_run(script)
    result = p.run_c0(q, backend, base.APP, base.DIR, custody)
    state = "HELD" if held else ("NEW" if method == "setup" else "READY")
    assert result == ("UNKNOWN", "CONTROL", state) and probes == []
    assert script.calls[-1] == method and script.calls.count(method) == 1  # zero later calls
    assert script.calls.count("close") == (1 if method == "close" else 0)
    assert custody.error is ctl and custody.first_control is ctl
    assert ctl.__context__ is None and ctl.__cause__ is None
    assert_retained(custody, script, backend)


# ---------------------------------------------------------------- refusals before acquisition


BAD_PATHS = {
    "relative": "python.exe",
    "drive-relative": "C:python.exe",
    "unc": "\\\\server\\share\\python.exe",
    "device": "\\\\?\\C:\\x\\python.exe",
    "quote": 'C:\\x"\\python.exe',
    "lf": "C:\\x\n\\python.exe",
    "cr": "C:\\x\r\\python.exe",
    "nul": "C:\\x\x00\\python.exe",
    "empty": "",
    "long": "C:\\" + "a" * 1022,
    "bytes": b"C:\\x\\python.exe",
    "none": None,
}


@pytest.mark.parametrize("which", ["application", "directory"])
@pytest.mark.parametrize("name", sorted(BAD_PATHS))
def test_invalid_input_refuses_before_request_or_owner(which: str, name: str) -> None:
    p = probe_module()
    script = base.Script()
    q, custody, backend = fresh_run(script)
    bad: object = BAD_PATHS[name]
    application = bad if which == "application" else base.APP
    directory = bad if which == "directory" else base.DIR
    result = p.run_c0(q, backend, application, directory, custody)
    assert result == ("REFUSED", "INPUT", "EMPTY")
    assert script.requests == [] and script.owners == [] and script.calls == []
    assert custody.request is None and custody.owner is None and custody.report is None


def _bad_backends() -> dict[str, object]:
    def without(name: str) -> types.ModuleType:
        module = base.make_backend(base.Script())
        del module.__dict__[name]
        return module

    def replaced(name: str) -> types.ModuleType:
        module = base.make_backend(base.Script())
        module.__dict__[name] = object()
        return module

    return {
        "not-module": SimpleNamespace(**vars(base.make_backend(base.Script()))),
        "no-owner": without("Owner"),
        "no-request": without("Request"),
        "owner-not-callable": replaced("Owner"),
        "request-not-callable": replaced("Request"),
    }


@pytest.mark.parametrize(
    "name",
    ["not-module", "no-owner", "no-request", "owner-not-callable", "request-not-callable"],
)
def test_invalid_backend_refuses_as_load_before_construction(name: str) -> None:
    p = probe_module()
    q = base.qual_module()
    custody = q.QualCustody()
    result = p.run_c0(q, _bad_backends()[name], base.APP, base.DIR, custody)
    assert result == ("REFUSED", "LOAD", "EMPTY")
    assert custody.request is None and custody.owner is None and custody.report is None


@pytest.mark.parametrize("kind", ["foreign", "claimed", "errored", "subclass", "reused"])
def test_invalid_or_reused_custody_is_refused_without_any_write(kind: str) -> None:
    p = probe_module()
    q = base.qual_module()
    script = base.Script()
    backend = base.make_backend(script)
    custody: Any
    if kind == "foreign":
        custody = SimpleNamespace(**dict.fromkeys(base.CUSTODY_FIELDS))
    elif kind == "subclass":
        custody = type("SubCustody", (q.QualCustody,), {"__slots__": ()})()
    else:
        custody = q.QualCustody()
        if kind == "claimed":
            custody.claimed = True
        elif kind == "errored":
            custody.error = base.FakeWin32Error("WIN32_STATE")
        else:
            script.custody = custody
            first = p.run_c0(q, backend, base.APP, base.DIR, custody)
            assert first == ("OBSERVED", "DONE", "CLOSED")
    before = base.custody_snapshot(custody)
    calls_before = len(script.calls)
    requests_before = len(script.requests)
    result = p.run_c0(q, backend, base.APP, base.DIR, custody)
    assert result == ("REFUSED", "CUSTODY", "EMPTY")
    assert all(x is y for x, y in zip(before, base.custody_snapshot(custody), strict=True))
    assert len(script.calls) == calls_before and len(script.requests) == requests_before


# ---------------------------------------------------------------- encode_c0


def test_encode_accepts_exactly_the_closed_combinations_within_128_bytes() -> None:
    p = probe_module()
    for status, step, state in itertools.product(STATUSES, STEPS, STATES):
        record = (status, step, state)
        if allowed(status, step, state):
            frame = p.encode_c0(record)
            assert type(frame) is bytes and frame == f"W1C0 {status} {step} {state}\n".encode()
            assert len(frame) <= 128 and frame.count(b"\n") == 1 and frame.isascii()
        else:
            error = encode_error(p, record)
            assert type(error) is ValueError and error.args == ("C0_RECORD",)
            assert error.__cause__ is None and error.__context__ is None


def test_encode_rejects_invalid_structures_without_inspecting_opaque_values() -> None:
    p = probe_module()
    probes: list[str] = []
    text_subclass = type("Text", (str,), {})
    invalid: list[object] = [
        ["OBSERVED", "DONE", "CLOSED"],
        ("OBSERVED", "DONE"),
        ("OBSERVED", "DONE", "CLOSED", "EXTRA"),
        (b"OBSERVED", "DONE", "CLOSED"),
        ("observed", "DONE", "CLOSED"),
        ("OBSERVED", "DONE", "CLOSED "),
        ("OBSERVED", "DONE", "CLOSED\n"),
        (text_subclass("OBSERVED"), "DONE", "CLOSED"),
        (base.Opaque(probes), "DONE", "CLOSED"),
        ("UNKNOWN", base.Opaque(probes), "OTHER"),
        base.Opaque(probes),
        None,
        "W1C0 OBSERVED DONE CLOSED",
    ]
    for record in invalid:
        error = encode_error(p, record)
        assert type(error) is ValueError and error.args == ("C0_RECORD",)
        assert error.__cause__ is None and error.__context__ is None
    assert probes == []


def test_unknown_and_refused_results_encode_as_closed_frames() -> None:
    p = probe_module()
    script = base.Script(raises={"close": [base.FakeWin32Error("WIN32_CLOSE")]})
    q, custody, backend = fresh_run(script)
    frame = p.encode_c0(p.run_c0(q, backend, base.APP, base.DIR, custody))
    assert frame == b"W1C0 UNKNOWN CLOSE READY\n"
    q2 = base.qual_module()
    refusal = p.run_c0(q2, backend, "relative", base.DIR, q2.QualCustody())
    assert p.encode_c0(refusal) == b"W1C0 REFUSED INPUT EMPTY\n"
    for secret in (base.APP, base.DIR, base.CANARY):
        assert secret.encode() not in frame


# ---------------------------------------------------------------- checked-byte fixed-sibling loader


def _copy_pair(directory: Path, qualifier: bytes | None) -> Path:
    probe = directory / PROBE_FILE.name
    probe.write_bytes(PROBE_FILE.read_bytes())  # source-identical; absent source fails here
    if qualifier is not None:
        (directory / QUAL_NAME).write_bytes(qualifier)
    return probe


def assert_load_error(namespace: dict[str, Any], error: Exception | None) -> None:
    assert error is not None and type(error) is namespace["C0LoadError"]
    assert error.args == ("C0_LOAD",)
    assert error.__cause__ is None and error.__context__ is None


def test_load_qualifier_returns_the_pinned_public_qualifier() -> None:
    p = probe_module()
    module = p.load_qualifier()
    assert type(module) is types.ModuleType
    for name in ("qualify", "load_backend", "QualCustody"):
        assert name in vars(module)
    assert callable(vars(module)["load_backend"]) and isinstance(vars(module)["QualCustody"], type)


def test_load_qualifier_checks_bytes_before_executing_and_refuses_closed(tmp_path: Path) -> None:
    p = probe_module()
    assert callable(p.load_qualifier)
    good_dir = tmp_path / "good"
    good_dir.mkdir()
    good = runpy.run_path(str(_copy_pair(good_dir, QUAL_FILE.read_bytes())), run_name="_c0_good")
    assert type(good["load_qualifier"]()) is types.ModuleType

    for kind in ("tampered", "oversize"):
        bad_dir = tmp_path / kind
        bad_dir.mkdir()
        marker = bad_dir / "executed"
        payload = f"\nimport pathlib as _tamper\n_tamper.Path({str(marker)!r}).write_text('x')\n"
        padding = "#" + "x" * (QUAL_LIMIT + 16) + "\n" if kind == "oversize" else ""
        altered = QUAL_FILE.read_bytes() + (padding + payload).encode("utf-8")
        ast.parse(altered.decode("utf-8"))  # valid Python: a refusal is never a SyntaxError
        compile(altered, str(bad_dir / QUAL_NAME), "exec")
        assert (kind == "oversize") == (len(altered) > QUAL_LIMIT)
        namespace = runpy.run_path(str(_copy_pair(bad_dir, altered)), run_name="_c0_" + kind)
        assert not marker.exists()  # importing the entry never loads the qualifier
        assert_load_error(namespace, error_of(namespace["load_qualifier"]))
        assert not marker.exists()  # altered bytes were never executed

    missing_dir = tmp_path / "missing"
    missing_dir.mkdir()
    namespace = runpy.run_path(str(_copy_pair(missing_dir, None)), run_name="_c0_missing")
    assert_load_error(namespace, error_of(namespace["load_qualifier"]))


# ---------------------------------------------------------------- static shape


FORBIDDEN_MODULES = frozenset(
    {
        "subprocess",
        "threading",
        "socket",
        "ctypes",
        "asyncio",
        "signal",
        "multiprocessing",
        "importlib",
        "runpy",
        "json",
        "docs",
    }
)
PARK = "_park_c0"  # the ONLY place for an endless retaining loop and time.sleep
LOADER = "load_qualifier"  # the ONLY place for a bounded file read
PURE_CALL_NAMES = frozenset({"frozenset", "tuple", "set", "dict"})
PURE_ATTRIBUTE_CALLS = frozenset({("re", "compile")})
DECORATOR_NAMES = frozenset({"dataclass", "staticmethod", "classmethod"})


def _scoped(node: ast.AST, scope: tuple[str, ...]) -> Iterator[tuple[ast.AST, tuple[str, ...]]]:
    """Every node with the names of the functions that lexically enclose it."""
    yield node, scope
    inner = scope
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        inner = (*scope, node.name)
    for child in ast.iter_child_nodes(node):
        yield from _scoped(child, inner)


def _assert_pure(expression: ast.AST) -> None:
    """An import-time expression may only build constants (no operational call)."""
    for node in ast.walk(expression):
        if isinstance(node, ast.Call):
            func = node.func
            named = isinstance(func, ast.Name) and func.id in PURE_CALL_NAMES
            attribute = (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and (func.value.id, func.attr) in PURE_ATTRIBUTE_CALLS
            )
            assert named or attribute, "operational call evaluated at import"
        assert not isinstance(node, ast.Await | ast.Yield | ast.YieldFrom | ast.NamedExpr)


def _assert_definition(node: ast.FunctionDef | ast.ClassDef) -> None:
    """Decorators, defaults and class bodies run at import: they must stay pure."""
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        assert isinstance(target, ast.Name) and target.id in DECORATOR_NAMES
        if isinstance(decorator, ast.Call):
            assert target.id == "dataclass"
            for keyword in decorator.keywords:
                assert isinstance(keyword.value, ast.Constant)
    if isinstance(node, ast.FunctionDef):
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                _assert_pure(default)
        return
    for base_node in (*node.bases, *(keyword.value for keyword in node.keywords)):
        _assert_pure(base_node)
    for statement in node.body:
        if isinstance(statement, ast.FunctionDef):
            _assert_definition(statement)
        elif isinstance(statement, ast.Assign | ast.AnnAssign):
            if statement.value is not None:
                _assert_pure(statement.value)
        else:
            assert isinstance(statement, ast.Pass) or (
                isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
            ), "operational class-body statement"


def _is_main_call(node: ast.AST) -> bool:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
        return False
    arguments = (*node.args, *(keyword.value for keyword in node.keywords))
    nested = any(isinstance(inner, ast.Call) for arg in arguments for inner in ast.walk(arg))
    return node.func.id == "main" and not nested


def _is_main_guard(node: ast.If) -> bool:
    """Exactly ``if __name__ == "__main__":`` with ONE ``main(...)`` or SystemExit(main(...))."""
    test = node.test
    guard = (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )
    if not guard or node.orelse or len(node.body) != 1:
        return False
    statement = node.body[0]
    if isinstance(statement, ast.Expr):
        return _is_main_call(statement.value)
    exc = statement.exc if isinstance(statement, ast.Raise) else None
    return (
        isinstance(exc, ast.Call)
        and isinstance(exc.func, ast.Name)
        and exc.func.id == "SystemExit"
        and len(exc.args) == 1
        and not exc.keywords
        and _is_main_call(exc.args[0])
    )


def _assert_node(node: ast.AST, scope: tuple[str, ...]) -> None:
    """Per-node C0 rules: imports, Owner/private attributes, read, time and endless loops."""
    if isinstance(node, ast.Import):
        assert not {alias.name.split(".")[0] for alias in node.names} & FORBIDDEN_MODULES
    if isinstance(node, ast.ImportFrom):
        root = (node.module or "").split(".")[0]
        assert root not in FORBIDDEN_MODULES and root != "time"
    assert not isinstance(node, ast.AsyncFunctionDef | ast.Await)
    if isinstance(node, ast.Attribute):
        assert node.attr not in base.PRIVATE_NAMES
        assert node.attr not in FORBIDDEN_OWNER_CALLS
        assert node.attr not in {"kill", "getpid"}
        if node.attr == "read":
            assert LOADER in scope, "read outside the bounded checked-byte loader"
        if isinstance(node.value, ast.Name) and node.value.id == "time":
            assert node.attr == "sleep" and PARK in scope, "time outside the park"
    if isinstance(node, ast.While) and isinstance(node.test, ast.Constant):
        assert PARK in scope, "endless loop outside the retaining park"


def check_c0_structure(source: str) -> None:
    """The narrow C0 entry shape (root C0 contract + test review): import defines only,
    one guarded main, an optional retaining ``_park_c0``, Owner calls only setup/close.
    Raises AssertionError on any violation. Not a general security analysis."""
    tree = ast.parse(source)
    for node, scope in _scoped(tree, ()):
        _assert_node(node, scope)
    body = tree.body
    for index, statement in enumerate(body):
        if isinstance(statement, ast.Expr):
            assert index == 0 and isinstance(statement.value, ast.Constant)  # docstring only
        elif isinstance(statement, ast.FunctionDef | ast.ClassDef):
            _assert_definition(statement)
        elif isinstance(statement, ast.Assign | ast.AnnAssign):
            if statement.value is not None:
                _assert_pure(statement.value)
        elif isinstance(statement, ast.If):
            assert index == len(body) - 1 and _is_main_guard(statement)
        else:
            assert isinstance(statement, ast.Import | ast.ImportFrom), "top-level operation"


def structure_accepts(source: str) -> bool:
    """Compiles a fixture for syntax ONLY (never executed), then applies the SAME checker."""
    compile(source, "<c0-structure-fixture>", "exec")
    try:
        check_c0_structure(source)
    except AssertionError:
        return False
    return True


_FIXTURE_DEFS = '''"""C0 structure fixture: compiled, never executed."""
from __future__ import annotations

import re
import sys
import time

_LOCAL = re.compile(r"[A-Za-z]:\\\\.*")
_STATES = frozenset({"READY", "CLOSED"})


class C0LoadError(Exception):
    def __init__(self) -> None:
        super().__init__("C0_LOAD")


def load_qualifier(path: object) -> object:
    with open(str(path), "rb") as stream:
        return stream.read(65537)


def run_c0(owner: object) -> object:
    return owner.setup(), owner.close()
'''
_FIXTURE_PARK = """

def _park_c0(custody: object, control: object) -> None:
    retained = (custody, control)
    while True:
        time.sleep(60)
        assert retained is not None
"""
_FIXTURE_MAIN = """

def main(argv: list[str]) -> int:
    return len(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
"""
STRUCTURE_FIXTURES: dict[str, tuple[str, bool]] = {
    "definitions-only": (_FIXTURE_DEFS, True),
    "guarded-main": (_FIXTURE_DEFS + _FIXTURE_MAIN, True),
    "retaining-park": (_FIXTURE_DEFS + _FIXTURE_PARK, True),
    "park-and-main": (_FIXTURE_DEFS + _FIXTURE_PARK + _FIXTURE_MAIN, True),
    "print-in-assignment": (_FIXTURE_DEFS + '_BANNER = print("x")\n', False),
    "top-level-call": (_FIXTURE_DEFS + "load_qualifier(__file__)\n", False),
    "call-in-default": (
        _FIXTURE_DEFS + 'def later(x: object = print("x")) -> None:\n    return None\n',
        False,
    ),
    "decorator-call": (
        _FIXTURE_DEFS + "@print\ndef decorated() -> None:\n    return None\n",
        False,
    ),
    "class-body-call": (_FIXTURE_DEFS + 'class K:\n    X = print("x")\n', False),
    "endless-loop-outside-park": (
        _FIXTURE_DEFS + "def spin() -> None:\n    while True:\n        pass\n",
        False,
    ),
    "sleep-outside-park": (
        _FIXTURE_DEFS + "def nap() -> None:\n    time.sleep(1)\n",
        False,
    ),
    "from-time-import": (
        _FIXTURE_DEFS.replace("import re\n", "import re\nfrom time import sleep\n", 1),
        False,
    ),
    "subprocess-import": (
        _FIXTURE_DEFS.replace("import re\n", "import re\nimport subprocess\n", 1),
        False,
    ),
    "owner-start": (
        _FIXTURE_DEFS + "def go(owner: object) -> object:\n    return owner.start()\n",
        False,
    ),
    "owner-read-outside-loader": (
        _FIXTURE_DEFS + "def peek(owner: object) -> object:\n    return owner.read()\n",
        False,
    ),
    "private-ledger": (
        _FIXTURE_DEFS + "def led(owner: object) -> object:\n    return owner.ledger\n",
        False,
    ),
    "top-level-for": (_FIXTURE_DEFS + "for _ in range(1):\n    pass\n", False),
    "guard-extra-statement": (
        _FIXTURE_DEFS
        + _FIXTURE_MAIN.replace(
            "    raise SystemExit(main(sys.argv[1:]))\n",
            "    print('x')\n    raise SystemExit(main(sys.argv[1:]))\n",
        ),
        False,
    ),
    "guard-not-last": (_FIXTURE_DEFS + _FIXTURE_MAIN + "_LATE = 1\n", False),
    "guard-nested-call": (
        _FIXTURE_DEFS + _FIXTURE_MAIN.replace("main(sys.argv[1:])", "main(print('x'))"),
        False,
    ),
}


@pytest.mark.parametrize("name", sorted(STRUCTURE_FIXTURES))
def test_sanity_structure_checker_on_non_executed_fixtures(name: str) -> None:
    """The SAME checker the candidate oracle uses; fixtures are compiled, never executed."""
    source, expected = STRUCTURE_FIXTURES[name]
    assert structure_accepts(source) is expected


def test_static_shape_import_defines_only_and_setup_close_only() -> None:
    p = probe_module()
    assert callable(p.run_c0) and callable(p.encode_c0)
    source = PROBE_FILE.read_text(encoding="utf-8")
    check_c0_structure(source)
    assert QUAL_SHA in source and QUAL_NAME in source and "W1_NATIVE_PROBE" in source
