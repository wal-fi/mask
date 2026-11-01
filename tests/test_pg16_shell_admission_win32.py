"""Fake-kernel tests for the private Win32 admission backend.

No real WinDLL, kernel object, process, thread or event loop: the module's
internal _load_api and sys are replaced inside a freshly executed namespace.
"""

import ast
import ctypes
import runpy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "docs/poc/pg16_shell_admission_win32.py"
PID = 4242
FOREIGN = (0x9001, 0x9002)  # never created by the owner under test


class HostileError(Exception):
    """Foreign exception whose every textual/attribute access fails."""

    def __str__(self) -> str:
        raise AssertionError("foreign str read")

    def __repr__(self) -> str:
        raise AssertionError("foreign repr read")

    def __getattribute__(self, name: str) -> Any:
        if name in ("args", "winerror", "errno", "strerror"):
            raise AssertionError("foreign attribute read")
        return super().__getattribute__(name)


def observed(item: Any, name: str) -> Any:
    """Fresh post-mutation read; keeps type checkers from reusing old narrowing."""
    return getattr(item, name)


class Kernel:
    """Raw kernel32-shaped fake; reads/writes the real ctypes structures passed in."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.counts: dict[str, int] = {}
        self.plan: dict[Any, Any] = {}
        self.last = 0
        self.next = 0x100
        self.inherit: dict[int, int] = {}
        self.closed: list[int] = []
        self.double_closed: list[int] = []
        self.limit = (0, 0)
        self.limit_override: Any = None
        self.lengths: dict[int, int] = {}
        self.updates: list[Any] = []
        self.attr_address: Any = None
        self.attr_live = False
        self.created: Any = None
        self.in_job = True
        self.alive = False
        self.suspended = False
        self.exit = 0
        self.total = 0
        self.extra_active = 0
        self.extra_members: tuple[int, ...] = ()
        self.pipe = bytearray()
        self.waits: list[int] = []
        self.reads: list[int] = []
        self.read_override: Any = None
        self.handles: dict[str, int] = {}
        self.touched: list[int] = []

    def _gate(self, name: str, *handles: int) -> Any:
        self.calls.append(name)
        self.touched.extend(handles)
        count = self.counts[name] = self.counts.get(name, 0) + 1
        spec = self.plan.get((name, count), self.plan.get(name))
        if spec == "raise":
            raise ValueError("secret-detail")
        if spec == "hostile":
            raise HostileError()
        if spec == "interrupt-now":
            raise KeyboardInterrupt
        if spec is not None and spec[0] == "false":
            self.last = spec[1]
        return spec

    def _new(self, kind: str, inherit: int) -> int:
        self.next += 4
        self.handles[kind] = self.next
        self.inherit[self.next] = inherit
        return self.next

    def CreateJobObjectW(self, security: Any, name: Any) -> Any:  # noqa: N802
        if self._gate("CreateJobObjectW"):
            return None
        assert security is None and name is None
        return self._new("job", 0)

    def SetInformationJobObject(  # noqa: N802
        self, job: int, kind: int, info: Any, size: int
    ) -> int:
        if self._gate("SetInformationJobObject", job):
            return 0
        basic = info._obj.BasicLimitInformation
        assert kind == 9 and size == 144
        self.limit = (basic.LimitFlags, basic.ActiveProcessLimit)
        return 1

    def QueryInformationJobObject(self, *args: Any) -> int:  # noqa: N802
        job, kind, info, size, length = args
        spec = self._gate("QueryInformationJobObject", job)
        if spec and spec[0] == "false":
            return 0
        target = info._obj
        assert ctypes.sizeof(target) == size
        if kind == 9:
            flags, active = self.limit_override or self.limit
            target.BasicLimitInformation.LimitFlags = flags
            target.BasicLimitInformation.ActiveProcessLimit = active
        elif kind == 1:
            running = 1 if self.alive and self.in_job else 0
            target.TotalProcesses = self.total
            target.ActiveProcesses = running + self.extra_active
        else:
            assert kind == 3
            pids = ((PID,) if self.alive and self.in_job else ()) + self.extra_members
            if len(pids) > 2:
                self.last = 234
                return 0
            target.NumberOfAssignedProcesses = len(pids)
            target.NumberOfProcessIdsInList = len(pids)
            for index, pid in enumerate(pids):
                target.ProcessIdList[index] = pid
            if spec and spec[0] == "short-frame":
                # Reviewer P2-E: success with a frame shorter than its header.
                target.NumberOfAssignedProcesses = target.NumberOfProcessIdsInList = 0
                length._obj.value = spec[1]
                return 1
            if spec and spec[0] == "short-list":
                length._obj.value = 8 + 8 * len(pids) - 1
                return 1
        length._obj.value = self.lengths.get(kind, size)
        return 1

    def CreateFileW(  # noqa: N802
        self, name: str, access: int, share: int, security: Any, *rest: Any
    ) -> Any:
        spec = self._gate("CreateFileW")
        if spec and spec[0] == "alias":
            return self.handles[spec[1]]
        if spec:
            return (1 << 64) - 1
        assert name == "NUL" and share == 3 and rest == (3, 0, None)
        sa = security._obj
        assert sa.nLength == 24 and sa.bInheritHandle == 1
        return self._new("stdin" if access == 0x80000000 else "stderr", 1)

    def CreatePipe(  # noqa: N802
        self, reader: Any, writer: Any, security: Any, size: int
    ) -> int:
        spec = self._gate("CreatePipe")
        assert security._obj.bInheritHandle == 1 and size == 0
        if spec and spec[0] == "false":
            return 0
        if spec and spec[0] == "false-out":
            # Reviewer P1-A: FALSE with indeterminate, non-owned output values.
            reader._obj.value, writer._obj.value = spec[1]
            self.last = 5
            return 0
        reader._obj.value = self._new("stdout_read", 1)
        writer._obj.value = self._new("stdout_write", 1)
        if spec and spec[0] == "alias":
            writer._obj.value = self.handles[spec[1]]
        if spec == ("half", 0):
            raise ValueError("secret-detail")
        if spec == ("interrupt", 0):
            raise KeyboardInterrupt
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
        spec = self._gate("InitializeProcThreadAttributeList")
        assert count == 2 and flags == 0
        if buffer is None:
            size._obj.value = 48
            self.last = spec[1] if spec else 122
            return 0
        if spec:
            return 0
        assert ctypes.sizeof(buffer) == 48
        self.attr_address, self.attr_live = ctypes.addressof(buffer), True
        return 1

    def UpdateProcThreadAttribute(self, *args: Any) -> int:  # noqa: N802
        buffer, flags, attribute, value, size, *rest = args
        if self._gate("UpdateProcThreadAttribute"):
            return 0
        assert ctypes.addressof(buffer) == self.attr_address and self.attr_live
        assert flags == 0 and rest == [None, None] and size == ctypes.sizeof(value)
        self.updates.append((attribute, list(value), size))
        return 1

    def DeleteProcThreadAttributeList(self, buffer: Any) -> None:  # noqa: N802
        self._gate("DeleteProcThreadAttributeList")
        assert ctypes.addressof(buffer) == self.attr_address
        self.attr_live = False

    def CreateProcessW(self, *args: Any) -> int:  # noqa: N802
        spec = self._gate("CreateProcessW")
        app, command, psa, tsa, inherit, flags, env, cwd, startup, info = args
        record = startup._obj
        base = record.StartupInfo
        self.created = {
            "app": app,
            "command": command.value,
            "security": (psa, tsa),
            "inherit": inherit,
            "flags": flags,
            "environment": env[: len(env)],
            "directory": cwd,
            "cb": base.cb,
            "startf": base.dwFlags,
            "stdio": (base.hStdInput, base.hStdOutput, base.hStdError),
            "attributes_ok": record.lpAttributeList == self.attr_address and self.attr_live,
        }
        if spec and spec[0] == "false":
            return 0
        if spec and spec[0] == "lost":
            raise ValueError("secret-detail")
        target = info._obj
        if spec and spec[0] == "false-out":
            # Reviewer P1-B: FALSE, no child, indeterminate non-owned outputs.
            target.hProcess, target.hThread = spec[1]
            target.dwProcessId = PID
            self.last = 2
            return 0
        target.hProcess = self._new("process", 0)
        target.hThread = self._new("thread", 0)
        target.dwProcessId = PID
        self.alive, self.suspended, self.total = True, True, 1
        if spec and spec[0] == "alias":
            target.hProcess = self.handles[spec[1]]
        if spec and spec[0] == "filled-raise":
            raise ValueError("secret-detail")
        if spec and spec[0] == "interrupt":
            # Reviewer P2-C: real creation, outputs filled, then interruption.
            raise KeyboardInterrupt
        return 1

    def IsProcessInJob(self, process: int, job: int, result: Any) -> int:  # noqa: N802
        if self._gate("IsProcessInJob", process, job):
            return 0
        assert process == self.handles["process"] and job == self.handles["job"]
        result._obj.value = 1 if self.in_job else 0
        return 1

    def ResumeThread(self, thread: int) -> int:  # noqa: N802
        spec = self._gate("ResumeThread", thread)
        assert thread == self.handles["thread"]
        self.suspended = False
        return int(spec[1]) if spec and spec[0] == "value" else 1

    def TerminateProcess(self, process: int, code: int) -> int:  # noqa: N802
        if self._gate("TerminateProcess", process):
            return 0
        assert process == self.handles["process"]
        self.alive, self.exit = False, code
        return 1

    def TerminateJobObject(self, job: int, code: int) -> int:  # noqa: N802
        if self._gate("TerminateJobObject", job):
            return 0
        assert job == self.handles["job"]
        if self.in_job:
            self.alive, self.exit = False, code
        self.extra_active, self.extra_members = 0, ()
        return 1

    def WaitForSingleObject(self, process: int, milliseconds: int) -> int:  # noqa: N802
        spec = self._gate("WaitForSingleObject", process)
        assert process == self.handles["process"]
        self.waits.append(milliseconds)
        if spec and spec[0] == "value":
            return int(spec[1])
        return 0 if not self.alive else 0x102

    def GetExitCodeProcess(self, process: int, code: Any) -> int:  # noqa: N802
        if self._gate("GetExitCodeProcess", process):
            return 0
        assert process == self.handles["process"]
        code._obj.value = self.exit
        return 1

    def _eof(self) -> bool:
        writer = self.handles.get("stdout_write")
        return not self.pipe and not self.alive and writer in self.closed

    def PeekNamedPipe(self, handle: int, *args: Any) -> int:  # noqa: N802
        if self._gate("PeekNamedPipe", handle):
            return 0
        buffer, size, read, available, left = args
        assert handle == self.handles["stdout_read"]
        assert buffer is None and size == 0 and read is None and left is None
        if not self.pipe and self._eof():
            self.last = 109
            return 0
        available._obj.value = len(self.pipe)
        return 1

    def ReadFile(self, *args: Any) -> int:  # noqa: N802
        handle, buffer, size, got, overlapped = args
        if self._gate("ReadFile", handle):
            return 0
        assert handle == self.handles["stdout_read"]
        assert overlapped is None and ctypes.sizeof(buffer) == size
        self.reads.append(size)
        data = bytes(self.pipe[:size])
        del self.pipe[:size]
        ctypes.memmove(buffer, data, len(data))
        got._obj.value = len(data) if self.read_override is None else self.read_override
        return 1

    def CloseHandle(self, handle: int) -> int:  # noqa: N802
        if self._gate("CloseHandle", handle):
            return 0
        if handle in self.closed:
            self.double_closed.append(handle)
        self.closed.append(handle)
        return 1


def runtime(**changes: Any) -> Any:
    flags = {"isolated": 1, "dont_write_bytecode": 1, "optimize": 0}
    base = {"platform": "win32", "version_info": (3, 11, 3), "maxsize": (1 << 63) - 1}
    for key, value in changes.items():
        if key in flags:
            flags[key] = value
        else:
            base[key] = value
    return SimpleNamespace(flags=SimpleNamespace(**flags), **base)


@pytest.fixture
def lab(monkeypatch: Any) -> Any:
    module = runpy.run_path(str(MODULE))
    namespace = module["Owner"].setup.__globals__
    kernel = Kernel()
    loads: list[int] = []

    def load() -> Any:
        loads.append(1)
        return module["_Api"](kernel, lambda: kernel.last)

    monkeypatch.setitem(namespace, "_load_api", load)
    monkeypatch.setitem(namespace, "sys", runtime())

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("real DLL load attempted")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden)
    request = module["Request"](
        "C:\\launcher\\python.exe",
        '"C:\\launcher\\python.exe" -I -B -c "print(1)"',
        (("SystemRoot", "C:\\Windows"), ("TEMP", "C:\\Temp")),
        "C:\\work",
    )
    return SimpleNamespace(
        module=module,
        namespace=namespace,
        kernel=kernel,
        loads=loads,
        request=request,
        owner=module["Owner"](request),
        monkeypatch=monkeypatch,
    )


def raises(lab: Any, code: str, function: Any, *args: Any) -> Any:
    with pytest.raises(lab.module["Win32Error"]) as caught:
        function(*args)
    assert caught.value.args == (code,)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert "secret" not in str(caught.value)
    return caught


def running(lab: Any) -> Any:
    lab.owner.setup()
    lab.owner.start()
    assert lab.owner.state == "RUNNING"
    return lab.owner


def finish(lab: Any) -> None:
    lab.kernel.alive = False


def test_import_and_construction_have_no_native_effect(monkeypatch: Any) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("native load")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden)
    module = runpy.run_path(str(MODULE))
    owner = module["Owner"](object())
    assert owner.state == "NEW" and owner.ledger == {} and owner._api is None


def test_source_has_no_consumer_or_process_surface() -> None:
    tree = ast.parse(MODULE.read_bytes())
    # Modules only: ImportFrom names (dataclass, wintypes) are symbols, not modules.
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported |= {
        str(node.module).split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported <= {"ctypes", "dataclasses", "ntpath", "sys"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not names & {"Thread", "Popen", "system", "OpenProcess", "maskgw"}
    assert not any(
        isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "__name__"
        for node in ast.walk(tree)
    )


def test_supported_abi_sizes_and_offsets(lab: Any) -> None:
    m = lab.module
    sizes = {kind.__name__: ctypes.sizeof(kind) for kind in m["ABI_SIZES"]}
    assert sizes == {
        "SecurityAttributes": 24,
        "StartupInfo": 104,
        "StartupInfoEx": 112,
        "ProcessInformation": 24,
        "BasicLimit": 64,
        "ExtendedLimit": 144,
        "Accounting": 48,
        "ProcessIdList": 24,
    }
    assert all(field.offset == offset for field, offset in m["ABI_OFFSETS"])
    assert m["CREATE_FLAGS"] == 0x00080000 | 0x00000004 | 0x08000000 | 0x00000400
    assert m["LIMIT_FLAGS"] == 0x2008 and m["ACTIVE_PROCESS_LIMIT"] == 2
    assert m["PROC_THREAD_ATTRIBUTE_JOB_LIST"] == 0x2000D
    assert m["PROC_THREAD_ATTRIBUTE_HANDLE_LIST"] == 0x20002


@pytest.mark.parametrize(
    "changes",
    [
        {"platform": "linux"},
        {"version_info": (3, 11, 4)},
        {"maxsize": (1 << 31) - 1},
        {"isolated": 0},
        {"dont_write_bytecode": 0},
        {"optimize": 1},
    ],
)
def test_runtime_refused_before_dll_load(lab: Any, changes: dict[str, Any]) -> None:
    lab.monkeypatch.setitem(lab.namespace, "sys", runtime(**changes))
    raises(lab, "WIN32_RUNTIME", lab.owner.setup)
    assert not lab.loads and lab.owner.state == "SETUP_FAILED" and not lab.kernel.calls


def test_abi_mismatch_refused_before_dll_load(lab: Any) -> None:
    sizes = dict(lab.module["ABI_SIZES"])
    sizes[lab.module["StartupInfoEx"]] = 111
    lab.monkeypatch.setitem(lab.namespace, "ABI_SIZES", sizes)
    raises(lab, "WIN32_RUNTIME", lab.owner.setup)
    assert not lab.loads


def requests(module: Any) -> list[Any]:
    request = module["Request"]
    env = (("SystemRoot", "C:\\Windows"),)
    return [
        object(),
        request("python.exe", "x", env, "C:\\w"),
        request("\\python.exe", "x", env, "C:\\w"),
        request("C:\\p.exe", "", env, "C:\\w"),
        request("C:\\p.exe", "x" * 2049, env, "C:\\w"),
        request("C:\\p.exe", "x\0", env, "C:\\w"),
        request("C:\\p.exe", "x", (), "C:\\w"),
        request("C:\\p.exe", "x", [("A", "b")], "C:\\w"),
        request("C:\\p.exe", "x", (("A=B", "b"),), "C:\\w"),
        request("C:\\p.exe", "x", (("A", "b"), ("a", "c")), "C:\\w"),
        request("C:\\p.exe", "x", (("A", "b"),) * 17, "C:\\w"),
        request("C:\\p.exe", "x", env, "relative"),
    ]


@pytest.mark.parametrize("index", range(12))
def test_invalid_request_refused_before_dll_load(lab: Any, index: int) -> None:
    owner = lab.module["Owner"](requests(lab.module)[index])
    raises(lab, "WIN32_REQUEST", owner.setup)
    assert not lab.loads and owner.ledger == {}


def test_happy_path_order_flags_inheritance_and_lifetimes(lab: Any) -> None:
    owner = running(lab)
    k = lab.kernel
    assert k.calls == [
        "CreateJobObjectW",
        "SetInformationJobObject",
        "QueryInformationJobObject",
        "CreateFileW",
        "CreateFileW",
        "CreatePipe",
        "SetHandleInformation",
        *["GetHandleInformation"] * 5,
        "InitializeProcThreadAttributeList",
        "InitializeProcThreadAttributeList",
        "UpdateProcThreadAttribute",
        "UpdateProcThreadAttribute",
        "CreateProcessW",
        "DeleteProcThreadAttributeList",
        "CloseHandle",
        "CloseHandle",
        "CloseHandle",
        "IsProcessInJob",
        "QueryInformationJobObject",
        "QueryInformationJobObject",
        "QueryInformationJobObject",
        "ResumeThread",
    ]
    h = k.handles
    assert k.limit == (0x2008, 2)
    assert k.inherit[h["job"]] == 0 and k.inherit[h["stdout_read"]] == 0
    assert k.inherit[h["stdin"]] == k.inherit[h["stderr"]] == k.inherit[h["stdout_write"]] == 1
    assert k.updates == [
        (0x2000D, [h["job"]], 8),
        (0x20002, [h["stdin"], h["stdout_write"], h["stderr"]], 24),
    ]
    created = k.created
    assert created["attributes_ok"] is True and not k.attr_live
    assert created["flags"] == lab.module["CREATE_FLAGS"] and created["inherit"] == 1
    assert created["cb"] == 112 and created["startf"] == 0x100
    assert created["stdio"] == (h["stdin"], h["stdout_write"], h["stderr"])
    assert created["security"] == (None, None)
    # Double-NUL block plus the buffer terminator added by create_unicode_buffer.
    assert created["environment"] == "SystemRoot=C:\\Windows\0TEMP=C:\\Temp\0\0\0"
    assert created["app"] == lab.request.application
    assert created["command"] == lab.request.command_line
    assert k.closed == [h["stdin"], h["stderr"], h["stdout_write"]]
    assert set(owner.ledger) == {"job", "stdout_read", "process", "thread"}
    assert owner.pid == PID and not k.suspended


@pytest.mark.parametrize(
    ("name", "spec", "code"),
    [
        ("CreateJobObjectW", ("false", 5), "WIN32_JOB"),
        ("SetInformationJobObject", ("false", 5), "WIN32_CONFIG"),
        ("QueryInformationJobObject", ("false", 5), "WIN32_CONFIG"),
        ("CreateFileW", ("false", 5), "WIN32_STDIO"),
        ("CreatePipe", ("false", 5), "WIN32_PIPE"),
        ("SetHandleInformation", ("false", 5), "WIN32_PIPE"),
        ("GetHandleInformation", ("false", 5), "WIN32_INHERIT"),
        ("GetHandleInformation", ("flip", 0), "WIN32_INHERIT"),
    ],
)
def test_clean_setup_failure_keeps_ledger_and_closes_once(
    lab: Any, name: str, spec: Any, code: str
) -> None:
    lab.kernel.plan[name] = spec
    raises(lab, code, lab.owner.setup)
    assert lab.owner.state == "SETUP_FAILED"
    owned = set(lab.owner.ledger.values())
    assert owned <= set(lab.kernel.handles.values()) and not lab.kernel.closed
    lab.owner.close()
    assert sorted(lab.kernel.closed) == sorted(owned) and not lab.kernel.double_closed
    assert lab.owner.state == "CLOSED" and lab.owner.ledger == {}


def test_config_mismatch_refused(lab: Any) -> None:
    lab.kernel.limit_override = (0x2008 | 0x800, 2)
    raises(lab, "WIN32_CONFIG", lab.owner.setup)


@pytest.mark.parametrize(
    ("name", "spec"),
    [
        ("CreateJobObjectW", "raise"),
        ("CreateFileW", "raise"),
        ("CreatePipe", ("half", 0)),
    ],
)
def test_uncertain_creation_is_held_with_partial_ledger(lab: Any, name: str, spec: Any) -> None:
    lab.kernel.plan[name] = spec
    raises(lab, "WIN32_HELD", lab.owner.setup)
    assert lab.owner.state == "HELD"
    if name == "CreatePipe":
        # Outputs of a call that raised are quarantined, never owned/actionable.
        assert not {"stdout_read", "stdout_write"} & set(lab.owner.ledger)
        assert lab.owner.quarantine == [
            lab.kernel.handles["stdout_read"],
            lab.kernel.handles["stdout_write"],
        ]
    raises(lab, "WIN32_HELD", lab.owner.close)
    assert not lab.kernel.closed


@pytest.mark.parametrize(
    ("name", "spec"),
    [
        (("InitializeProcThreadAttributeList", 1), ("false", 5)),
        (("InitializeProcThreadAttributeList", 2), ("false", 5)),
        (("UpdateProcThreadAttribute", 1), ("false", 5)),
        (("UpdateProcThreadAttribute", 2), ("false", 5)),
        ("CreateProcessW", ("false", 2)),
    ],
)
def test_launch_failure_without_child_is_closable(lab: Any, name: Any, spec: Any) -> None:
    lab.owner.setup()
    lab.kernel.plan[name] = spec
    raises(lab, "WIN32_ATTRIBUTE" if "Attr" in str(name) else "WIN32_CREATE", lab.owner.start)
    assert lab.owner.state == "LAUNCH_FAILED" and "process" not in lab.owner.ledger
    assert "CreateProcessW" not in lab.kernel.calls or name == "CreateProcessW"
    assert not lab.kernel.attr_live
    lab.owner.close()
    assert lab.owner.state == "CLOSED" and not lab.kernel.double_closed


def test_lost_child_handle_is_held(lab: Any) -> None:
    lab.owner.setup()
    lab.kernel.plan["CreateProcessW"] = ("lost", 0)
    raises(lab, "WIN32_HELD", lab.owner.start)
    assert lab.owner.held_reason == "WIN32_CREATE"


def test_create_false_never_touches_indeterminate_outputs(lab: Any) -> None:
    # Reviewer P1-B: FALSE with non-owned PROCESS_INFORMATION values.
    lab.owner.setup()
    lab.kernel.plan["CreateProcessW"] = ("false-out", FOREIGN)
    raises(lab, "WIN32_CREATE", lab.owner.start)
    k = lab.kernel
    assert not set(FOREIGN) & set(k.touched)
    assert "TerminateProcess" not in k.calls and "TerminateJobObject" not in k.calls
    assert lab.owner.state == "LAUNCH_FAILED" and lab.owner.quarantine == list(FOREIGN)
    assert not {"process", "thread"} & set(lab.owner.ledger) and lab.owner.pid is None
    lab.owner.close()
    assert lab.owner.state == "CLOSED" and not set(FOREIGN) & set(k.touched)


def test_create_raise_after_filling_uses_owned_job_and_holds(lab: Any) -> None:
    lab.owner.setup()
    lab.kernel.plan["CreateProcessW"] = ("filled-raise", 0)
    raises(lab, "WIN32_HELD", lab.owner.start)
    k = lab.kernel
    assert lab.owner.held_reason == "WIN32_CREATE" and not k.alive
    assert "TerminateJobObject" in k.calls and "TerminateProcess" not in k.calls
    assert k.handles["process"] not in k.touched
    assert not {"process", "thread"} & set(lab.owner.ledger)
    assert lab.owner.quarantine == [k.handles["process"], k.handles["thread"]]


def test_create_success_aliasing_owned_handle_is_held(lab: Any) -> None:
    lab.owner.setup()
    lab.kernel.plan["CreateProcessW"] = ("alias", "stdout_read")
    raises(lab, "WIN32_HELD", lab.owner.start)
    assert lab.owner.held_reason == "WIN32_CREATE" and not lab.kernel.alive
    assert "process" not in lab.owner.ledger and "TerminateProcess" not in lab.kernel.calls


def test_create_false_with_job_member_is_held(lab: Any) -> None:
    lab.owner.setup()
    lab.kernel.plan["CreateProcessW"] = ("false-out", FOREIGN)
    lab.kernel.extra_members = (7,)
    raises(lab, "WIN32_HELD", lab.owner.start)
    assert "TerminateJobObject" in lab.kernel.calls
    assert not set(FOREIGN) & set(lab.kernel.touched)


def test_unassigned_child_is_terminated_by_handle_never_job(lab: Any) -> None:
    lab.owner.setup()
    lab.kernel.in_job = False
    raises(lab, "WIN32_MEMBERSHIP", lab.owner.start)
    calls = lab.kernel.calls
    assert "TerminateProcess" in calls and "TerminateJobObject" not in calls
    assert "ResumeThread" not in calls and lab.kernel.waits == [5000]
    lab.owner.close()
    assert lab.owner.state == "CLOSED" and not lab.kernel.double_closed


@pytest.mark.parametrize(
    ("setup", "code"),
    [
        ("config", "WIN32_CONFIG"),
        ("active", "WIN32_TREE"),
        ("member", "WIN32_TREE"),
        ("resume0", "WIN32_RESUME"),
        ("resume2", "WIN32_RESUME"),
        ("resume-fail", "WIN32_RESUME"),
        ("resume-raise", "WIN32_RESUME"),
    ],
)
def test_verification_failure_terminates_member_job(lab: Any, setup: str, code: str) -> None:
    lab.owner.setup()
    k = lab.kernel
    if setup == "config":
        k.plan[("QueryInformationJobObject", 2)] = ("false", 5)
    elif setup == "active":
        k.extra_active = 1
    elif setup == "member":
        k.extra_members = (7,)
    elif setup == "resume-raise":
        k.plan["ResumeThread"] = "raise"
    else:
        value = {"resume0": 0, "resume2": 2, "resume-fail": 0xFFFFFFFF}[setup]
        k.plan["ResumeThread"] = ("value", value)
    raises(lab, code, lab.owner.start)
    assert "TerminateJobObject" in k.calls and "TerminateProcess" not in k.calls
    assert lab.owner.state == "LAUNCH_FAILED"


@pytest.mark.parametrize(
    ("name", "spec", "reason"),
    [
        ("TerminateProcess", ("false", 5), "WIN32_TERMINATE"),
        ("WaitForSingleObject", ("value", 0x102), "WIN32_WAIT"),
        ("WaitForSingleObject", ("value", 0xFFFFFFFF), "WIN32_WAIT"),
    ],
)
def test_unproven_abort_is_held_and_never_released(
    lab: Any, name: str, spec: Any, reason: str
) -> None:
    lab.owner.setup()
    lab.kernel.in_job = False
    lab.kernel.plan[name] = spec
    raises(lab, "WIN32_HELD", lab.owner.start)
    assert lab.owner.state == "HELD" and lab.owner.held_reason == reason
    before = dict(lab.owner.ledger)
    for call in (lab.owner.close, lab.owner.terminate, lab.owner.read):
        raises(lab, "WIN32_HELD", call)
    assert lab.owner.ledger == before and "process" in before


def test_job_abort_needs_zero_active(lab: Any) -> None:
    lab.owner.setup()
    lab.kernel.extra_members = (7,)
    lab.kernel.plan[("QueryInformationJobObject", 5)] = ("false", 5)
    raises(lab, "WIN32_HELD", lab.owner.start)
    assert lab.owner.held_reason == "WIN32_ACCOUNTING"


def test_child_copy_close_failure_aborts_and_holds(lab: Any) -> None:
    lab.owner.setup()
    lab.kernel.plan[("CloseHandle", 2)] = ("false", 6)
    raises(lab, "WIN32_HELD", lab.owner.start)
    assert lab.owner.held_reason == "WIN32_CLOSE"
    assert "TerminateProcess" in lab.kernel.calls and "stderr" in lab.owner.ledger


def test_attribute_delete_failure_aborts_and_holds(lab: Any) -> None:
    lab.owner.setup()
    lab.kernel.plan["DeleteProcThreadAttributeList"] = "raise"
    raises(lab, "WIN32_HELD", lab.owner.start)
    assert lab.owner.held_reason == "WIN32_ATTRIBUTE"
    # The undeleted list stays recorded; it is never claimed to be gone.
    assert lab.owner._attributes is not None


# -- regressions from the independent review (red before the fix) -------------


def test_p1a_pipe_false_outputs_are_never_adopted(lab: Any) -> None:
    lab.kernel.plan["CreatePipe"] = ("false-out", FOREIGN)
    raises(lab, "WIN32_PIPE", lab.owner.setup)
    owner = lab.owner
    assert not {"stdout_read", "stdout_write"} & set(owner.ledger)
    assert owner.quarantine == list(FOREIGN) and owner.state == "SETUP_FAILED"
    owner.close()
    assert owner.state == "CLOSED" and not set(FOREIGN) & set(lab.kernel.touched)


def test_pipe_success_aliasing_owned_handle_is_held(lab: Any) -> None:
    lab.kernel.plan["CreatePipe"] = ("alias", "job")
    raises(lab, "WIN32_HELD", lab.owner.setup)
    assert lab.owner.held_reason == "WIN32_PIPE"
    assert lab.owner.ledger["job"] == lab.kernel.handles["job"]
    assert not {"stdout_read", "stdout_write"} & set(lab.owner.ledger)


def test_file_success_aliasing_owned_handle_is_held(lab: Any) -> None:
    lab.kernel.plan["CreateFileW"] = ("alias", "job")
    raises(lab, "WIN32_HELD", lab.owner.setup)
    assert lab.owner.held_reason == "WIN32_STDIO" and "stdin" not in lab.owner.ledger


def test_p2c_interrupt_after_real_creation_contains_and_holds(lab: Any) -> None:
    lab.owner.setup()
    lab.kernel.plan["CreateProcessW"] = ("interrupt", 0)
    with pytest.raises(KeyboardInterrupt):
        lab.owner.start()
    owner, k = lab.owner, lab.kernel
    assert owner.state == "HELD" and owner.held_reason == "WIN32_INTERRUPTED"
    assert owner.quarantine == [k.handles["process"], k.handles["thread"]]
    assert "TerminateJobObject" in k.calls and not k.alive
    assert "process" not in owner.ledger and k.handles["process"] not in k.touched
    raises(lab, "WIN32_HELD", owner.close)


@pytest.mark.parametrize(
    ("name", "spec"), [("CreateFileW", "interrupt-now"), ("CreatePipe", ("interrupt", 0))]
)
def test_interrupt_during_setup_is_held_with_known_resources(
    lab: Any, name: str, spec: Any
) -> None:
    lab.kernel.plan[name] = spec
    with pytest.raises(KeyboardInterrupt):
        lab.owner.setup()
    owner = lab.owner
    assert owner.state == "HELD" and owner.held_reason == "WIN32_INTERRUPTED"
    assert owner.ledger["job"] == lab.kernel.handles["job"]
    assert "TerminateJobObject" not in lab.kernel.calls
    if name == "CreatePipe":
        assert owner.quarantine == [
            lab.kernel.handles["stdout_read"],
            lab.kernel.handles["stdout_write"],
        ]
        assert "stdout_read" not in owner.ledger


def test_p2d_allocation_failure_after_attribute_init_is_closed(lab: Any) -> None:
    lab.owner.setup()

    def exhausted(*_args: Any) -> Any:
        raise MemoryError

    lab.monkeypatch.setattr(ctypes, "create_unicode_buffer", exhausted)
    caught = raises(lab, "WIN32_HELD", lab.owner.start)
    assert type(caught.value) is lab.module["Win32Error"]
    assert lab.owner.held_reason == "WIN32_INTERNAL" and lab.owner.state == "HELD"
    assert not lab.kernel.attr_live and lab.owner._attributes is None
    assert "CreateProcessW" not in lab.kernel.calls


def test_allocation_failure_during_setup_is_closed(lab: Any) -> None:
    def exhausted(*_args: Any) -> Any:
        raise MemoryError

    lab.monkeypatch.setitem(lab.namespace, "SecurityAttributes", exhausted)
    raises(lab, "WIN32_HELD", lab.owner.setup)
    assert lab.owner.held_reason == "WIN32_INTERNAL" and "job" in lab.owner.ledger


@pytest.mark.parametrize("length", [0, 1, 7])
def test_p2e_short_membership_frame_is_not_empty_membership(lab: Any, length: int) -> None:
    owner = running(lab)
    finish(lab)
    lab.kernel.plan["QueryInformationJobObject"] = ("short-frame", length)
    raises(lab, "WIN32_HELD", owner.members)
    assert owner.held_reason == "WIN32_ACCOUNTING"


def test_p2e_short_frame_never_releases_on_close(lab: Any) -> None:
    owner = running(lab)
    finish(lab)
    # Queries: setup 1, start 2-4, close accounting 5, close membership 6.
    lab.kernel.plan[("QueryInformationJobObject", 6)] = ("short-frame", 1)
    raises(lab, "WIN32_HELD", owner.close)
    assert owner.state == "HELD" and "job" in owner.ledger


def test_membership_frame_shorter_than_its_list_is_refused(lab: Any) -> None:
    owner = running(lab)
    lab.kernel.plan["QueryInformationJobObject"] = ("short-list", 0)
    raises(lab, "WIN32_HELD", owner.members)


def test_hostile_foreign_exception_is_never_inspected(lab: Any) -> None:
    lab.kernel.plan["CreatePipe"] = "hostile"
    caught = raises(lab, "WIN32_HELD", lab.owner.setup)
    assert lab.owner.held_reason == "WIN32_PIPE" and caught.value.args == ("WIN32_HELD",)


def test_false_return_aliasing_owned_handles_is_not_adopted(lab: Any) -> None:
    lab.owner.setup()
    h = lab.kernel.handles
    lab.kernel.plan["CreateProcessW"] = ("false-out", (h["job"], h["stdout_read"]))
    raises(lab, "WIN32_CREATE", lab.owner.start)
    assert lab.owner.ledger["job"] == h["job"] and "process" not in lab.owner.ledger
    assert "TerminateProcess" not in lab.kernel.calls
    lab.owner.close()
    assert not lab.kernel.double_closed


def test_bounded_reads_and_eof_distinct_from_tree(lab: Any) -> None:
    owner = running(lab)
    k = lab.kernel
    assert owner.read() == b"" and "ReadFile" not in k.calls
    k.pipe.extend(b"x" * 10000)
    assert owner.available() == 10000
    assert owner.read() == b"x" * 4096 and k.reads == [4096]
    assert owner.read() == b"x" * 4096 and owner.read() == b"x" * 1808
    assert k.reads == [4096, 4096, 1808]
    assert owner.wait(0) is False and observed(owner, "eof") is False
    finish(lab)
    assert owner.wait(50) is True and owner.accounting() == (1, 0) and owner.members() == ()
    assert owner.available() is None
    assert observed(owner, "eof") is True and owner.read() == b""
    assert owner.exit_code() == 0


def test_eof_alone_does_not_mean_tree_finished(lab: Any) -> None:
    owner = running(lab)
    lab.kernel.extra_active = 1
    finish(lab)
    assert owner.available() is None and owner.eof
    assert owner.accounting() == (1, 1)
    raises(lab, "WIN32_NOT_QUIESCENT", owner.close)
    assert owner.state == "RUNNING"


def test_exit_code_requires_signal(lab: Any) -> None:
    owner = running(lab)
    raises(lab, "WIN32_STATE", owner.exit_code)


@pytest.mark.parametrize("value", [-1, 51, True, 1.0])
def test_wait_bound(lab: Any, value: Any) -> None:
    owner = running(lab)
    raises(lab, "WIN32_REQUEST", owner.wait, value)


@pytest.mark.parametrize(
    ("call", "plan", "reason"),
    [
        ("wait", ("WaitForSingleObject", ("value", 0x80)), "WIN32_WAIT"),
        ("wait", ("WaitForSingleObject", "raise"), "WIN32_WAIT"),
        ("available", ("PeekNamedPipe", ("false", 5)), "WIN32_PIPE"),
        ("accounting", ("QueryInformationJobObject", ("false", 5)), "WIN32_ACCOUNTING"),
        ("members", ("QueryInformationJobObject", ("false", 5)), "WIN32_ACCOUNTING"),
        ("check_config", ("QueryInformationJobObject", ("false", 5)), "WIN32_CONFIG"),
        ("terminate", ("TerminateJobObject", ("false", 5)), "WIN32_TERMINATE"),
    ],
)
def test_supervision_failures_hold(lab: Any, call: str, plan: Any, reason: str) -> None:
    owner = running(lab)
    lab.kernel.plan[plan[0]] = plan[1]
    args = (0,) if call == "wait" else ()
    raises(lab, "WIN32_HELD", getattr(owner, call), *args)
    assert owner.state == "HELD" and owner.held_reason == reason


def test_exit_code_failure_holds(lab: Any) -> None:
    owner = running(lab)
    finish(lab)
    owner.wait(0)
    lab.kernel.plan["GetExitCodeProcess"] = ("false", 5)
    raises(lab, "WIN32_HELD", owner.exit_code)


@pytest.mark.parametrize("override", [0, 4097])
def test_malformed_read_count_holds(lab: Any, override: int) -> None:
    owner = running(lab)
    lab.kernel.pipe.extend(b"abc")
    lab.kernel.read_override = override
    raises(lab, "WIN32_HELD", owner.read)


def test_read_failure_other_than_broken_pipe_holds(lab: Any) -> None:
    owner = running(lab)
    lab.kernel.pipe.extend(b"abc")
    lab.kernel.plan["ReadFile"] = ("false", 5)
    raises(lab, "WIN32_HELD", owner.read)


def test_read_broken_pipe_is_eof(lab: Any) -> None:
    owner = running(lab)
    lab.kernel.pipe.extend(b"abc")
    lab.kernel.plan["ReadFile"] = ("false", 109)
    assert owner.read() == b"" and owner.eof


@pytest.mark.parametrize("change", ["total", "active", "too-many", "length"])
def test_accounting_and_members_bounds(lab: Any, change: str) -> None:
    owner = running(lab)
    k = lab.kernel
    if change == "total":
        k.total = 3
        raises(lab, "WIN32_TREE", owner.accounting)
    elif change == "active":
        k.extra_active = 1
        raises(lab, "WIN32_TREE", owner.accounting)
    elif change == "too-many":
        k.extra_members = (7, 8)
        raises(lab, "WIN32_TREE", owner.members)
    else:
        k.lengths[1] = 40
        raises(lab, "WIN32_HELD", owner.accounting)


def test_running_config_mismatch_is_refused(lab: Any) -> None:
    owner = running(lab)
    lab.kernel.limit_override = (0x2008, 3)
    raises(lab, "WIN32_CONFIG", owner.check_config)
    assert owner.state == "RUNNING"


def test_terminate_then_quiescent_close_order_once(lab: Any) -> None:
    owner = running(lab)
    owner.terminate()
    assert owner.terminated and not lab.kernel.alive
    h = lab.kernel.handles
    owner.close()
    assert lab.kernel.closed[3:] == [h["thread"], h["process"], h["stdout_read"], h["job"]]
    assert not lab.kernel.double_closed and owner.state == "CLOSED" and owner.ledger == {}
    raises(lab, "WIN32_STATE", owner.close)


@pytest.mark.parametrize("missing", ["signal", "eof", "members"])
def test_close_refused_without_quiescence(lab: Any, missing: str) -> None:
    owner = running(lab)
    if missing != "signal":
        finish(lab)
    if missing == "eof":
        lab.kernel.pipe.extend(b"tail")
    if missing == "members":
        lab.kernel.extra_members = (7,)
    raises(lab, "WIN32_NOT_QUIESCENT", owner.close)
    assert owner.state == "RUNNING" and "job" in owner.ledger


def test_close_failure_holds_and_keeps_remaining_ledger(lab: Any) -> None:
    owner = running(lab)
    finish(lab)
    lab.kernel.plan[("CloseHandle", 5)] = ("false", 6)
    raises(lab, "WIN32_HELD", owner.close)
    assert owner.held_reason == "WIN32_CLOSE"
    assert set(owner.ledger) == {"process", "stdout_read", "job"}
    raises(lab, "WIN32_HELD", owner.close)
    assert not lab.kernel.double_closed


def test_state_machine(lab: Any) -> None:
    raises(lab, "WIN32_STATE", lab.owner.start)
    raises(lab, "WIN32_STATE", lab.owner.read)
    lab.owner.setup()
    raises(lab, "WIN32_STATE", lab.owner.setup)
    raises(lab, "WIN32_STATE", lab.owner.wait, 0)


def test_load_failure_is_closed_and_sanitized(lab: Any) -> None:
    def broken() -> Any:
        raise OSError("secret-detail")

    lab.monkeypatch.setitem(lab.namespace, "_load_api", broken)
    raises(lab, "WIN32_LOAD", lab.owner.setup)
    assert lab.owner.state == "SETUP_FAILED" and lab.owner.ledger == {}
