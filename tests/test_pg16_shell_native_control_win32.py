"""Fake two-job kernel tests for the nested-job control adapter.

No real WinDLL, kernel object, process, thread or loop. The accepted backend
source is read by SHA into a private namespace; only that private copy's
_load_api and sys seams are replaced. No .venv, pyvenv.cfg or binary read.
"""

import ctypes
import os
import runpy
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "docs/poc/pg16_shell_native_control_win32.py"
PID = 4242
FOREIGN = (0x9001, 0x9002)
JOB_LIST = 0x2000D
HANDLE_LIST = 0x20002


class Kernel:
    """Raw kernel32-shaped fake with any number of jobs."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.counts: dict[str, int] = {}
        self.plan: dict[Any, Any] = {}
        self.last = 0
        self.next = 0x100
        self.inherit: dict[int, int] = {}
        self.closed: list[int] = []
        self.double_closed: list[int] = []
        self.handles: dict[str, int] = {}
        self.limits: dict[int, tuple[int, int]] = {}
        self.limit_override: dict[str, tuple[int, int]] = {}
        self.extra: dict[str, tuple[int, ...]] = {}
        self.updates: list[Any] = []
        self.attr_address: Any = None
        self.attr_live = False
        self.created: Any = None
        self.process_jobs: tuple[int, ...] = ()
        self.alive = False
        self.suspended = False
        self.exit = 0
        self.pipe = bytearray()
        self.touched: list[int] = []
        self.kill_on_close = True

    def _gate(self, name: str, *handles: int) -> Any:
        self.calls.append(name)
        self.touched.extend(handles)
        count = self.counts[name] = self.counts.get(name, 0) + 1
        spec = self.plan.get((name, count), self.plan.get(name))
        if spec == "raise":
            raise ValueError("secret-detail")
        if spec == "interrupt":
            raise KeyboardInterrupt
        if spec is not None and spec[0] == "false":
            self.last = spec[1]
        return spec

    def _new(self, kind: str, inherit: int) -> int:
        self.next += 4
        self.handles[kind] = self.next
        self.inherit[self.next] = inherit
        return self.next

    def _kind(self, handle: int) -> str:
        return next(kind for kind, value in self.handles.items() if value == handle)

    def _members(self, job: int) -> tuple[int, ...]:
        own = (PID,) if self.alive and job in self.process_jobs else ()
        return own + self.extra.get(self._kind(job), ())

    def CreateJobObjectW(self, security: Any, name: Any) -> Any:  # noqa: N802
        spec = self._gate("CreateJobObjectW")
        if spec and spec[0] == "alias":
            return self.handles[spec[1]]
        if spec:
            return None
        assert security is None and name is None
        handle = self._new("job" if "job" not in self.handles else "inner", 0)
        self.limits[handle] = (0, 0)
        return handle

    def SetInformationJobObject(  # noqa: N802
        self, job: int, kind: int, info: Any, size: int
    ) -> int:
        if self._gate("SetInformationJobObject", job):
            return 0
        basic = info._obj.BasicLimitInformation
        assert kind == 9 and size == 144
        self.limits[job] = (basic.LimitFlags, basic.ActiveProcessLimit)
        return 1

    def QueryInformationJobObject(self, *args: Any) -> int:  # noqa: N802
        job, kind, info, size, length = args
        spec = self._gate("QueryInformationJobObject", job)
        if spec and spec[0] == "false":
            return 0
        target = info._obj
        assert ctypes.sizeof(target) == size
        name = self._kind(job)
        if kind == 9:
            flags, active = self.limit_override.get(name, self.limits[job])
            target.BasicLimitInformation.LimitFlags = flags
            target.BasicLimitInformation.ActiveProcessLimit = active
        elif kind == 1:
            own = 1 if self.created and job in self.process_jobs else 0
            target.TotalProcesses = own + len(self.extra.get(name, ()))
            target.ActiveProcesses = len(self._members(job))
        else:
            assert kind == 3
            pids = self._members(job)
            if len(pids) > 2:
                self.last = 234
                return 0
            target.NumberOfAssignedProcesses = len(pids)
            target.NumberOfProcessIdsInList = len(pids)
            for index, pid in enumerate(pids):
                target.ProcessIdList[index] = pid
            if spec and spec[0] == "short":
                length._obj.value = 8 + 8 * len(pids) - 1
                return 1
        length._obj.value = size
        return 1

    def CreateFileW(  # noqa: N802
        self, name: str, access: int, share: int, security: Any, *rest: Any
    ) -> Any:
        if self._gate("CreateFileW"):
            return (1 << 64) - 1
        assert name == "NUL" and share == 3 and security._obj.bInheritHandle == 1
        assert rest == (3, 0, None)
        return self._new("stdin" if access == 0x80000000 else "stderr", 1)

    def CreatePipe(  # noqa: N802
        self, reader: Any, writer: Any, security: Any, size: int
    ) -> int:
        if self._gate("CreatePipe"):
            return 0
        assert security._obj.bInheritHandle == 1 and size == 0
        reader._obj.value = self._new("stdout_read", 1)
        writer._obj.value = self._new("stdout_write", 1)
        return 1

    def SetHandleInformation(self, handle: int, mask: int, flags: int) -> int:  # noqa: N802
        if self._gate("SetHandleInformation", handle):
            return 0
        self.inherit[handle] = flags & mask
        return 1

    def GetHandleInformation(self, handle: int, flags: Any) -> int:  # noqa: N802
        spec = self._gate("GetHandleInformation", handle)
        if spec and spec[0] == "false":
            return 0
        flags._obj.value = self.inherit[handle] ^ (1 if spec == ("flip", 0) else 0)
        return 1

    def InitializeProcThreadAttributeList(  # noqa: N802
        self, buffer: Any, count: int, flags: int, size: Any
    ) -> int:
        self._gate("InitializeProcThreadAttributeList")
        assert count == 2 and flags == 0
        if buffer is None:
            size._obj.value = 48
            self.last = 122
            return 0
        self.attr_address, self.attr_live = ctypes.addressof(buffer), True
        return 1

    def UpdateProcThreadAttribute(self, *args: Any) -> int:  # noqa: N802
        buffer, flags, attribute, value, size, *rest = args
        if self._gate("UpdateProcThreadAttribute"):
            return 0
        assert ctypes.addressof(buffer) == self.attr_address and self.attr_live
        assert flags == 0 and rest == [None, None] and size == ctypes.sizeof(value)
        self.updates.append((attribute, list(value), size, value))
        return 1

    def DeleteProcThreadAttributeList(self, buffer: Any) -> None:  # noqa: N802
        self._gate("DeleteProcThreadAttributeList")
        assert ctypes.addressof(buffer) == self.attr_address
        self.attr_live = False

    def CreateProcessW(self, *args: Any) -> int:  # noqa: N802
        spec = self._gate("CreateProcessW")
        info = args[9]._obj
        jobs = next(item for item in self.updates if item[0] == JOB_LIST)
        # The pair buffer object must still be alive and unchanged at creation.
        self.created = {"jobs": list(jobs[3]), "attributes_live": self.attr_live}
        if spec and spec[0] == "false":
            self.created = None
            return 0
        if spec and spec[0] == "false-out":
            info.hProcess, info.hThread = spec[1]
            info.dwProcessId = PID
            self.created = None
            return 0
        info.hProcess = self._new("process", 0)
        info.hThread = self._new("thread", 0)
        info.dwProcessId = PID
        order = tuple(jobs[1])
        self.process_jobs = order[:1] if spec and spec[0] == "only-outer" else order
        self.alive, self.suspended = True, True
        return 1

    def IsProcessInJob(self, process: int, job: int, result: Any) -> int:  # noqa: N802
        if self._gate("IsProcessInJob", process, job):
            return 0
        result._obj.value = 1 if job in self.process_jobs else 0
        return 1

    def ResumeThread(self, thread: int) -> int:  # noqa: N802
        self._gate("ResumeThread", thread)
        self.suspended = False
        return 1

    def TerminateProcess(self, process: int, code: int) -> int:  # noqa: N802
        if self._gate("TerminateProcess", process):
            return 0
        self.alive, self.exit = False, code
        return 1

    def TerminateJobObject(self, job: int, code: int) -> int:  # noqa: N802
        if self._gate("TerminateJobObject", job):
            return 0
        if job in self.process_jobs:
            self.alive, self.exit = False, code
        self.extra[self._kind(job)] = ()
        return 1

    def WaitForSingleObject(self, process: int, milliseconds: int) -> int:  # noqa: N802
        self._gate("WaitForSingleObject", process)
        assert 0 <= milliseconds <= 5000
        return 0 if not self.alive else 0x102

    def GetExitCodeProcess(self, process: int, code: Any) -> int:  # noqa: N802
        self._gate("GetExitCodeProcess", process)
        code._obj.value = self.exit
        return 1

    def PeekNamedPipe(self, handle: int, *args: Any) -> int:  # noqa: N802
        if self._gate("PeekNamedPipe", handle):
            return 0
        available = args[3]
        writer = self.handles.get("stdout_write")
        if not self.pipe and not self.alive and writer in self.closed:
            self.last = 109
            return 0
        available._obj.value = len(self.pipe)
        return 1

    def ReadFile(self, *args: Any) -> int:  # noqa: N802
        self._gate("ReadFile", args[0])
        return 0

    def CloseHandle(self, handle: int) -> int:  # noqa: N802
        if self._gate("CloseHandle", handle):
            return 0
        if handle in self.closed:
            self.double_closed.append(handle)
        self.closed.append(handle)
        flags = self.limits.get(handle, (0, 0))[0]
        if self.kill_on_close and flags & 0x2000 and handle in self.process_jobs:
            self.alive, self.exit = False, 0
        return 1


def runtime() -> Any:
    flags = SimpleNamespace(isolated=1, dont_write_bytecode=1, optimize=0)
    return SimpleNamespace(
        platform="win32", version_info=(3, 11, 3), maxsize=(1 << 63) - 1, flags=flags
    )


@pytest.fixture
def lab(monkeypatch: Any) -> Any:
    module = runpy.run_path(str(MODULE))
    loaded = module["definitions"]()
    backend = loaded["backend"]
    kernel = Kernel()

    def load() -> Any:
        return backend["_Api"](kernel, lambda: kernel.last)

    # Seams of the private executed copy only; the accepted file is untouched.
    monkeypatch.setitem(backend, "_load_api", load)
    monkeypatch.setitem(backend, "sys", runtime())

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("native effect attempted")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(threading.Thread, "start", forbidden)
    request = loaded["Request"](
        "C:\\launcher\\python.exe",
        '"C:\\launcher\\python.exe" -I -B -c "print(1)"',
        (("SystemRoot", "C:\\Windows"),),
        "C:\\work",
    )
    owner = loaded["NestedJobOwner"](request)
    return SimpleNamespace(
        module=module, loaded=loaded, backend=backend, kernel=kernel, owner=owner
    )


def raises(lab: Any, code: str, function: Any, *args: Any) -> Any:
    with pytest.raises(lab.loaded["Win32Error"]) as caught:
        function(*args)
    assert caught.value.args == (code,)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    return caught


def running(lab: Any) -> Any:
    lab.owner.setup()
    lab.owner.start()
    assert lab.owner.state == "RUNNING"
    return lab.owner


def no_terminate(lab: Any) -> bool:
    audit = lab.owner.audit
    return "TerminateJobObject" not in audit and "TerminateProcess" not in audit


# -- source, lazy purity, reuse invariants -------------------------------------


def test_import_and_construction_are_pure(monkeypatch: Any) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("read or native effect")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden)
    module = runpy.run_path(str(MODULE))
    assert module["_DEFINITIONS"] == {}
    loaded = module["definitions"]()
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "lstat", forbidden)
    owner = loaded["NestedJobOwner"](object())
    assert owner.state == "NEW" and owner.ledger == {} and owner.audit == ()
    assert owner.audit_valid is True and owner._api is None


def test_backend_source_pin_is_enforced(monkeypatch: Any) -> None:
    module = runpy.run_path(str(MODULE))
    monkeypatch.setitem(module["definitions"].__globals__, "BACKEND_SHA", "0" * 64)
    with pytest.raises(module["ControlError"]) as caught:
        module["definitions"]()
    assert caught.value.args == ("CONTROL_SOURCE",) and caught.value.__context__ is None


def test_inherited_start_and_dispatch_assumptions(lab: Any) -> None:
    owner_class = lab.loaded["NestedJobOwner"]
    base = lab.backend["Owner"]
    assert owner_class._start is base._start and owner_class.start is base.start
    assert owner_class._abort is base._abort and owner_class._interrupt is base._interrupt
    overridden = {
        name for name in vars(owner_class) if not name.startswith("__") or name == "__init__"
    }
    assert overridden == {
        "__init__",
        "_entry",
        "_record",
        "_query",
        "_job_config",
        "_job_accounting",
        "_job_members",
        "_setup",
        "_call",
        "_expand_job_list",
        "_verify_inner",
        "close_inner",
        "_close_inner",
        "close",
        "_close_extra",
    }
    raw = (REPO / "docs/poc/pg16_shell_admission_win32.py").read_bytes()
    check = lab.module["_dispatch_assumptions"]
    assert check(raw) is True
    changed = raw.replace(b'self._call("ResumeThread"', b'self._ok("ResumeThread"')
    assert changed != raw and check(changed) is False


# -- setup and start -------------------------------------------------------------


def test_happy_path_nested_jobs_and_pre_resume_inner_checks(lab: Any) -> None:
    owner, k = running(lab), lab.kernel
    outer, inner = k.handles["job"], k.handles["inner"]
    assert owner.ledger["job"] == outer and owner.ledger["inner"] == inner
    assert k.limits[outer] == k.limits[inner] == (0x2008, 2)
    assert k.inherit[outer] == k.inherit[inner] == 0
    jobs = [item for item in k.updates if item[0] == JOB_LIST]
    assert [(item[1], item[2]) for item in jobs] == [([outer, inner], 16)]
    handles = [item for item in k.updates if item[0] == HANDLE_LIST]
    assert handles[0][1] == [k.handles["stdin"], k.handles["stdout_write"], k.handles["stderr"]]
    assert k.created == {"jobs": [outer, inner], "attributes_live": True}
    assert jobs[0][3] is owner._pair and owner._pair in owner._keep
    assert k.process_jobs == (outer, inner) and owner.inner_verified is True
    resume = k.calls.index("ResumeThread")
    checks = [index for index, name in enumerate(k.calls) if name == "IsProcessInJob"]
    assert len(checks) == 2 and all(index < resume for index in checks)
    assert "ResumeThread" in owner.audit and no_terminate(lab) and owner.audit_valid


def test_unexpected_job_list_argument_is_never_delegated(lab: Any) -> None:
    lab.owner.setup()
    before = list(lab.kernel.calls)
    handle_type = lab.backend["HANDLE"]
    for items, size in (
        ((handle_type * 1)(0x9999), 8),
        ((handle_type * 2)(1, 2), 16),
        ((handle_type * 1)(lab.owner.ledger["job"]), 16),
    ):
        arguments = (None, 0, JOB_LIST, items, size, None, None)
        assert lab.owner._call("UpdateProcThreadAttribute", *arguments) == (True, None)
    assert lab.kernel.calls == before and lab.owner._pair is None


@pytest.mark.parametrize("extra", [-1, 1, 2], ids=["short", "long-8", "long-9"])
def test_malformed_attribute_arity_is_never_delegated(lab: Any, extra: int) -> None:
    # Review P2-A: a valid JOB_LIST at args[2] with 8 arguments reached native.
    lab.owner.setup()
    before = list(lab.kernel.calls)
    items = (lab.backend["HANDLE"] * 1)(lab.owner.ledger["job"])
    valid = [None, 0, JOB_LIST, items, 8, None, None]
    arguments = valid[:extra] if extra < 0 else valid + [None] * extra
    assert lab.owner._call("UpdateProcThreadAttribute", *arguments) == (True, None)
    handle_list = [None, 0, HANDLE_LIST, items, 8, None, None, None]
    assert lab.owner._call("UpdateProcThreadAttribute", *handle_list) == (True, None)
    assert lab.kernel.calls == before and lab.owner._pair is None


def test_nested_list_refused_is_clean_launch_failure_with_proof(lab: Any) -> None:
    lab.owner.setup()
    lab.kernel.plan["CreateProcessW"] = ("false", 87)
    raises(lab, "WIN32_CREATE", lab.owner.start)
    owner = lab.owner
    assert owner.state == "LAUNCH_FAILED" and "inner" in owner.ledger
    owner.close()
    assert owner.state == "CLOSED" and owner.ledger == {} and not lab.kernel.double_closed
    assert lab.kernel.handles["inner"] in lab.kernel.closed


def test_foreign_creation_outputs_are_never_acted_upon(lab: Any) -> None:
    lab.owner.setup()
    lab.kernel.plan["CreateProcessW"] = ("false-out", FOREIGN)
    raises(lab, "WIN32_CREATE", lab.owner.start)
    lab.owner.close()
    assert not set(FOREIGN) & set(lab.kernel.touched) and lab.owner.state == "CLOSED"


def test_membership_only_in_outer_never_resumes(lab: Any) -> None:
    lab.owner.setup()
    lab.kernel.plan["CreateProcessW"] = ("only-outer", 0)
    raises(lab, "WIN32_RESUME", lab.owner.start)
    owner, k = lab.owner, lab.kernel
    assert owner.inner_verified is False and "ResumeThread" not in k.calls and k.suspended
    assert "TerminateJobObject" in owner.audit and not k.alive
    assert owner.state == "LAUNCH_FAILED"
    owner.close()
    assert owner.state == "CLOSED" and not k.double_closed


@pytest.mark.parametrize("fault", ["config", "extra-member", "short-frame", "query-false"])
def test_inner_verification_failure_never_resumes(lab: Any, fault: str) -> None:
    lab.owner.setup()
    k = lab.kernel
    if fault == "config":
        k.limit_override["inner"] = (0x2008 | 0x800, 2)
    elif fault == "extra-member":
        k.extra["inner"] = (7,)
    # Queries: setup outer 1, setup inner 2, start outer 3-5, inner 6-8.
    elif fault == "short-frame":
        k.plan[("QueryInformationJobObject", 8)] = ("short", 0)
    else:
        k.plan[("QueryInformationJobObject", 6)] = ("false", 5)
    raises(lab, "WIN32_RESUME", lab.owner.start)
    assert "ResumeThread" not in k.calls and lab.owner.inner_verified is False


@pytest.mark.parametrize(
    ("plan", "code", "state"),
    [
        ((("CreateJobObjectW", 2), ("false", 5)), "WIN32_JOB", "SETUP_FAILED"),
        ((("CreateJobObjectW", 2), "raise"), "WIN32_HELD", "HELD"),
        ((("CreateJobObjectW", 2), ("alias", "job")), "WIN32_HELD", "HELD"),
        ((("SetInformationJobObject", 2), ("false", 5)), "WIN32_CONFIG", "SETUP_FAILED"),
        ((("GetHandleInformation", 6), ("flip", 0)), "WIN32_INHERIT", "SETUP_FAILED"),
    ],
)
def test_inner_acquisition_failures(lab: Any, plan: Any, code: str, state: str) -> None:
    lab.kernel.plan[plan[0]] = plan[1]
    raises(lab, code, lab.owner.setup)
    owner = lab.owner
    assert owner.state == state
    if state == "HELD":
        raises(lab, "WIN32_HELD", owner.close)
        assert not lab.kernel.closed
        if plan[1] == ("alias", "job"):
            assert owner.quarantine == [lab.kernel.handles["job"]] and "inner" not in owner.ledger
    else:
        owned = set(owner.ledger.values())
        owner.close()
        assert sorted(lab.kernel.closed) == sorted(owned) and not lab.kernel.double_closed


# -- ordinary close vs deliberate inner close ----------------------------------------


def test_ordinary_close_while_live_never_drops_inner(lab: Any) -> None:
    owner, k = running(lab), lab.kernel
    raises(lab, "WIN32_NOT_QUIESCENT", owner.close)
    assert k.handles["inner"] not in k.closed and "inner" in owner.ledger and k.alive
    assert owner.state == "RUNNING" and no_terminate(lab)


def test_explicit_inner_close_kills_without_terminate_then_closes(lab: Any) -> None:
    owner, k = running(lab), lab.kernel
    owner.close_inner()
    assert owner.inner_closed and "inner" not in owner.ledger and not k.alive
    assert owner.wait(0) is True and owner.accounting() == (1, 0) and owner.members() == ()
    owner.close()
    assert owner.state == "CLOSED" and owner.ledger == {} and not k.double_closed
    assert no_terminate(lab) and owner.audit_valid


def test_inner_close_failure_contains_outer_before_held(lab: Any) -> None:
    owner, k = running(lab), lab.kernel
    k.plan[("CloseHandle", 4)] = ("false", 6)  # 3 stdio copies, then INNER
    raises(lab, "WIN32_HELD", owner.close_inner)
    assert owner.held_reason == "WIN32_CLOSE" and "inner" in owner.ledger
    audit = list(owner.audit)
    assert audit.index("TerminateJobObject") > len(audit) - 3 and not k.alive
    for call in (owner.close_inner, owner.close, owner.terminate):
        raises(lab, "WIN32_HELD", call)


def test_inner_close_interruption_keeps_inner_and_audits_direct_terminate(lab: Any) -> None:
    owner, k = running(lab), lab.kernel
    k.plan[("CloseHandle", 4)] = "interrupt"
    with pytest.raises(KeyboardInterrupt):
        owner.close_inner()
    assert owner.state == "HELD" and "inner" in owner.ledger
    assert owner.audit[-1] == "TerminateJobObject" and not k.alive


def finished(lab: Any) -> Any:
    """Running owner whose tree already ended on its own; INNER still owned."""
    owner = running(lab)
    lab.kernel.alive = False
    return owner


def test_interrupt_at_ordinary_inner_close_is_held_and_retains_inner(lab: Any) -> None:
    # Review P2-B: control interruption from the audit on the INNER CloseHandle.
    owner, k = finished(lab), lab.kernel
    original = owner._entry

    def interrupted(name: str) -> str:
        if name == "CloseHandle":
            raise KeyboardInterrupt
        return str(original(name))

    owner._entry = interrupted
    with pytest.raises(KeyboardInterrupt):
        owner.close()
    assert owner.state == "HELD" and owner.held_reason == "WIN32_INTERRUPTED"
    assert "inner" in owner.ledger and k.handles["inner"] not in k.closed
    assert owner.audit_valid is False
    raises(lab, "WIN32_HELD", owner.close)


def test_allocation_failure_at_ordinary_inner_close_is_held(lab: Any, monkeypatch: Any) -> None:
    owner, k = finished(lab), lab.kernel

    def exhausted(*_args: Any) -> Any:
        raise MemoryError

    monkeypatch.setattr(ctypes, "byref", exhausted)
    raises(lab, "WIN32_HELD", owner.close)
    assert owner.state == "HELD" and owner.held_reason == "WIN32_INTERNAL"
    assert "inner" in owner.ledger and k.handles["inner"] not in k.closed


@pytest.mark.parametrize("spec", ["raise", ("false", 6)], ids=["foreign-error", "false"])
def test_inner_close_handle_failure_in_ordinary_close_is_held(lab: Any, spec: Any) -> None:
    owner, k = finished(lab), lab.kernel
    k.plan[("CloseHandle", 4)] = spec  # 3 stdio copies in start, then INNER
    raises(lab, "WIN32_HELD", owner.close)
    assert owner.state == "HELD" and owner.held_reason == "WIN32_CLOSE"
    assert "inner" in owner.ledger and k.handles["job"] not in k.closed


def test_close_inner_requires_running(lab: Any) -> None:
    lab.owner.setup()
    raises(lab, "WIN32_STATE", lab.owner.close_inner)


# -- audit integrity ----------------------------------------------------------------


def test_audit_overflow_invalidates_but_forwards(lab: Any) -> None:
    # Fresh runpy namespace per test: this cap change dies with the test.
    lab.module["definitions"].__globals__["AUDIT_LIMIT"] = 3
    owner, k = running(lab), lab.kernel
    assert owner.audit_valid is False and len(owner.audit) == 3
    assert "ResumeThread" in k.calls and owner.state == "RUNNING"


def test_audit_record_error_invalidates_and_still_terminates(lab: Any) -> None:
    owner, k = running(lab), lab.kernel
    original = owner._entry

    def broken(name: str) -> str:
        if name == "TerminateJobObject":
            raise ValueError("audit failure")
        return str(original(name))

    owner._entry = broken
    owner.terminate()
    assert owner.audit_valid is False and "TerminateJobObject" not in owner.audit
    assert "TerminateJobObject" in k.calls and not k.alive


@pytest.mark.parametrize("operation", ["CreateProcessW", "ResumeThread"])
def test_interruption_while_auditing_never_delegates(lab: Any, operation: str) -> None:
    owner, k = lab.owner, lab.kernel
    owner.setup()
    original = owner._entry

    def interrupted(name: str) -> str:
        if name == operation:
            raise KeyboardInterrupt
        return str(original(name))

    owner._entry = interrupted
    with pytest.raises(KeyboardInterrupt):
        owner.start()
    assert operation not in k.calls and owner.state == "HELD"
    assert owner.audit_valid is False and operation not in owner.audit
    assert "TerminateJobObject" in owner.audit  # inherited direct containment audited
