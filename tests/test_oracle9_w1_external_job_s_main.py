"""First fake oracles for the specific Windows S main (SM3 under SM-R1..SM-R3 and MB4).

Contract for the FUTURE ``docs/poc/oracle9_w1_external_job_s_main.py``. The source stays
ABSENT until the root reads every oracle and freezes a measured RED. Each source-dependent
case starts with ``require_source()``: an absent source is an explicit ``pytest.fail``,
never a skip, a pass or a collection/fixture error. ``test_sanity_*`` cases exercise only
this file's static helpers on pinned public sources or on inert in-memory text fixtures
(parsed, never executed, never an entry) and are NOT product proof.

Seam (SM3 §9): ONE real ``_load_entry`` over the pinned entry bytes, ONE real
``_prepare``, then only the already accepted private-backend seams of THAT SAME
``AdoptionLoad`` (``_load_api``/``sys``) and the frozen ``EntryKernel``/``Reader``/``Writer``
of test 1835, then ``_enter``. The REAL reviewed ``run_entry`` runs; there is no fake
Owner, fake entry, product patch, valid ``main``/``_run_s`` run past loading or real park.

Coverage kinds, kept apart: (a) DYNAMIC reachable cases through the seam; (b) HOSTILE data
in the caller's own holder (entered flag, used custody with the real fake-SDK Owner, the
four custody guards, wrong Request type with truly fresh custody); (c) STRUCTURAL-only
obligations checked on the AST (escaping Exception from ``run_entry``, control in the
post-return gap and in ``_inputs``, the outer ``main`` region, the park). Whole-main runs
with real interpreter ports, physical lifetime of S/park, handles and cleanup are NOT
measured here. The kernel job count is never used as a ``run_entry`` invocation count.

Interpretations of SM3 fixed by these oracles (for root review): ``_inputs`` returns the
exact ``(application, directory)`` pair; the main's static profile constants reuse the
pinned source names ``_ENV``/``_NATURAL_CODE``/``_PATH_LIMIT``/``_COMMAND_LIMIT``/
``_PARK_SLICE_S`` plus ``_LOCAL_PATTERN``; ``_load_entry`` also sets ``holder.adoption``.
SM-R4: the loader is called DIRECTLY on temporary trees; an ordinary refusal is the closed
``SMainLoadError`` (``S_MAIN_LOAD``), a control propagates by identity, and the caller's
phase-A recording/exit 3/park are STRUCTURAL obligations. ``_run_s`` is only called with
INVALID argv (exit 2, no file access); never with valid inputs, not even as a prefix.

The structural classifiers check the specific families the contract names (guard
direction and ``return None`` effect, first-object preservation, the entered-gated exit 3,
live references and a reachable slice sleep in the park). They are partial shape proofs,
not a general program analyser and not a physical proof.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium.
"""

from __future__ import annotations

import ast
import builtins
import copy
import dataclasses
import hashlib
import io
import os
import runpy
import sys
import types
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests import test_oracle9_w1_external_job_adoption as xj
from tests import test_oracle9_w1_external_job_entry as et
from tests import test_oracle9_w1_supervisor_qualification as qbase
from tests import test_pg16_shell_native_control_win32 as ref

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "docs/poc/oracle9_w1_external_job_s_main.py"
ENTRY_FILE = REPO / "docs/poc/oracle9_w1_external_job_entry.py"
ENTRY_SHA = "b4826e0b649e37b485b4ca065e225e1103cbd41e19836c2ac95ca78172a62e18"
ENTRY_SIZE = 16809
ENTRY_TEST_FILE = REPO / "tests/test_oracle9_w1_external_job_entry.py"
ENTRY_TEST_SHA = "1835ba817343cea1076fa95ec3add21d0828a074bfb8ac968f1e2dd8d0ef3fad"
QUAL_FILE = REPO / "docs/poc/oracle9_w1_supervisor_qualification.py"
QUAL_SHA = "999f4a8d627e1550e8c95c6c6fa42aaa7a5edfb7045acbb33ccf51561d5fe015"
C0_FILE = REPO / "docs/poc/oracle9_w1_supervisor_setup_probe.py"
C0_SHA = "43ffbf92c1fb747f61cc764f6db95fdfed800976cfe17cc2bd4e5c8f5657d511"
LOAD_LIMIT = 65536
APP = r"C:\fictional\w1\s-main\base.exe"  # fictional test data; no executable is touched
DIR = r"C:\fictional\w1\s-main\work"
CANARY = "SYNTHETIC-S-MAIN-CANARY-DO-NOT-RETAIN"
SWAP_FROM = b"W1 entry of S for"
SWAP_TO = b"W9 entry of S for"  # same length
HOLDER_FIELDS = (
    "reader",
    "writer",
    "entry",
    "adoption",
    "request",
    "custody",
    "entered",
    "result",
    "first_error",
    "first_control",
)
EXITS = {"DONE": 0, "DONE_NONZERO": 10, "REFUSED": 11, "SETUP_REFUSED": 12, "ACK_FAILED": 13}
CUSTODY_KEYS = ("type", "claimed", "owner", "first_control")
BANNED_IMPORTS = frozenset(
    {
        "subprocess",
        "threading",
        "socket",
        "asyncio",
        "multiprocessing",
        "runpy",
        "ctypes",
        "importlib",
        "tests",
        "docs",
    }
)
GUARD_TEXT = 'if __name__ == "__main__":\n    raise SystemExit(main(sys.argv[1:]))\n'


# ---------------------------------------------------------------- static helpers (no source)


def _parse_pinned(path: Path, digest: str) -> ast.Module:
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    return ast.parse(raw)


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    first = body[0] if body else None
    text = first.value if isinstance(first, ast.Expr) else None
    if isinstance(text, ast.Constant) and isinstance(text.value, str):
        return body[1:]
    return body


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    found = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    named = [node for node in found if node.name == name]
    return named[0] if len(named) == 1 else None


def _top_value(tree: ast.Module, name: str) -> ast.expr:
    values: list[ast.expr] = []
    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        named = any(isinstance(target, ast.Name) and target.id == name for target in targets)
        if named and value is not None:
            values.append(value)
    assert len(values) == 1, name
    return values[0]


def _literal(tree: ast.Module, name: str) -> object:
    return ast.literal_eval(_top_value(tree, name))


def _compile_literal(tree: ast.Module, name: str) -> str:
    """R1: the EXACT ``re.compile(<str literal>)`` form; never literal_eval of the Call."""
    value = _top_value(tree, name)
    assert isinstance(value, ast.Call) and not value.keywords and len(value.args) == 1
    func = value.func
    assert isinstance(func, ast.Attribute) and func.attr == "compile"
    assert isinstance(func.value, ast.Name) and func.value.id == "re"
    argument = value.args[0]
    assert isinstance(argument, ast.Constant)
    text = argument.value
    assert isinstance(text, str)
    return text


def _returned(function: ast.FunctionDef) -> ast.expr:
    last = function.body[-1]
    assert isinstance(last, ast.Return) and last.value is not None
    return last.value


def _renamed_dump(expression: ast.expr, old: str, new: str) -> str:
    clone = copy.deepcopy(expression)
    for node in ast.walk(clone):
        if isinstance(node, ast.Name) and node.id == old:
            node.id = new
    return ast.dump(clone)


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    found: list[ast.Call] = []
    for item in ast.walk(node):
        if isinstance(item, ast.Call):
            func = item.func
            direct = isinstance(func, ast.Name) and func.id == name
            if direct or (isinstance(func, ast.Attribute) and func.attr == name):
                found.append(item)
    return found


def _contains(region: list[ast.stmt] | ast.AST, target: ast.AST) -> bool:
    nodes: list[Any] = region if isinstance(region, list) else [region]
    return any(item is target for node in nodes for item in ast.walk(node))


def _is_const(node: ast.AST, value: object) -> bool:
    return isinstance(node, ast.Constant) and node.value is value


def _is_custody(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "custody"
    return isinstance(node, ast.Attribute) and node.attr == "custody"


GUARD_EXPECTED: dict[str, object] = {
    "entered": False,
    "claimed": False,
    "owner": None,
    "first_control": None,
}


def _is_type_of_custody(node: ast.expr) -> bool:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
        return False
    return node.func.id == "type" and len(node.args) == 1 and _is_custody(node.args[0])


def _guard_key(node: ast.AST) -> str:
    """Which SM3 §5 guard ``node`` is, ONLY in the violating ``is not`` direction."""
    if not (isinstance(node, ast.Compare) and len(node.ops) == 1):
        return ""
    if not isinstance(node.ops[0], ast.IsNot):
        return ""  # ``is`` would park on the HEALTHY value: reversed direction
    left, right = node.left, node.comparators[0]
    if _is_type_of_custody(left):
        return "type" if isinstance(right, ast.Attribute) and right.attr == "EntryCustody" else ""
    if not isinstance(left, ast.Attribute) or left.attr not in GUARD_EXPECTED:
        return ""
    owned = left.attr == "entered" or _is_custody(left.value)
    known = owned and _is_const(right, GUARD_EXPECTED[left.attr])
    return left.attr if known else ""


def _returns_none(body: list[ast.stmt]) -> bool:
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return False
    value = body[0].value
    return value is None or _is_const(value, None)


def _guard_lines(region: ast.Try) -> dict[str, int]:
    """Guards that count: a top-level ``if <is not ...> [or ...]: return None``."""
    lines: dict[str, int] = {}
    for statement in region.body:
        if not isinstance(statement, ast.If) or statement.orelse:
            continue
        if not _returns_none(statement.body):
            continue  # the guard must END the attempt, not merely mention the field
        test = statement.test
        either = isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or)
        operands = test.values if isinstance(test, ast.BoolOp) and either else [test]
        for operand in operands:
            key = _guard_key(operand)
            if key:
                lines.setdefault(key, statement.lineno)
    return lines


def _handler_problems(handlers: list[ast.ExceptHandler]) -> list[str]:
    """Handlers: pure assignments/returns only (no Call, no Raise)."""
    problems: list[str] = []
    for handler in handlers:
        for node in ast.walk(handler):
            if isinstance(node, ast.Call | ast.Raise):
                problems.append("handler-effect")
    return problems


def _is_none_check(node: ast.AST, attribute: str, *, on_custody: bool) -> bool:
    """``<x>.<attribute> is None`` where <x> is (or is not) the custody reference."""
    if not (isinstance(node, ast.Compare) and len(node.ops) == 1):
        return False
    left = node.left
    if not (isinstance(node.ops[0], ast.Is) and _is_const(node.comparators[0], None)):
        return False
    if not (isinstance(left, ast.Attribute) and left.attr == attribute):
        return False
    return _is_custody(left.value) == on_custody


def _custody_free(node: ast.AST) -> bool:
    """The custody holds no control: ``c.first_control is None`` or ``c is None or ...``."""
    if _is_none_check(node, "first_control", on_custody=True):
        return True
    if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
        return False
    if len(node.values) != 2:
        return False
    empty, free = node.values
    absent = isinstance(empty, ast.Compare) and _is_none_check(empty, "custody", on_custody=False)
    return absent and _is_none_check(free, "first_control", on_custody=True)


def _first_test(test: ast.expr, slot: str, *, custody_rule: bool) -> bool:
    both = isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And)
    parts = test.values if isinstance(test, ast.BoolOp) and both else [test]
    own = [part for part in parts if _is_none_check(part, slot, on_custody=False)]
    if not custody_rule:
        return len(parts) == 1 and len(own) == 1
    rest = [part for part in parts if part not in own]
    return len(parts) == 2 and len(own) == 1 and len(rest) == 1 and _custody_free(rest[0])


def _assigns(body: list[ast.stmt], slot: str, name: str) -> bool:
    for statement in body:
        if not (isinstance(statement, ast.Assign) and len(statement.targets) == 1):
            continue
        target, value = statement.targets[0], statement.value
        if not (isinstance(target, ast.Attribute) and target.attr == slot):
            continue
        if not _is_custody(target.value) and isinstance(value, ast.Name) and value.id == name:
            return True
    return False


def _slot_writes(handler: ast.ExceptHandler, slot: str) -> list[ast.stmt]:
    """EVERY statement in the handler that stores into or deletes ``<holder>.<slot>``."""
    writes: list[ast.stmt] = []
    for node in ast.walk(handler):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign | ast.Delete):
            targets = list(node.targets)
        elif isinstance(node, ast.AugAssign | ast.AnnAssign):
            targets = [node.target]
        stored = [
            item
            for target in targets
            for item in ast.walk(target)
            if isinstance(item, ast.Attribute)
            and item.attr == slot
            and not _is_custody(item.value)
            and isinstance(item.ctx, ast.Store | ast.Del)
        ]
        if stored and isinstance(node, ast.stmt):
            writes.append(node)
    return writes


def _guarded_writes(handler: ast.ExceptHandler, slot: str, *, custody_rule: bool) -> set[int]:
    """Ids of the plain ``<holder>.<slot> = <name>`` directly under a correct first-guard."""
    name = handler.name
    allowed: set[int] = set()
    if name is None:
        return allowed
    for statement in handler.body:
        if not isinstance(statement, ast.If) or statement.orelse:
            continue
        if not _first_test(statement.test, slot, custody_rule=custody_rule):
            continue
        allowed.update(id(item) for item in statement.body if _assigns([item], slot, name))
    return allowed


def _records_first(handler: ast.ExceptHandler, slot: str, *, custody_rule: bool) -> bool:
    """Keeps the FIRST object: at least one write, and ALL writes to the slot are the plain
    ``= <name>`` under ``if <holder>.<slot> is None [and custody free]``."""
    writes = _slot_writes(handler, slot)
    allowed = _guarded_writes(handler, slot, custody_rule=custody_rule)
    return bool(writes) and all(id(write) in allowed for write in writes)


def _returns_only(handler: ast.ExceptHandler, value: object) -> bool:
    returns = [node for node in ast.walk(handler) if isinstance(node, ast.Return)]
    if value is None:
        return bool(returns) and all(_returns_none([item]) for item in returns)
    return bool(returns) and all(
        item.value is not None and _is_int(item.value, value) for item in returns
    )


def _is_int(node: ast.AST, value: object) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) is int and node.value == value


def _handler_names(region: ast.Try) -> list[str]:
    return [h.type.id if isinstance(h.type, ast.Name) else "" for h in region.handlers]


def _region_shape(region: ast.Try) -> list[str]:
    problems: list[str] = []
    if _handler_names(region) != ["Exception", "BaseException"]:
        return ["enter-handlers"]
    if region.orelse or region.finalbody:
        problems.append("enter-handlers")
    problems += _handler_problems(region.handlers)
    error, control = region.handlers
    if not (_records_first(error, "first_error", custody_rule=False)):
        problems.append("error-rule")
    if not _records_first(control, "first_control", custody_rule=True):
        problems.append("control-rule")  # never replace the control retained by the entry
    if not (_returns_only(error, None) and _returns_only(control, None)):
        problems.append("handler-not-park")
    return problems


def _marks(tree: ast.Module) -> list[ast.Assign]:
    found: list[ast.Assign] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target = node.targets[0]
        entered = isinstance(target, ast.Attribute) and target.attr == "entered"
        if entered and _is_const(node.value, True):
            found.append(node)
    return found


def _guard_order(tree: ast.Module, region: ast.Try) -> list[str]:
    lines = _guard_lines(region)
    marks = _marks(tree)
    calls = _calls(ast.Module(body=region.body, type_ignores=[]), "run_entry")
    if set(lines) != {"entered", *CUSTODY_KEYS} or len(marks) != 1 or len(calls) != 1:
        return ["guard-incomplete"]
    mark, call = marks[0], calls[0]
    problems: list[str] = []
    custody_lines = [lines[key] for key in CUSTODY_KEYS]
    if not _contains(region.body, mark):
        problems.append("mark-outside-region")
    if not lines["entered"] < min(custody_lines):
        problems.append("reentry-order")
    if not max(custody_lines) < mark.lineno < call.lineno:
        problems.append("mark-order")
    end = call.end_lineno if call.end_lineno is not None else call.lineno
    later = [
        node
        for statement in region.body
        for node in ast.walk(statement)
        if isinstance(node, ast.expr) and node.lineno > end and _mentions_result(node)
    ]
    if not later:
        problems.append("classification-order")
    return problems


def _mentions_result(node: ast.expr) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr == "result" and isinstance(node.ctx, ast.Load)
    return isinstance(node, ast.Name) and node.id == "result" and isinstance(node.ctx, ast.Load)


def _call_sites(tree: ast.Module, run_s: ast.FunctionDef, region: ast.Try) -> list[str]:
    problems: list[str] = []
    runs = _calls(tree, "run_entry")
    if len(runs) != 1 or not _contains(region.body, runs[0]):
        problems.append("run-entry-site")
    enters = _calls(tree, "_enter")
    tries = [node for node in ast.walk(run_s) if isinstance(node, ast.Try)]
    inside_a = len(enters) == 1 and any(_contains(t, enters[0]) for t in tries)
    if len(enters) != 1 or not _contains(run_s, enters[0]) or inside_a:
        problems.append("enter-site")
    for name in ("_inputs", "_load_entry", "_prepare"):
        sites = _calls(run_s, name)
        if not sites or not all(any(_contains(t.body, site) for t in tries) for site in sites):
            problems.append("region-a:" + name)
    problems += _handler_problems([handler for t in tries for handler in t.handlers])
    return problems


def _custody_writes(tree: ast.Module) -> list[str]:
    problems: list[str] = []
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AugAssign | ast.AnnAssign):
            targets = [node.target]
        problems += [
            "custody-write"
            for target in targets
            if isinstance(target, ast.Attribute) and _is_custody(target.value)
        ]
        func = node.func if isinstance(node, ast.Call) else None
        if isinstance(func, ast.Name) and func.id in ("setattr", "delattr"):
            problems.append("dynamic-write")
    return problems


def _enter_violations(tree: ast.Module) -> list[str]:
    """SM3 §5/§9.3: single region, ordered guards, single call, no repeat path."""
    enter, run_s = _function(tree, "_enter"), _function(tree, "_run_s")
    if enter is None or run_s is None:
        return ["functions"]
    body = _strip_docstring(enter.body)
    if len(body) != 1 or not isinstance(body[0], ast.Try):
        return ["enter-not-single-try"]
    region = body[0]
    problems = _region_shape(region) + _guard_order(tree, region)
    problems += _call_sites(tree, run_s, region) + _custody_writes(tree)
    for function in (enter, run_s):
        if any(isinstance(node, ast.For | ast.While) for node in ast.walk(function)):
            problems.append("loop")
    return problems


def _is_slice_sleep(call: ast.Call) -> bool:
    func = call.func
    if not (isinstance(func, ast.Attribute) and func.attr == "sleep"):
        return False
    if not (isinstance(func.value, ast.Name) and func.value.id == "time") or call.keywords:
        return False
    if len(call.args) != 1:
        return False
    argument = call.args[0]
    return isinstance(argument, ast.Name) and argument.id == "_PARK_SLICE_S"


def _live_names(park: ast.FunctionDef) -> set[str]:
    """``holder`` (never rebound) plus names bound ONCE at top level to ``holder``."""
    stores: dict[str, int] = {}
    for node in ast.walk(park):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store | ast.Del):
            stores[node.id] = stores.get(node.id, 0) + 1
    if "holder" in stores:
        return set()  # the parameter itself was dropped or rebound
    live = {"holder"}
    for statement in park.body:
        if not (isinstance(statement, ast.Assign) and len(statement.targets) == 1):
            continue
        target, value = statement.targets[0], statement.value
        if not isinstance(target, ast.Name):
            continue
        bound = stores.get(target.id) == 1
        if bound and isinstance(value, ast.Name) and value.id == "holder":
            live.add(target.id)
    return live


def _reachable_wait(loop: ast.stmt, live: set[str]) -> bool:
    """Inner ``while True`` or ``while <live> is not None`` whose body is ONLY the sleep."""
    if not isinstance(loop, ast.While) or loop.orelse:
        return False
    test = loop.test
    endless = _is_const(test, True)
    alive = (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.IsNot)
        and isinstance(test.left, ast.Name)
        and test.left.id in live
        and _is_const(test.comparators[0], None)
    )
    if not (endless or alive) or len(loop.body) != 1:
        return False
    only = loop.body[0]
    if not (isinstance(only, ast.Expr) and isinstance(only.value, ast.Call)):
        return False
    return _is_slice_sleep(only.value)


def _park_loop_ok(loop: ast.While, live: set[str]) -> bool:
    if len(loop.body) != 1 or not isinstance(loop.body[0], ast.Try):
        return False
    region = loop.body[0]
    if len(region.handlers) != 1 or region.orelse or region.finalbody:
        return False
    handler = region.handlers[0]
    kind = handler.type
    if not (isinstance(kind, ast.Name) and kind.id == "BaseException"):
        return False
    if len(handler.body) != 1 or not isinstance(handler.body[0], ast.Continue):
        return False
    return len(region.body) == 1 and _reachable_wait(region.body[0], live)


def _park_violations(tree: ast.Module) -> list[str]:
    """SM3 §8: retains holder forever; only a reachable slice sleep; swallows controls."""
    park = _function(tree, "_park_s")
    if park is None:
        return ["park-missing"]
    problems: list[str] = []
    for node in ast.walk(park):
        if isinstance(node, ast.Return | ast.Raise | ast.Break | ast.Yield | ast.YieldFrom):
            problems.append("park-exit")
        if isinstance(node, ast.Call) and not _is_slice_sleep(node):
            problems.append("park-call")
    live = _live_names(park)
    if not live:
        problems.append("park-holder-dropped")
    loops = [s for s in park.body if isinstance(s, ast.While) and _is_const(s.test, True)]
    if len(loops) != 1 or not _park_loop_ok(loops[0], live):
        problems.append("park-loop")
    held = any(
        isinstance(node, ast.Name) and node.id == "holder" and isinstance(node.ctx, ast.Load)
        for node in ast.walk(park)
    )
    if not held:
        problems.append("park-holder")
    return problems


def _entered_false(test: ast.expr) -> bool:
    return (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Is)
        and isinstance(test.left, ast.Attribute)
        and test.left.attr == "entered"
        and _is_const(test.comparators[0], False)
    )


def _three_gated(handler: ast.ExceptHandler) -> bool:
    """Every exit 3 sits on the TRUE side of ``<holder>.entered is False``."""
    threes = [node for node in ast.walk(handler) if _is_int(node, 3)]
    gated: set[int] = set()
    for node in ast.walk(handler):
        if isinstance(node, ast.IfExp) and _entered_false(node.test):
            gated.update(id(item) for item in ast.walk(node.body))
        if isinstance(node, ast.If) and _entered_false(node.test):
            gated.update(id(item) for part in node.body for item in ast.walk(part))
    return bool(threes) and all(id(node) in gated for node in threes)


def _main_region_violations(tree: ast.Module) -> list[str]:
    """SM3 §6: outer region keeps first objects, exit 3 only while NOT entered, park outside."""
    main = _function(tree, "main")
    if main is None:
        return ["main-missing"]
    runs = _calls(main, "_run_s")
    regions = [
        node
        for node in ast.walk(main)
        if isinstance(node, ast.Try) and runs and _contains(node.body, runs[0])
    ]
    if len(runs) != 1 or len(regions) != 1:
        return ["main-run-s"]
    region = regions[0]
    if _handler_names(region) != ["Exception", "BaseException"]:
        return ["main-handlers"]
    problems = _handler_problems(region.handlers)
    error, control = region.handlers
    if not _records_first(error, "first_error", custody_rule=False):
        problems.append("main-first-error")
    if not _three_gated(error):
        problems.append("main-entered")
    if not _records_first(control, "first_control", custody_rule=True):
        problems.append("main-first-control")
    if any(_is_int(node, 3) for node in ast.walk(control)):
        problems.append("main-control-exit")
    parks = _calls(main, "_park_s")
    hidden = [call for handler in region.handlers for call in parks if _contains(handler, call)]
    if not parks or hidden:
        problems.append("main-park")
    return problems


def _region_a_violations(tree: ast.Module) -> list[str]:
    """SM3 §6/SM-R4: phase A keeps first objects; exit 3 only there, before ``_enter``."""
    run_s = _function(tree, "_run_s")
    if run_s is None:
        return ["run-s-missing"]
    inputs = _calls(run_s, "_inputs")
    regions = [
        node
        for node in ast.walk(run_s)
        if isinstance(node, ast.Try) and inputs and _contains(node.body, inputs[0])
    ]
    if len(inputs) != 1 or len(regions) != 1:
        return ["region-a-missing"]
    region = regions[0]
    if _handler_names(region) != ["Exception", "BaseException"]:
        return ["region-a-handlers"]
    problems = _handler_problems(region.handlers)
    error, control = region.handlers
    if not (_records_first(error, "first_error", custody_rule=False) and _returns_only(error, 3)):
        problems.append("region-a-error")
    if not _records_first(control, "first_control", custody_rule=True):
        problems.append("region-a-control")
    if not _returns_only(control, None):
        problems.append("region-a-control-exit")
    threes = [node for node in ast.walk(run_s) if _is_int(node, 3)]
    if not threes or not all(_contains(error, node) for node in threes):
        problems.append("exit-3-outside-phase-a")
    return problems


def _loader_violations(tree: ast.Module) -> list[str]:
    """SM-R4: closed SMainLoadError raised outside handlers; no recording/park in loader."""
    loader = _function(tree, "_load_entry")
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SMainLoadError"]
    if loader is None or len(classes) != 1:
        return ["loader-missing"]
    problems: list[str] = []
    error_class = classes[0]
    bases = [base.id for base in error_class.bases if isinstance(base, ast.Name)]
    if bases != ["Exception"] or "S_MAIN_LOAD" not in _constants(ast.Module([error_class], [])):
        problems.append("loader-error-class")
    handlers = [n for n in ast.walk(loader) if isinstance(n, ast.ExceptHandler)]
    if any(isinstance(node, ast.Raise) for h in handlers for node in ast.walk(h)):
        problems.append("loader-raise-in-handler")
    raises = [
        node
        for node in ast.walk(loader)
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
        and node.exc.func.id == "SMainLoadError"
        and not node.exc.args
    ]
    if not raises:
        problems.append("loader-closed-refusal")
    if not any(isinstance(n, ast.Try) and n.finalbody for n in ast.walk(loader)):
        problems.append("loader-registration")
    touched = {n.attr for n in ast.walk(loader) if isinstance(n, ast.Attribute)}
    if touched & {"first_error", "first_control", "custody", "entered"}:
        problems.append("loader-records")
    if _calls(loader, "_park_s"):
        problems.append("loader-parks")
    return problems


def _guard_ok(tree: ast.Module) -> bool:
    expected = ast.parse(GUARD_TEXT).body[0]
    return bool(tree.body) and ast.dump(tree.body[-1]) == ast.dump(expected)


def _docstring_ids(tree: ast.Module) -> set[int]:
    found: set[int] = set()
    for holder in ast.walk(tree):
        if isinstance(holder, ast.Module | ast.ClassDef | ast.FunctionDef) and holder.body:
            first = holder.body[0]
            if isinstance(first, ast.Expr):
                found.add(id(first.value))
    return found


def _constants(tree: ast.Module) -> list[str]:
    skip = _docstring_ids(tree)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip
    ]


def _import_problems(tree: ast.Module) -> list[str]:
    problems: list[str] = []
    for node in ast.walk(tree):
        roots: set[str] = set()
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            roots = {(node.module or "").split(".")[0]}
        if roots & BANNED_IMPORTS:
            problems.append("import")
        func = node.func if isinstance(node, ast.Call) else None
        owner = func.value if isinstance(func, ast.Attribute) else None
        regex = isinstance(owner, ast.Name) and owner.id == "re"
        if regex and isinstance(func, ast.Attribute) and func.attr == "compile":
            problems.append("re.compile")
    if [value for value in _constants(tree) if "oracle9_w1_supervisor" in value]:
        problems.append("qualifier-or-c0-reference")  # never read at runtime by the main
    return problems


def _stdio_violations(tree: ast.Module) -> list[str]:
    main = _function(tree, "main")
    inside = set() if main is None else {id(node) for node in ast.walk(main)}
    problems: list[str] = []
    seen: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "stderr":
            problems.append("stderr")
        port = isinstance(node, ast.Attribute) and node.attr in ("stdin", "stdout")
        if port and isinstance(node, ast.Attribute):
            seen.add(node.attr)
            problems += [node.attr] if id(node) not in inside else []
        if isinstance(node, ast.Name) and node.id == "print":
            problems.append("print")
    if seen != {"stdin", "stdout"}:
        problems.append("ports-not-captured-by-main")
    return problems


# ---------------------------------------------------------------- inert text fixtures

RUN_S_ERROR = (
    "    except Exception as error:\n"
    "        if holder.first_error is None:\n"
    "            holder.first_error = error\n"
    "        return 3\n"
)
RUN_S_CONTROL = (
    "    except BaseException as control:\n"
    "        if holder.first_control is None and (\n"
    "            holder.custody is None or holder.custody.first_control is None\n"
    "        ):\n"
    "            holder.first_control = control\n"
    "        return None\n"
)
RUN_S_A = (
    "def _run_s(argv, holder):\n"
    "    try:\n"
    "        values = _inputs(argv)\n"
    "        if values is None:\n"
    "            return 2\n"
    "        _load_entry(holder)\n"
    "        _prepare(holder, values[0], values[1])\n" + RUN_S_ERROR + RUN_S_CONTROL
)
RUN_S_GOOD = RUN_S_A + "    return _enter(holder)\n"
REGION_A_BAD = {
    "error-not-first": RUN_S_GOOD.replace(
        "        if holder.first_error is None:\n            holder.first_error = error\n",
        "        holder.first_error = error\n",
    ),
    "error-not-exit-3": RUN_S_GOOD.replace(
        "            holder.first_error = error\n        return 3\n",
        "            holder.first_error = error\n        return None\n",
    ),
    "control-exit-3": RUN_S_GOOD.replace(
        "            holder.first_control = control\n        return None\n",
        "            holder.first_control = control\n        return 3\n",
    ),
    "control-replaces-entry": RUN_S_GOOD.replace(
        "holder.custody is None or holder.custody.first_control is None",
        "holder.custody is None or holder.custody.first_control is not None",
    ),
    "no-control-handler": RUN_S_GOOD.replace(RUN_S_CONTROL, ""),
    "exit-3-after-entry": RUN_S_GOOD.replace(
        "    return _enter(holder)\n",
        "    code = _enter(holder)\n    return 3 if code is None else code\n",
    ),
}
RUN_S_ENTER_IN_A = RUN_S_A.replace(
    "        _prepare(holder, values[0], values[1])\n",
    "        _prepare(holder, values[0], values[1])\n        return _enter(holder)\n",
)
ENTER_HEAD = "def _enter(holder):\n    try:\n"
REENTRY = "        if holder.entered is not False:\n            return None\n"
CUSTODY_GUARDS = (
    "        custody = holder.custody\n"
    "        if type(custody) is not holder.entry.EntryCustody:\n"
    "            return None\n"
    "        if custody.claimed is not False:\n"
    "            return None\n"
    "        if custody.owner is not None:\n"
    "            return None\n"
    "        if custody.first_control is not None:\n"
    "            return None\n"
)
MARK = "        holder.entered = True\n"
CALL = (
    "        holder.result = holder.entry.run_entry(\n"
    "            holder.adoption, holder.request, holder.reader, holder.writer,\n"
    "            holder.entry.MAX_TURNS, custody\n"
    "        )\n"
)
MAPPING = "        return _EXIT.get(holder.result) if type(holder.result) is str else None\n"
HANDLERS = (
    "    except Exception as error:\n"
    "        if holder.first_error is None:\n"
    "            holder.first_error = error\n"
    "        return None\n"
    "    except BaseException as control:\n"
    "        if holder.first_control is None and (\n"
    "            holder.custody is None or holder.custody.first_control is None\n"
    "        ):\n"
    "            holder.first_control = control\n"
    "        return None\n"
)
ENTER_GOOD = ENTER_HEAD + REENTRY + CUSTODY_GUARDS + MARK + CALL + MAPPING + HANDLERS
ENTER_BAD = {
    "no-reentry": ENTER_GOOD.replace(REENTRY, ""),
    "no-owner-guard": ENTER_GOOD.replace(
        "        if custody.owner is not None:\n            return None\n", ""
    ),
    "mark-after-call": "".join(
        (ENTER_HEAD, REENTRY, CUSTODY_GUARDS, CALL, MARK, MAPPING, HANDLERS)
    ),
    "guard-after-mark": "".join(
        (ENTER_HEAD, REENTRY, MARK, CUSTODY_GUARDS, CALL, MAPPING, HANDLERS)
    ),
    "reentry-after-guards": "".join(
        (ENTER_HEAD, CUSTODY_GUARDS, REENTRY, MARK, CALL, MAPPING, HANDLERS)
    ),
    "call-outside-try": "".join(
        (
            "def _enter(holder):\n    holder.entry.run_entry(holder)\n    try:\n",
            REENTRY,
            CUSTODY_GUARDS,
            MARK,
            MAPPING,
            HANDLERS,
        )
    ),
    "loop": ENTER_GOOD.replace(
        CALL, "        for _ in range(1):\n    " + CALL.replace("\n", "\n    ")
    ),
    "handler-call": ENTER_GOOD.replace(
        "            holder.first_error = error\n",
        "            holder.first_error = error\n            _park_s(holder)\n",
    ),
    "handler-raise": ENTER_GOOD.replace(
        "            holder.first_error = error\n",
        "            holder.first_error = error\n            raise\n",
    ),
    "control-rule": ENTER_GOOD.replace(
        "        if holder.first_control is None and (\n"
        "            holder.custody is None or holder.custody.first_control is None\n"
        "        ):\n",
        "        if holder.first_control is None:\n",
    ),
    "custody-write": ENTER_GOOD.replace(MARK, "        custody.claimed = True\n" + MARK),
    "no-classification": ENTER_GOOD.replace(MAPPING, "        return 0\n"),
}
PARK_GOOD = (
    "def _park_s(holder):\n"
    "    retained = holder\n"
    "    while True:\n"
    "        try:\n"
    "            while retained is not None:\n"
    "                time.sleep(_PARK_SLICE_S)\n"
    "        except BaseException:\n"
    "            continue\n"
)
PARK_BAD = {
    "return": PARK_GOOD + "    return None\n",
    "break": PARK_GOOD.replace("            continue\n", "            break\n"),
    "close": PARK_GOOD.replace(
        "                time.sleep(_PARK_SLICE_S)\n",
        "                time.sleep(_PARK_SLICE_S)\n                holder.close()\n",
    ),
    "other-slice": PARK_GOOD.replace("time.sleep(_PARK_SLICE_S)", "time.sleep(1)"),
    "ordinary-handler": PARK_GOOD.replace("except BaseException:", "except Exception:"),
    "no-holder": PARK_GOOD.replace("    retained = holder\n", "    retained = 1\n"),
    "no-outer-loop": PARK_GOOD.replace("    while True:\n", "    if True:\n"),
}
MAIN_HEAD = (
    "def main(argv):\n"
    "    holder = SHolder()\n"
    "    code = None\n"
    "    try:\n"
    "        holder.reader, holder.writer = sys.stdin.buffer, sys.stdout.buffer\n"
    "        code = _run_s(argv, holder)\n"
)
MAIN_ERROR = (
    "    except Exception as error:\n"
    "        if holder.first_error is None:\n"
    "            holder.first_error = error\n"
    "        code = 3 if holder.entered is False else None\n"
)
MAIN_CONTROL = (
    "    except BaseException as control:\n"
    "        if holder.first_control is None and (\n"
    "            holder.custody is None or holder.custody.first_control is None\n"
    "        ):\n"
    "            holder.first_control = control\n"
    "        code = None\n"
)
MAIN_TAIL = "    if code is None:\n        _park_s(holder)\n    return code\n"
MAIN_GOOD = MAIN_HEAD + MAIN_ERROR + MAIN_CONTROL + MAIN_TAIL
MAIN_BAD = {
    "no-entered": MAIN_GOOD.replace("3 if holder.entered is False else None", "3"),
    "handler-park": MAIN_GOOD.replace(
        "        code = None\n    if code is None:\n",
        "        _park_s(holder)\n    if code is None:\n",
    ),
    "run-outside": MAIN_GOOD.replace("        code = _run_s(argv, holder)\n", "").replace(
        MAIN_TAIL, "    code = _run_s(argv, holder)\n" + MAIN_TAIL
    ),
    "error-not-first": MAIN_GOOD.replace(
        "        if holder.first_error is None:\n            holder.first_error = error\n",
        "        holder.first_error = error\n",
    ),
    "control-exit-3": MAIN_GOOD.replace(
        "            holder.first_control = control\n        code = None\n",
        "            holder.first_control = control\n        code = 3\n",
    ),
    "control-replaces-entry": MAIN_GOOD.replace(
        "holder.custody is None or holder.custody.first_control is None",
        "holder.custody is None or holder.custody.first_control is not None",
    ),
}
MODULE_GOOD = "".join(
    (
        '"""Inert fixture module with the guard shape."""\n',
        "\nimport sys\nimport time\n\n_PARK_SLICE_S = 1.0\n\n",
        MAIN_GOOD,
        "\n",
        GUARD_TEXT,
    )
)
# Permitted equivalent shapes: the classifiers must not demand one implementation text.
ENTER_OR_FORM = ENTER_GOOD.replace(
    "        if custody.claimed is not False:\n"
    "            return None\n"
    "        if custody.owner is not None:\n"
    "            return None\n",
    "        if custody.claimed is not False or custody.owner is not None:\n"
    "            return None\n",
)
MAIN_IF_FORM = MAIN_GOOD.replace(
    "        code = 3 if holder.entered is False else None\n",
    "        if holder.entered is False:\n            code = 3\n",
)
PARK_ENDLESS_FORM = PARK_GOOD.replace(
    "            while retained is not None:\n", "            while True:\n"
)
PARK_DIRECT_FORM = PARK_GOOD.replace("    retained = holder\n", "").replace(
    "while retained is not None", "while holder is not None"
)


def _fixture(*parts: str) -> ast.Module:
    return ast.parse("\n\n".join(parts))


# ---------------------------------------------------------------- fake-only sanities


def test_sanity_pins_of_reused_public_sources_and_frozen_helpers() -> None:
    raw = ENTRY_FILE.read_bytes()
    assert len(raw) == ENTRY_SIZE <= LOAD_LIMIT
    assert hashlib.sha256(raw).hexdigest() == ENTRY_SHA
    assert raw.count(SWAP_FROM) == 1 and len(SWAP_FROM) == len(SWAP_TO)
    assert hashlib.sha256(ENTRY_TEST_FILE.read_bytes()).hexdigest() == ENTRY_TEST_SHA
    _parse_pinned(QUAL_FILE, QUAL_SHA)
    _parse_pinned(C0_FILE, C0_SHA)
    assert hashlib.sha256(et.XJ_FILE.read_bytes()).hexdigest() == et.XJ_SHA
    assert callable(et.import_violations) and callable(et.import_effects)
    assert issubclass(et.EntryKernel, xj.AdoptKernel)


def test_sanity_static_extraction_on_pinned_sources() -> None:
    qual = _parse_pinned(QUAL_FILE, QUAL_SHA)
    c0 = _parse_pinned(C0_FILE, C0_SHA)
    entry = _parse_pinned(ENTRY_FILE, ENTRY_SHA)
    with pytest.raises(ValueError, match="malformed node"):
        ast.literal_eval(_top_value(qual, "_LOCAL_PATH"))  # R1: a Call, not a literal
    pattern = _compile_literal(qual, "_LOCAL_PATH")
    assert pattern and type(pattern) is str
    environment = _literal(qual, "_ENV")
    assert type(environment) is tuple and len(environment) == 1
    assert type(_literal(qual, "_NATURAL_CODE")) is str
    assert type(_literal(qual, "_PATH_LIMIT")) is int
    assert type(_literal(qual, "_COMMAND_LIMIT")) is int
    assert _literal(entry, "MAX_TURNS") == _literal(qual, "MAX_TURNS")
    assert type(_literal(c0, "_PARK_SLICE_S")) is float
    command = _function(qual, "_command_line")
    assert command is not None
    assert "_NATURAL_CODE" in _renamed_dump(_returned(command), "code", "_NATURAL_CODE")


@pytest.mark.parametrize(
    "text",
    [
        'X = re.compile("a", 0)\n',
        'X = re.compile("a", flags=0)\n',
        "X = re.compile(PATTERN)\n",
        'X = regex.compile("a")\n',
        'X = re.match("a")\n',
        'X = "a"\n',
    ],
)
def test_sanity_compile_literal_rejects_other_forms(text: str) -> None:
    with pytest.raises(AssertionError):
        _compile_literal(ast.parse(text), "X")


def test_sanity_enter_oracle_accepts_the_specified_shape() -> None:
    assert _enter_violations(_fixture(RUN_S_GOOD, ENTER_GOOD)) == []


@pytest.mark.parametrize("case", sorted(ENTER_BAD))
def test_sanity_enter_oracle_rejects_each_adversarial_shape(case: str) -> None:
    assert _enter_violations(_fixture(RUN_S_GOOD, ENTER_BAD[case])) != []


def test_sanity_enter_oracle_rejects_enter_inside_region_a_and_second_call() -> None:
    assert _enter_violations(_fixture(RUN_S_ENTER_IN_A, ENTER_GOOD)) != []
    second = RUN_S_GOOD + "\n\ndef _again(holder):\n    return holder.entry.run_entry(holder)\n"
    assert _enter_violations(_fixture(second, ENTER_GOOD)) != []


def test_sanity_park_oracle_accepts_the_specified_shape() -> None:
    assert _park_violations(_fixture(PARK_GOOD)) == []


@pytest.mark.parametrize("case", sorted(PARK_BAD))
def test_sanity_park_oracle_rejects_each_adversarial_shape(case: str) -> None:
    assert _park_violations(_fixture(PARK_BAD[case])) != []


def test_sanity_main_region_and_stdio_oracles_on_fixtures() -> None:
    good = _fixture(MAIN_GOOD)
    assert _main_region_violations(good) == [] and _stdio_violations(good) == []
    for case in sorted(MAIN_BAD):
        assert _main_region_violations(_fixture(MAIN_BAD[case])) != [], case
    leaked = _fixture(MAIN_GOOD, "def _other():\n    return sys.stdout\n")
    assert "stdout" in _stdio_violations(leaked)
    assert "stderr" in _stdio_violations(_fixture(MAIN_GOOD, "X = sys.stderr\n"))
    assert "print" in _stdio_violations(_fixture(MAIN_GOOD, "def f():\n    print(1)\n"))


def test_sanity_region_a_oracle_on_fixtures() -> None:
    assert _region_a_violations(_fixture(RUN_S_GOOD)) == []
    for case in sorted(REGION_A_BAD):
        assert _region_a_violations(_fixture(REGION_A_BAD[case])) != [], case


def test_sanity_permitted_equivalent_shapes_are_accepted() -> None:
    """Not one mandated text: an or-combined guard, an if-statement exit 3, other loops."""
    assert ENTER_OR_FORM != ENTER_GOOD and MAIN_IF_FORM != MAIN_GOOD
    assert _enter_violations(_fixture(RUN_S_GOOD, ENTER_OR_FORM)) == []
    assert _main_region_violations(_fixture(MAIN_IF_FORM)) == []
    for form in (PARK_ENDLESS_FORM, PARK_DIRECT_FORM):
        assert form != PARK_GOOD and _park_violations(_fixture(form)) == []


LOADER_GOOD = (
    "class SMainLoadError(Exception):\n"
    "    def __init__(self):\n"
    '        super().__init__("S_MAIN_LOAD")\n'
    "\n"
    "\n"
    "def _load_entry(holder):\n"
    "    failed = False\n"
    "    try:\n"
    "        holder.entry = _execute_checked_bytes()\n"
    "    except Exception:\n"
    "        failed = True\n"
    "    finally:\n"
    "        _restore_own_binding()\n"
    "    if failed:\n"
    "        raise SMainLoadError()\n"
)
LOADER_BAD = {
    "raise-in-handler": LOADER_GOOD.replace(
        "        failed = True\n", "        raise SMainLoadError()\n"
    ),
    "records-first-error": LOADER_GOOD.replace(
        "        failed = True\n", "        failed = True\n        holder.first_error = 1\n"
    ),
    "parks": LOADER_GOOD.replace("        raise SMainLoadError()\n", "        _park_s(holder)\n"),
    "other-text": LOADER_GOOD.replace('"S_MAIN_LOAD"', '"LOAD"'),
    "no-registration-finally": LOADER_GOOD.replace(
        "    finally:\n        _restore_own_binding()\n", ""
    ),
}


def test_sanity_loader_oracle_on_fixtures() -> None:
    assert _loader_violations(_fixture(LOADER_GOOD)) == []
    for case in sorted(LOADER_BAD):
        assert _loader_violations(_fixture(LOADER_BAD[case])) != [], case


def test_sanity_guard_and_import_oracles_on_inert_fixtures(monkeypatch: Any) -> None:
    """Counter-proof of the import/guard oracles; fixtures are inert text, never an entry."""
    tree = ast.parse(MODULE_GOOD)
    assert _guard_ok(tree) and _import_problems(tree) == []
    body = ast.Module(body=tree.body[:-1], type_ignores=[])
    assert et.import_violations(body) == []
    assert et.import_violations(tree) != []  # the guard itself is never a pure statement
    error, effects, namespace = et.import_effects(
        MODULE_GOOD.encode(), "<s-main-inert-fixture>", monkeypatch
    )
    assert error is None and effects == [] and callable(namespace["main"])
    for bad in (
        GUARD_TEXT.replace("sys.argv[1:]", "sys.argv"),
        GUARD_TEXT.replace("raise SystemExit(", "SystemExit("),
        GUARD_TEXT + "else:\n    pass\n",
    ):
        assert not _guard_ok(ast.parse(MODULE_GOOD.replace(GUARD_TEXT, bad)))
    impure = MODULE_GOOD.replace("_PARK_SLICE_S = 1.0\n", "_PARK_SLICE_S = time.time()\n")
    assert et.import_violations(ast.Module(body=ast.parse(impure).body[:-1], type_ignores=[]))
    for text in (
        "import subprocess\n",
        "from tests import x\n",
        'P = re.compile("a")\n',
        'N = "oracle9_w1_supervisor_qualification.py"\n',
    ):
        assert _import_problems(ast.parse(text)) != [], text


# ---------------------------------------------------------------- source loading and seam


def require_source() -> None:
    """Explicit FAIL (never skip/pass/collection error) while the source is absent."""
    if not SOURCE.exists():
        pytest.fail("docs/poc/oracle9_w1_external_job_s_main.py is absent (RED)")


def main_namespace() -> dict[str, Any]:
    require_source()
    return runpy.run_path(str(SOURCE), run_name="_w1_s_main_test")


def source_tree() -> ast.Module:
    require_source()
    return ast.parse(SOURCE.read_bytes())


def seam(monkeypatch: pytest.MonkeyPatch) -> Any:
    """ONE real load and ONE real prepare, then the accepted seams of THAT backend."""
    namespace = main_namespace()
    xj.native_traps(monkeypatch)
    holder = namespace["SHolder"]()
    namespace["_load_entry"](holder)
    namespace["_prepare"](holder, APP, DIR)
    backend = holder.adoption.backend
    kernel = et.EntryKernel()

    def load() -> Any:
        return backend["_Api"](kernel, lambda: kernel.last)

    monkeypatch.setitem(backend, "_load_api", load)
    monkeypatch.setitem(backend, "sys", ref.runtime())
    external = kernel.add_external()
    kernel.exit_at = 1
    holder.reader = et.Reader(kernel, [et.record(external)])
    holder.writer = et.Writer(kernel)
    lab = SimpleNamespace(namespace=namespace, holder=holder, kernel=kernel)
    lab.external = external
    return lab


def custody_snapshot(custody: Any) -> list[object]:
    return [getattr(custody, name) for name in et.FIELDS]


def same(before: list[object], after: list[object]) -> bool:
    return all(old is new for old, new in zip(before, after, strict=True))


def no_new_effect(lab: Any, marker: int) -> None:
    assert lab.kernel.calls[marker:] == []
    assert lab.holder.reader.lookups == 0 and lab.holder.writer.lookups == {}


# ---------------------------------------------------------------- 2. import purity and form


def test_import_is_pure_and_the_guard_is_the_only_entry(monkeypatch: Any) -> None:
    tree = source_tree()
    assert _guard_ok(tree)
    assert et.import_violations(ast.Module(body=tree.body[:-1], type_ignores=[])) == []
    xj.native_traps(monkeypatch)
    error, effects, namespace = et.import_effects(SOURCE.read_bytes(), str(SOURCE), monkeypatch)
    assert error is None and effects == []
    for name in ("SHolder", "_inputs", "_load_entry", "_prepare", "_enter", "_run_s"):
        assert name in namespace
    assert callable(namespace["_park_s"]) and callable(namespace["main"])


def test_imports_stdio_and_regex_are_confined() -> None:
    tree = source_tree()
    assert _import_problems(tree) == []
    assert _stdio_violations(tree) == []


def test_holder_has_exactly_ten_fields_with_redacted_repr() -> None:
    namespace = main_namespace()
    holder_class = namespace["SHolder"]
    holder = holder_class()
    assert dataclasses.is_dataclass(type(holder)) and "__slots__" in vars(holder_class)
    names = [field.name for field in dataclasses.fields(holder_class)]
    assert sorted(names) == sorted(HOLDER_FIELDS) and len(names) == 10
    for name in HOLDER_FIELDS:
        expected = False if name == "entered" else None
        assert getattr(holder, name) is expected, name
    holder.first_error = ValueError(CANARY)
    assert CANARY not in repr(holder)
    assert all(type(value) is not holder_class for value in namespace.values())


# ---------------------------------------------------------------- 3. structure


def test_enter_region_guards_single_call_and_no_repeat_path() -> None:
    assert _enter_violations(source_tree()) == []


def test_park_shape_is_the_specific_retaining_park() -> None:
    assert _park_violations(source_tree()) == []


def test_main_outer_region_consults_entered_and_parks_outside_handlers() -> None:
    assert _main_region_violations(source_tree()) == []


def test_loader_registers_only_temporarily_and_pins_the_entry() -> None:
    tree = source_tree()
    loader = _function(tree, "_load_entry")
    assert loader is not None
    assert _loader_violations(tree) == []
    assert any(isinstance(n, ast.Attribute) and n.attr == "modules" for n in ast.walk(loader))
    constants = _constants(tree)
    assert ENTRY_SHA in constants and ENTRY_FILE.name in constants


def test_region_a_keeps_first_objects_and_exit_3_only_before_entry() -> None:
    """SM-R4: phase-A recording, exit 3 and park after a loader control are STRUCTURAL."""
    assert _region_a_violations(source_tree()) == []


def test_structural_only_gaps_keep_their_shape_obligations() -> None:
    """Not reachable through faithful ports: escaping Exception from run_entry, control in
    the post-return gap/classification, control in _inputs, the outer main region."""
    tree = source_tree()
    enter = _function(tree, "_enter")
    assert enter is not None
    region = _strip_docstring(enter.body)[0]
    assert isinstance(region, ast.Try)
    assert _region_shape(region) == []
    for handler in region.handlers:
        assert _returns_only(handler, None)
    run_s = _function(tree, "_run_s")
    assert run_s is not None
    inputs = _calls(run_s, "_inputs")
    tries = [n for n in ast.walk(run_s) if isinstance(n, ast.Try)]
    assert len(inputs) == 1 and any(_contains(t.body, inputs[0]) for t in tries)
    assert _region_a_violations(tree) == []
    assert _main_region_violations(tree) == []


# ---------------------------------------------------------------- 4. static compatibility


def test_profile_path_budget_and_park_slice_match_pinned_sources() -> None:
    tree = source_tree()
    qual = _parse_pinned(QUAL_FILE, QUAL_SHA)
    c0 = _parse_pinned(C0_FILE, C0_SHA)
    entry = _parse_pinned(ENTRY_FILE, ENTRY_SHA)
    for name in ("_ENV", "_NATURAL_CODE", "_PATH_LIMIT", "_COMMAND_LIMIT"):
        assert _literal(tree, name) == _literal(qual, name), name
    assert _literal(tree, "_PARK_SLICE_S") == _literal(c0, "_PARK_SLICE_S")
    assert _literal(entry, "MAX_TURNS") == _literal(qual, "MAX_TURNS")
    pattern = _top_value(tree, "_LOCAL_PATTERN")
    assert isinstance(pattern, ast.Constant) and type(pattern.value) is str
    assert pattern.value == _compile_literal(qual, "_LOCAL_PATH")
    inputs = _function(tree, "_inputs")
    assert inputs is not None
    matches = [
        call
        for call in _calls(inputs, "fullmatch")
        if isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "re"
        and call.args
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "_LOCAL_PATTERN"
    ]
    assert matches
    mine, theirs = _function(tree, "_natural_command"), _function(qual, "_command_line")
    assert mine is not None and theirs is not None
    expected = _renamed_dump(_returned(theirs), "code", "_NATURAL_CODE")
    assert ast.dump(_returned(mine)) == expected


# ---------------------------------------------------------------- 5. loading


def _tree(root: Path, entry: bytes | None, *, directory: bool = False) -> Path:
    poc = root / "docs" / "poc"
    poc.mkdir(parents=True)
    copy_path = poc / SOURCE.name
    copy_path.write_bytes(SOURCE.read_bytes())
    (poc / et.XJ_FILE.name).write_bytes(et.XJ_FILE.read_bytes())
    (poc / xj.BACKEND_FILE.name).write_bytes(xj.BACKEND_FILE.read_bytes())
    if directory:
        (poc / ENTRY_FILE.name).mkdir()
    elif entry is not None:
        (poc / ENTRY_FILE.name).write_bytes(entry)
    return copy_path


def phase_a_refusal(holder: Any, code: object, expected: int) -> None:
    """Phase A: before ``entered``; no adoption, Request, custody, result or control."""
    assert type(code) is int and code == expected
    assert holder.entered is False and holder.adoption is None and holder.custody is None
    assert holder.request is None and holder.result is None and holder.first_control is None
    error = holder.first_error
    assert error is None or isinstance(error, Exception)


def loader_refusal(namespace: dict[str, Any], holder: Any, error: BaseException | None) -> None:
    """SM-R4: the closed ``SMainLoadError`` only; never a trap AssertionError."""
    assert error is not None and type(error) is namespace["SMainLoadError"]
    assert error.args == ("S_MAIN_LOAD",)
    assert error.__cause__ is None and error.__context__ is None
    assert holder.adoption is None and holder.request is None and holder.custody is None
    assert holder.entered is False and holder.result is None
    assert holder.first_error is None and holder.first_control is None  # caller's job


def tree_namespace(copy_path: Path, run_name: str) -> dict[str, Any]:
    require_source()
    return runpy.run_path(str(copy_path), run_name=run_name)


def test_load_entry_executes_the_pinned_entry_and_restores_registration(monkeypatch: Any) -> None:
    namespace = main_namespace()
    xj.native_traps(monkeypatch)
    holder = namespace["SHolder"]()
    before = set(sys.modules)
    namespace["_load_entry"](holder)
    entry = holder.entry
    assert type(entry) is types.ModuleType
    entry_file = entry.__file__
    assert isinstance(entry_file, str)
    assert Path(entry_file).resolve() == ENTRY_FILE.resolve()
    assert entry.__name__ not in sys.modules and set(sys.modules) - before == set()
    assert entry.EntryCustody.__module__ == entry.__name__  # the dataclasses needed it
    assert type(holder.adoption) is entry.AdoptionLoad
    assert holder.request is None and holder.custody is None and holder.entered is False


@pytest.mark.parametrize("kind", ["missing", "tampered", "oversize", "directory"])
def test_bad_entry_is_refused_by_the_loader_before_execution(
    tmp_path: Path, monkeypatch: Any, kind: str
) -> None:
    require_source()
    xj.native_traps(monkeypatch)
    marker = tmp_path / "executed"
    raw = ENTRY_FILE.read_bytes()
    entry: bytes | None = None
    if kind == "tampered":
        entry = raw + et._marker_payload(marker)
    elif kind == "oversize":
        entry = raw + ("#" + "x" * LOAD_LIMIT + "\n").encode() + et._marker_payload(marker)
    copy_path = _tree(tmp_path / kind, entry, directory=kind == "directory")
    namespace = tree_namespace(copy_path, "_w1_s_main_tree")
    holder = namespace["SHolder"]()
    loader_refusal(namespace, holder, xj.error_of(lambda: namespace["_load_entry"](holder)))
    assert not marker.exists()


@pytest.mark.parametrize("kind", ["reparse", "size"])
def test_forged_entry_metadata_is_refused(tmp_path: Path, monkeypatch: Any, kind: str) -> None:
    require_source()
    xj.native_traps(monkeypatch)
    copy_path = _tree(tmp_path, ENTRY_FILE.read_bytes())
    namespace = tree_namespace(copy_path, "_w1_s_main_meta")
    holder = namespace["SHolder"]()
    with monkeypatch.context() as patch:
        et._forge_metadata(patch, copy_path.parent / ENTRY_FILE.name, kind)
        error = xj.error_of(lambda: namespace["_load_entry"](holder))
    loader_refusal(namespace, holder, error)


def test_load_executes_the_same_captured_entry_bytes(tmp_path: Path, monkeypatch: Any) -> None:
    require_source()
    xj.native_traps(monkeypatch)
    raw = ENTRY_FILE.read_bytes()
    copy_path = _tree(tmp_path, raw)
    namespace = tree_namespace(copy_path, "_w1_s_main_same")
    target = copy_path.parent / ENTRY_FILE.name
    key = os.path.normcase(str(target.resolve()))
    real_open = io.open
    opened: list[str] = []

    def fake_open(file: Any, mode: Any = "r", *args: Any, **kwargs: Any) -> Any:
        if et._same_path(file, key):
            opened.append(str(mode))
            if len(opened) == 1:
                with real_open(file, "rb") as stream:
                    data = stream.read()
                with real_open(file, "wb") as stream:  # swapped AFTER the capture
                    stream.write(raw.replace(SWAP_FROM, SWAP_TO))
                return io.BytesIO(data)
        return real_open(file, mode, *args, **kwargs)

    holder = namespace["SHolder"]()
    with monkeypatch.context() as patch:  # scoped stdlib port
        patch.setattr(io, "open", fake_open)
        patch.setattr(builtins, "open", fake_open)
        namespace["_load_entry"](holder)
    assert opened == ["rb"] and holder.entry.__doc__.startswith("W1 entry of S")
    other = namespace["SHolder"]()
    swapped = xj.error_of(lambda: namespace["_load_entry"](other))
    loader_refusal(namespace, other, swapped)  # the swap was real


def test_blocked_module_name_is_refused_and_left_untouched(monkeypatch: Any) -> None:
    namespace = main_namespace()
    xj.native_traps(monkeypatch)
    first = namespace["SHolder"]()
    namespace["_load_entry"](first)
    name = first.entry.__name__
    sentinel = types.ModuleType(name)
    monkeypatch.setitem(sys.modules, name, sentinel)
    holder = namespace["SHolder"]()
    loader_refusal(namespace, holder, xj.error_of(lambda: namespace["_load_entry"](holder)))
    assert sys.modules[name] is sentinel


def test_control_during_load_propagates_by_identity(tmp_path: Path, monkeypatch: Any) -> None:
    """SM-R4: the loader neither wraps nor records a control; recording/park are the
    caller's STRUCTURAL obligation (see the region-A oracle)."""
    require_source()
    xj.native_traps(monkeypatch)
    copy_path = _tree(tmp_path, ENTRY_FILE.read_bytes())
    namespace = tree_namespace(copy_path, "_w1_s_main_ctl")
    key = os.path.normcase(str((copy_path.parent / ENTRY_FILE.name).resolve()))
    control = xj.KernelCtl()
    ports = {"stat": os.stat, "lstat": os.lstat}
    real_open = io.open

    def scripted(original: Callable[..., Any]) -> Callable[..., Any]:
        def call(path: Any, *args: Any, **kwargs: Any) -> Any:
            if et._same_path(path, key):
                raise control
            return original(path, *args, **kwargs)

        return call

    holder = namespace["SHolder"]()
    with monkeypatch.context() as patch:
        for name, original in ports.items():
            patch.setattr(os, name, scripted(original))
        patch.setattr(io, "open", scripted(real_open))
        patch.setattr(builtins, "open", scripted(real_open))
        outcome = xj.error_of(lambda: namespace["_load_entry"](holder))
    assert outcome is control
    assert control.__cause__ is None and control.__context__ is None
    assert holder.first_control is None and holder.first_error is None
    assert holder.adoption is None and holder.entered is False and holder.custody is None


# ---------------------------------------------------------------- 6. inputs


def _bad_argv() -> list[object]:
    sub = type("StrSub", (str,), {})
    return [
        None,
        (APP, DIR),
        [APP],
        [APP, DIR, DIR],
        [APP, 5],
        [sub(APP), DIR],
        ["relative.exe", DIR],
        [APP, 'C:\\a"b'],
        [APP + "\x00", DIR],
        [APP, DIR + "\r"],
        [APP, DIR + "\n"],
        ["", DIR],
        ["C:\\" + "a" * 1022, DIR],
        ["\\\\server\\share\\x.exe", DIR],
    ]


@pytest.mark.parametrize("index", range(14))
def test_argv_outside_the_domain_exits_2_without_file_access(monkeypatch: Any, index: int) -> None:
    namespace = main_namespace()
    holder = namespace["SHolder"]()
    argv = _bad_argv()[index]
    with monkeypatch.context() as patch:
        for name in ("open", "lstat", "stat", "read_bytes", "resolve"):
            patch.setattr(Path, name, xj.forbidden)
        patch.setattr(io, "open", xj.forbidden)
        code = namespace["_run_s"](argv, holder)
    phase_a_refusal(holder, code, 2)
    assert holder.entry is None


def test_valid_argv_is_returned_as_the_exact_pair() -> None:
    namespace = main_namespace()
    assert namespace["_inputs"]([APP, DIR]) == (APP, DIR)


# ---------------------------------------------------------------- 7. dynamic flow (seam)


def test_prepare_builds_the_request_from_the_same_adoption_with_fresh_custody(
    monkeypatch: Any,
) -> None:
    lab = seam(monkeypatch)
    holder, namespace = lab.holder, lab.namespace
    adoption, request = holder.adoption, holder.request
    assert type(request) is adoption.Request
    assert request.application == APP and request.directory == DIR
    assert request.command_line == namespace["_natural_command"](APP)
    qual = _parse_pinned(QUAL_FILE, QUAL_SHA)
    assert request.environment == _literal(qual, "_ENV")
    assert type(holder.custody) is holder.entry.EntryCustody
    et.assert_defaults(holder.entry, holder.custody)
    assert holder.entered is False and holder.result is None and lab.kernel.calls == []


def _script(lab: Any, category: str) -> None:
    """Faithful fake-SDK/port scripts already used by test 1835; DONE needs none."""
    if category == "DONE_NONZERO":
        lab.kernel.exit_value = 3
    elif category == "REFUSED":
        lab.holder.reader.items = [b"W1XT1 0\n"]
    elif category == "SETUP_REFUSED":
        lab.kernel.plan["CreateJobObjectW"] = ("false", 5)
    elif category == "ACK_FAILED":
        lab.holder.writer.returns = ["short"]


@pytest.mark.parametrize("category", sorted(EXITS))
def test_reachable_categories_map_to_their_exit_codes(
    monkeypatch: Any, capsys: pytest.CaptureFixture[str], category: str
) -> None:
    lab = seam(monkeypatch)
    holder = lab.holder
    reader, writer = holder.reader, holder.writer
    request, custody = holder.request, holder.custody
    _script(lab, category)
    code = lab.namespace["_enter"](holder)
    assert type(code) is int and code == EXITS[category]
    assert holder.result == category and holder.entered is True
    assert holder.reader is reader and holder.writer is writer
    assert holder.request is request and holder.custody is custody
    assert custody.request is request and custody.adoption is holder.adoption
    assert custody.owner is not None and custody.owner.state == "CLOSED"
    assert holder.first_error is None and holder.first_control is None
    assert capsys.readouterr() == ("", "")
    xj.assert_c_safe(lab.kernel, lab.external)


@pytest.mark.parametrize("cause", ["entry-control", "budget"])
def test_retain_parks_without_overwriting_the_entry_control(monkeypatch: Any, cause: str) -> None:
    lab = seam(monkeypatch)
    holder = lab.holder
    control = xj.KernelCtl()
    if cause == "entry-control":
        holder.reader.items = [control]
    else:
        lab.kernel.exit_at = None  # alive child: the pinned MAX_TURNS budget is exhausted
    assert lab.namespace["_enter"](holder) is None
    assert holder.result == "RETAIN" and holder.entered is True
    custody = holder.custody
    assert custody.owner is not None and custody.owner.state != "CLOSED"
    assert holder.first_control is None and holder.first_error is None
    assert custody.first_control is (control if cause == "entry-control" else None)
    xj.assert_c_safe(lab.kernel, lab.external)


# ---------------------------------------------------------------- 8. hostile own-holder data


def test_entered_flag_parks_without_any_effect(monkeypatch: Any) -> None:
    lab = seam(monkeypatch)
    holder = lab.holder
    before = custody_snapshot(holder.custody)
    holder.entered = True
    assert lab.namespace["_enter"](holder) is None
    no_new_effect(lab, 0)
    assert holder.result is None and same(before, custody_snapshot(holder.custody))


@pytest.mark.parametrize("cause", ["entry-control", "budget"])
def test_used_custody_keeps_the_same_real_owner_without_new_effect(
    monkeypatch: Any, cause: str
) -> None:
    lab = seam(monkeypatch)
    holder, kernel = lab.holder, lab.kernel
    if cause == "entry-control":
        holder.reader.items = [xj.KernelCtl()]
    else:
        kernel.exit_at = None
    assert lab.namespace["_enter"](holder) is None
    custody = holder.custody
    owner = custody.owner
    assert type(owner) is holder.adoption.ExternalJobOwner  # the real fake-SDK Owner
    state, result, before = owner.state, holder.result, custody_snapshot(custody)
    marker = len(kernel.calls)
    holder.entered = False  # hostile own-holder data
    holder.reader, holder.writer = et.Reader(kernel, []), et.Writer(kernel)
    assert lab.namespace["_enter"](holder) is None
    no_new_effect(lab, marker)
    assert holder.entered is False and holder.result is result
    assert holder.custody is custody and custody.owner is owner and owner.state == state
    assert same(before, custody_snapshot(custody))
    xj.assert_c_safe(kernel, lab.external)


GUARD_CASES = ("namespace", "subclass", "claimed", "owner", "first_control")


@pytest.mark.parametrize("case", GUARD_CASES)
def test_each_custody_guard_parks_before_entry_without_effect(monkeypatch: Any, case: str) -> None:
    lab = seam(monkeypatch)
    holder = lab.holder
    custody = holder.custody
    if case == "namespace":
        values = dict(zip(et.FIELDS, custody_snapshot(custody), strict=True))
        holder.custody = SimpleNamespace(**values)
    elif case == "subclass":
        forged = type("ForgedCustody", (holder.entry.EntryCustody,), {"__slots__": ()})
        holder.custody = forged()
    elif case == "claimed":
        custody.claimed = True
    elif case == "owner":
        custody.owner = object()
    else:
        custody.first_control = xj.KernelCtl()
    before = custody_snapshot(holder.custody)
    assert lab.namespace["_enter"](holder) is None
    no_new_effect(lab, 0)
    assert holder.entered is False and holder.result is None
    assert same(before, custody_snapshot(holder.custody))


@pytest.mark.parametrize("kind", ["object", "text", "other-load"])
def test_wrong_request_type_with_fresh_custody_is_rejected_14(monkeypatch: Any, kind: str) -> None:
    lab = seam(monkeypatch)
    holder, namespace = lab.holder, lab.namespace
    if kind == "object":
        holder.request = object()
    elif kind == "text":
        holder.request = CANARY
    else:
        other = namespace["SHolder"]()
        namespace["_load_entry"](other)
        namespace["_prepare"](other, APP, DIR)
        assert type(other.request) is not holder.adoption.Request
        holder.request = other.request
    custody = holder.custody
    et.assert_defaults(holder.entry, custody)  # truly fresh: no Owner, no control
    code = namespace["_enter"](holder)
    assert type(code) is int and code == 14
    assert holder.result == "REJECTED" and holder.entered is True
    no_new_effect(lab, 0)
    assert holder.custody is custody
    et.assert_defaults(holder.entry, custody)  # the entry wrote nothing


def test_qbase_controls_are_not_inspected_by_the_main(monkeypatch: Any) -> None:
    lab = seam(monkeypatch)
    probes: list[str] = []
    control = qbase.BoomCtl(probes)
    lab.holder.reader.items = [control]
    assert lab.namespace["_enter"](lab.holder) is None
    assert probes == [] and lab.holder.custody.first_control is control
    assert lab.holder.first_control is None


# ---------------------------------------------------------------- root regressions (lot A)
# Root-measured false acceptances (receipt external-job-s-main-test-initial-root-probes).
# Each case feeds INERT text to the ACTUAL current classifier; nothing here is executed.


def test_sanity_root_regression_enter_rejects_reversed_owner_guard() -> None:
    owner_guard = "        if custody.owner is not None:\n"
    assert ENTER_GOOD.count(owner_guard) == 1
    reversed_guard = ENTER_GOOD.replace(owner_guard, "        if custody.owner is None:\n")
    assert _enter_violations(_fixture(RUN_S_GOOD, reversed_guard)) != []


def test_sanity_root_regression_enter_rejects_reversed_first_control_retention() -> None:
    retention = "holder.custody is None or holder.custody.first_control is None"
    assert ENTER_GOOD.count(retention) == 1
    reversed_rule = ENTER_GOOD.replace(
        retention, "holder.custody is None or holder.custody.first_control is not None"
    )
    assert _enter_violations(_fixture(RUN_S_GOOD, reversed_rule)) != []


def test_sanity_root_regression_main_rejects_release_after_entered() -> None:
    decision = "3 if holder.entered is False else None"
    assert MAIN_GOOD.count(decision) == 1
    reversed_main = MAIN_GOOD.replace(decision, "3 if holder.entered is True else None")
    assert _main_region_violations(_fixture(reversed_main)) != []


def test_sanity_root_regression_park_rejects_forgotten_references() -> None:
    keep = "    retained = holder\n"
    assert PARK_GOOD.count(keep) == 1
    forgetful = PARK_GOOD.replace(keep, keep + "    holder = None\n    retained = None\n")
    assert _park_violations(_fixture(forgetful)) != []


def test_sanity_root_regression_park_rejects_unreachable_sleep() -> None:
    inner = "            while retained is not None:\n"
    assert PARK_GOOD.count(inner) == 1
    unreachable = PARK_GOOD.replace(inner, "            while False:\n")
    assert _park_violations(_fixture(unreachable)) != []


MAIN_WITHOUT_FIRST_SLOTS = (
    "def main(argv):\n"
    "    holder = SHolder()\n"
    "    code = None\n"
    "    try:\n"
    "        holder.reader, holder.writer = sys.stdin.buffer, sys.stdout.buffer\n"
    "        code = _run_s(argv, holder)\n"
    "    except Exception:\n"
    "        code = 3 if holder.entered is False else None\n"
    "    except BaseException:\n"
    "        code = None\n"
    "    if code is None:\n"
    "        _park_s(holder)\n"
    "    return code\n"
)  # standalone literal: never records holder.first_error nor holder.first_control


def test_sanity_root_regression_main_rejects_lost_first_error_and_control() -> None:
    tree = _fixture(MAIN_WITHOUT_FIRST_SLOTS)
    names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "first_error" not in names and "first_control" not in names
    assert _main_region_violations(tree) != []


# ---------------------------------------------------------------- root regressions (lot C)
# Root-measured false acceptances (receipt first-slot-extra-writes-red): one more
# UNCONDITIONAL write to the same slot right after the protected one replaces the first
# object. Inert text fed to the ACTUAL classifiers; nothing here is executed.

EXTRA_WRITE_SLOTS = {"first_error": "error", "first_control": "control"}


ExtraWriteCase = tuple[str, str, Callable[[ast.Module], list[str]]]


def _extra_write_case(site: str) -> ExtraWriteCase:
    """(unchanged prefix, region text to mutate, actual classifier)."""
    if site == "enter":
        return RUN_S_GOOD, ENTER_GOOD, _enter_violations  # only the _enter text mutates
    if site == "main":
        return "", MAIN_GOOD, _main_region_violations
    assert site == "region-a"
    return "", RUN_S_GOOD, _region_a_violations


@pytest.mark.parametrize("slot", sorted(EXTRA_WRITE_SLOTS))
@pytest.mark.parametrize("site", ["enter", "main", "region-a"])
def test_sanity_root_extra_write_rejects_unconditional_second_write(site: str, slot: str) -> None:
    prefix, text, classifier = _extra_write_case(site)
    name = EXTRA_WRITE_SLOTS[slot]
    protected = f"            holder.{slot} = {name}\n"
    assert text.count(protected) == 1  # the unique mutation anchor
    mutated = text.replace(protected, protected + f"        holder.{slot} = {name}\n")
    assert mutated.count(f"holder.{slot} = {name}\n") == 2
    assert classifier(ast.parse(prefix + "\n\n" + mutated)) != []
