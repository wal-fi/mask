"""First fake oracles for the S entry of the external job adoption (XE2 under ER1-ER3).

Contract for the FUTURE ``docs/poc/oracle9_w1_external_job_entry.py``. The source stays
ABSENT until the root reads every oracle and freezes RED. Each source-dependent case loads
it explicitly inside its body; an absent source is an explicit ``pytest.fail``, never a
skip, a pass or a collection/fixture error. ``test_sanity_*`` cases exercise only this
file's fake helpers and are NOT product proof.

Fakes: the published ``AdoptKernel`` of the N-S test (itself the frozen raw kernel32 fake
``Kernel``) is reused through one small subclass that adds a scripted natural exit of P,
a scripted wait inconsistency, pipe reads bounded by the requested size, an optional EOF
while P is alive, an optional broken read and post-exit accounting/members faults. Only the
private executed backend copy's ``_load_api``/``sys`` seams are replaced; stdlib traps
forbid a real DLL, process, shell or thread. stdin/stdout are concrete binary port fakes
whose events join the kernel trace. No live product function, Owner or main is replaced.

ER3 overrides XE2/ER2 where narrower: after a positive exit, accounting (1, 0) OR (2, 0)
plus exact empty members discharges; N-S pre-resume stays (1, 1). R1 (test review V1): a
turn may end with a fresh ``available() is None`` observed AFTER the positive inventory and
the turn's read, so no extra EOF turn is required.

Honest dynamic gaps, left to the root's review of the future source (no product patch, no
fake Owner): an adopt result outside the eight closed values; non-exact return types of
the backend public methods; and, because the pinned backend caches EOF, whether the
``available()`` that closes was really called after the inventory/last read (the faithful
SDK makes it indistinguishable from an earlier cached one).

Import purity is checked twice: ``import_violations`` (operations allowed in the module
body) and ``import_effects`` (body executed from bytes compiled BEFORE scoped stdlib traps,
restored before any assertion). ``test_sanity_import_*`` cases apply both to inert
in-memory fixtures only; they never create or call an entry.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium. Senff policy: AI-generated
tests require human and security review.
"""

from __future__ import annotations

import ast
import builtins
import ctypes
import dataclasses
import enum
import hashlib
import io
import os
import runpy
import socket
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from ctypes import wintypes
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from tests import test_oracle9_w1_external_job_adoption as xj
from tests import test_oracle9_w1_supervisor_qualification as qbase
from tests import test_pg16_shell_native_control_win32 as ref

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "docs/poc/oracle9_w1_external_job_entry.py"
XJ_FILE = REPO / "docs/poc/oracle9_w1_external_job_adoption.py"
XJ_SHA = "465ae9067e0f24fe656259e3757f45e8a5788f55ed177db2ab82160d5b6ba5ae"
XJ_SIZE = 15836
LOAD_LIMIT = 65536
MAX_TURNS = 400  # the qualifier's source cap, reused by XE2/ER2
MAX_WAIT_MS, MAX_READ = 50, 4096  # backend 10c9058f constants (sanity-checked below)
INVALID = (1 << 64) - 1
CANARY = "SYNTHETIC-ENTRY-CANARY-DO-NOT-RETAIN"
APP = r"C:\fictional\w1\entry\python.exe"  # fictional; only the fake kernel sees it
COMMAND = f'"{APP}" -I -B -c "pass" {CANARY}'
ENV = (("W1_ENTRY_FAKE", "1"),)
DIR = r"C:\fictional\w1\work"
EXTENDED, ACCOUNTING, MEMBERS = xj.EXTENDED, xj.ACCOUNTING, xj.MEMBERS
FIELDS = (
    "claimed",
    "adoption",
    "request",
    "owner",
    "reference",
    "adopt_result",
    "ack",
    "output_bytes",
    "first_error",
    "first_control",
    "stage",
)
STAGES = (
    "NEW",
    "CLAIMED",
    "OWNER",
    "SETUP",
    "INPUT",
    "ADOPT",
    "ACK",
    "START",
    "SUPERVISE",
    "DRAIN",
    "CLOSE",
    "DONE",
)
LOAD_FIELDS = frozenset({"definitions", "backend", "Request", "ExternalJobOwner", "Win32Error"})
ACKS = {
    "ADOPTED": b"W1XA1 ADOPTED\n",
    "REFUSED_INPUT": b"W1XA1 REFUSED INPUT\n",
    "REFUSED_HANDLE": b"W1XA1 REFUSED HANDLE\n",
    "REFUSED_CONFIG": b"W1XA1 REFUSED CONFIG\n",
    "REFUSED_NOT_EMPTY": b"W1XA1 REFUSED NOT_EMPTY\n",
    "REFUSED_QUERY": b"W1XA1 REFUSED QUERY\n",
    "REFUSED_CONTROL": b"W1XA1 REFUSED CONTROL\n",
    "REFUSED_INTERNAL": b"W1XA1 REFUSED INTERNAL\n",
}
SWAP_FROM = b"One borrowed external job C adopted"
SWAP_TO = b"Two borrowed external job C adopted"  # same length: size checks stay equal
EXACT = "exact"


def record(value: int) -> bytes:
    return f"W1XT1 {value:x}\n".encode()


# ---------------------------------------------------------------- fake kernel subclass


class EntryKernel(xj.AdoptKernel):
    """AdoptKernel plus natural exit, wait inconsistency, pipe reads and exit faults."""

    def __init__(self) -> None:
        super().__init__()
        self.exit_at: int | None = None  # entry wait (MAX_WAIT_MS) at which P exits
        self.exit_value = 0
        self.revive_at: int | None = None  # entry wait at which P looks alive again
        self.exited = False
        self.entry_waits = 0
        self.wait_args: list[int] = []
        self.read_sizes: list[int] = []
        self.read_broken = 0
        self.eof_while_alive = False
        self.exit_faults: dict[tuple[str, int], object] = {}
        wrappers: tuple[tuple[str, Callable[[Callable[..., Any]], Callable[..., Any]]], ...] = (
            ("WaitForSingleObject", self._waiting),
            ("QueryInformationJobObject", self._inventory),
            ("PeekNamedPipe", self._peeking),
            ("ReadFile", self._reading),
        )
        for name, wrap in wrappers:
            setattr(self, name, wrap(getattr(self, name)))

    def _scripted(self, name: str) -> None:
        count = self.counts.get(name, 0) + 1
        control = self.raise_on.get((name, count))
        if control is not None:
            self.counts[name] = count
            self._control(name, control)

    def _waiting(self, original: Callable[..., Any]) -> Callable[..., Any]:
        def call(process: int, milliseconds: int) -> Any:
            self.wait_args.append(milliseconds)
            if milliseconds == MAX_WAIT_MS:
                self.entry_waits += 1
                if self.entry_waits == self.exit_at:
                    self.alive, self.exit, self.exited = False, self.exit_value, True
                if self.entry_waits == self.revive_at:
                    self.alive = True  # scripted inconsistency after a positive exit
            return original(process, milliseconds)

        return call

    def _inventory(self, original: Callable[..., Any]) -> Callable[..., Any]:
        def call(*args: Any) -> Any:
            fault = self.exit_faults.get((self._job_name(args[0]), args[1]))
            if not self.exited:
                fault = None
            if isinstance(fault, BaseException):
                self._control("QueryInformationJobObject", fault)
            result = original(*args)
            target = args[2]._obj
            if fault == "two_done":
                target.TotalProcesses, target.ActiveProcesses = 2, 0
            elif fault == "zero":
                target.TotalProcesses, target.ActiveProcesses = 0, 0
            elif fault == "active":
                target.TotalProcesses, target.ActiveProcesses = 1, 1
            elif fault == "three":
                target.TotalProcesses, target.ActiveProcesses = 3, 0
            elif fault == "members":
                target.NumberOfAssignedProcesses, target.NumberOfProcessIdsInList = 1, 1
                target.ProcessIdList[0] = 999
            return result

        return call

    def _peeking(self, original: Callable[..., Any]) -> Callable[..., Any]:
        def call(handle: int, *args: Any) -> Any:
            self._scripted("PeekNamedPipe")
            if self.eof_while_alive and self.alive and not self.pipe:
                self._gate("PeekNamedPipe", handle)
                self.last = 109  # P closed its stdout but is still running
                return 0
            return original(handle, *args)

        return call

    def _reading(self, _original: Callable[..., Any]) -> Callable[..., Any]:
        def call(*args: Any) -> Any:
            handle, buffer, size, got = args[0], args[1], args[2], args[3]
            self._scripted("ReadFile")
            self._gate("ReadFile", handle)
            self.read_sizes.append(size)
            if self.read_broken > 0:
                self.read_broken -= 1
                self.last = 109
                return 0
            chunk = bytes(self.pipe[:size])
            del self.pipe[: len(chunk)]
            buffer[: len(chunk)] = chunk
            got._obj.value = len(chunk)
            return 1 if chunk else 0

        return call


# ---------------------------------------------------------------- binary port fakes


class Reader:
    """Binary stdin fake: one scripted item per read(n); b"" (true EOF) once exhausted."""

    def __init__(self, kernel: EntryKernel, items: list[object]) -> None:
        self.kernel = kernel
        self.items = list(items)
        self.sizes: list[int] = []
        self.lookups = 0
        self.on_eof: Callable[[], None] | None = None

    def __getattribute__(self, name: str) -> Any:
        if name == "read":
            object.__setattr__(self, "lookups", object.__getattribute__(self, "lookups") + 1)
        return object.__getattribute__(self, name)

    def read(self, size: int) -> Any:
        self.sizes.append(size)
        item: object = self.items.pop(0) if self.items else b""
        if isinstance(item, BaseException) and not isinstance(item, Exception):
            self.kernel._control("port.read", item)
        self.kernel.calls.append("port.read")
        if isinstance(item, Exception):
            raise item
        if type(item) is bytes and item == b"" and self.on_eof is not None:
            self.on_eof()
        return item


class Writer:
    """Binary stdout fake: scripted write results, one optional flush fault."""

    def __init__(self, kernel: EntryKernel) -> None:
        self.kernel = kernel
        self.returns: list[object] = []
        self.flush_item: BaseException | None = None
        self.data: list[object] = []
        self.flushes = 0
        self.lookups: dict[str, int] = {}
        self.on_write: Callable[[], None] | None = None

    def __getattribute__(self, name: str) -> Any:
        if name in ("write", "flush"):
            counts = object.__getattribute__(self, "lookups")
            counts[name] = counts.get(name, 0) + 1
        return object.__getattribute__(self, name)

    def write(self, data: Any) -> Any:
        self.data.append(data)
        if self.on_write is not None:
            self.on_write()
        item: object = self.returns.pop(0) if self.returns else EXACT
        if isinstance(item, BaseException) and not isinstance(item, Exception):
            self.kernel._control("port.write", item)
        self.kernel.calls.append("port.write")
        if isinstance(item, Exception):
            raise item
        if type(item) is not str:  # returned as-is, never compared (opaque stays unprobed)
            return item
        if item == EXACT:
            return len(data)
        if item == "short":
            return len(data) - 1
        if item == "long":
            return len(data) + 1
        assert item == "bigint"
        return type("BigInt", (int,), {})(len(data))

    def flush(self) -> None:
        item = self.flush_item
        if item is not None and not isinstance(item, Exception):
            self.kernel._control("port.flush", item)
        self.kernel.calls.append("port.flush")
        if item is not None:
            raise item
        self.flushes += 1


# ---------------------------------------------------------------- source loading and lab


def require_source() -> None:
    """Explicit FAIL (never skip/pass/collection error) while the source is absent."""
    if not SOURCE.exists():
        pytest.fail("docs/poc/oracle9_w1_external_job_entry.py is absent (RED)")


def entry_module() -> Any:
    require_source()
    return SimpleNamespace(**runpy.run_path(str(SOURCE), run_name="_w1_external_job_entry_test"))


def make_lab(monkeypatch: pytest.MonkeyPatch) -> Any:
    module = entry_module()
    adoption = module.load_adoption()
    backend = adoption.backend
    kernel = EntryKernel()

    def load() -> Any:
        return backend["_Api"](kernel, lambda: kernel.last)

    # Seams of the private executed backend copy ONLY; no live product is patched.
    monkeypatch.setitem(backend, "_load_api", load)
    monkeypatch.setitem(backend, "sys", ref.runtime())
    xj.native_traps(monkeypatch)
    external = kernel.add_external()
    kernel.exit_at = 1
    lab = SimpleNamespace(module=module, adoption=adoption, backend=backend, kernel=kernel)
    lab.external, lab.outer = external, external + 4  # fake handle order, sanity-checked
    lab.request = adoption.Request(APP, COMMAND, ENV, DIR)
    lab.custody = module.EntryCustody()
    lab.reader = Reader(kernel, [record(external)])
    lab.writer = Writer(kernel)
    return lab


def run(lab: Any, budget: object = MAX_TURNS) -> Any:
    return lab.module.run_entry(
        lab.adoption, lab.request, lab.reader, lab.writer, budget, lab.custody
    )


def assert_defaults(module: Any, custody: Any) -> None:
    assert custody.claimed is False and custody.ack == "NOT_ATTEMPTED"
    assert type(custody.output_bytes) is int and custody.output_bytes == 0
    assert custody.stage is module.EntryStage.NEW
    for name in ("adoption", "request", "owner", "reference", "adopt_result"):
        assert getattr(custody, name) is None
    assert custody.first_error is None and custody.first_control is None


def released(lab: Any, result: object, category: str) -> Any:
    custody = lab.custody
    assert type(result) is str and result == category
    assert custody.claimed is True
    assert custody.adoption is lab.adoption and custody.request is lab.request
    owner = custody.owner
    assert type(owner) is lab.adoption.ExternalJobOwner and owner.state == "CLOSED"
    assert custody.stage is lab.module.EntryStage.DONE and custody.first_control is None
    assert "TerminateJobObject" not in lab.kernel.calls
    xj.assert_c_safe(lab.kernel, lab.external)
    return owner


def retained(lab: Any, result: object) -> Any:
    custody = lab.custody
    assert type(result) is str and result == "RETAIN"
    assert custody.claimed is True
    assert custody.adoption is lab.adoption and custody.request is lab.request
    owner = custody.owner
    assert type(owner) is lab.adoption.ExternalJobOwner and owner.state != "CLOSED"
    assert custody.stage is not lab.module.EntryStage.DONE
    assert [h for h in owner.ledger.values() if h in lab.kernel.closed] == []
    # Strong custody stays with the caller: no hidden module-level registry of Owners.
    assert all(value is not owner for value in lab.module.run_entry.__globals__.values())
    xj.assert_c_safe(lab.kernel, lab.external)
    return owner


def rejected(lab: Any, result: object) -> None:
    assert type(result) is str and result == "REJECTED"
    assert lab.kernel.calls == [] and lab.reader.sizes == [] and lab.writer.data == []
    assert lab.reader.lookups == 0 and lab.writer.lookups == {}


def win32(lab: Any, error: object, code: str) -> None:
    assert isinstance(error, BaseException) and type(error) is lab.adoption.Win32Error
    assert error.args == (code,)


# ---------------------------------------------------------------- fake helper sanities


def test_sanity_pinned_sources_limits_and_protocol_constants() -> None:
    raw = XJ_FILE.read_bytes()
    assert len(raw) == XJ_SIZE <= LOAD_LIMIT and hashlib.sha256(raw).hexdigest() == XJ_SHA
    assert raw.count(SWAP_FROM) == 1 and len(SWAP_FROM) == len(SWAP_TO)
    backend = xj.BACKEND_FILE.read_bytes()
    assert hashlib.sha256(backend).hexdigest() == xj.BACKEND_SHA
    assert backend.count(b"\nMAX_WAIT_MS = 50\n") == 1
    assert backend.count(b"\nMAX_READ = 4096\n") == 1
    assert max(len(ack) for ack in ACKS.values()) == len(ACKS["REFUSED_NOT_EMPTY"]) == 24
    assert len(b"W1XT1 " + b"f" * 16 + b"\n") == 23 and record(0xAB) == b"W1XT1 ab\n"


def test_sanity_fake_exit_revive_and_handle_order() -> None:
    kernel = EntryKernel()
    external = kernel.add_external()
    assert kernel.CreateJobObjectW(None, None) == external + 4  # outer job follows C
    kernel.alive, kernel.exit_at, kernel.exit_value, kernel.revive_at = True, 2, 7, 3
    assert kernel.WaitForSingleObject(1, MAX_WAIT_MS) == 0x102
    assert kernel.WaitForSingleObject(1, 0) == 0x102 and kernel.entry_waits == 1
    assert kernel.WaitForSingleObject(1, MAX_WAIT_MS) == 0 and kernel.exited
    assert kernel.exit == 7
    assert kernel.WaitForSingleObject(1, MAX_WAIT_MS) == 0x102  # scripted inconsistency
    assert kernel.wait_args == [MAX_WAIT_MS, 0, MAX_WAIT_MS, MAX_WAIT_MS]


def test_sanity_fake_pipe_reads_are_bounded_and_eof_is_explicit() -> None:
    kernel = EntryKernel()
    read_end = kernel._new("stdout_read", 0)
    write_end = kernel._new("stdout_write", 1)
    kernel.pipe.extend(b"p" * (MAX_READ + 3))
    kernel.alive = True
    available = wintypes.DWORD(0)
    peek = (None, 0, None, ctypes.byref(available), None)
    assert kernel.PeekNamedPipe(read_end, *peek) == 1 and available.value == MAX_READ + 3
    buffer, got = ctypes.create_string_buffer(MAX_READ), wintypes.DWORD(0)
    assert kernel.ReadFile(read_end, buffer, MAX_READ, ctypes.byref(got), None) == 1
    assert got.value == MAX_READ and buffer.raw == b"p" * MAX_READ
    assert kernel.ReadFile(read_end, buffer, MAX_READ, ctypes.byref(got), None) == 1
    assert got.value == 3 and kernel.read_sizes == [MAX_READ, MAX_READ]
    kernel.read_broken = 1
    kernel.pipe.extend(b"q")
    assert kernel.ReadFile(read_end, buffer, 1, ctypes.byref(got), None) == 0
    assert kernel.last == 109 and kernel.pipe == bytearray(b"q")
    kernel.pipe.clear()
    kernel.eof_while_alive = True
    assert kernel.PeekNamedPipe(read_end, *peek) == 0 and kernel.last == 109
    kernel.eof_while_alive, kernel.alive, kernel.last = False, False, 0
    assert kernel.PeekNamedPipe(read_end, *peek) == 1  # writer end not yet closed
    kernel.closed.append(write_end)
    assert kernel.PeekNamedPipe(read_end, *peek) == 0 and kernel.last == 109


class _Counts(ctypes.Structure):
    _fields_ = [("TotalProcesses", wintypes.DWORD), ("ActiveProcesses", wintypes.DWORD)]


def test_sanity_fake_exit_faults_apply_only_after_exit() -> None:
    kernel = EntryKernel()
    job = kernel.CreateJobObjectW(None, None)
    kernel.exit_faults[("job", ACCOUNTING)] = "two_done"
    info, length = _Counts(), wintypes.DWORD(0)
    args = (job, ACCOUNTING, ctypes.byref(info), ctypes.sizeof(info), ctypes.byref(length))
    assert kernel.QueryInformationJobObject(*args) == 1
    assert (info.TotalProcesses, info.ActiveProcesses) == (0, 0)
    kernel.exited = True
    assert kernel.QueryInformationJobObject(*args) == 1
    assert (info.TotalProcesses, info.ActiveProcesses) == (2, 0)
    control = xj.KernelCtl()
    kernel.exit_faults[("job", ACCOUNTING)] = control
    assert qbase.control_of(lambda: kernel.QueryInformationJobObject(*args)) is control
    assert kernel.snapshot is not None and kernel.snapshot[0][-1] == "QueryInformationJobObject"


def test_sanity_ports_script_results_and_join_the_trace() -> None:
    kernel = EntryKernel()
    error = ValueError(CANARY)
    reader = Reader(kernel, [b"ab", error])
    eof: list[str] = []
    reader.on_eof = lambda: eof.append("eof")
    assert reader.read(24) == b"ab"
    assert qbase.refused(lambda: reader.read(22)) and reader.read(22) == b"" and eof == ["eof"]
    assert reader.sizes == [24, 22, 22] and reader.lookups == 3
    writer = Writer(kernel)
    writer.returns = ["short", None]
    assert writer.write(b"abc") == 2 and writer.write(b"abc") is None
    assert writer.write(b"abc") == 3
    writer.flush()
    control = xj.KernelCtl()
    writer.flush_item = control
    assert qbase.control_of(writer.flush) is control and writer.flushes == 1
    assert kernel.calls == ["port.read"] * 3 + ["port.write"] * 3 + ["port.flush"] * 2
    assert kernel.snapshot is not None and kernel.snapshot[0] == kernel.calls
    assert writer.lookups == {"write": 3, "flush": 2}


# ---------------------------------------------------------------- pure import and static shape


SAFE_CALLS = frozenset(
    {
        "dataclass",
        "dataclasses.dataclass",
        "field",
        "dataclasses.field",
        "auto",
        "enum.auto",
        "Enum",
        "enum.Enum",
        "frozenset",
    }
)
SAFE_DECORATORS = frozenset(
    {
        "dataclass",
        "dataclasses.dataclass",
        "property",
        "staticmethod",
        "classmethod",
        "unique",
        "enum.unique",
    }
)
GENUINE_FROM = frozenset(
    {
        ("dataclasses", "dataclass"),
        ("dataclasses", "field"),
        ("enum", "auto"),
        ("enum", "Enum"),
        ("enum", "unique"),
    }
)
GUARDED_NAMES = frozenset(
    {
        "dataclass",
        "dataclasses",
        "field",
        "auto",
        "enum",
        "Enum",
        "unique",
        "frozenset",
        "property",
        "staticmethod",
        "classmethod",
    }
)
INERT_NODES = (
    ast.Attribute,
    ast.Tuple,
    ast.List,
    ast.Set,
    ast.Dict,
    ast.BinOp,
    ast.UnaryOp,
    ast.Subscript,
)


def _qualified(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id + "." + node.attr
    return ""


def _inert(node: ast.expr | None) -> bool:
    """Evaluated at import time without calling anything except SAFE_CALLS."""
    if node is None or isinstance(node, ast.Constant | ast.Name):
        return True
    if isinstance(node, ast.Call):
        values = [*node.args, *(keyword.value for keyword in node.keywords)]
        return (
            _qualified(node.func) in SAFE_CALLS
            and all(keyword.arg is not None for keyword in node.keywords)
            and all(_inert(value) for value in values)
        )
    if isinstance(node, ast.Attribute) and not isinstance(node.value, ast.Name | ast.Attribute):
        return False  # attribute of a call result
    if isinstance(node, ast.Dict) and None in node.keys:
        return False  # ** unpacking
    children = [child for child in ast.iter_child_nodes(node) if isinstance(child, ast.expr)]
    return isinstance(node, INERT_NODES) and all(_inert(child) for child in children)


def _decorator_ok(node: ast.expr) -> bool:
    if isinstance(node, ast.Call):
        return _qualified(node.func) in {"dataclass", "dataclasses.dataclass"} and _inert(node)
    return _qualified(node) in SAFE_DECORATORS


def _docstring_ok(statement: ast.stmt, index: int, _in_class: bool) -> bool:
    value = statement.value if isinstance(statement, ast.Expr) else None
    return index == 0 and isinstance(value, ast.Constant) and isinstance(value.value, str)


def _import_ok(statement: ast.stmt, _index: int, _in_class: bool) -> bool:
    """Imports never shadow the few callables that SAFE_CALLS/SAFE_DECORATORS trust."""
    assert isinstance(statement, ast.Import | ast.ImportFrom)
    for alias in statement.names:
        if isinstance(statement, ast.Import):
            bound = alias.asname or alias.name.split(".")[0]
            genuine = alias.name in ("dataclasses", "enum")
        else:
            bound = alias.asname or alias.name
            genuine = (statement.module, alias.name) in GENUINE_FROM
        genuine = genuine and alias.asname in (None, alias.name)
        if alias.name == "*" or (bound in GUARDED_NAMES and not genuine):
            return False
    return True


def _function_ok(statement: ast.stmt, _index: int, _in_class: bool) -> bool:
    assert isinstance(statement, ast.FunctionDef)
    args = statement.args
    every = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    every += [arg for arg in (args.vararg, args.kwarg) if arg is not None]
    evaluated = [*args.defaults, *args.kw_defaults, statement.returns]
    evaluated += [arg.annotation for arg in every]
    return (
        statement.name not in GUARDED_NAMES
        and all(_decorator_ok(decorator) for decorator in statement.decorator_list)
        and all(_inert(value) for value in evaluated)
    )


def _class_ok(statement: ast.stmt, _index: int, _in_class: bool) -> bool:
    assert isinstance(statement, ast.ClassDef)
    return (
        statement.name not in GUARDED_NAMES
        and not statement.keywords
        and all(isinstance(base, ast.Name | ast.Attribute) for base in statement.bases)
        and all(_inert(base) for base in statement.bases)
        and all(_decorator_ok(decorator) for decorator in statement.decorator_list)
    )


def _assign_ok(statement: ast.stmt, _index: int, _in_class: bool) -> bool:
    targets: list[ast.expr]
    values: list[ast.expr | None]
    if isinstance(statement, ast.AnnAssign):
        targets, values = [statement.target], [statement.annotation, statement.value]
    else:
        assert isinstance(statement, ast.Assign)
        targets, values = list(statement.targets), [statement.value]
    names: list[ast.expr] = []
    for target in targets:
        names.extend(target.elts if isinstance(target, ast.Tuple) else [target])
    named = all(isinstance(name, ast.Name) and name.id not in GUARDED_NAMES for name in names)
    return named and all(_inert(value) for value in values)


def _pass_ok(_statement: ast.stmt, _index: int, in_class: bool) -> bool:
    return in_class


STATEMENT_CHECKS: dict[type[ast.stmt], Callable[[ast.stmt, int, bool], bool]] = {
    ast.Expr: _docstring_ok,
    ast.Import: _import_ok,
    ast.ImportFrom: _import_ok,
    ast.FunctionDef: _function_ok,
    ast.ClassDef: _class_ok,
    ast.Assign: _assign_ok,
    ast.AnnAssign: _assign_ok,
    ast.Pass: _pass_ok,
}


def _body_violations(body: list[ast.stmt], in_class: bool) -> list[str]:
    found: list[str] = []
    for index, statement in enumerate(body):
        check = STATEMENT_CHECKS.get(type(statement))
        if check is None or not check(statement, index, in_class):
            found.append(f"{statement.lineno}:{type(statement).__name__}")
        if isinstance(statement, ast.ClassDef):
            found.extend(_body_violations(statement.body, True))  # class bodies run too
    return found


def import_violations(tree: ast.Module) -> list[str]:
    """Static classifier: module-body OPERATIONS beyond inert definitions (not words)."""
    return _body_violations(tree.body, False)


IMPORT_PROBE = "_w1_xe_import_probe"
OS_EFFECTS = (
    "open",
    "system",
    "startfile",
    "popen",
    "remove",
    "unlink",
    "rename",
    "replace",
    "mkdir",
    "makedirs",
    "rmdir",
    "stat",
    "lstat",
    "scandir",
    "listdir",
    "kill",
    "spawnv",
    "execv",
)
PATH_EFFECTS = (
    "open",
    "read_bytes",
    "read_text",
    "write_bytes",
    "write_text",
    "stat",
    "lstat",
    "resolve",
    "exists",
    "is_file",
    "mkdir",
    "touch",
    "unlink",
    "iterdir",
)


class _Trap:
    """Native loader stand-in: any attribute or call is a recorded import-time effect."""

    def __init__(self, name: str, effects: list[str]) -> None:
        self.name, self.effects = name, effects

    def __getattr__(self, _attribute: str) -> Any:
        self.effects.append(self.name)
        raise AssertionError("import-time effect: " + self.name)

    def __call__(self, *_args: Any, **_kwargs: Any) -> Any:
        self.effects.append(self.name)
        raise AssertionError("import-time effect: " + self.name)


def _install_import_traps(patch: pytest.MonkeyPatch, effects: list[str], filename: str) -> None:
    """Real stdlib ports, reachable also through an imported ``builtins``/``io``/``os``."""

    def always(name: str) -> Callable[..., Any]:
        def trap(*_args: Any, **_kwargs: Any) -> Any:
            effects.append(name)
            raise AssertionError("import-time effect: " + name)

        return trap

    def from_body(name: str, real: Callable[..., Any]) -> Callable[..., Any]:
        def trap(*args: Any, **kwargs: Any) -> Any:
            if sys._getframe(1).f_code.co_filename == filename:
                effects.append(name)
                raise AssertionError("import-time effect: " + name)
            return real(*args, **kwargs)  # e.g. dataclasses' own generated methods

        return trap

    patch.setattr(builtins, "open", always("builtins.open"))
    for name in ("exec", "eval", "compile"):
        patch.setattr(builtins, name, from_body("builtins." + name, getattr(builtins, name)))
    patch.setattr(io, "open", always("io.open"))
    patch.setattr(sys.modules["_io"], "open", always("_io.open"))
    for name in OS_EFFECTS:
        if hasattr(os, name):
            patch.setattr(os, name, always("os." + name))
    for name in PATH_EFFECTS:
        patch.setattr(Path, name, always("Path." + name))
    for name in ("windll", "cdll", "oledll", "WinDLL", "CDLL"):
        if hasattr(ctypes, name):
            patch.setattr(ctypes, name, _Trap("ctypes." + name, effects))
    patch.setattr(subprocess, "Popen", always("subprocess.Popen"))
    patch.setattr(threading.Thread, "start", always("Thread.start"))
    patch.setattr(socket, "socket", always("socket.socket"))
    patch.setattr(time, "sleep", always("time.sleep"))


def import_effects(
    source: bytes, filename: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[BaseException | None, list[str], dict[str, Any]]:
    """Dynamic classifier: runs a module BODY once; every trap is restored before return."""
    code = compile(source, filename, "exec", dont_inherit=True)  # prepared BEFORE the traps
    run_body = builtins.exec  # the real callable, captured before the traps
    module = ModuleType(IMPORT_PROBE)
    module.__file__ = filename
    namespace = vars(module)
    effects: list[str] = []
    before = set(sys.modules)
    with monkeypatch.context() as patch:
        # Harness-only registration (dataclasses resolves string annotations through it);
        # restored with the traps and never attributed to the classified body.
        patch.setitem(sys.modules, IMPORT_PROBE, module)
        _install_import_traps(patch, effects, filename)
        error = xj.error_of(lambda: run_body(code, namespace))
    added = {name for name in set(sys.modules) - before if "w1" in name or "external" in name}
    assert added == set() and IMPORT_PROBE not in sys.modules
    return error, effects, namespace


INERT_FIXTURE = '''"""Inert import fixture: definitions only; nothing here is an entry."""

from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass, field

LIMIT = 1 << 16
NAMES = frozenset({"a", "b"})
TABLE: dict[str, int] = {"a": 1}


class FixtureError(Exception):
    """Closed refusal."""


class FixtureStage(enum.Enum):
    NEW = enum.auto()
    DONE = enum.auto()


@dataclass(frozen=True, slots=True)
class FixtureCarrier:
    value: int = 0
    items: list[int] = field(default_factory=list)


@dataclasses.dataclass(slots=True)
class FixtureCustody:
    claimed: bool = False

    @property
    def flag(self) -> bool:
        return self.claimed


def fixture_api(value: int = LIMIT, *, name: str = "x") -> str:
    return open(name).read()  # a function BODY is not import time; never called
'''
FIXTURE_FILE = "<inert-import-fixture>"  # no file exists: no marker can be written
IMPURE_FIXTURES: dict[str, tuple[str, str]] = {
    "imported-builtin": ('DATA = __import__("builtins").open(__file__, "rb")\n', "builtins.open"),
    "io-open": ('import io\nDATA = io.open(__file__, "rb")\n', "io.open"),
    "os-stat": ("import os\nINFO = os.stat(__file__)\n", "os.stat"),
    "path-read": (
        "from pathlib import Path\nDATA = Path(__file__).read_bytes()\n",
        "Path.read_bytes",
    ),
    "exec": ('exec("VALUE = 1")\n', "builtins.exec"),
    "default-argument": (
        "import os\n\n\ndef api(value=os.stat(__file__)):\n    return value\n",
        "os.stat",
    ),
    "class-body": ('class Api:\n    DATA = __import__("io").open(__file__, "rb")\n', "io.open"),
    "decorator": ("import os\n\n\n@os.stat\ndef api():\n    pass\n", "os.stat"),
    "shadowed-name": ("from os import stat as field\n\nINFO = field(__file__)\n", "os.stat"),
    "control-flow": ("import os\n\nif True:\n    os.stat(__file__)\n", "os.stat"),
}


def test_sanity_import_classifiers_accept_inert_definitions(monkeypatch: Any) -> None:
    """Fake-only counter-proof of the import oracles; not an entry, never product proof."""
    assert import_violations(ast.parse(INERT_FIXTURE)) == []
    error, effects, namespace = import_effects(INERT_FIXTURE.encode(), FIXTURE_FILE, monkeypatch)
    assert error is None and effects == []
    assert dataclasses.is_dataclass(namespace["FixtureCarrier"])
    assert issubclass(namespace["FixtureStage"], enum.Enum)
    assert namespace["fixture_api"].__defaults__ == (1 << 16,)
    assert namespace["FixtureCustody"]().flag is False


@pytest.mark.parametrize("case", sorted(IMPURE_FIXTURES))
def test_sanity_import_classifiers_reject_body_effects(monkeypatch: Any, case: str) -> None:
    """Fake-only counter-proof: the SAME family of effects through imported builtins."""
    source, effect = IMPURE_FIXTURES[case]
    assert import_violations(ast.parse(source)) != []
    originals = (builtins.open, builtins.exec, io.open, os.stat, Path.read_bytes)
    error, effects, _namespace = import_effects(source.encode(), FIXTURE_FILE, monkeypatch)
    assert originals == (builtins.open, builtins.exec, io.open, os.stat, Path.read_bytes)
    assert type(error) is AssertionError and effects[:1] == [effect]


def test_import_is_pure_defines_the_api_and_registers_nothing(monkeypatch: Any) -> None:
    require_source()
    xj.native_traps(monkeypatch)
    error, effects, namespace = import_effects(SOURCE.read_bytes(), str(SOURCE), monkeypatch)
    assert error is None and effects == []
    for name in ("load_adoption", "run_entry", "AdoptionLoad", "EntryCustody", "EntryStage"):
        assert name in namespace
    module = entry_module()
    assert callable(module.load_adoption) and callable(module.run_entry)
    assert issubclass(module.EntryLoadError, Exception)
    assert issubclass(module.EntryStage, enum.Enum)
    assert isinstance(module.AdoptionLoad, type) and isinstance(module.EntryCustody, type)


PRIVATE_ATTRIBUTES = frozenset(
    {
        "ledger",
        "quarantine",
        "held_reason",
        "pid",
        "_api",
        "_call",
        "_ok",
        "_hold",
        "_fail",
        "_guarded",
        "_interrupt",
        "_accounting",
        "_members",
        "_wait",
        "_peek",
        "_close",
        "_pending",
        "_keep",
        "terminate",
        "environ",
        "getenv",
        "stdin",
        "stdout",
        "stderr",
        "sleep",
        "exit",
    }
)
NATIVE_OPERATIONS = frozenset({"CloseHandle", "TerminateJobObject", "TerminateProcess"})


def test_static_shape_defines_only_and_never_touches_private_or_process_io() -> None:
    require_source()
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned = {
        "subprocess",
        "threading",
        "socket",
        "asyncio",
        "multiprocessing",
        "runpy",
        "importlib",
        "time",
        "signal",
        "selectors",
        "ctypes",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not {alias.name.split(".")[0] for alias in node.names} & banned
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in banned | {"docs", "tests"}
        if isinstance(node, ast.Attribute):
            assert node.attr not in PRIVATE_ATTRIBUTES | NATIVE_OPERATIONS
            assert not node.attr.startswith("_xj_")
        if isinstance(node, ast.Name):
            assert node.id not in {"print", "input", "breakpoint", "__import__"}
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            names = {target.id for target in node.targets if isinstance(target, ast.Name)}
            assert not names & {"MAX_WAIT_MS", "MAX_READ"}  # reused from the backend
    assert import_violations(tree) == []
    # Operations, not loose words: docstrings and comments may name what is forbidden.
    docstrings: set[int] = set()
    for holder in ast.walk(tree):
        if isinstance(holder, ast.Module | ast.ClassDef | ast.FunctionDef) and holder.body:
            first = holder.body[0]
            if isinstance(first, ast.Expr):
                docstrings.add(id(first.value))
    constants = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]
    assert XJ_SHA in constants and any(XJ_FILE.name in value for value in constants)
    assert not [value for value in constants if value in NATIVE_OPERATIONS]
    assert not [value for value in constants if "pg16_shell_native_control_win32" in value]


# ---------------------------------------------------------------- loader: pin and carrier


def _tree(root: Path, adoption: bytes | None, *, directory: bool = False) -> Path:
    poc = root / "docs" / "poc"
    poc.mkdir(parents=True)
    copy = poc / SOURCE.name
    copy.write_bytes(SOURCE.read_bytes())
    (poc / xj.BACKEND_FILE.name).write_bytes(xj.BACKEND_FILE.read_bytes())
    if directory:
        (poc / XJ_FILE.name).mkdir()
    elif adoption is not None:
        (poc / XJ_FILE.name).write_bytes(adoption)
    return copy


def _marker_payload(marker: Path) -> bytes:
    return f"\nimport pathlib as _tamper\n_tamper.Path({str(marker)!r}).write_text('x')\n".encode()


def load_error(namespace: dict[str, Any], error: BaseException | None) -> None:
    assert error is not None and type(error) is namespace["EntryLoadError"]
    assert error.args == ("ENTRY_LOAD",)
    assert error.__cause__ is None and error.__context__ is None


def test_load_executes_the_pinned_sibling_of_its_own_tree(tmp_path: Path) -> None:
    require_source()
    copy = _tree(tmp_path, XJ_FILE.read_bytes())
    namespace = runpy.run_path(str(copy), run_name="_w1_xe_tree")
    adoption = namespace["load_adoption"]()
    assert type(adoption) is namespace["AdoptionLoad"]
    backend_file = Path(adoption.backend["__file__"]).resolve()
    assert backend_file == (copy.parent / xj.BACKEND_FILE.name).resolve()


@pytest.mark.parametrize("kind", ["missing", "tampered", "oversize", "directory"])
def test_bad_sibling_is_refused_before_execution(tmp_path: Path, kind: str) -> None:
    require_source()
    marker = tmp_path / "executed"
    raw = XJ_FILE.read_bytes()
    adoption: bytes | None = None
    if kind == "tampered":
        adoption = raw + _marker_payload(marker)
    elif kind == "oversize":
        adoption = raw + ("#" + "x" * LOAD_LIMIT + "\n").encode() + _marker_payload(marker)
    if adoption is not None:
        ast.parse(adoption.decode("utf-8"))  # valid Python: a refusal is never a SyntaxError
    copy = _tree(tmp_path / kind, adoption, directory=kind == "directory")
    namespace = runpy.run_path(str(copy), run_name="_w1_xe_" + kind)
    load_error(namespace, xj.error_of(namespace["load_adoption"]))
    assert not marker.exists()


def _same_path(path: object, key: str) -> bool:
    if not isinstance(path, str | os.PathLike):
        return False
    return os.path.normcase(os.path.abspath(os.fspath(path))) == key


def _forge_metadata(monkeypatch: Any, target: Path, kind: str) -> None:
    """Scoped stdlib port: forged lstat/stat metadata for the sibling path only."""
    key = os.path.normcase(str(target.resolve()))
    real_stat, real_lstat = os.stat, os.lstat

    def forge(result: os.stat_result) -> os.stat_result:
        values = list(result)
        attributes = result.st_file_attributes
        if kind == "size":
            values[6] += 1
        else:
            attributes |= 0x400  # FILE_ATTRIBUTE_REPARSE_POINT
        extra = {"st_file_attributes": attributes, "st_reparse_tag": result.st_reparse_tag}
        return os.stat_result(values, extra)

    def fake_stat(path: Any, *args: Any, **kwargs: Any) -> Any:
        result = real_stat(path, *args, **kwargs)
        return forge(result) if _same_path(path, key) else result

    def fake_lstat(path: Any, *args: Any, **kwargs: Any) -> Any:
        result = real_lstat(path, *args, **kwargs)
        return forge(result) if _same_path(path, key) else result

    monkeypatch.setattr(os, "stat", fake_stat)
    monkeypatch.setattr(os, "lstat", fake_lstat)


@pytest.mark.parametrize("kind", ["reparse", "size"])
def test_forged_sibling_metadata_is_refused(tmp_path: Path, monkeypatch: Any, kind: str) -> None:
    require_source()
    copy = _tree(tmp_path, XJ_FILE.read_bytes())
    namespace = runpy.run_path(str(copy), run_name="_w1_xe_meta")
    target = copy.parent / XJ_FILE.name
    assert stat.S_ISREG(target.lstat().st_mode)  # the real file is regular and pinned
    with monkeypatch.context() as patch:
        _forge_metadata(patch, target, kind)
        outcome = xj.error_of(namespace["load_adoption"])
    load_error(namespace, outcome)


def test_load_executes_the_same_captured_bytes(tmp_path: Path, monkeypatch: Any) -> None:
    require_source()
    raw = XJ_FILE.read_bytes()
    copy = _tree(tmp_path, raw)
    namespace = runpy.run_path(str(copy), run_name="_w1_xe_same")
    target = copy.parent / XJ_FILE.name
    key = os.path.normcase(str(target.resolve()))
    real_open = io.open
    opened: list[str] = []

    def fake_open(file: Any, mode: Any = "r", *args: Any, **kwargs: Any) -> Any:
        if _same_path(file, key):
            opened.append(str(mode))
            if len(opened) == 1:
                with real_open(file, "rb") as stream:
                    data = stream.read()
                with real_open(file, "wb") as stream:  # swapped AFTER the capture
                    stream.write(raw.replace(SWAP_FROM, SWAP_TO))
                return io.BytesIO(data)
        return real_open(file, mode, *args, **kwargs)

    with monkeypatch.context() as patch:  # scoped stdlib port
        patch.setattr(io, "open", fake_open)
        patch.setattr(builtins, "open", fake_open)
        adoption = namespace["load_adoption"]()
    assert opened == ["rb"]  # one capture, never a second read for execution
    assert adoption.ExternalJobOwner.__doc__.startswith("One borrowed")
    load_error(namespace, xj.error_of(namespace["load_adoption"]))  # the swap was real


def test_control_during_load_propagates_before_acquisition(
    tmp_path: Path, monkeypatch: Any
) -> None:
    require_source()
    copy = _tree(tmp_path, XJ_FILE.read_bytes())
    namespace = runpy.run_path(str(copy), run_name="_w1_xe_ctl")
    key = os.path.normcase(str((copy.parent / XJ_FILE.name).resolve()))
    control = xj.KernelCtl()
    ports = {"stat": os.stat, "lstat": os.lstat}
    real_open = io.open

    def scripted(original: Callable[..., Any]) -> Callable[..., Any]:
        def call(path: Any, *args: Any, **kwargs: Any) -> Any:
            if _same_path(path, key):
                raise control
            return original(path, *args, **kwargs)

        return call

    with monkeypatch.context() as patch:
        for name, original in ports.items():
            patch.setattr(os, name, scripted(original))
        patch.setattr(io, "open", scripted(real_open))
        patch.setattr(builtins, "open", scripted(real_open))
        outcome = xj.error_of(namespace["load_adoption"])
    assert outcome is control  # never swallowed or converted
    assert type(namespace["load_adoption"]()) is namespace["AdoptionLoad"]


def test_load_returns_the_exact_trusted_carrier() -> None:
    module = entry_module()
    adoption = module.load_adoption()
    carrier = module.AdoptionLoad
    assert type(adoption) is carrier and dataclasses.is_dataclass(carrier)
    assert {field.name for field in dataclasses.fields(carrier)} == LOAD_FIELDS
    definitions, backend = adoption.definitions, adoption.backend
    assert type(definitions) is dict and set(definitions) == xj.KEYS
    assert type(backend) is dict and definitions["backend"] is backend
    assert adoption.Request is definitions["Request"] is backend["Request"]
    assert adoption.Win32Error is definitions["Win32Error"] is backend["Win32Error"]
    owner_class = adoption.ExternalJobOwner
    assert owner_class is definitions["ExternalJobOwner"]
    assert owner_class.__bases__ == (backend["Owner"],)
    with pytest.raises(AttributeError):
        adoption.backend = {}  # frozen carrier
    assert adoption.backend is backend
    text = repr(adoption)
    assert str(REPO) not in text and len(text) < 200


def _forge(cls: type, values: dict[str, object]) -> Any:
    item: object = object.__new__(cls)
    for name, value in values.items():
        object.__setattr__(item, name, value)
    return item


FORGERIES = (
    "dict",
    "definitions-dict",
    "namespace",
    "subclass",
    "request",
    "win32",
    "owner-base",
    "owner-foreign",
    "backend",
    "definitions",
)


@pytest.mark.parametrize("kind", FORGERIES)
def test_malformed_carrier_shape_or_identity_is_rejected(monkeypatch: Any, kind: str) -> None:
    """Shape/identity of the carrier only; no claim against privileged forging code."""
    lab = make_lab(monkeypatch)
    adoption, other = lab.adoption, lab.module.load_adoption()
    values = {field.name: getattr(adoption, field.name) for field in dataclasses.fields(adoption)}
    carrier: object
    if kind == "dict":
        carrier = dict(values)
    elif kind == "definitions-dict":
        carrier = adoption.definitions
    elif kind == "namespace":
        carrier = SimpleNamespace(**values)
    elif kind == "subclass":
        carrier = _forge(type("ForgedLoad", (lab.module.AdoptionLoad,), {}), values)
    else:
        swaps = {
            "request": ("Request", other.Request),
            "win32": ("Win32Error", other.Win32Error),
            "owner-base": ("ExternalJobOwner", adoption.backend["Owner"]),
            "owner-foreign": ("ExternalJobOwner", other.ExternalJobOwner),
            "backend": ("backend", other.backend),
            "definitions": ("definitions", other.definitions),
        }
        name, value = swaps[kind]
        carrier = _forge(lab.module.AdoptionLoad, {**values, name: value})
    result = lab.module.run_entry(
        carrier, lab.request, lab.reader, lab.writer, MAX_TURNS, lab.custody
    )
    rejected(lab, result)
    assert_defaults(lab.module, lab.custody)


# ---------------------------------------------------------------- custody and preflight


def test_custody_and_stage_types_are_exact_and_redacted() -> None:
    module = entry_module()
    custody = module.EntryCustody()
    # Checked on the type expression so the dynamic instance is not narrowed.
    assert dataclasses.is_dataclass(type(custody)) and type(custody) is module.EntryCustody
    assert "__slots__" in vars(module.EntryCustody)
    assert {field.name for field in dataclasses.fields(custody)} == set(FIELDS)
    assert_defaults(module, custody)
    assert [member.name for member in module.EntryStage] == list(STAGES)
    custody.first_error = ValueError(CANARY)
    assert CANARY not in repr(custody)


@pytest.mark.parametrize("value", [True, False, 0, -1, 401, 1.0, None, "1", "bigint"])
def test_budget_outside_exact_builtin_1_to_400_is_rejected(monkeypatch: Any, value: object) -> None:
    lab = make_lab(monkeypatch)
    budget = type("BigInt", (int,), {})(5) if value == "bigint" else value
    rejected(lab, run(lab, budget))
    assert_defaults(lab.module, lab.custody)


@pytest.mark.parametrize("budget", [1, MAX_TURNS])
def test_budget_edges_are_accepted(monkeypatch: Any, budget: int) -> None:
    lab = make_lab(monkeypatch)
    lab.reader.items = [b"W1XT1 0\n"]
    released(lab, run(lab, budget), "REFUSED")


@pytest.mark.parametrize("kind", ["object", "none", "text", "dict", "other-load"])
def test_request_of_another_type_is_rejected(monkeypatch: Any, kind: str) -> None:
    lab = make_lab(monkeypatch)
    requests: dict[str, object] = {
        "object": object(),
        "none": None,
        "text": COMMAND,
        "dict": {"application": APP},
    }
    if kind == "other-load":
        requests[kind] = lab.module.load_adoption().Request(APP, COMMAND, ENV, DIR)
    lab.request = requests[kind]
    rejected(lab, run(lab))
    assert_defaults(lab.module, lab.custody)


@pytest.mark.parametrize("kind", ["claimed", "reference", "owner", "namespace", "subclass", "none"])
def test_foreign_or_non_empty_custody_is_rejected_untouched(monkeypatch: Any, kind: str) -> None:
    lab = make_lab(monkeypatch)
    module = lab.module
    sentinel = object()
    if kind == "claimed":
        lab.custody.claimed = True
    elif kind == "reference":
        lab.custody.reference = 5
    elif kind == "owner":
        lab.custody.owner = sentinel
    elif kind == "namespace":
        lab.custody = SimpleNamespace(**{name: getattr(lab.custody, name) for name in FIELDS})
    elif kind == "subclass":
        lab.custody = type("ForgedCustody", (module.EntryCustody,), {"__slots__": ()})()
    else:
        lab.custody = None
    before = None if lab.custody is None else [getattr(lab.custody, name) for name in FIELDS]
    rejected(lab, run(lab))
    if before is not None:
        after = [getattr(lab.custody, name) for name in FIELDS]
        assert all(old is new for old, new in zip(before, after, strict=True))


def test_reused_custody_is_rejected_without_new_effects(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    lab.reader.items = [b"W1XT1 0\n"]
    released(lab, run(lab), "REFUSED")
    before = [getattr(lab.custody, name) for name in FIELDS]
    marker = len(lab.kernel.calls)
    lab.reader, lab.writer = Reader(lab.kernel, [record(lab.external)]), Writer(lab.kernel)
    result = run(lab)
    assert type(result) is str and result == "REJECTED"
    assert lab.kernel.calls[marker:] == [] and lab.reader.lookups == 0
    assert lab.writer.lookups == {}
    after = [getattr(lab.custody, name) for name in FIELDS]
    assert all(old is new for old, new in zip(before, after, strict=True))


# ---------------------------------------------------------------- positive path


def test_positive_padded_reference_adopts_starts_drains_and_closes(
    monkeypatch: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    lab = make_lab(monkeypatch)
    lab.reader.items = [b"W1XT1 " + f"{lab.external:016x}".encode() + b"\n"]
    owner = released(lab, run(lab), "DONE")
    custody, kernel = lab.custody, lab.kernel
    assert type(custody.reference) is int and custody.reference == lab.external
    assert custody.adopt_result == "ADOPTED" and custody.ack == "DELIVERED_LOCAL"
    assert custody.first_error is None and custody.output_bytes == 0
    assert owner.external == lab.external and owner.external_state == "ADOPTED"
    assert lab.writer.data == [ACKS["ADOPTED"]] and lab.writer.flushes == 1
    assert type(lab.writer.data[0]) is bytes
    assert lab.reader.sizes == [24, 1]  # the 23-byte record, then the true EOF read
    assert lab.reader.lookups == 1 and lab.writer.lookups == {"write": 1, "flush": 1}
    calls = kernel.calls
    assert kernel.handles["job"] == lab.outer
    assert calls.index("CreateJobObjectW") < calls.index("port.read")  # setup first
    assert calls.index("port.flush") < calls.index("CreateProcessW")  # start after delivery
    tail = calls[calls.index("GetExitCodeProcess") :]
    assert tail[1:3] == ["QueryInformationJobObject"] * 2  # accounting then members
    assert [ms for ms in kernel.wait_args if ms != 0] == [MAX_WAIT_MS] * kernel.entry_waits
    assert lab.external not in kernel.closed
    assert capsys.readouterr() == ("", "")  # stdout is the ack port only; stderr silent
    assert CANARY not in repr(custody)


def test_fragmented_input_with_leading_zeros_is_accepted(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    lab.reader.items = [b"W1", b"XT1 0", b"001", b"04\n"]  # "W1XT1 000104\n"
    assert lab.external == 0x104
    released(lab, run(lab), "DONE")
    assert lab.reader.sizes == [24, 22, 17, 14, 11]  # only what is missing up to 24
    assert lab.custody.reference == 0x104


# ---------------------------------------------------------------- input refusals


INPUTS: dict[str, list[object]] = {
    "uppercase": [b"W1XT1 1A\n"],
    "cr": [b"W1XT1 104\r\n"],
    "double-space": [b"W1XT1  104\n"],
    "trailing-space": [b"W1XT1 104 \n"],
    "no-lf": [b"W1XT1 104"],
    "empty": [],
    "prefix": [b"W1XT2 104\n"],
    "no-digits": [b"W1XT1 \n"],
    "plus": [b"W1XT1 +104\n"],
    "underscore": [b"W1XT1 1_04\n"],
    "0x": [b"W1XT1 0x104\n"],
    "unicode-digit": [b"W1XT1 \xd9\xa1\n"],
    "seventeen-digits": [b"W1XT1 " + b"0" * 16 + b"1\n"],
    "zero": [b"W1XT1 0\n"],
    "zero-padded": [b"W1XT1 0000000000000000\n"],
    "invalid-handle": [b"W1XT1 ffffffffffffffff\n"],
    "second-record": [b"W1XT1 104\n", b"W1XT1 104\n"],
    "extra-after": [b"W1XT1 104\n", b"x"],
    "bytearray": [bytearray(b"W1XT1 104\n")],
    "memoryview": [memoryview(b"W1XT1 104\n")],
    "text": ["W1XT1 104\n"],
    "none": [None],
    "over-request": [b"W1XT1 104\n" + b" " * 20],
}


@pytest.mark.parametrize("case", sorted(INPUTS))
def test_invalid_input_is_refused_input_without_adopt(monkeypatch: Any, case: str) -> None:
    lab = make_lab(monkeypatch)
    lab.reader.items = list(INPUTS[case])
    owner = released(lab, run(lab), "REFUSED")
    custody = lab.custody
    assert custody.reference is None and custody.adopt_result is None
    assert owner.adopt_attempted is False and owner.external is None
    assert xj.external_kinds(lab.kernel, lab.external) == []
    assert lab.writer.data == [ACKS["REFUSED_INPUT"]] and custody.ack == "DELIVERED_LOCAL"
    assert "CreateProcessW" not in lab.kernel.calls
    if case in ("seventeen-digits", "over-request"):
        assert lab.reader.sizes == [24]  # never reads past the 24-byte bound


def test_opaque_read_result_is_refused_without_inspection(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    probes: list[str] = []
    lab.reader.items = [qbase.Opaque(probes)]
    released(lab, run(lab), "REFUSED")
    assert probes == [] and lab.writer.data == [ACKS["REFUSED_INPUT"]]


def test_ordinary_read_error_is_first_error_and_refused_input(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    error = ValueError(CANARY)
    lab.reader.items = [error]
    released(lab, run(lab), "REFUSED")
    assert lab.custody.first_error is error and lab.custody.adopt_result is None
    assert lab.writer.data == [ACKS["REFUSED_INPUT"]]
    assert CANARY not in repr(lab.custody)


def test_maximum_reference_is_adopted_as_query_refusal(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    maximum = INVALID - 1
    lab.reader.items = [record(maximum)]
    released(lab, run(lab), "REFUSED")
    assert lab.custody.reference == maximum and lab.custody.adopt_result == "REFUSED_QUERY"
    assert xj.external_kinds(lab.kernel, maximum)[:1] == [EXTENDED]
    assert lab.writer.data == [ACKS["REFUSED_QUERY"]]
    xj.assert_c_safe(lab.kernel, maximum)


# ---------------------------------------------------------------- adopt outcomes and acks


def _broken_byref(*_args: Any, **_kwargs: Any) -> Any:
    raise ValueError(CANARY)


ADOPT_REFUSALS = {
    "handle": "REFUSED_HANDLE",
    "query": "REFUSED_QUERY",
    "config": "REFUSED_CONFIG",
    "not-empty": "REFUSED_NOT_EMPTY",
    "members-short": "REFUSED_QUERY",
    "internal": "REFUSED_INTERNAL",
}


@pytest.mark.parametrize("case", sorted(ADOPT_REFUSALS))
def test_adopt_refusal_gets_one_exact_ack_and_releases(monkeypatch: Any, case: str) -> None:
    lab = make_lab(monkeypatch)
    kernel = lab.kernel
    if case == "handle":
        lab.reader.items = [record(lab.outer)]  # owned job: an alias, never borrowed
    elif case == "query":
        lab.reader.items = [record(0xABC)]  # unknown to the fake kernel
    elif case == "config":
        kernel.limit_override["external"] = (xj.LIMIT_FLAGS, 1)
    elif case == "not-empty":
        kernel.job_faults[("external", ACCOUNTING, "adopt")] = "accounting_nonempty"
    elif case == "members-short":
        kernel.job_faults[("external", MEMBERS, "adopt")] = "short"
    else:  # scoped stdlib port fault ONLY between the true EOF and the ack write
        original = ctypes.byref
        lab.reader.on_eof = lambda: monkeypatch.setattr(ctypes, "byref", _broken_byref)
        lab.writer.on_write = lambda: monkeypatch.setattr(ctypes, "byref", original)
    owner = released(lab, run(lab), "REFUSED")
    expected = ADOPT_REFUSALS[case]
    custody = lab.custody
    assert custody.adopt_result == expected and owner.adopt_attempted is True
    assert owner.external_state == "REFUSED" and custody.first_error is None
    assert lab.writer.data == [ACKS[expected]] and lab.writer.flushes == 1
    assert "CreateProcessW" not in kernel.calls


def test_adopt_internal_with_held_owner_acks_once_and_retains(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    lab.reader.on_eof = lambda: lab.custody.owner.quarantine.append(0)  # malformed shape
    owner = retained(lab, run(lab))
    assert lab.custody.adopt_result == "REFUSED_INTERNAL" and owner.state == "HELD"
    assert lab.writer.data == [ACKS["REFUSED_INTERNAL"]]
    assert "CloseHandle" not in lab.kernel.calls and "CreateProcessW" not in lab.kernel.calls
    assert lab.custody.first_error is None and lab.custody.first_control is None


WRITE_RESULTS: dict[str, object] = {
    "short": "short",
    "long": "long",
    "zero": 0,
    "none": None,
    "bool": True,
    "bigint": "bigint",
    "float": 14.0,
}


@pytest.mark.parametrize("branch", ["adopted", "input"])
@pytest.mark.parametrize("case", sorted(WRITE_RESULTS))
def test_inexact_write_is_write_failed_without_flush_retry_or_start(
    monkeypatch: Any, case: str, branch: str
) -> None:
    lab = make_lab(monkeypatch)
    if branch == "input":
        lab.reader.items = [b"W1XT1 0\n"]
    lab.writer.returns = [WRITE_RESULTS[case]]
    released(lab, run(lab), "ACK_FAILED")
    expected = ACKS["ADOPTED"] if branch == "adopted" else ACKS["REFUSED_INPUT"]
    assert lab.writer.data == [expected] and lab.writer.flushes == 0
    assert "port.flush" not in lab.kernel.calls and "CreateProcessW" not in lab.kernel.calls
    assert lab.custody.ack == "WRITE_FAILED" and lab.custody.first_error is None


def test_opaque_write_result_is_write_failed_without_inspection(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    probes: list[str] = []
    lab.writer.returns = [qbase.Opaque(probes)]
    released(lab, run(lab), "ACK_FAILED")
    assert probes == [] and lab.custody.ack == "WRITE_FAILED"
    assert "CreateProcessW" not in lab.kernel.calls


@pytest.mark.parametrize("port", ["write", "flush"])
def test_ordinary_port_error_is_first_error_and_ack_failed(monkeypatch: Any, port: str) -> None:
    lab = make_lab(monkeypatch)
    error = OSError(CANARY)
    if port == "write":
        lab.writer.returns = [error]
    else:
        lab.writer.flush_item = error
    released(lab, run(lab), "ACK_FAILED")
    custody = lab.custody
    assert custody.first_error is error
    assert custody.ack == ("WRITE_FAILED" if port == "write" else "FLUSH_FAILED")
    assert lab.writer.data == [ACKS["ADOPTED"]] and lab.kernel.calls.count("port.write") == 1
    assert lab.kernel.calls.count("port.flush") == (0 if port == "write" else 1)
    assert "CreateProcessW" not in lab.kernel.calls
    assert CANARY not in repr(custody)


def test_first_error_is_kept_when_a_later_close_fails(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    error = OSError(CANARY)
    lab.writer.returns = [error]
    lab.kernel.plan[("CloseHandle", 1)] = ("false", 5)
    owner = retained(lab, run(lab))
    assert lab.custody.first_error is error and owner.state == "HELD"


# ---------------------------------------------------------------- setup before input


def test_clean_setup_failure_acks_internal_without_reading(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    lab.kernel.plan["CreateJobObjectW"] = ("false", 5)
    released(lab, run(lab), "SETUP_REFUSED")
    custody = lab.custody
    assert lab.reader.sizes == []  # the record may stay unconsumed
    assert lab.writer.data == [ACKS["REFUSED_INTERNAL"]] and custody.ack == "DELIVERED_LOCAL"
    assert custody.adopt_result is None and custody.reference is None
    win32(lab, custody.first_error, "WIN32_JOB")


def test_invalid_request_content_is_a_clean_setup_refusal(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    lab.request = lab.adoption.Request("relative.exe", COMMAND, ENV, DIR)
    released(lab, run(lab), "SETUP_REFUSED")
    assert lab.kernel.calls == ["port.write", "port.flush"] and lab.reader.sizes == []
    win32(lab, lab.custody.first_error, "WIN32_REQUEST")


def test_setup_failure_with_undelivered_ack_is_ack_failed(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    lab.kernel.plan["CreateJobObjectW"] = ("false", 5)
    lab.writer.returns = ["short"]
    released(lab, run(lab), "ACK_FAILED")
    assert lab.custody.ack == "WRITE_FAILED" and lab.reader.sizes == []


def test_held_setup_acks_internal_and_retains(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    lab.kernel.plan["CreateJobObjectW"] = "raise"
    owner = retained(lab, run(lab))
    assert owner.state == "HELD" and lab.reader.sizes == []
    assert lab.writer.data == [ACKS["REFUSED_INTERNAL"]] and "CloseHandle" not in lab.kernel.calls
    win32(lab, lab.custody.first_error, "WIN32_HELD")


@pytest.mark.parametrize("branch", ["setup-failed", "ready"])
def test_failed_close_in_a_refusal_branch_retains(monkeypatch: Any, branch: str) -> None:
    lab = make_lab(monkeypatch)
    if branch == "setup-failed":
        lab.kernel.plan["SetInformationJobObject"] = ("false", 5)  # job already owned
    else:
        lab.reader.items = [b"W1XT1 0\n"]
    lab.kernel.plan[("CloseHandle", 1)] = ("false", 5)
    owner = retained(lab, run(lab))
    assert owner.state == "HELD" and lab.custody.ack == "DELIVERED_LOCAL"
    first = "WIN32_CONFIG" if branch == "setup-failed" else "WIN32_HELD"
    win32(lab, lab.custody.first_error, first)


# ---------------------------------------------------------------- supervision and drain


@pytest.mark.parametrize("code", [0, 1, 0xFFFFFFFF])
def test_exit_code_selects_done_or_done_nonzero(monkeypatch: Any, code: int) -> None:
    lab = make_lab(monkeypatch)
    lab.kernel.exit_value = code
    released(lab, run(lab), "DONE" if code == 0 else "DONE_NONZERO")


@pytest.mark.parametrize("fault", ["one", "two_done"])
def test_post_exit_accounting_one_or_two_with_zero_active_discharges(
    monkeypatch: Any, fault: str
) -> None:
    lab = make_lab(monkeypatch)
    if fault == "two_done":  # ER3: P plus one finished helper; no helper is allocated
        lab.kernel.exit_faults[("job", ACCOUNTING)] = "two_done"
    released(lab, run(lab), "DONE")
    assert "CreateProcessW" in lab.kernel.calls and lab.kernel.calls.count("CreateProcessW") == 1


@pytest.mark.parametrize("fault", ["zero", "active", "three", "members"])
def test_post_exit_inventory_outside_domain_retains(monkeypatch: Any, fault: str) -> None:
    lab = make_lab(monkeypatch)
    kind = MEMBERS if fault == "members" else ACCOUNTING
    lab.kernel.exit_faults[("job", kind)] = fault
    owner = retained(lab, run(lab))
    assert owner.state == "RUNNING" and lab.kernel.calls.count("CloseHandle") == 3
    assert "TerminateJobObject" not in lab.kernel.calls
    if fault == "three":
        win32(lab, lab.custody.first_error, "WIN32_TREE")


def test_alive_child_exhausts_the_finite_budget_and_retains(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    lab.kernel.exit_at = None
    owner = retained(lab, run(lab, 3))
    assert lab.kernel.entry_waits == 3 and owner.state == "RUNNING"
    assert "TerminateJobObject" not in lab.kernel.calls
    assert lab.kernel.calls.count("CloseHandle") == 3  # only the start's parent copies


def test_budget_cap_is_exactly_400_turns(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    lab.kernel.exit_at = None
    retained(lab, run(lab, MAX_TURNS))
    assert lab.kernel.entry_waits == MAX_TURNS


@pytest.mark.parametrize("budget", [2, 3])
def test_output_before_exit_shares_the_same_budget(monkeypatch: Any, budget: int) -> None:
    lab = make_lab(monkeypatch)
    lab.kernel.exit_at = 3
    lab.kernel.pipe.extend(b"p" * (2 * MAX_READ))
    result = run(lab, budget)
    if budget == 3:
        released(lab, result, "DONE")
    else:
        assert retained(lab, result).state == "RUNNING"
    assert lab.custody.output_bytes == 2 * MAX_READ and lab.kernel.entry_waits == budget


@pytest.mark.parametrize("budget", [3, 4, MAX_TURNS])
def test_multichunk_drain_after_exit_until_fresh_eof(monkeypatch: Any, budget: int) -> None:
    """R1: the 4th turn reads the last 5 bytes and may close on a fresh None after it."""
    lab = make_lab(monkeypatch)
    size = 3 * MAX_READ + 5
    lab.kernel.pipe.extend(b"p" * size)
    result = run(lab, budget)
    kernel = lab.kernel
    assert max(kernel.read_sizes) <= MAX_READ and kernel.entry_waits <= budget
    if budget == 3:  # 5 bytes still buffered: no EOF can have been observed
        assert retained(lab, result).state == "RUNNING"
        assert kernel.calls.count("ReadFile") == 3 and kernel.entry_waits == 3
        assert lab.custody.output_bytes == 3 * MAX_READ and len(kernel.pipe) == 5
    else:  # one wait and at most one read per turn: four turns are necessary and enough
        released(lab, result, "DONE")
        assert kernel.calls.count("ReadFile") == 4 and 4 <= kernel.entry_waits <= 5
        assert lab.custody.output_bytes == size and len(kernel.pipe) == 0


def test_output_counter_is_bounded_by_budget_reads(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    lab.kernel.exit_at = None
    lab.kernel.pipe.extend(b"p" * (10 * MAX_READ))
    retained(lab, run(lab, 3))
    custody = lab.custody
    assert custody.output_bytes == 3 * MAX_READ and lab.kernel.calls.count("ReadFile") == 3
    assert not any(isinstance(getattr(custody, name), bytes | bytearray) for name in FIELDS)


@pytest.mark.parametrize("budget", [1, 2])
def test_none_before_inventory_is_not_eof(monkeypatch: Any, budget: int) -> None:
    lab = make_lab(monkeypatch)
    lab.kernel.exit_at, lab.kernel.eof_while_alive = 2, True
    result = run(lab, budget)
    if budget == 2:
        released(lab, result, "DONE")
    else:
        assert retained(lab, result).state == "RUNNING"
        assert lab.kernel.calls.count("CloseHandle") == 3


@pytest.mark.parametrize(
    ("exit_at", "budget", "category"), [(1, 1, "DONE"), (2, 1, "RETAIN"), (2, 2, "DONE")]
)
def test_empty_read_alone_is_not_eof(
    monkeypatch: Any, exit_at: int, budget: int, category: str
) -> None:
    """R1: b"" proves nothing; a NEW available None after the positive inventory does.

    With exit at the first wait, one turn holds the empty read, the inventory and the
    fresh None, so it may close. Before the exit the same empty read must retain.
    """
    lab = make_lab(monkeypatch)
    lab.kernel.exit_at = exit_at
    lab.kernel.pipe.extend(b"p" * 10)
    lab.kernel.read_broken = 1
    result = run(lab, budget)
    assert lab.kernel.calls.count("ReadFile") == 1 and lab.kernel.entry_waits == budget
    if category == "DONE":
        released(lab, result, "DONE")
    else:
        assert retained(lab, result).state == "RUNNING"
        assert lab.kernel.calls.count("CloseHandle") == 3
    assert lab.custody.output_bytes == 0


def test_wait_false_after_true_is_inconsistent_and_retains(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    lab.kernel.revive_at = 2
    lab.kernel.pipe.extend(b"p" * (MAX_READ + 1))
    owner = retained(lab, run(lab))
    assert lab.kernel.entry_waits == 2 and owner.state == "RUNNING"
    assert lab.kernel.calls.count("CloseHandle") == 3


HOLDS: dict[str, tuple[Any, object]] = {
    "peek": (("PeekNamedPipe", 1), ("false", 5)),
    "wait": (("WaitForSingleObject", 1), "raise"),
    "close": (("CloseHandle", 4), ("false", 5)),
}


@pytest.mark.parametrize("case", sorted(HOLDS))
def test_backend_hold_during_supervision_or_close_retains(monkeypatch: Any, case: str) -> None:
    lab = make_lab(monkeypatch)
    key, spec = HOLDS[case]
    lab.kernel.plan[key] = spec
    owner = retained(lab, run(lab))
    assert owner.state == "HELD" and "TerminateJobObject" not in lab.kernel.calls
    win32(lab, lab.custody.first_error, "WIN32_HELD")


# ---------------------------------------------------------------- first control


SUPERVISION = frozenset({"SUPERVISE", "DRAIN"})
CONTROL_POINTS: dict[str, tuple[frozenset[str], str, str]] = {
    "setup": (frozenset({"SETUP"}), "HELD", "NOT_ATTEMPTED"),
    "reader": (frozenset({"INPUT"}), "READY", "NOT_ATTEMPTED"),
    "write": (frozenset({"ACK"}), "READY", ""),
    "flush": (frozenset({"ACK"}), "READY", ""),
    "start": (frozenset({"START"}), "HELD", "DELIVERED_LOCAL"),
    "wait": (SUPERVISION, "RUNNING", "DELIVERED_LOCAL"),
    "available": (SUPERVISION, "RUNNING", "DELIVERED_LOCAL"),
    "read": (SUPERVISION, "RUNNING", "DELIVERED_LOCAL"),
    "exit-code": (SUPERVISION, "RUNNING", "DELIVERED_LOCAL"),
    "accounting": (SUPERVISION, "RUNNING", "DELIVERED_LOCAL"),
    "members": (SUPERVISION, "RUNNING", "DELIVERED_LOCAL"),
    "close": (frozenset({"CLOSE"}), "RUNNING", "DELIVERED_LOCAL"),
    "close-refused": (frozenset({"CLOSE"}), "READY", "DELIVERED_LOCAL"),
}


KERNEL_ARMS: dict[str, tuple[str, tuple[str, int]]] = {
    "setup": ("raise_on", ("QueryInformationJobObject", 1)),  # _config inside setup
    "start": ("raise_on", ("IsProcessInJob", 1)),
    "wait": ("raise_on", ("WaitForSingleObject", 1)),
    "available": ("raise_on", ("PeekNamedPipe", 1)),
    "read": ("raise_on", ("ReadFile", 1)),
    "exit-code": ("raise_on", ("GetExitCodeProcess", 1)),
    "accounting": ("exit_faults", ("job", ACCOUNTING)),
    "members": ("exit_faults", ("job", MEMBERS)),
    "close": ("raise_on", ("WaitForSingleObject", 2)),  # close's own wait(0)
    "close-refused": ("raise_on", ("CloseHandle", 1)),
}
PORT_ARMS = {"reader": ("reader", "items"), "write": ("writer", "returns")}


def _arm(lab: Any, point: str, control: BaseException) -> None:
    """Table-driven: every CONTROL_POINTS entry arms exactly one first control."""
    if point == "read":
        lab.kernel.exit_at = None  # P alive with output: the read happens before any exit
        lab.kernel.pipe.extend(b"p" * 10)
    if point == "close-refused":
        lab.reader.items = [b"W1XT1 0\n"]  # INPUT refusal, then the READY close
    if point in KERNEL_ARMS:
        table, key = KERNEL_ARMS[point]
        getattr(lab.kernel, table)[key] = control
    elif point in PORT_ARMS:
        port, attribute = PORT_ARMS[point]
        setattr(getattr(lab, port), attribute, [control])
    else:
        assert point == "flush"
        lab.writer.flush_item = control


def test_sanity_control_arm_tables_cover_every_point() -> None:
    """Fake-only: the table-driven _arm drops no control point."""
    armed = set(KERNEL_ARMS) | set(PORT_ARMS) | {"flush"}
    assert armed == set(CONTROL_POINTS) and len(armed) == 13
    assert not set(KERNEL_ARMS) & set(PORT_ARMS)


@pytest.mark.parametrize("ctl_type", [qbase.FalseCtl, qbase.BoomCtl, "kernel"])
@pytest.mark.parametrize("point", sorted(CONTROL_POINTS))
def test_first_control_is_retained_with_no_later_entry_effect(
    monkeypatch: Any, point: str, ctl_type: Any
) -> None:
    lab = make_lab(monkeypatch)
    probes: list[str] = []
    control: BaseException = xj.KernelCtl() if ctl_type == "kernel" else ctl_type(probes)
    _arm(lab, point, control)
    owner = retained(lab, run(lab))
    custody, kernel = lab.custody, lab.kernel
    stages, state, ack = CONTROL_POINTS[point]
    assert custody.first_control is control and probes == []
    assert control.__cause__ is None and control.__context__ is None
    assert custody.first_error is None and custody.stage.name in stages
    assert owner.state == state
    if ack:
        assert custody.ack == ack
    if ack == "NOT_ATTEMPTED":
        assert lab.writer.data == []
    snapshot = kernel.snapshot
    assert snapshot is not None
    calls, roles, kinds = kernel.trace()
    tail, role_tail = calls[len(snapshot[0]) :], roles[len(snapshot[1]) :]
    if point == "start":  # inherited _interrupt residual on the OWNED outer job only
        assert tail in ([], ["TerminateJobObject"])
        assert role_tail in ([], [("TerminateJobObject", "terminate_job", lab.outer)])
    else:
        assert tail == [] and role_tail == [] and kinds == snapshot[2]
    if point in ("setup", "reader", "write", "flush"):
        assert "CreateProcessW" not in calls


@pytest.mark.parametrize(
    "after", ["delivered", "write-control", "write-short", "flush-control", "flush-error"]
)
def test_refused_control_allows_exactly_one_control_ack(monkeypatch: Any, after: str) -> None:
    lab = make_lab(monkeypatch)
    control, second, error = xj.KernelCtl(), xj.KernelCtl(), OSError(CANARY)
    lab.kernel.job_faults[("external", EXTENDED, "adopt")] = control
    if after == "write-control":
        lab.writer.returns = [second]
    elif after == "write-short":
        lab.writer.returns = ["short"]
    elif after == "flush-control":
        lab.writer.flush_item = second
    elif after == "flush-error":
        lab.writer.flush_item = error
    owner = retained(lab, run(lab))
    custody, kernel = lab.custody, lab.kernel
    assert custody.adopt_result == "REFUSED_CONTROL" and owner.state == "HELD"
    assert owner.adopt_control is control and custody.first_control is control
    assert custody.reference == lab.external
    assert lab.writer.data == [ACKS["REFUSED_CONTROL"]]  # exactly one attempt, no retry
    snapshot = kernel.snapshot  # taken at the FIRST control, inside adopt
    assert snapshot is not None
    calls, roles, kinds = kernel.trace()
    expected = ["port.write"] if after.startswith("write") else ["port.write", "port.flush"]
    assert calls[len(snapshot[0]) :] == expected  # no SDK call after the first control
    assert roles == snapshot[1] and kinds == snapshot[2]
    assert custody.first_error is (error if after == "flush-error" else None)
    if after == "delivered":
        assert custody.ack == "DELIVERED_LOCAL"
    elif after == "write-short":
        assert custody.ack == "WRITE_FAILED"
    elif after == "flush-error":
        assert custody.ack == "FLUSH_FAILED"


def test_retained_custody_keeps_every_reference_for_the_caller(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    lab.kernel.exit_at = None
    owner = retained(lab, run(lab, 2))
    custody = lab.custody
    assert custody.owner is owner and custody.reference == lab.external
    assert owner.external == lab.external and lab.external not in owner.ledger.values()
    assert {"job", "process", "thread", "stdout_read"} <= set(owner.ledger)
    assert custody.adopt_result == "ADOPTED" and custody.ack == "DELIVERED_LOCAL"
    assert custody.first_error is None and custody.first_control is None
