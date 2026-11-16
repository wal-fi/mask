"""First fake oracles for the N-S external job adoption (root contract 0e26bddc, EJ1-EJ6).

Contract for the FUTURE ``docs/poc/oracle9_w1_external_job_adoption.py``. The source stays
ABSENT until the root reads every oracle and freezes RED. Each source-dependent case loads
it explicitly inside its body; an absent source is an explicit ``pytest.fail``, never a
skip, a pass or a collection/fixture error. ``test_sanity_*`` cases exercise only this
file's fake helpers and are NOT product proof.

Fakes: the frozen raw kernel32 fake ``Kernel`` of ``tests/test_pg16_shell_native_control_
win32.py`` is reused unchanged through a small subclass that adds ONE empty external job
(the borrowed ``C``), a per-call ROLE trace, an exact trace SNAPSHOT at a scripted control,
query faults addressed by job / information kind / phase (before or after creation) and
forced ``CreateProcessW`` output collisions. Only the private executed backend copy's
``_load_api``/``sys`` seams are replaced; stdlib traps forbid a real DLL, process, shell or
thread. No live product module or function is patched. Role rules:
``QueryInformationJobObject(C)`` and ``IsProcessInJob(P, C)`` are legitimate uses of ``C``
as a JOB; ``C`` as a process or thread, ``CloseHandle(C)``, ``TerminateProcess(C)`` or
``TerminateJobObject(C)`` are not.

Author: Claude2 (session 51ea0d85), claude-opus-5-5/medium; V2 applies the root test
review (six points). Senff policy: AI-generated tests require human and security review.
"""

from __future__ import annotations

import ast
import builtins
import ctypes
import hashlib
import os
import runpy
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests import test_oracle9_w1_supervisor_qualification as qbase
from tests import test_pg16_shell_native_control_win32 as ref

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "docs/poc/oracle9_w1_external_job_adoption.py"
BACKEND_RELATIVE = "docs/poc/pg16_shell_admission_win32.py"
BACKEND_FILE = REPO / BACKEND_RELATIVE
BACKEND_SHA = "10c9058f0d6071e86c7b4c8b2566c1ae4c9f78aeba9d92c50687ae6481f22726"
SOURCE_LIMIT = 65536
INVALID_HANDLE = (1 << 64) - 1
LIMIT_FLAGS = 0x2008  # backend JOB_LIMIT_ACTIVE_PROCESS | JOB_LIMIT_KILL_ON_JOB_CLOSE
EXTENDED, ACCOUNTING, MEMBERS = 9, 1, 3  # JOBOBJECTINFOCLASS values used by the backend
JOB_LIST = ref.JOB_LIST
HANDLE_LIST = ref.HANDLE_LIST
KEYS = {"backend", "Request", "Win32Error", "ExternalJobOwner"}
PROPERTIES = ("external", "external_state", "adopt_attempted", "adopt_control")
FORBIDDEN_C_ROLES = frozenset({"close", "terminate_job", "process", "thread"})
ROLE_MAP: dict[str, tuple[str, ...]] = {
    "QueryInformationJobObject": ("job_query",),
    "IsProcessInJob": ("process", "job_member"),
    "CloseHandle": ("close",),
    "TerminateJobObject": ("terminate_job",),
    "TerminateProcess": ("process",),
    "WaitForSingleObject": ("process",),
    "GetExitCodeProcess": ("process",),
    "ResumeThread": ("thread",),
}
CREATION_PORTS = ("CreateProcessW",)
Trace = tuple[list[str], list[tuple[str, str, int]], list[tuple[int, int]]]


class KernelCtl(BaseException):
    """A control raised by the fake kernel; identity is what matters."""


# ---------------------------------------------------------------- fake kernel subclass


class AdoptKernel(ref.Kernel):
    """Frozen fake kernel plus one external job, role trace, faults and collisions."""

    def __init__(self) -> None:
        super().__init__()
        self.roles: list[tuple[str, str, int]] = []
        self.query_kinds: list[tuple[int, int]] = []
        self.raise_on: dict[tuple[str, int], BaseException] = {}
        self.job_faults: dict[tuple[str, int, str], object] = {}
        self.snapshot: Trace | None = None
        self.collide: tuple[str, str] | None = None
        self.collide_control: BaseException | None = None
        for name, roles in ROLE_MAP.items():
            setattr(self, name, self._recording(name, roles, getattr(self, name)))
        for name in CREATION_PORTS:
            setattr(self, name, self._creating(getattr(self, name)))

    def add_external(self) -> int:
        handle = self._new("external", 0)
        self.limits[handle] = (LIMIT_FLAGS, 2)
        return handle

    def trace(self) -> Trace:
        return (list(self.calls), list(self.roles), list(self.query_kinds))

    def _control(self, name: str, control: BaseException) -> None:
        self.calls.append(name)
        if self.snapshot is None:  # the FIRST control's exact trace is kept forever
            self.snapshot = self.trace()
        raise control

    def _job_name(self, handle: object) -> str:
        return next((kind for kind, value in self.handles.items() if value == handle), "")

    def _recording(
        self, name: str, roles: tuple[str, ...], original: Callable[..., Any]
    ) -> Callable[..., Any]:
        def call(*args: Any) -> Any:
            for role, handle in zip(roles, args, strict=False):
                self.roles.append((name, role, handle))
            count = self.counts.get(name, 0) + 1
            control = self.raise_on.get((name, count))
            if control is not None:
                self.counts[name] = count
                self._control(name, control)
            if name != "QueryInformationJobObject":
                return original(*args)
            self.query_kinds.append((args[0], args[1]))
            phase = "created" if self.created else "adopt"
            fault = self.job_faults.get((self._job_name(args[0]), args[1], phase))
            if fault is None:
                return original(*args)
            return self._faulted(original, args, fault)

        return call

    def _faulted(self, original: Callable[..., Any], args: tuple[Any, ...], fault: object) -> Any:
        name = "QueryInformationJobObject"
        if isinstance(fault, BaseException):
            self._control(name, fault)
        if fault == "raise":
            self.calls.append(name)
            raise ValueError(qbase.CANARY)
        if fault == "false":
            self.calls.append(name)
            self.last = 5
            return 0
        result = original(*args)
        target, length, size = args[2]._obj, args[4]._obj, args[3]
        if fault == "short" and args[1] == MEMBERS:
            # BELOW the parent's minimum: header + count * entry - 1.
            header = type(target).ProcessIdList.offset
            count = target.NumberOfProcessIdsInList
            length.value = header + count * ctypes.sizeof(ctypes.c_size_t) - 1
        elif fault == "short":
            length.value = size - 1  # fixed-size structures
        elif fault == "padded":
            length.value = size - 1  # members: still WITHIN header+count*entry..size
        elif fault == "config":
            target.BasicLimitInformation.LimitFlags = LIMIT_FLAGS | 0x800
        elif fault == "accounting_nonempty":
            target.TotalProcesses, target.ActiveProcesses = 1, 1
        elif fault == "accounting_two":
            target.TotalProcesses, target.ActiveProcesses = 2, 2
        elif fault == "members_nonempty":
            target.NumberOfAssignedProcesses, target.NumberOfProcessIdsInList = 1, 1
            target.ProcessIdList[0] = 999
        else:
            assert fault == "members_mismatch"
            target.NumberOfAssignedProcesses = 3  # list/assigned disagree: malformed
        return result

    def _creating(self, original: Callable[..., Any]) -> Callable[..., Any]:
        def call(*args: Any) -> Any:
            if self.collide is None:
                return original(*args)
            kind, which = self.collide
            self._gate("CreateProcessW")
            info = args[9]._obj
            borrowed = self.handles["external"]
            fresh = self._new("thread" if which == "process" else "process", 0)
            if which == "process":
                info.hProcess, info.hThread = borrowed, fresh
            else:
                info.hProcess, info.hThread = fresh, borrowed
            info.dwProcessId = ref.PID
            if kind == "true":
                jobs = next(item for item in self.updates if item[0] == JOB_LIST)
                self.created = {"jobs": list(jobs[3]), "attributes_live": self.attr_live}
                self.process_jobs = tuple(jobs[1])
                self.alive, self.suspended = True, True
                return 1
            if kind == "false":
                self.created = None
                return 0
            if kind == "raise":
                raise ValueError(qbase.CANARY)
            assert self.collide_control is not None
            raise self.collide_control

        return call


def assert_c_safe(kernel: AdoptKernel, external: int) -> None:
    """C may be queried as a JOB; never used as process/thread, closed or terminated."""
    misuse = [(name, role) for name, role, h in kernel.roles if h == external]
    assert [item for item in misuse if item[1] in FORBIDDEN_C_ROLES] == []
    assert external not in kernel.closed and external not in kernel.double_closed


def terminated_jobs(kernel: AdoptKernel) -> list[int]:
    return [handle for _name, role, handle in kernel.roles if role == "terminate_job"]


# ---------------------------------------------------------------- source loading and lab


def require_source() -> None:
    """Explicit FAIL (never skip/pass/collection error) while the source is absent."""
    if not SOURCE.exists():
        pytest.fail("docs/poc/oracle9_w1_external_job_adoption.py is absent (RED)")


def source_namespace() -> dict[str, Any]:
    require_source()
    return runpy.run_path(str(SOURCE), run_name="_w1_external_job_adoption_test")


def forbidden(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("native or read effect attempted")


def native_traps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ctypes, "WinDLL", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(threading.Thread, "start", forbidden)


def make_lab(monkeypatch: pytest.MonkeyPatch, *, setup: bool = True) -> Any:
    module = source_namespace()
    loaded = module["definitions"]()
    backend = loaded["backend"]
    kernel = AdoptKernel()

    def load() -> Any:
        return backend["_Api"](kernel, lambda: kernel.last)

    # Seams of the private executed backend copy ONLY; no live product is patched.
    monkeypatch.setitem(backend, "_load_api", load)
    monkeypatch.setitem(backend, "sys", ref.runtime())
    native_traps(monkeypatch)
    request = loaded["Request"](
        "C:\\launcher\\python.exe",
        '"C:\\launcher\\python.exe" -I -B -c "print(1)"',
        (("SystemRoot", "C:\\Windows"),),
        "C:\\work",
    )
    owner = loaded["ExternalJobOwner"](request)
    lab = SimpleNamespace(module=module, loaded=loaded, backend=backend, kernel=kernel)
    lab.owner = owner
    lab.external = None
    if setup:
        owner.setup()
        assert owner.state == "READY"
        lab.external = kernel.add_external()
    return lab


def w32(lab: Any, code: str, call: Callable[[], object]) -> None:
    with pytest.raises(lab.loaded["Win32Error"]) as caught:
        call()
    assert caught.value.args == (code,)
    assert caught.value.__cause__ is None and caught.value.__context__ is None


def adopted(lab: Any) -> Any:
    assert lab.owner.adopt(lab.external) == "ADOPTED"
    return lab.owner


def error_of(call: Callable[[], object]) -> BaseException | None:
    try:
        call()
    except BaseException as error:
        return error
    return None


def external_kinds(kernel: AdoptKernel, external: int, start: int = 0) -> list[int]:
    return [kind for job, kind in kernel.query_kinds[start:] if job == external]


# ---------------------------------------------------------------- fake helper sanities


def test_sanity_fake_external_job_roles_and_control_snapshot() -> None:
    kernel = AdoptKernel()
    external = kernel.add_external()
    assert kernel.limits[external] == (LIMIT_FLAGS, 2)
    assert kernel._members(external) == () and kernel._job_name(external) == "external"
    control = KernelCtl()
    kernel.raise_on[("CloseHandle", 1)] = control
    with pytest.raises(KernelCtl) as caught:
        kernel.CloseHandle(external)  # role is recorded before the scripted control
    assert caught.value is control
    assert kernel.roles == [("CloseHandle", "close", external)]
    assert kernel.snapshot == kernel.trace() == (["CloseHandle"], kernel.roles, [])
    assert external not in kernel.closed


def test_sanity_second_control_never_replaces_the_first_snapshot() -> None:
    kernel = AdoptKernel()
    external = kernel.add_external()
    kernel.raise_on[("CloseHandle", 1)] = KernelCtl()
    kernel.raise_on[("CloseHandle", 2)] = KernelCtl()
    with pytest.raises(KernelCtl):
        kernel.CloseHandle(external)
    first = kernel.snapshot
    assert first is not None and first == kernel.trace()
    with pytest.raises(KernelCtl):
        kernel.CloseHandle(external)  # a second query/control after the first
    assert kernel.snapshot is first  # identity unchanged
    assert kernel.trace() != first and len(kernel.trace()[0]) == len(first[0]) + 1


def test_sanity_role_checker_accepts_job_use_and_rejects_misuse() -> None:
    kernel = AdoptKernel()
    external = kernel.add_external()
    kernel.roles.append(("QueryInformationJobObject", "job_query", external))
    kernel.roles.append(("IsProcessInJob", "job_member", external))
    assert_c_safe(kernel, external)
    for role in sorted(FORBIDDEN_C_ROLES):
        bad = AdoptKernel()
        bad_external = bad.add_external()
        bad.roles.append(("X", role, bad_external))
        with pytest.raises(AssertionError):
            assert_c_safe(bad, bad_external)


def test_sanity_pinned_backend_and_contract_constants() -> None:
    raw = BACKEND_FILE.read_bytes()
    assert len(raw) <= SOURCE_LIMIT and hashlib.sha256(raw).hexdigest() == BACKEND_SHA
    assert JOB_LIST == 0x2000D and HANDLE_LIST == 0x20002
    for old, _new in DISPATCH_BREAKS.values():
        assert raw.count(old) == 1  # each synthetic break edits exactly one dispatch site


# ---------------------------------------------------------------- pure import, loader, cache


def test_import_body_is_pure_and_separate_from_the_harness(monkeypatch: Any) -> None:
    require_source()
    trapped = dict(vars(builtins))
    for name in ("open", "compile", "exec", "eval"):
        trapped[name] = forbidden
    native_traps(monkeypatch)
    # runpy compiles with real builtins; only the module BODY sees the trapped builtins.
    # Path traps are scoped and restored before any assertion or pytest report.
    with monkeypatch.context() as patch:
        for name in ("resolve", "lstat", "open", "read_bytes", "stat"):
            patch.setattr(Path, name, forbidden)
        outcome = error_of(
            lambda: runpy.run_path(
                str(SOURCE), init_globals={"__builtins__": trapped}, run_name="_w1_xj_pure"
            )
        )
    assert outcome is None
    module = source_namespace()
    assert callable(module["definitions"]) and isinstance(module["AdoptionError"], type)
    assert issubclass(module["AdoptionError"], Exception)


def test_definitions_exact_keys_identities_and_namespace_cache() -> None:
    module = source_namespace()
    first = module["definitions"]()
    assert type(first) is dict and set(first) == KEYS
    assert module["definitions"]() is first  # same COMPLETE dictionary
    backend = first["backend"]
    assert first["Request"] is backend["Request"]
    assert first["Win32Error"] is backend["Win32Error"]
    owner_class = first["ExternalJobOwner"]
    assert issubclass(owner_class, backend["Owner"]) and owner_class is not backend["Owner"]
    other = source_namespace()["definitions"]()
    assert other is not first and other["backend"] is not backend  # per-namespace cache


def test_inherited_backend_paths_are_reused_unchanged() -> None:
    loaded = source_namespace()["definitions"]()
    owner_class, base = loaded["ExternalJobOwner"], loaded["backend"]["Owner"]
    assert owner_class._start is base._start and owner_class._abort is base._abort
    assert owner_class._interrupt is base._interrupt and owner_class.close is base.close
    assert "start" in vars(owner_class) and "adopt" in vars(owner_class)
    assert "_call" in vars(owner_class)


def adoption_error(module: dict[str, Any], error: BaseException | None) -> None:
    assert error is not None and type(error) is module["AdoptionError"]
    assert error.args == ("ADOPT_SOURCE",)
    assert error.__cause__ is None and error.__context__ is None


def test_pin_failure_leaves_no_cache_then_complete_publication(monkeypatch: Any) -> None:
    module = source_namespace()
    definitions = module["definitions"]
    monkeypatch.setitem(definitions.__globals__, "BACKEND_SHA", "0" * 64)
    adoption_error(module, error_of(definitions))
    monkeypatch.setitem(definitions.__globals__, "BACKEND_SHA", BACKEND_SHA)
    loaded = definitions()  # nothing partial was published before the failure
    assert set(loaded) == KEYS and definitions() is loaded


def test_control_during_load_propagates_and_leaves_no_cache(monkeypatch: Any) -> None:
    module = source_namespace()
    definitions = module["definitions"]
    control = KernelCtl()

    def interrupt(*_args: Any, **_kwargs: Any) -> Any:
        raise control

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", interrupt)
        outcome = error_of(definitions)
    assert outcome is control  # never swallowed or converted
    loaded = definitions()
    assert set(loaded) == KEYS and definitions() is loaded


def _tree(root: Path, backend: bytes | None) -> Path:
    poc = root / "docs" / "poc"
    poc.mkdir(parents=True)
    copy = poc / SOURCE.name
    copy.write_bytes(SOURCE.read_bytes())
    if backend is not None:
        (poc / Path(BACKEND_RELATIVE).name).write_bytes(backend)
    return copy


def _marker_payload(marker: Path) -> bytes:
    return f"\nimport pathlib as _tamper\n_tamper.Path({str(marker)!r}).write_text('x')\n".encode()


@pytest.mark.parametrize("kind", ["missing", "tampered", "oversize"])
def test_bad_backend_bytes_are_refused_before_execution(tmp_path: Path, kind: str) -> None:
    require_source()
    marker = tmp_path / "executed"
    raw = BACKEND_FILE.read_bytes()
    backend: bytes | None = None
    if kind == "tampered":
        backend = raw + _marker_payload(marker)
    elif kind == "oversize":
        backend = raw + ("#" + "x" * SOURCE_LIMIT + "\n").encode() + _marker_payload(marker)
    if backend is not None:
        ast.parse(backend.decode("utf-8"))  # valid Python: a refusal is never a SyntaxError
    module = runpy.run_path(str(_tree(tmp_path / kind, backend)), run_name="_w1_xj_" + kind)
    adoption_error(module, error_of(module["definitions"]))
    assert not marker.exists()


DISPATCH_BREAKS: dict[str, tuple[bytes, bytes]] = {
    "resume-not-call": (b'self._call("ResumeThread"', b'self._ok("ResumeThread"'),
    "create-not-call": (
        b'self._call(\n            "CreateProcessW"',
        b'self._ok(\n            "CreateProcessW"',
    ),
    "update-not-ok": (
        b'self._ok(\n                "UpdateProcThreadAttribute"',
        b'self._call(\n                "UpdateProcThreadAttribute"',
    ),
}


@pytest.mark.parametrize("variant", sorted(DISPATCH_BREAKS))
def test_dispatch_broken_backend_with_matching_private_pin_is_refused(
    tmp_path: Path, monkeypatch: Any, variant: str
) -> None:
    require_source()
    marker = tmp_path / "executed"
    old, new = DISPATCH_BREAKS[variant]
    raw = BACKEND_FILE.read_bytes()
    assert raw.count(old) == 1
    altered = raw.replace(old, new) + _marker_payload(marker)
    ast.parse(altered.decode("utf-8"))  # valid Python whose dispatch premise is broken
    assert len(altered) <= SOURCE_LIMIT
    module = runpy.run_path(str(_tree(tmp_path / variant, altered)), run_name="_w1_xj_ast")
    # The pin is adjusted ONLY in this private executed namespace of the new module.
    digest = hashlib.sha256(altered).hexdigest()
    monkeypatch.setitem(module["definitions"].__globals__, "BACKEND_SHA", digest)
    adoption_error(module, error_of(module["definitions"]))
    assert not marker.exists()  # refused by the AST premise BEFORE execution


def test_static_shape_import_defines_only() -> None:
    require_source()
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned = {"subprocess", "threading", "socket", "asyncio", "multiprocessing", "runpy"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not {alias.name.split(".")[0] for alias in node.names} & banned
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in banned | {"docs", "tests"}
    for index, statement in enumerate(tree.body):
        if isinstance(statement, ast.Expr):
            assert index == 0 and isinstance(statement.value, ast.Constant)
        assert not isinstance(statement, ast.If | ast.For | ast.While | ast.With | ast.Try)
    assert BACKEND_SHA in source and BACKEND_RELATIVE in source
    assert "pg16_shell_native_control_win32" not in source
    assert "oracle9_w1_supervisor_qualification" not in source


# ---------------------------------------------------------------- construction and properties


def test_construction_is_pure_and_properties_start_closed(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch, setup=False)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", forbidden)
        patch.setattr(Path, "lstat", forbidden)
        owner = lab.loaded["ExternalJobOwner"](lab.owner.request)
    assert lab.kernel.calls == [] and owner.state == "NEW" and owner.ledger == {}
    assert owner.external is None and owner.external_state == "NOT_ADOPTED"
    assert owner.adopt_attempted is False and owner.adopt_control is None


@pytest.mark.parametrize("name", PROPERTIES)
def test_public_properties_are_read_only(monkeypatch: Any, name: str) -> None:
    lab = make_lab(monkeypatch)
    before = getattr(lab.owner, name)
    with pytest.raises(AttributeError):
        setattr(lab.owner, name, 1)
    with pytest.raises(AttributeError):
        delattr(lab.owner, name)
    assert getattr(lab.owner, name) is before


# ---------------------------------------------------------------- adopt: state and repetition


@pytest.mark.parametrize("phase", ["new", "running", "closed", "held"])
def test_adopt_outside_ready_raises_without_consuming(monkeypatch: Any, phase: str) -> None:
    lab = make_lab(monkeypatch, setup=phase != "new")
    owner, kernel = lab.owner, lab.kernel
    code = "WIN32_STATE"
    if phase == "running":
        adopted(lab).start()
        assert owner.state == "RUNNING"
    elif phase == "closed":
        owner.close()
        assert owner.state == "CLOSED"
    elif phase == "held":
        kernel.job_faults[("external", EXTENDED, "adopt")] = KernelCtl()
        assert owner.adopt(lab.external) == "REFUSED_CONTROL"
        code = "WIN32_HELD"
    attempted, state = owner.adopt_attempted, owner.external_state
    before = kernel.trace()
    w32(lab, code, lambda: owner.adopt(0x7777))
    assert kernel.trace() == before
    assert owner.adopt_attempted is attempted and owner.external_state == state


def test_second_adopt_in_ready_is_state_error_without_operation(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel = lab.owner, lab.kernel
    assert owner.adopt(True) == "REFUSED_INPUT" and owner.adopt_attempted is True
    before = kernel.trace()
    w32(lab, "WIN32_STATE", lambda: owner.adopt(lab.external))
    assert kernel.trace() == before and owner.external is None and owner.state == "READY"


# ---------------------------------------------------------------- adopt: input and shapes


def _invalid_inputs(probes: list[str]) -> list[object]:
    big = type("BigInt", (int,), {})
    return [
        True,
        False,
        0,
        -1,
        INVALID_HANDLE,
        2**64,
        1.5,
        "0x7777",
        b"\x77",
        None,
        big(0x7777),
        qbase.Opaque(probes),
    ]


@pytest.mark.parametrize("index", range(12))
def test_invalid_reference_is_refused_input_without_query(monkeypatch: Any, index: int) -> None:
    lab = make_lab(monkeypatch)
    probes: list[str] = []
    candidate = _invalid_inputs(probes)[index]
    owner, kernel = lab.owner, lab.kernel
    before = kernel.trace()
    assert owner.adopt(candidate) == "REFUSED_INPUT"
    assert kernel.trace() == before and probes == []
    assert owner.external is None and owner.external_state == "REFUSED"
    assert owner.adopt_attempted is True and owner.state == "READY"


def test_maximum_reference_is_queried_and_refused_as_query(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel = lab.owner, lab.kernel
    maximum = INVALID_HANDLE - 1  # inside the _handle domain; the fake knows no such job
    marker = len(kernel.query_kinds)
    assert owner.adopt(maximum) == "REFUSED_QUERY"
    assert external_kinds(kernel, maximum, marker)[:1] == [EXTENDED]  # actually queried
    assert owner.external == maximum and owner.external_state == "REFUSED"
    assert owner.state == "READY"
    owner.close()
    assert_c_safe(kernel, maximum)


def _corrupt(owner: Any, kind: str, probes: list[str]) -> None:
    ledger_values: dict[str, object] = {
        "ledger-bool-value": True,
        "ledger-zero-value": 0,
        "ledger-invalid-value": INVALID_HANDLE,
        "ledger-opaque-value": qbase.Opaque(probes),
    }
    quarantine_entries: dict[str, object] = {
        "quarantine-opaque": qbase.Opaque(probes),
        "quarantine-nested": [0x5555],
        "quarantine-zero": 0,
        "quarantine-bool": True,
        "quarantine-invalid": INVALID_HANDLE,
    }
    if kind == "ledger-not-dict":
        owner.ledger = list(owner.ledger.items())
    elif kind == "ledger-key":
        owner.ledger[7] = 0x5555
    elif kind == "quarantine-tuple":
        owner.quarantine = tuple(owner.quarantine)
    elif kind in ledger_values:
        owner.ledger["extra"] = ledger_values[kind]
    else:
        owner.quarantine.append(quarantine_entries[kind])


SHAPES = (
    "ledger-not-dict",
    "ledger-key",
    "ledger-bool-value",
    "ledger-zero-value",
    "ledger-invalid-value",
    "ledger-opaque-value",
    "quarantine-tuple",
    "quarantine-opaque",
    "quarantine-nested",
    "quarantine-zero",
    "quarantine-bool",
    "quarantine-invalid",
)


@pytest.mark.parametrize("kind", SHAPES)
def test_malformed_internal_shape_is_refused_internal_and_held(monkeypatch: Any, kind: str) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel = lab.owner, lab.kernel
    probes: list[str] = []
    _corrupt(owner, kind, probes)
    before = kernel.trace()
    assert owner.adopt(lab.external) == "REFUSED_INTERNAL"
    assert kernel.trace() == before and probes == []  # no query, no opaque inspection
    assert owner.external is None and owner.external_state == "REFUSED"
    assert owner.state == "HELD" and owner.held_reason == "WIN32_INTERNAL"
    w32(lab, "WIN32_HELD", owner.close)
    w32(lab, "WIN32_HELD", owner.start)
    assert kernel.trace() == before


@pytest.mark.parametrize("failure", [ValueError, MemoryError])
def test_unexpected_ordinary_error_in_adoption_is_refused_internal(
    monkeypatch: Any, failure: type[Exception]
) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel, external = lab.owner, lab.kernel, lab.external

    def broken(*_args: Any, **_kwargs: Any) -> Any:
        raise failure(qbase.CANARY)

    with monkeypatch.context() as patch:  # SCOPED stdlib port fault, after setup only
        patch.setattr(ctypes, "byref", broken)
        result = owner.adopt(external)
    assert result == "REFUSED_INTERNAL"
    assert owner.external == external and owner.external_state == "REFUSED"
    assert owner.state == "READY" and owner.adopt_control is None
    owner.close()  # normal close only after the port was restored
    assert owner.state == "CLOSED"
    assert_c_safe(kernel, external)


# ---------------------------------------------------------------- adopt: alias versus borrowed C


@pytest.mark.parametrize("target", ["job", "stdin", "stdout_read", "quarantined"])
def test_alias_is_owned_not_borrowed_and_close_stays_normal(monkeypatch: Any, target: str) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel = lab.owner, lab.kernel
    if target == "quarantined":
        owner.quarantine.append(0x7777)
        candidate = 0x7777
    else:
        candidate = owner.ledger[target]
    before = kernel.trace()
    assert owner.adopt(candidate) == "REFUSED_HANDLE"
    assert kernel.trace() == before and owner.external is None and owner.state == "READY"
    owned = dict(owner.ledger)
    owner.close()  # the genuine owned ledger handle is closed normally
    assert owner.state == "CLOSED" and owner.ledger == {}
    assert all(handle in kernel.closed for handle in owned.values())


# ---------------------------------------------------------------- adopt: queries


def test_positive_adoption_queries_c_in_order_and_retains_it(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel, external = lab.owner, lab.kernel, lab.external
    marker = len(kernel.query_kinds)
    assert owner.adopt(external) == "ADOPTED"
    assert external_kinds(kernel, external, marker) == [EXTENDED, ACCOUNTING, MEMBERS]
    assert owner.external == external and owner.external_state == "ADOPTED"
    assert owner.state == "READY" and owner.adopt_control is None
    assert external not in owner.ledger.values()
    assert_c_safe(kernel, external)


QUERY_FAULTS: dict[str, tuple[int, object, str]] = {
    "extended-false": (EXTENDED, "false", "REFUSED_QUERY"),
    "extended-short": (EXTENDED, "short", "REFUSED_QUERY"),
    "extended-raises": (EXTENDED, "raise", "REFUSED_QUERY"),
    "extended-diverges": (EXTENDED, "config", "REFUSED_CONFIG"),
    "accounting-false": (ACCOUNTING, "false", "REFUSED_QUERY"),
    "accounting-short": (ACCOUNTING, "short", "REFUSED_QUERY"),
    "accounting-nonempty": (ACCOUNTING, "accounting_nonempty", "REFUSED_NOT_EMPTY"),
    "members-false": (MEMBERS, "false", "REFUSED_QUERY"),
    "members-short": (MEMBERS, "short", "REFUSED_QUERY"),
    "members-mismatch": (MEMBERS, "members_mismatch", "REFUSED_QUERY"),
    "members-nonempty": (MEMBERS, "members_nonempty", "REFUSED_NOT_EMPTY"),
}
ORDER = [EXTENDED, ACCOUNTING, MEMBERS]


@pytest.mark.parametrize("case", sorted(QUERY_FAULTS))
def test_query_outcomes_are_deterministic_and_retain_c(monkeypatch: Any, case: str) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel, external = lab.owner, lab.kernel, lab.external
    kind, fault, expected = QUERY_FAULTS[case]
    kernel.job_faults[("external", kind, "adopt")] = fault
    marker = len(kernel.query_kinds)
    assert owner.adopt(external) == expected
    seen = external_kinds(kernel, external, marker)
    reached = ORDER[: ORDER.index(kind) + 1]
    assert seen[: len(reached)] == reached and seen == ORDER[: len(seen)]  # fixed order
    assert owner.external == external and owner.external_state == "REFUSED"
    assert owner.state == "READY" and owner.adopt_control is None
    w32(lab, "WIN32_STATE", owner.start)  # no adoption, no P
    assert "CreateProcessW" not in kernel.calls
    owner.close()
    assert owner.state == "CLOSED" and owner.external == external
    assert_c_safe(kernel, external)


def test_members_length_within_parent_interval_is_accepted_at_adoption(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel, external = lab.owner, lab.kernel, lab.external
    kernel.job_faults[("external", MEMBERS, "adopt")] = "padded"  # count 0, length size-1
    assert owner.adopt(external) == "ADOPTED"
    assert owner.external == external and owner.external_state == "ADOPTED"
    assert_c_safe(kernel, external)


def test_members_length_within_parent_interval_is_accepted_before_resume(
    monkeypatch: Any,
) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel, external = adopted(lab), lab.kernel, lab.external
    kernel.job_faults[("external", MEMBERS, "created")] = "padded"  # count 1, length size-1
    owner.start()
    assert owner.state == "RUNNING" and kernel.calls.count("ResumeThread") == 1
    assert external not in owner.ledger.values()
    assert_c_safe(kernel, external)


def test_extended_limit_count_divergence_is_config(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    lab.kernel.limit_override["external"] = (LIMIT_FLAGS, 1)
    assert lab.owner.adopt(lab.external) == "REFUSED_CONFIG"
    assert lab.owner.external == lab.external and lab.owner.state == "READY"


# ---------------------------------------------------------------- adopt: first control


@pytest.mark.parametrize("ctl_type", [qbase.FalseCtl, qbase.BoomCtl, "kernel"])
@pytest.mark.parametrize("kind", ORDER)
def test_first_control_is_refused_control_held_with_zero_later_sdk(
    monkeypatch: Any, ctl_type: Any, kind: int
) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel, external = lab.owner, lab.kernel, lab.external
    probes: list[str] = []
    control: BaseException = KernelCtl() if ctl_type == "kernel" else ctl_type(probes)
    kernel.job_faults[("external", kind, "adopt")] = control
    assert owner.adopt(external) == "REFUSED_CONTROL"
    snapshot = kernel.snapshot
    assert snapshot is not None and kernel.trace() == snapshot  # NOTHING after the control
    assert owner.adopt_control is control and probes == []
    assert control.__context__ is None and control.__cause__ is None
    assert owner.external == external and owner.external_state == "REFUSED"
    assert owner.state == "HELD" and owner.held_reason == "WIN32_INTERRUPTED"
    w32(lab, "WIN32_HELD", owner.start)
    w32(lab, "WIN32_HELD", owner.close)
    w32(lab, "WIN32_HELD", lambda: owner.adopt(external))
    assert kernel.trace() == snapshot
    assert_c_safe(kernel, external)


# ---------------------------------------------------------------- start without adoption


@pytest.mark.parametrize("prior", ["none", "refused-input"])
def test_start_without_adoption_has_zero_sdk_and_attributes(monkeypatch: Any, prior: str) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel = lab.owner, lab.kernel
    if prior == "refused-input":
        assert owner.adopt(-5) == "REFUSED_INPUT"
    before = kernel.trace()
    w32(lab, "WIN32_STATE", owner.start)
    assert kernel.trace() == before and owner.state == "READY"
    assert owner._attributes is None and owner._create_attempted is False


def test_start_before_setup_keeps_state_priority(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch, setup=False)
    w32(lab, "WIN32_STATE", lab.owner.start)
    assert lab.kernel.calls == [] and lab.owner.state == "NEW"


# ---------------------------------------------------------------- positive two-job start


def test_positive_two_job_start_with_c_verified_before_resume(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel, external = adopted(lab), lab.kernel, lab.external
    owner.start()
    assert owner.state == "RUNNING"
    outer = owner.ledger["job"]
    jobs = [item for item in kernel.updates if item[0] == JOB_LIST]
    assert [(item[1], item[2]) for item in jobs] == [([outer, external], 16)]
    assert any(item is jobs[0][3] for item in owner._keep)  # pair alive through creation
    assert kernel.created == {"jobs": [outer, external], "attributes_live": True}
    assert kernel.calls.count("ResumeThread") == 1 and kernel.suspended is False
    process = owner.ledger["process"]
    resume_role = [i for i, item in enumerate(kernel.roles) if item[0] == "ResumeThread"]
    member = [
        index
        for index, (name, role, handle) in enumerate(kernel.roles)
        if name == "IsProcessInJob" and role == "job_member" and handle == external
    ]
    c_queries = [
        index
        for index, (_name, role, handle) in enumerate(kernel.roles)
        if handle == external and role == "job_query"
    ]
    assert len(resume_role) == 1 and len(member) == 1
    assert member[0] < resume_role[0]  # membership of P in C proven BEFORE the resume
    after_member = [index for index in c_queries if index > member[0]]
    assert len(after_member) == 3 and max(after_member) < resume_role[0]
    assert ("IsProcessInJob", "process", process) in kernel.roles
    assert external not in owner.ledger.values() and owner.external == external
    assert_c_safe(kernel, external)


PRE_RESUME_FAULTS: dict[str, tuple[int, str] | None] = {
    "only-outer": None,
    "c-extended-diverges": (EXTENDED, "config"),
    "c-accounting-two": (ACCOUNTING, "accounting_two"),
    "c-members-short": (MEMBERS, "short"),
}


@pytest.mark.parametrize("case", sorted(PRE_RESUME_FAULTS))
def test_c_pre_resume_failure_never_resumes_and_contains_owned_outer(
    monkeypatch: Any, case: str
) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel, external = adopted(lab), lab.kernel, lab.external
    outer = owner.ledger["job"]
    fault = PRE_RESUME_FAULTS[case]
    if fault is None:
        kernel.plan["CreateProcessW"] = ("only-outer", 0)
    else:  # injected ONLY after creation, addressed to C by job and information kind
        kernel.job_faults[("external", fault[0], "created")] = fault[1]
    w32(lab, "WIN32_RESUME", owner.start)
    assert owner.state == "LAUNCH_FAILED"
    assert kernel.created == {"jobs": [outer, external], "attributes_live": True}
    assert "ResumeThread" not in kernel.calls and kernel.suspended is True
    assert terminated_jobs(kernel) == [outer]  # positive containment of the OWNED OUTER
    assert external not in owner.ledger.values()
    assert_c_safe(kernel, external)


# ---------------------------------------------------------------- dispatch validation


def test_unexpected_job_list_arguments_are_never_delegated(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel = adopted(lab), lab.kernel
    before = kernel.trace()
    handle = lab.backend["HANDLE"]
    for items, size in (
        ((handle * 1)(0x9999), 8),
        ((handle * 2)(1, 2), 16),
        ((handle * 1)(owner.ledger["job"]), 16),
    ):
        arguments = (None, 0, JOB_LIST, items, size, None, None)
        assert owner._call("UpdateProcThreadAttribute", *arguments) == (True, None)
    outer_items = (handle * 1)(owner.ledger["job"])
    short_arity = (None, 0, JOB_LIST, outer_items, 8, None)
    long_arity = (None, 0, JOB_LIST, outer_items, 8, None, None, None)
    long_handles = (None, 0, HANDLE_LIST, outer_items, 8, None, None, None)
    for bad_arity in (short_arity, long_arity, long_handles):
        assert owner._call("UpdateProcThreadAttribute", *bad_arity) == (True, None)
    assert kernel.trace() == before


# ---------------------------------------------------------------- CreateProcessW collisions


@pytest.mark.parametrize("which", ["process", "thread"])
@pytest.mark.parametrize("kind", ["true", "false", "raise"])
def test_output_aliasing_c_is_never_adopted(monkeypatch: Any, kind: str, which: str) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel, external = adopted(lab), lab.kernel, lab.external
    outer = owner.ledger["job"]
    kernel.collide = (kind, which)
    w32(lab, "WIN32_HELD", owner.start)
    assert owner.state == "HELD" and owner.held_reason == "WIN32_CREATE"
    assert external not in owner.ledger.values()
    assert "process" not in owner.ledger and "thread" not in owner.ledger
    assert "ResumeThread" not in kernel.calls
    assert terminated_jobs(kernel) == [outer]  # inherited containment of OWNED OUTER only
    assert owner.external == external and owner.external_state == "ADOPTED"
    w32(lab, "WIN32_HELD", owner.close)
    assert_c_safe(kernel, external)


@pytest.mark.parametrize("which", ["process", "thread"])
def test_output_aliasing_c_with_control_follows_inherited_interrupt(
    monkeypatch: Any, which: str
) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel, external = adopted(lab), lab.kernel, lab.external
    control = KernelCtl()
    kernel.collide, kernel.collide_control = ("control", which), control
    raised = qbase.control_of(owner.start)
    assert raised is control
    assert owner.state == "HELD" and owner.held_reason == "WIN32_INTERRUPTED"
    assert external not in owner.ledger.values() and "ResumeThread" not in kernel.calls
    assert external not in terminated_jobs(kernel)
    assert_c_safe(kernel, external)


def test_non_colliding_creation_keeps_inherited_behaviour(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel, external = adopted(lab), lab.kernel, lab.external
    kernel.plan["CreateProcessW"] = ("false-out", ref.FOREIGN)
    w32(lab, "WIN32_CREATE", owner.start)
    assert owner.state == "LAUNCH_FAILED" and external not in owner.ledger.values()
    owner.close()
    assert owner.state == "CLOSED"
    assert not set(ref.FOREIGN) & set(kernel.touched)
    assert_c_safe(kernel, external)


# ---------------------------------------------------------------- close: owned versus borrowed


def test_close_after_natural_exit_releases_owned_and_retains_c(monkeypatch: Any) -> None:
    lab = make_lab(monkeypatch)
    owner, kernel, external = adopted(lab), lab.kernel, lab.external
    owner.start()
    owned = dict(owner.ledger)
    kernel.alive = False  # natural exit of P in the fake
    owner.close()
    assert owner.state == "CLOSED" and owner.ledger == {}
    assert all(handle in kernel.closed for handle in owned.values())
    assert owner.external == external and owner.external_state == "ADOPTED"
    assert not kernel.double_closed
    assert_c_safe(kernel, external)
