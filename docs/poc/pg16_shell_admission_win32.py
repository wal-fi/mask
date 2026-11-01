"""Private Win32 job/process backend for the future PG16 admission caller.

No consumer, no CLI and no __main__. Import and Owner construction never load
a DLL nor create a handle; the kernel32 binding is created lazily inside
setup() only after a strict Windows x64 / CPython 3.11.3 -I -B optimize-0
runtime guard and an ABI size/offset check. The owner records every native
handle in its ledger immediately after the call that produced it, so it stays
reachable across every partial failure. Uncertain resources make the owner
HELD: nothing is released, nothing is declared closed. Handle retention only
lasts while the owning process lives; there is no universal OS time bound.
"""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import ntpath
import sys

DWORD, WORD, BOOL = wintypes.DWORD, wintypes.WORD, wintypes.BOOL
HANDLE, LPWSTR = wintypes.HANDLE, wintypes.LPWSTR
POINTER = ctypes.c_void_p
INVALID = (1 << 64) - 1

ACTIVE_PROCESS_LIMIT = 2
JOB_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_LIMIT_BREAKAWAY_OK = 0x00000800
JOB_LIMIT_SILENT_BREAKAWAY_OK = 0x00001000
JOB_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
LIMIT_FLAGS = JOB_LIMIT_ACTIVE_PROCESS | JOB_LIMIT_KILL_ON_JOB_CLOSE
JOB_BASIC_ACCOUNTING = 1
JOB_BASIC_PROCESS_ID_LIST = 3
JOB_EXTENDED_LIMIT = 9
PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
PROC_THREAD_ATTRIBUTE_JOB_LIST = 0x0002000D
CREATE_SUSPENDED = 0x00000004
CREATE_UNICODE_ENVIRONMENT = 0x00000400
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_NO_WINDOW = 0x08000000
CREATE_FLAGS = (
    CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT | CREATE_NO_WINDOW
)
STARTF_USESTDHANDLES = 0x00000100
HANDLE_FLAG_INHERIT = 0x00000001
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ_WRITE = 0x00000003
OPEN_EXISTING = 3
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
ERROR_BROKEN_PIPE = 109
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_MORE_DATA = 234
MAX_WAIT_MS = 50
ABORT_WAIT_MS = 5000
ABORT_EXIT_CODE = 97
TERMINATE_EXIT_CODE = 1
MAX_READ = 4096
MAX_ATTRIBUTE_BYTES = 4096
MAX_PATH_CHARS = 1024
MAX_COMMAND_CHARS = 2048
MAX_ENVIRONMENT = 16
MAX_ENVIRONMENT_CHARS = 32767
CODES = frozenset(
    (
        "WIN32_STATE",
        "WIN32_REQUEST",
        "WIN32_RUNTIME",
        "WIN32_LOAD",
        "WIN32_JOB",
        "WIN32_CONFIG",
        "WIN32_STDIO",
        "WIN32_PIPE",
        "WIN32_INHERIT",
        "WIN32_ATTRIBUTE",
        "WIN32_CREATE",
        "WIN32_MEMBERSHIP",
        "WIN32_TREE",
        "WIN32_RESUME",
        "WIN32_WAIT",
        "WIN32_EXIT",
        "WIN32_ACCOUNTING",
        "WIN32_TERMINATE",
        "WIN32_CLOSE",
        "WIN32_NOT_QUIESCENT",
        "WIN32_INTERNAL",
        "WIN32_INTERRUPTED",
        "WIN32_HELD",
    )
)


class Win32Error(Exception):
    def __init__(self, code):
        super().__init__(code if type(code) is str and code in CODES else "WIN32_STATE")


class SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", DWORD),
        ("lpSecurityDescriptor", POINTER),
        ("bInheritHandle", BOOL),
    ]


class StartupInfo(ctypes.Structure):
    _fields_ = [
        ("cb", DWORD),
        ("lpReserved", LPWSTR),
        ("lpDesktop", LPWSTR),
        ("lpTitle", LPWSTR),
        ("dwX", DWORD),
        ("dwY", DWORD),
        ("dwXSize", DWORD),
        ("dwYSize", DWORD),
        ("dwXCountChars", DWORD),
        ("dwYCountChars", DWORD),
        ("dwFillAttribute", DWORD),
        ("dwFlags", DWORD),
        ("wShowWindow", WORD),
        ("cbReserved2", WORD),
        ("lpReserved2", POINTER),
        ("hStdInput", HANDLE),
        ("hStdOutput", HANDLE),
        ("hStdError", HANDLE),
    ]


class StartupInfoEx(ctypes.Structure):
    _fields_ = [("StartupInfo", StartupInfo), ("lpAttributeList", POINTER)]


class ProcessInformation(ctypes.Structure):
    _fields_ = [
        ("hProcess", HANDLE),
        ("hThread", HANDLE),
        ("dwProcessId", DWORD),
        ("dwThreadId", DWORD),
    ]


class BasicLimit(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", DWORD),
        ("SchedulingClass", DWORD),
    ]


class IoCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint64)
        for name in (
            "ReadOperationCount",
            "WriteOperationCount",
            "OtherOperationCount",
            "ReadTransferCount",
            "WriteTransferCount",
            "OtherTransferCount",
        )
    ]


class ExtendedLimit(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", BasicLimit),
        ("IoInfo", IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class Accounting(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_int64),
        ("TotalKernelTime", ctypes.c_int64),
        ("ThisPeriodTotalUserTime", ctypes.c_int64),
        ("ThisPeriodTotalKernelTime", ctypes.c_int64),
        ("TotalPageFaultCount", DWORD),
        ("TotalProcesses", DWORD),
        ("ActiveProcesses", DWORD),
        ("TotalTerminatedProcesses", DWORD),
    ]


class ProcessIdList(ctypes.Structure):
    _fields_ = [
        ("NumberOfAssignedProcesses", DWORD),
        ("NumberOfProcessIdsInList", DWORD),
        ("ProcessIdList", ctypes.c_size_t * ACTIVE_PROCESS_LIMIT),
    ]


# Supported ABI: Windows x64 only. Checked before the DLL is loaded.
ABI_SIZES = {
    SecurityAttributes: 24,
    StartupInfo: 104,
    StartupInfoEx: 112,
    ProcessInformation: 24,
    BasicLimit: 64,
    ExtendedLimit: 144,
    Accounting: 48,
    ProcessIdList: 24,
}
ABI_OFFSETS = (
    (SecurityAttributes.bInheritHandle, 16),
    (StartupInfo.dwFlags, 60),
    (StartupInfo.hStdInput, 80),
    (StartupInfo.hStdOutput, 88),
    (StartupInfo.hStdError, 96),
    (StartupInfoEx.lpAttributeList, 104),
    (ProcessInformation.dwProcessId, 16),
    (BasicLimit.LimitFlags, 16),
    (BasicLimit.ActiveProcessLimit, 40),
    (ExtendedLimit.IoInfo, 64),
    (ExtendedLimit.ProcessMemoryLimit, 112),
    (Accounting.TotalProcesses, 36),
    (Accounting.ActiveProcesses, 40),
    (ProcessIdList.ProcessIdList, 8),
)
SIGNATURES = (
    ("CreateJobObjectW", (POINTER, wintypes.LPCWSTR), HANDLE),
    ("SetInformationJobObject", (HANDLE, ctypes.c_int, POINTER, DWORD), BOOL),
    ("QueryInformationJobObject", (HANDLE, ctypes.c_int, POINTER, DWORD, POINTER), BOOL),
    (
        "CreateFileW",
        (wintypes.LPCWSTR, DWORD, DWORD, POINTER, DWORD, DWORD, HANDLE),
        HANDLE,
    ),
    ("CreatePipe", (POINTER, POINTER, POINTER, DWORD), BOOL),
    ("SetHandleInformation", (HANDLE, DWORD, DWORD), BOOL),
    ("GetHandleInformation", (HANDLE, POINTER), BOOL),
    ("InitializeProcThreadAttributeList", (POINTER, DWORD, DWORD, POINTER), BOOL),
    (
        "UpdateProcThreadAttribute",
        (POINTER, DWORD, ctypes.c_size_t, POINTER, ctypes.c_size_t, POINTER, POINTER),
        BOOL,
    ),
    ("DeleteProcThreadAttributeList", (POINTER,), None),
    (
        "CreateProcessW",
        (
            wintypes.LPCWSTR,
            POINTER,
            POINTER,
            POINTER,
            BOOL,
            DWORD,
            POINTER,
            wintypes.LPCWSTR,
            POINTER,
            POINTER,
        ),
        BOOL,
    ),
    ("IsProcessInJob", (HANDLE, HANDLE, POINTER), BOOL),
    ("ResumeThread", (HANDLE,), DWORD),
    ("TerminateProcess", (HANDLE, wintypes.UINT), BOOL),
    ("TerminateJobObject", (HANDLE, wintypes.UINT), BOOL),
    ("WaitForSingleObject", (HANDLE, DWORD), DWORD),
    ("GetExitCodeProcess", (HANDLE, POINTER), BOOL),
    ("PeekNamedPipe", (HANDLE, POINTER, DWORD, POINTER, POINTER, POINTER), BOOL),
    ("ReadFile", (HANDLE, POINTER, DWORD, POINTER, POINTER), BOOL),
    ("CloseHandle", (HANDLE,), BOOL),
)


class _Api:
    def __init__(self, kernel, last_error):
        self.k, self.last_error = kernel, last_error


def _load_api():
    """Only reached after the runtime and ABI guards inside setup()."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    for name, arguments, result in SIGNATURES:
        function = getattr(kernel, name)
        function.argtypes = list(arguments)
        function.restype = result
    return _Api(kernel, ctypes.get_last_error)


def _runtime():
    flags = sys.flags
    return (
        sys.platform == "win32"
        and tuple(sys.version_info[:3]) == (3, 11, 3)
        and sys.maxsize == (1 << 63) - 1
        and flags.isolated == 1
        and flags.dont_write_bytecode == 1
        and flags.optimize == 0
    )


def _abi():
    return all(ctypes.sizeof(kind) == size for kind, size in ABI_SIZES.items()) and all(
        field.offset == offset for field, offset in ABI_OFFSETS
    )


def _handle(value):
    return value if type(value) is int and 0 < value < INVALID else None


@dataclass(frozen=True)
class Request:
    """Internal data for a future fixed caller/control mode; never a CLI surface."""

    application: str
    command_line: str
    environment: tuple
    directory: str


def _text(value, limit):
    return type(value) is str and 0 < len(value) <= limit and "\0" not in value


def _absolute(value):
    return (
        _text(value, MAX_PATH_CHARS) and bool(ntpath.splitdrive(value)[0]) and ntpath.isabs(value)
    )


def _environment_block(environment):
    pairs = sorted(environment, key=lambda item: item[0].upper())
    return "".join(name + "=" + value + "\0" for name, value in pairs) + "\0"


def _request_ok(request):
    if type(request) is not Request:
        return False
    if not (
        _absolute(request.application)
        and _text(request.command_line, MAX_COMMAND_CHARS)
        and _absolute(request.directory)
    ):
        return False
    environment = request.environment
    if type(environment) is not tuple or not 0 < len(environment) <= MAX_ENVIRONMENT:
        return False
    names = set()
    for item in environment:
        if type(item) is not tuple or len(item) != 2:
            return False
        name, value = item
        if not (_text(name, 64) and "=" not in name and _text(value, 4096)):
            return False
        if name.upper() in names:
            return False
        names.add(name.upper())
    return len(_environment_block(environment)) <= MAX_ENVIRONMENT_CHARS


class Owner:
    """Single owner of one job, its stdio and at most one direct child."""

    def __init__(self, request):
        # Pure: no validation that can lose ownership, no DLL, no handle.
        self.request = request
        self.state = "NEW"
        self.held_reason = None
        self.ledger = {}
        self.pid = None
        self.process_created = False
        self.signaled = False
        self.eof = False
        self.terminated = False
        # Indeterminate outputs of failed/raised calls: recorded, never owned,
        # never passed to any terminate, wait or close.
        self.quarantine = []
        self._api = None
        self._attributes = None  # non-None until deletion is confirmed
        self._pending = None  # output buffers of the in-flight creating call
        self._create_attempted = False
        self._keep = []

    # -- primitive helpers: never inside an except block when raising ----------

    def _call(self, name, *args):
        raised, value = False, None
        try:
            value = getattr(self._api.k, name)(*args)
        except Exception:
            raised = True
        return raised, value

    def _ok(self, name, *args):
        raised, value = self._call(name, *args)
        return raised, (not raised and type(value) is int and value != 0)

    def _error(self):
        raised, value = False, None
        try:
            value = self._api.last_error()
        except Exception:
            raised = True
        return value if not raised and type(value) is int else -1

    def _fail(self, code, state):
        self.state = state
        raise Win32Error(code) from None

    def _hold(self, reason):
        self.state = "HELD"
        self.held_reason = reason
        raise Win32Error("WIN32_HELD") from None

    def _expect(self, *states):
        if self.state not in states:
            raise Win32Error("WIN32_HELD" if self.state == "HELD" else "WIN32_STATE") from None

    def _close(self, name):
        handle = self.ledger.get(name)
        if handle is None:
            return True
        raised, ok = self._ok("CloseHandle", handle)
        if ok:
            del self.ledger[name]
        return ok

    def _config(self):
        info, length = ExtendedLimit(), DWORD(0)
        raised, ok = self._ok(
            "QueryInformationJobObject",
            self.ledger["job"],
            JOB_EXTENDED_LIMIT,
            ctypes.byref(info),
            ctypes.sizeof(info),
            ctypes.byref(length),
        )
        if not ok or length.value != ctypes.sizeof(info):
            return "FAILED"
        basic = info.BasicLimitInformation
        exact = (
            basic.LimitFlags == LIMIT_FLAGS
            and basic.ActiveProcessLimit == ACTIVE_PROCESS_LIMIT
            and not basic.LimitFlags & (JOB_LIMIT_BREAKAWAY_OK | JOB_LIMIT_SILENT_BREAKAWAY_OK)
        )
        return "OK" if exact else "MISMATCH"

    def _accounting(self):
        info, length = Accounting(), DWORD(0)
        raised, ok = self._ok(
            "QueryInformationJobObject",
            self.ledger["job"],
            JOB_BASIC_ACCOUNTING,
            ctypes.byref(info),
            ctypes.sizeof(info),
            ctypes.byref(length),
        )
        if not ok or length.value != ctypes.sizeof(info):
            return None
        return info.TotalProcesses, info.ActiveProcesses

    def _members(self):
        info, length = ProcessIdList(), DWORD(0)
        raised, ok = self._ok(
            "QueryInformationJobObject",
            self.ledger["job"],
            JOB_BASIC_PROCESS_ID_LIST,
            ctypes.byref(info),
            ctypes.sizeof(info),
            ctypes.byref(length),
        )
        if not raised and not ok and self._error() == ERROR_MORE_DATA:
            return "TOO_MANY"
        count = info.NumberOfProcessIdsInList
        header = ProcessIdList.ProcessIdList.offset
        entry = ctypes.sizeof(ctypes.c_size_t)
        if (
            not ok
            or count != info.NumberOfAssignedProcesses
            or count > ACTIVE_PROCESS_LIMIT
            or not header + count * entry <= length.value <= ctypes.sizeof(info)
        ):
            return None
        pids = tuple(int(info.ProcessIdList[index]) for index in range(count))
        return pids if all(0 < pid < (1 << 32) for pid in pids) else None

    def _wait(self, milliseconds):
        raised, value = self._call("WaitForSingleObject", self.ledger["process"], milliseconds)
        if not raised and value == WAIT_OBJECT_0:
            self.signaled = True
            return True
        if not raised and value == WAIT_TIMEOUT:
            return False
        return None

    def _peek(self):
        if self.eof:
            return None, True
        available = DWORD(0)
        raised, ok = self._ok(
            "PeekNamedPipe",
            self.ledger["stdout_read"],
            None,
            0,
            None,
            ctypes.byref(available),
            None,
        )
        if ok:
            return available.value, True
        if not raised and self._error() == ERROR_BROKEN_PIPE:
            self.eof = True
            return None, True
        return None, False

    def _abort(self, reason, in_job, held=False):
        """Suspended child: job terminate only if membership was proven, else direct handle."""
        if in_job:
            raised, ok = self._ok("TerminateJobObject", self.ledger["job"], ABORT_EXIT_CODE)
        else:
            raised, ok = self._ok("TerminateProcess", self.ledger["process"], ABORT_EXIT_CODE)
        if not ok:
            self._hold("WIN32_TERMINATE")
        if self._wait(ABORT_WAIT_MS) is not True:
            self._hold("WIN32_WAIT")
        if in_job:
            counts = self._accounting()
            if counts is None or counts[1] != 0:
                self._hold("WIN32_ACCOUNTING")
        if held:
            self._hold(reason)
        self._fail(reason, "LAUNCH_FAILED")

    def _delete_attributes(self):
        """Clears the record only after a confirmed deletion."""
        if self._attributes is None:
            return True
        raised, _value = self._call("DeleteProcThreadAttributeList", self._attributes)
        if raised:
            return False
        self._attributes = None
        return True

    def _quarantine(self, values):
        self.quarantine.extend(value for value in values if _handle(value) is not None)

    def _contain_job(self):
        """Uncertain creation: the atomic JOB_LIST makes the owned job the only target."""
        if "job" in self.ledger and self._api is not None:
            self._ok("TerminateJobObject", self.ledger["job"], ABORT_EXIT_CODE)

    def _pending_values(self):
        pending, self._pending = self._pending, None
        if isinstance(pending, ProcessInformation):
            return (pending.hProcess, pending.hThread)
        if isinstance(pending, tuple):
            return tuple(item.value for item in pending)
        return ()

    def _interrupt(self):
        """Control interruption: quarantine pending outputs, bounded containment, HELD."""
        self._quarantine(self._pending_values())
        self.state = "HELD"
        self.held_reason = "WIN32_INTERRUPTED"
        if self._create_attempted and "job" in self.ledger and self._api is not None:
            try:
                self._api.k.TerminateJobObject(self.ledger["job"], ABORT_EXIT_CODE)
            except Exception:
                pass

    def _guarded(self, body):
        """Win32Error passes; other failures become HELD; interruptions propagate as HELD."""
        problem = None
        try:
            body()
        except Win32Error:
            raise
        except Exception:
            problem = "WIN32_INTERNAL"
        except BaseException:
            self._interrupt()
            raise
        if problem is not None:
            self._quarantine(self._pending_values())
            self._delete_attributes()
            if self._create_attempted:
                self._contain_job()
            self._hold(problem)

    # -- setup and start -------------------------------------------------------

    def setup(self):
        self._expect("NEW")
        self.state = "SETUP"
        self._guarded(self._setup)

    def _setup(self):
        if not _request_ok(self.request):
            self._fail("WIN32_REQUEST", "SETUP_FAILED")
        if not _runtime() or not _abi():
            self._fail("WIN32_RUNTIME", "SETUP_FAILED")
        api, failed = None, False
        try:
            api = _load_api()
        except Exception:
            failed = True
        if failed or api is None:
            self._fail("WIN32_LOAD", "SETUP_FAILED")
        self._api = api
        raised, value = self._call("CreateJobObjectW", None, None)
        if raised:
            self._hold("WIN32_JOB")
        job = _handle(value)
        if job is None:
            self._fail("WIN32_JOB", "SETUP_FAILED")
        self.ledger["job"] = job
        limits = ExtendedLimit()
        limits.BasicLimitInformation.LimitFlags = LIMIT_FLAGS
        limits.BasicLimitInformation.ActiveProcessLimit = ACTIVE_PROCESS_LIMIT
        raised, ok = self._ok(
            "SetInformationJobObject",
            job,
            JOB_EXTENDED_LIMIT,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        )
        if not ok or self._config() != "OK":
            self._fail("WIN32_CONFIG", "SETUP_FAILED")
        inherit = SecurityAttributes(ctypes.sizeof(SecurityAttributes), None, 1)
        self._keep.append(inherit)
        for name, access in (("stdin", GENERIC_READ), ("stderr", GENERIC_WRITE)):
            raised, value = self._call(
                "CreateFileW",
                "NUL",
                access,
                FILE_SHARE_READ_WRITE,
                ctypes.byref(inherit),
                OPEN_EXISTING,
                0,
                None,
            )
            if raised:
                self._hold("WIN32_STDIO")
            handle = _handle(value)
            if handle is None:
                self._fail("WIN32_STDIO", "SETUP_FAILED")
            if handle in self.ledger.values():
                self._quarantine((handle,))
                self._hold("WIN32_STDIO")  # success that aliases an owned handle
            self.ledger[name] = handle
        reader, writer = HANDLE(), HANDLE()
        self._pending = (reader, writer)
        raised, ok = self._ok(
            "CreatePipe", ctypes.byref(reader), ctypes.byref(writer), ctypes.byref(inherit), 0
        )
        outputs = self._pending_values()
        read_end, write_end = (_handle(value) for value in outputs)
        owned = set(self.ledger.values())
        if (
            raised
            or not ok
            or read_end is None
            or write_end is None
            or read_end == write_end
            or {read_end, write_end} & owned
        ):
            # Failure outputs are indeterminate: quarantined, never adopted.
            self._quarantine(outputs)
            if raised or ok:
                self._hold("WIN32_PIPE")
            self._fail("WIN32_PIPE", "SETUP_FAILED")
        self.ledger["stdout_read"] = read_end
        self.ledger["stdout_write"] = write_end
        raised, ok = self._ok(
            "SetHandleInformation", self.ledger["stdout_read"], HANDLE_FLAG_INHERIT, 0
        )
        if not ok:
            self._fail("WIN32_PIPE", "SETUP_FAILED")
        expected = {"job": 0, "stdin": 1, "stderr": 1, "stdout_read": 0, "stdout_write": 1}
        for name, flag in expected.items():
            flags = DWORD(0)
            raised, ok = self._ok("GetHandleInformation", self.ledger[name], ctypes.byref(flags))
            if not ok or flags.value & HANDLE_FLAG_INHERIT != flag:
                self._fail("WIN32_INHERIT", "SETUP_FAILED")
        self.state = "READY"

    def start(self):
        self._expect("READY")
        self.state = "STARTING"
        self._guarded(self._start)

    def _start(self):
        ledger, request = self.ledger, self.request
        size = ctypes.c_size_t(0)
        raised, value = self._call(
            "InitializeProcThreadAttributeList", None, 2, 0, ctypes.byref(size)
        )
        if (
            raised
            or value != 0
            or self._error() != ERROR_INSUFFICIENT_BUFFER
            or not 0 < size.value <= MAX_ATTRIBUTE_BYTES
        ):
            self._fail("WIN32_ATTRIBUTE", "LAUNCH_FAILED")
        attributes = ctypes.create_string_buffer(size.value)
        jobs = (HANDLE * 1)(ledger["job"])
        handles = (HANDLE * 3)(ledger["stdin"], ledger["stdout_write"], ledger["stderr"])
        # Kept alive by the owner until after CreateProcessW and deletion.
        self._keep.extend((attributes, jobs, handles))
        raised, ok = self._ok(
            "InitializeProcThreadAttributeList", attributes, 2, 0, ctypes.byref(size)
        )
        if not ok:
            self._fail("WIN32_ATTRIBUTE", "LAUNCH_FAILED")
        self._attributes = attributes
        for attribute, items in (
            (PROC_THREAD_ATTRIBUTE_JOB_LIST, jobs),
            (PROC_THREAD_ATTRIBUTE_HANDLE_LIST, handles),
        ):
            raised, ok = self._ok(
                "UpdateProcThreadAttribute",
                attributes,
                0,
                attribute,
                items,
                ctypes.sizeof(items),
                None,
                None,
            )
            if not ok:
                if not self._delete_attributes():
                    self._hold("WIN32_ATTRIBUTE")
                self._fail("WIN32_ATTRIBUTE", "LAUNCH_FAILED")
        startup = StartupInfoEx()
        startup.StartupInfo.cb = ctypes.sizeof(StartupInfoEx)
        startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES
        startup.StartupInfo.hStdInput = ledger["stdin"]
        startup.StartupInfo.hStdOutput = ledger["stdout_write"]
        startup.StartupInfo.hStdError = ledger["stderr"]
        startup.lpAttributeList = ctypes.addressof(attributes)
        information = ProcessInformation()
        command = ctypes.create_unicode_buffer(request.command_line)
        environment = ctypes.create_unicode_buffer(_environment_block(request.environment))
        self._keep.extend((startup, information, command, environment))
        self._pending = information
        self._create_attempted = True
        raised, value = self._call(
            "CreateProcessW",
            request.application,
            command,
            None,
            None,
            1,
            CREATE_FLAGS,
            environment,
            request.directory,
            ctypes.byref(startup),
            ctypes.byref(information),
        )
        outputs = self._pending_values()
        process, thread = (_handle(item) for item in outputs)
        pid = int(information.dwProcessId)
        deleted = self._delete_attributes()
        created = not raised and type(value) is int and value != 0
        owned = set(ledger.values())
        if not (
            created
            and process is not None
            and thread is not None
            and process != thread
            and not {process, thread} & owned
            and 0 < pid
        ):
            # Never adopt, terminate, wait or close these outputs.
            self._quarantine(outputs)
            if created or raised:
                self._contain_job()
                self._hold("WIN32_CREATE")
            # Clean FALSE: JOB_LIST is atomic, so any created process is in the job.
            if self._accounting() != (0, 0) or self._members() != ():
                self._contain_job()
                self._hold("WIN32_CREATE")
            if not deleted:
                self._hold("WIN32_ATTRIBUTE")
            self._fail("WIN32_CREATE", "LAUNCH_FAILED")
        ledger["process"] = process
        ledger["thread"] = thread
        self.process_created = True
        self.pid = pid
        if not deleted:
            self._abort("WIN32_ATTRIBUTE", in_job=False, held=True)
        # Parent copies of the child stdio: EOF must depend only on the tree.
        for name in ("stdin", "stderr", "stdout_write"):
            if not self._close(name):
                self._abort("WIN32_CLOSE", in_job=False, held=True)
        member = BOOL(0)
        raised, ok = self._ok("IsProcessInJob", process, ledger["job"], ctypes.byref(member))
        if not ok or member.value != 1:
            self._abort("WIN32_MEMBERSHIP", in_job=False)
        if self._config() != "OK":
            self._abort("WIN32_CONFIG", in_job=True)
        if self._accounting() != (1, 1) or self._members() != (self.pid,):
            self._abort("WIN32_TREE", in_job=True)
        raised, value = self._call("ResumeThread", thread)
        if raised or value != 1:
            self._abort("WIN32_RESUME", in_job=True)
        self.state = "RUNNING"

    # -- supervision primitives (single thread, bounded) -----------------------

    def wait(self, milliseconds):
        self._expect("RUNNING")
        if type(milliseconds) is not int or not 0 <= milliseconds <= MAX_WAIT_MS:
            raise Win32Error("WIN32_REQUEST") from None
        result = self._wait(milliseconds)
        if result is None:
            self._hold("WIN32_WAIT")
        return result

    def exit_code(self):
        self._expect("RUNNING")
        if not self.signaled:
            raise Win32Error("WIN32_STATE") from None
        code = DWORD(0)
        raised, ok = self._ok("GetExitCodeProcess", self.ledger["process"], ctypes.byref(code))
        if not ok:
            self._hold("WIN32_EXIT")
        return int(code.value)

    def accounting(self):
        """(TotalProcesses, ActiveProcesses), bounded by the active-process cap."""
        self._expect("RUNNING")
        counts = self._accounting()
        if counts is None:
            self._hold("WIN32_ACCOUNTING")
        total, active = counts
        if active > total or total > ACTIVE_PROCESS_LIMIT:
            raise Win32Error("WIN32_TREE") from None
        return total, active

    def members(self):
        self._expect("RUNNING")
        pids = self._members()
        if pids == "TOO_MANY":
            raise Win32Error("WIN32_TREE") from None
        if pids is None:
            self._hold("WIN32_ACCOUNTING")
        return pids

    def check_config(self):
        self._expect("RUNNING")
        state = self._config()
        if state == "FAILED":
            self._hold("WIN32_CONFIG")
        if state != "OK":
            raise Win32Error("WIN32_CONFIG") from None

    def terminate(self):
        self._expect("RUNNING")
        raised, ok = self._ok("TerminateJobObject", self.ledger["job"], TERMINATE_EXIT_CODE)
        if not ok:
            self._hold("WIN32_TERMINATE")
        self.terminated = True

    def available(self):
        """Bytes available now, or None after EOF. Never starts a read."""
        self._expect("RUNNING")
        available, ok = self._peek()
        if not ok:
            self._hold("WIN32_PIPE")
        return available

    def read(self):
        """Reads only bytes already available, at most MAX_READ; b"" if none or EOF."""
        available = self.available()
        if not available:
            return b""
        size = min(available, MAX_READ)
        buffer, got = ctypes.create_string_buffer(size), DWORD(0)
        raised, ok = self._ok(
            "ReadFile", self.ledger["stdout_read"], buffer, size, ctypes.byref(got), None
        )
        if ok and 0 < got.value <= size:
            return buffer.raw[: got.value]
        if not ok and not raised and self._error() == ERROR_BROKEN_PIPE:
            self.eof = True
            return b""
        self._hold("WIN32_PIPE")
        return b""

    # -- release ---------------------------------------------------------------

    def close(self):
        """Closes the ledger only over proven quiescence; failure makes HELD."""
        self._expect("SETUP_FAILED", "READY", "LAUNCH_FAILED", "RUNNING")
        if self.process_created:
            waited = self._wait(0)
            if waited is None:
                self._hold("WIN32_WAIT")
            counts, pids = self._accounting(), self._members()
            if counts is None or pids is None or pids == "TOO_MANY":
                self._hold("WIN32_ACCOUNTING")
            if not (waited and counts[1] == 0 and pids == ()):
                raise Win32Error("WIN32_NOT_QUIESCENT") from None
            # Tree proven gone: parent stdio copies (if an abort kept them) go
            # first so that EOF can only depend on the finished tree.
            for name in ("stdin", "stderr", "stdout_write"):
                if not self._close(name):
                    self._hold("WIN32_CLOSE")
            available, ok = self._peek()
            if not ok:
                self._hold("WIN32_PIPE")
            if not (available is None and self.eof):
                raise Win32Error("WIN32_NOT_QUIESCENT") from None
        for name in ("thread", "process", "stdout_read", "stdin", "stderr", "stdout_write", "job"):
            if not self._close(name):
                self._hold("WIN32_CLOSE")
        self.state = "CLOSED"
